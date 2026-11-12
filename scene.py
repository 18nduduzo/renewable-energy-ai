"""A tiny vector scene model with two renderers.

One drawing description -> SVG (free on-screen preview) and PDF (paid download).
All coordinates are in millimetres on the sheet, origin top-left, y pointing down.
Text sizes are in millimetres too (2.8 mm is about 8 pt).
"""

from __future__ import annotations

import io
import math
from xml.sax.saxutils import escape

try:  # reportlab is a requirement of the app; fall back to a rough estimate if missing
    from reportlab.pdfbase.pdfmetrics import stringWidth as _string_width
except Exception:  # pragma: no cover
    _string_width = None

MM = 72.0 / 25.4  # points per millimetre

_PDF_REPLACE = {
    "−": "-", "–": "-", "—": "-", "≥": ">=", "≤": "<=", "Ω": "ohm",
    "→": "->", "←": "<-", "…": "...", "≈": "~", "θ": "theta", "·": ".",
    "✓": "ok", "•": "-", "Δ": "d", "α": "alpha", "β": "beta",
}


def pdf_safe(s: str) -> str:
    """Make text safe for the standard PDF fonts (WinAnsi)."""
    for k, v in _PDF_REPLACE.items():
        s = s.replace(k, v)
    return s.encode("cp1252", "replace").decode("cp1252")


def text_width(s: str, size: float, bold: bool = False) -> float:
    s = pdf_safe(s)
    if _string_width:
        return _string_width(s, "Helvetica-Bold" if bold else "Helvetica", size)
    return 0.52 * size * len(s)


def fit_text(s: str, size: float, max_w: float, bold: bool = False) -> str:
    """Shorten text with an ellipsis so it fits max_w millimetres."""
    if text_width(s, size, bold) <= max_w:
        return s
    while s and text_width(s + "...", size, bold) > max_w:
        s = s[:-1]
    return s + "..."


class Scene:
    def __init__(self, width: float = 420.0, height: float = 297.0):
        self.width = width
        self.height = height
        self.items: list[dict] = []

    # ------------------------------------------------------------ primitives
    def line(self, x1, y1, x2, y2, sw=0.25, color="#111111", dash=None, alpha=1.0, cap="butt"):
        self.items.append(dict(t="line", x1=x1, y1=y1, x2=x2, y2=y2, sw=sw, color=color, dash=dash, alpha=alpha, cap=cap))

    def rect(self, x, y, w, h, sw=0.25, stroke="#111111", fill=None, dash=None, alpha=1.0):
        self.items.append(dict(t="rect", x=x, y=y, w=w, h=h, sw=sw, stroke=stroke, fill=fill, dash=dash, alpha=alpha))

    def poly(self, pts, sw=0.25, stroke="#111111", fill=None, closed=True, dash=None, alpha=1.0):
        self.items.append(dict(t="poly", pts=list(pts), sw=sw, stroke=stroke, fill=fill, closed=closed, dash=dash, alpha=alpha))

    def circle(self, cx, cy, r, sw=0.25, stroke="#111111", fill=None, alpha=1.0):
        self.items.append(dict(t="circle", cx=cx, cy=cy, r=r, sw=sw, stroke=stroke, fill=fill, alpha=alpha))

    def text(self, x, y, s, size=3.0, anchor="start", bold=False, italic=False, rot=0, color="#111111", alpha=1.0):
        self.items.append(dict(t="text", x=x, y=y, s=str(s), size=size, anchor=anchor, bold=bold, italic=italic,
                               rot=rot, color=color, alpha=alpha))

    def arc(self, cx, cy, r, a0, a1, sw=0.25, stroke="#111111", dash=None, steps=24):
        """Arc from angle a0 to a1 in degrees, counter-clockwise as seen on the sheet (0 = right, 90 = up)."""
        pts = []
        for i in range(steps + 1):
            a = math.radians(a0 + (a1 - a0) * i / steps)
            pts.append((cx + r * math.cos(a), cy - r * math.sin(a)))
        self.poly(pts, sw=sw, stroke=stroke, fill=None, closed=False, dash=dash)

    # -------------------------------------------------------------- helpers
    def multiline(self, x, y, lines, size=2.8, gap=1.25, **kw):
        for i, ln in enumerate(lines):
            self.text(x, y + i * size * gap, ln, size=size, **kw)

    def to_svg(self) -> str:
        return to_svg(self)


