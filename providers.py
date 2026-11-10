"""AI provider layer: Groq, Google Gemini, xAI Grok and OpenAI behind one interface.

All four expose an OpenAI-compatible chat API, so one client library (`openai`)
covers them by changing only the base URL, key and model name.

Free vs paid (as of Nov 2026, from third-party summaries; verify with each vendor):
  - Groq:   free tier (for testing; production should use a paid plan)
  - Gemini: free tier on Flash models with low daily limits; Google may use
            free-tier prompts to improve its products
  - xAI / OpenAI: pay-as-you-go, no free API credits for new accounts

Model names change often, so every model name can be overridden with a secret.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterator, Sequence


@dataclass(frozen=True)
class ProviderSpec:
    key: str
    label: str
    base_url: str | None
    key_env: str
    model_env: str
    default_model: str
    fallback_env: str
    default_fallback: str
    note: str


SPECS: list[ProviderSpec] = [
    ProviderSpec(
        key="groq",
        label="Groq",
        base_url="https://api.groq.com/openai/v1",
        key_env="GROQ_API_KEY",
        model_env="MODEL",  # kept as "MODEL" so existing secrets keep working
        default_model="openai/gpt-oss-120b",
        fallback_env="FALLBACK_MODEL",
        default_fallback="openai/gpt-oss-20b",
        note="Free tier: fast, but rate-limited.",
    ),
    ProviderSpec(
        key="gemini",
        label="Google Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        key_env="GEMINI_API_KEY",
        model_env="GEMINI_MODEL",
        default_model="gemini-3.5-flash-lite",
        fallback_env="GEMINI_FALLBACK_MODEL",
        default_fallback="gemini-3.1-flash-lite",
        note="Free tier has low daily limits, and Google may use free-tier prompts "
        "to improve its products. Do not send client-confidential data.",
    ),
    ProviderSpec(
        key="xai",
        label="xAI Grok",
        base_url="https://api.x.ai/v1",
        key_env="XAI_API_KEY",
        model_env="XAI_MODEL",
        default_model="grok-4.7",
        fallback_env="XAI_FALLBACK_MODEL",
        default_fallback="",
        note="Paid API (no free credits).",
    ),
    ProviderSpec(
        key="openai",
        label="OpenAI (ChatGPT)",
        base_url=None,
        key_env="OPENAI_API_KEY",
        model_env="OPENAI_MODEL",
        default_model="gpt-5-mini",
        fallback_env="OPENAI_FALLBACK_MODEL",
        default_fallback="",
        note="Paid API (no free credits). Set OPENAI_MODEL to a model your account can use.",
    ),
]


@dataclass(frozen=True)
class Provider:
    spec: ProviderSpec
    api_key: str
    models: tuple[str, ...]  # primary first, then optional fallback

    @property
    def key(self) -> str:
        return self.spec.key

    @property
    def label(self) -> str:
        return self.spec.label


def enabled_providers(get: Callable[[str, str], str]) -> list[Provider]:
    """Providers whose API key is present. `get(name, default)` reads a secret."""
    out: list[Provider] = []
    for spec in SPECS:
        api_key = get(spec.key_env, "").strip()
        if not api_key:
            continue
        primary = get(spec.model_env, spec.default_model).strip() or spec.default_model
        fallback = get(spec.fallback_env, spec.default_fallback).strip()
        models = (primary,) + ((fallback,) if fallback and fallback != primary else ())
        out.append(Provider(spec, api_key, models))
    return out


def default_client_factory(provider: Provider):
    from openai import OpenAI  # imported lazily so tests need no network library

    kwargs = {"api_key": provider.api_key, "timeout": 90.0, "max_retries": 1}
    if provider.spec.base_url:
        kwargs["base_url"] = provider.spec.base_url
    return OpenAI(**kwargs)


def trim_history(messages: Sequence[dict], max_messages: int = 30, max_chars: int = 28000) -> list[dict]:
    """Keep the most recent messages that fit a budget, like a rolling chat window.

    Always keeps the latest message, and never starts with an assistant message.
    """
    kept: list[dict] = []
    total = 0
    for m in reversed(messages[-max_messages:]):
        size = len(m["content"])
        if kept and total + size > max_chars:
            break
        kept.append({"role": m["role"], "content": m["content"]})
        total += size
    kept.reverse()
    while len(kept) > 1 and kept[0]["role"] != "user":
        kept.pop(0)
    return kept


class ChatStream:
    """Iterate to receive text chunks. Tries the preferred provider first, then the others.

    After iteration:
      used_provider / used_model : who actually answered
      finish_reason              : "stop", "length" (cut off), or None
      error_text                 : set if every option failed, or if the stream broke part-way
      failed                     : True when nothing at all was produced
    """

    def __init__(
        self,
        providers: Sequence[Provider],
        preferred: str | None,
        messages: list[dict],
        client_factory: Callable[[Provider], object] = default_client_factory,
    ):
        ordered = sorted(providers, key=lambda p: 0 if p.key == preferred else 1)
        self._providers = ordered
        self._messages = messages
        self._factory = client_factory
        self.used_provider: str | None = None
        self.used_model: str | None = None
        self.finish_reason: str | None = None
        self.error_text: str | None = None
        self.failed = False

    def __iter__(self) -> Iterator[str]:
        errors: list[str] = []
        for provider in self._providers:
            try:
                client = self._factory(provider)
            except Exception as e:  # missing library, bad config
                errors.append(f"{provider.label}: {e}")
                continue
            for model in provider.models:
                produced = False
                try:
                    stream = client.chat.completions.create(
                        model=model, messages=self._messages, stream=True
                    )
                    for chunk in stream:
                        if not chunk.choices:
                            continue
                        choice = chunk.choices[0]
                        text = getattr(choice.delta, "content", None)
                        if text:
                            if not produced:
                                produced = True
                                self.used_provider = provider.label
                                self.used_model = model
                            yield text
                        if getattr(choice, "finish_reason", None):
                            self.finish_reason = choice.finish_reason
                    if produced:
                        return
                    errors.append(f"{provider.label} ({model}): empty reply")
                except Exception as e:
                    if produced:
                        # Broke part-way through; cannot cleanly retry elsewhere.
                        self.error_text = f"{provider.label} stopped part-way: {e}"
                        self.finish_reason = "length"  # lets the UI offer "Continue"
                        return
                    errors.append(f"{provider.label} ({model}): {_short(e)}")
        self.failed = True
        self.error_text = " | ".join(errors) or "No AI provider is configured."


def _short(e: Exception, limit: int = 220) -> str:
    s = str(e).replace("\n", " ")
    return s if len(s) <= limit else s[: limit - 1] + "…"
