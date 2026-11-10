"""Run with:  python test_core.py   (no network, no API keys needed)"""

import os
import tempfile
from types import SimpleNamespace as NS

from chatstore import MemoryStore, SqliteStore
from providers import ChatStream, Provider, SPECS, enabled_providers, trim_history


def chunk(text=None, finish=None):
    return NS(choices=[NS(delta=NS(content=text), finish_reason=finish)])


class FakeClient:
    """behaviour: list of items; str -> text chunk, Exception -> raise, ('finish', x) -> finish chunk"""

    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.chat = NS(completions=NS(create=self._create))
        self.calls = []

    def _create(self, model, messages, stream):
        self.calls.append(model)
        b = self.behaviour(model) if callable(self.behaviour) else self.behaviour
        if isinstance(b, Exception):
            raise b

        def gen():
            for item in b:
                if isinstance(item, Exception):
                    raise item
                if isinstance(item, tuple):
                    yield chunk(None, item[1])
                else:
                    yield chunk(item)

        return gen()


def prov(key, models=("m1",)):
    spec = next(s for s in SPECS if s.key == key)
    return Provider(spec, "k", tuple(models))


def run(stream):
    return "".join(stream)


# ---------------------------------------------------------------- providers
def test_enabled_providers():
    env = {"GROQ_API_KEY": "a", "GEMINI_API_KEY": "b", "MODEL": "x/y"}
    got = enabled_providers(lambda n, d="": env.get(n, d))
    assert [p.key for p in got] == ["groq", "gemini"]
    assert got[0].models == ("x/y", "openai/gpt-oss-20b")
    assert enabled_providers(lambda n, d="": d) == []


def test_preferred_provider_first_and_success():
    clients = {"groq": FakeClient(["Hel", "lo", ("f", "stop")]), "gemini": FakeClient(["never"])}
    s = ChatStream([prov("groq"), prov("gemini")], "groq", [], lambda p: clients[p.key])
    assert run(s) == "Hello"
    assert s.used_provider == "Groq" and s.used_model == "m1" and s.finish_reason == "stop"
    assert not s.failed and s.error_text is None
    assert clients["gemini"].calls == []


def test_preferred_gemini_is_tried_first():
    clients = {"groq": FakeClient(["g"]), "gemini": FakeClient(["gem"])}
    s = ChatStream([prov("groq"), prov("gemini")], "gemini", [], lambda p: clients[p.key])
    assert run(s) == "gem" and s.used_provider == "Google Gemini"


def test_fallback_to_other_provider_on_error():
    clients = {
        "groq": FakeClient(RuntimeError("429 rate limit")),
        "gemini": FakeClient(["from gemini"]),
    }
    s = ChatStream([prov("groq"), prov("gemini")], "groq", [], lambda p: clients[p.key])
    assert run(s) == "from gemini"
    assert s.used_provider == "Google Gemini" and not s.failed


def test_fallback_to_second_model_same_provider():
    def behaviour(model):
        return RuntimeError("model retired") if model == "old" else ["ok"]

    c = FakeClient(behaviour)
    s = ChatStream([prov("groq", ("old", "new"))], "groq", [], lambda p: c)
    assert run(s) == "ok" and s.used_model == "new" and c.calls == ["old", "new"]


def test_all_fail():
    clients = {"groq": FakeClient(RuntimeError("boom1")), "gemini": FakeClient(RuntimeError("boom2"))}
    s = ChatStream([prov("groq"), prov("gemini")], "groq", [], lambda p: clients[p.key])
    assert run(s) == ""
    assert s.failed and "boom1" in s.error_text and "boom2" in s.error_text


def test_empty_reply_counts_as_failure_then_falls_back():
    clients = {"groq": FakeClient([]), "gemini": FakeClient(["hi"])}
    s = ChatStream([prov("groq"), prov("gemini")], "groq", [], lambda p: clients[p.key])
    assert run(s) == "hi"


def test_cut_off_reports_length():
    c = FakeClient(["part", ("f", "length")])
    s = ChatStream([prov("groq")], "groq", [], lambda p: c)
    assert run(s) == "part" and s.finish_reason == "length"


def test_midstream_error_keeps_partial_and_offers_continue():
    c = FakeClient(["partial ", RuntimeError("connection dropped")])
    s = ChatStream([prov("groq"), prov("gemini")], "groq", [], lambda p: c)
    assert run(s) == "partial "
    assert not s.failed and s.finish_reason == "length" and "part-way" in s.error_text


def test_factory_error_is_handled():
    def factory(p):
        raise ImportError("no openai library")

    s = ChatStream([prov("groq")], "groq", [], factory)
    assert run(s) == "" and s.failed and "no openai library" in s.error_text


def test_no_providers():
    s = ChatStream([], None, [], lambda p: None)
    assert run(s) == "" and s.failed and "No AI provider" in s.error_text


def test_trim_history():
    msgs = [{"role": "assistant" if i % 2 else "user", "content": "x" * 10} for i in range(80)]
    out = trim_history(msgs, max_messages=30, max_chars=10_000)
    assert len(out) <= 30 and out[0]["role"] == "user" and out[-1] == {"role": msgs[-1]["role"], "content": "x" * 10}
    big = [{"role": "user", "content": "a" * 100}, {"role": "assistant", "content": "b" * 100},
           {"role": "user", "content": "c" * 100}]
    out = trim_history(big, max_chars=150)
    assert out == [{"role": "user", "content": "c" * 100}]  # newest always kept; no leading assistant
    assert trim_history([{"role": "user", "content": "z" * 99999}])[0]["content"].startswith("z")


# ------------------------------------------------------------------- stores
def exercise_store(store):
    cid = store.create_chat("alice", "First")
    other = store.create_chat("bob", "Bob's")
    store.add_message(cid, "alice", "user", "hello")
    store.add_message(cid, "alice", "assistant", "hi", "meta1")
    assert [m["role"] for m in store.get_messages(cid, "alice")] == ["user", "assistant"]
    assert store.get_messages(cid, "alice")[1]["meta"] == "meta1"
    # ownership is enforced
    assert store.get_messages(cid, "bob") == []
    store.add_message(cid, "bob", "user", "intrusion")
    assert len(store.get_messages(cid, "alice")) == 2
    store.delete_chat(cid, "bob")
    assert len(store.list_chats("alice")) == 1
    store.set_title(cid, "bob", "hacked")
    assert store.list_chats("alice")[0]["title"] == "First"
    # list is scoped and most recent first
    assert [c["id"] for c in store.list_chats("bob")] == [other]
    c2 = store.create_chat("alice", "Second")
    store.add_message(c2, "alice", "user", "newer")
    assert [c["title"] for c in store.list_chats("alice")] == ["Second", "First"]
    # regenerate support
    store.pop_last_message(cid, "alice")
    assert [m["role"] for m in store.get_messages(cid, "alice")] == ["user"]
    store.set_title(cid, "alice", "Renamed")
    assert {c["title"] for c in store.list_chats("alice")} == {"Renamed", "Second"}
    store.delete_chat(cid, "alice")
    assert store.get_messages(cid, "alice") == [] and len(store.list_chats("alice")) == 1


def test_memory_store():
    exercise_store(MemoryStore({}))


def test_sqlite_store_and_persistence():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.db")
        exercise_store(SqliteStore(path))
        s2 = SqliteStore(path)  # reopen: data persisted
        assert [c["title"] for c in s2.list_chats("alice")] == ["Second"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"\n{len(tests)} tests passed")
