"""Repair LaTeX written by the AI so Streamlit can render it.

Streamlit draws maths only when it is wrapped in $...$ (inline) or $$...$$ (display).
Models often emit \\[ ... \\], \\( ... \\), or bare [ ... ] / ( ... ) wrappers instead.
This module converts those to the $ forms. It is pure Python so it can be tested alone.
"""

from __future__ import annotations

import re

_DISPLAY_BRACKETS = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
_INLINE_PARENS = re.compile(r"\\\((.+?)\\\)", re.DOTALL)
# A line that is only "[ ... ]" and contains a LaTeX command.
_BARE_LINE_BRACKETS = re.compile(r"^[ \t]*\[[ \t]*(.+?)[ \t]*\][ \t]*$", re.MULTILINE)
# A multi-line "[" ... "]" block on their own lines.
_BARE_BLOCK_BRACKETS = re.compile(r"^[ \t]*\[[ \t]*\n(.+?)\n[ \t]*\][ \t]*$", re.MULTILINE | re.DOTALL)
# "(P_{\text{cond}})" style parentheses holding a LaTeX command.
_BARE_PARENS = re.compile(r"\(([^()\n$]*\\[A-Za-z]+[^()\n$]*)\)")
_MATH_SPAN = re.compile(r"(\$\$.+?\$\$|\$[^$\n]+?\$)", re.DOTALL)


def _display(m: re.Match) -> str:
    return "\n\n$$" + m.group(1).strip() + "$$\n\n"


def _bare_line(m: re.Match) -> str:
    inner = m.group(1)
    if "\\" not in inner:  # not LaTeX, leave it (could be a normal bracketed note)
        return m.group(0)
    return "\n$$" + inner.strip() + "$$\n"


def _bare_block(m: re.Match) -> str:
    inner = m.group(1)
    if "\\" not in inner:
        return m.group(0)
    return "\n$$" + inner.strip() + "$$\n"


def normalize_math(text: str) -> str:
    if not text:
        return text
    text = _DISPLAY_BRACKETS.sub(_display, text)
    text = _INLINE_PARENS.sub(lambda m: "$" + m.group(1).strip() + "$", text)
    text = _BARE_BLOCK_BRACKETS.sub(_bare_block, text)
    text = _BARE_LINE_BRACKETS.sub(_bare_line, text)

    # Parenthesised maths: only touch text OUTSIDE existing $...$ spans.
    parts = _MATH_SPAN.split(text)
    for i in range(0, len(parts), 2):
        parts[i] = _BARE_PARENS.sub(lambda m: "$" + m.group(1).strip() + "$", parts[i])
    text = "".join(parts)

    # Common model slip: "\;" spacing and "{\rm W}" are fine for KaTeX; tidy lone ";" before units.
    return text