# ---------------------------------------------------------------- SVG render
def _dash_attr(d):
    return f' stroke-dasharray="{",".join(f"{v:g}" for v in d)}"' if d else ""


def _alpha(a, kind):
    return f' {kind}-opacity="{a:g}"' if a is not None and a < 1.0 else ""


def to_svg(sc: Scene) -> str:
    W, H = sc.width, sc.height
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:g} {H:g}" width="{W:g}mm" height="{H:g}mm" '
        f'font-family="Helvetica, Arial, sans-serif">',
        f'<rect x="0" y="0" width="{W:g}" height="{H:g}" fill="#ffffff"/>',
    ]
    for it in sc.items:
        t = it["t"]
        if t == "line":
            out.append(
                f'<line x1="{it["x1"]:.3f}" y1="{it["y1"]:.3f}" x2="{it["x2"]:.3f}" y2="{it["y2"]:.3f}" '
                f'stroke="{it["color"]}" stroke-width="{it["sw"]:g}" stroke-linecap="{it["cap"]}"'
                f'{_dash_attr(it["dash"])}{_alpha(it["alpha"], "stroke")}/>'
            )
        elif t == "rect":
            fill = it["fill"] or "none"
            stroke = it["stroke"] or "none"
            out.append(
                f'<rect x="{it["x"]:.3f}" y="{it["y"]:.3f}" width="{it["w"]:.3f}" height="{it["h"]:.3f}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{it["sw"]:g}"{_dash_attr(it["dash"])}'
                f'{_alpha(it["alpha"], "fill")}{_alpha(it["alpha"], "stroke")}/>'
            )
        elif t == "poly":
            pts = " ".join(f"{x:.3f},{y:.3f}" for x, y in it["pts"])
            tag = "polygon" if it["closed"] else "polyline"
            fill = it["fill"] or "none"
            stroke = it["stroke"] or "none"
            out.append(
                f'<{tag} points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{it["sw"]:g}" '
                f'stroke-linejoin="round"{_dash_attr(it["dash"])}{_alpha(it["alpha"], "fill")}{_alpha(it["alpha"], "stroke")}/>'
            )
        elif t == "circle":
            fill = it["fill"] or "none"
            stroke = it["stroke"] or "none"
            out.append(
                f'<circle cx="{it["cx"]:.3f}" cy="{it["cy"]:.3f}" r="{it["r"]:.3f}" fill="{fill}" '
                f'stroke="{stroke}" stroke-width="{it["sw"]:g}"{_alpha(it["alpha"], "fill")}{_alpha(it["alpha"], "stroke")}/>'
            )
        elif t == "text":
            anchor = {"start": "start", "middle": "middle", "end": "end"}[it["anchor"]]
            extra = ""
            if it["bold"]:
                extra += ' font-weight="bold"'
            if it["italic"]:
                extra += ' font-style="italic"'
            if it["rot"]:
                extra += f' transform="rotate({it["rot"]:g} {it["x"]:.3f} {it["y"]:.3f})"'
            out.append(
                f'<text x="{it["x"]:.3f}" y="{it["y"]:.3f}" font-size="{it["size"]:g}" text-anchor="{anchor}" '
                f'fill="{it["color"]}"{extra}{_alpha(it["alpha"], "fill")}>{escape(pdf_safe(it["s"]))}</text>'
            )
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- PDF render
def draw_pdf(sc: Scene, c) -> None:
    """Draw the scene onto the current page of a reportlab canvas sized to the scene."""
    from reportlab.lib.colors import HexColor

    H = sc.height

    def X(x):
        return x * MM

    def Y(y):
        return (H - y) * MM

    for it in sc.items:
        t = it["t"]
        c.saveState()
        a = it.get("alpha", 1.0)
        if a is not None and a < 1.0:
            c.setFillAlpha(a)
            c.setStrokeAlpha(a)
        if t == "line":
            c.setStrokeColor(HexColor(it["color"]))
            c.setLineWidth(it["sw"] * MM)
            c.setLineCap({"butt": 0, "round": 1, "square": 2}[it["cap"]])
            if it["dash"]:
                c.setDash([d * MM for d in it["dash"]])
            c.line(X(it["x1"]), Y(it["y1"]), X(it["x2"]), Y(it["y2"]))
        elif t == "rect":
            if it["fill"]:
                c.setFillColor(HexColor(it["fill"]))
            if it["stroke"]:
                c.setStrokeColor(HexColor(it["stroke"]))
                c.setLineWidth(it["sw"] * MM)
            if it["dash"]:
                c.setDash([d * MM for d in it["dash"]])
            c.rect(X(it["x"]), Y(it["y"] + it["h"]), it["w"] * MM, it["h"] * MM,
                   stroke=1 if it["stroke"] else 0, fill=1 if it["fill"] else 0)
        elif t == "poly":
            if it["fill"]:
                c.setFillColor(HexColor(it["fill"]))
            if it["stroke"]:
                c.setStrokeColor(HexColor(it["stroke"]))
                c.setLineWidth(it["sw"] * MM)
            c.setLineJoin(1)
            if it["dash"]:
                c.setDash([d * MM for d in it["dash"]])
            p = c.beginPath()
            pts = it["pts"]
            p.moveTo(X(pts[0][0]), Y(pts[0][1]))
            for x, y in pts[1:]:
                p.lineTo(X(x), Y(y))
            if it["closed"]:
                p.close()
            c.drawPath(p, stroke=1 if it["stroke"] else 0, fill=1 if (it["fill"] and it["closed"]) else 0)
        elif t == "circle":
            if it["fill"]:
                c.setFillColor(HexColor(it["fill"]))
            if it["stroke"]:
                c.setStrokeColor(HexColor(it["stroke"]))
                c.setLineWidth(it["sw"] * MM)
            c.circle(X(it["cx"]), Y(it["cy"]), it["r"] * MM,
                     stroke=1 if it["stroke"] else 0, fill=1 if it["fill"] else 0)
        elif t == "text":
            font = "Helvetica"
            if it["bold"] and it["italic"]:
                font = "Helvetica-BoldOblique"
            elif it["bold"]:
                font = "Helvetica-Bold"
            elif it["italic"]:
                font = "Helvetica-Oblique"
            c.setFillColor(HexColor(it["color"]))
            c.setFont(font, it["size"] * MM)
            c.translate(X(it["x"]), Y(it["y"]))
            if it["rot"]:
                c.rotate(-it["rot"])
            s = pdf_safe(it["s"])
            if it["anchor"] == "middle":
                c.drawCentredString(0, 0, s)
            elif it["anchor"] == "end":
                c.drawRightString(0, 0, s)
            else:
                c.drawString(0, 0, s)
        c.restoreState()


def build_pdf(scenes, title="", author="", subject="") -> bytes:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    first = scenes[0]
    c = canvas.Canvas(buf, pagesize=(first.width * MM, first.height * MM))
    c.setTitle(pdf_safe(title))
    c.setAuthor(pdf_safe(author))
    c.setSubject(pdf_safe(subject))
    c.setCreator("Solar & Electrical Design AI")
    for sc in scenes:
        c.setPageSize((sc.width * MM, sc.height * MM))
        draw_pdf(sc, c)
        c.showPage()
    c.save()
    return buf.getvalue()
