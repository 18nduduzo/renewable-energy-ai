"""Engineering drawing sheets (A3 landscape) built on the Scene model.

Sheets: cover, single line diagram (SLD), array layout plan, mounting detail, BOM + schedules.
Each sheet is a Scene, so it can be shown on screen as SVG (watermarked preview) or exported
as a clean vector PDF (paid).

All drawings are PRELIMINARY and must be reviewed and signed off by a competent person.
"""

from __future__ import annotations

import datetime as _dt
import math
from dataclasses import dataclass, field

from scene import Scene, build_pdf, fit_text, text_width

W, H = 420.0, 297.0
INK = "#111111"
GREY = "#666666"
LIGHT = "#d9d9d9"
RED = "#c1121f"
BLUE = "#1d4ed8"
GREEN = "#2a7a2a"
STRING_COLORS = ["#cfe8ff", "#ffe0b3", "#d7f0c8", "#f6c9e6", "#e2d6ff", "#ffd6d6", "#c9f0ee", "#f3efb0"]

SHEET_ORDER = ["cover", "sld", "layout", "mount", "bom"]
SHEET_TITLES = {
    "cover": "Cover sheet and design summary",
    "sld": "Single line diagram",
    "layout": "Array layout plan",
    "mount": "Mounting structure detail",
    "bom": "Bill of materials and schedules",
}
TIERS = {
    "sld": ["sld"],
    "pack": list(SHEET_ORDER),
}


@dataclass
class Meta:
    project: str = "Untitled project"
    client: str = ""
    address: str = ""
    drawn_by: str = ""
    company: str = ""
    revision: str = "A"
    date: str = field(default_factory=lambda: _dt.date.today().isoformat())
    drawing_no: str = "PV-001"
    software: str = "Solar & Electrical Design AI"


# ---------------------------------------------------------------- helpers
def wrap(s: str, size: float, max_w: float, bold: bool = False) -> list[str]:
    words = s.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if text_width(trial, size, bold) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def new_sheet(meta: Meta, key: str, number: int, total: int, scale: str = "NTS") -> Scene:
    sc = Scene(W, H)
    sc.rect(5, 5, W - 10, H - 10, sw=0.7)
    sc.rect(10, 10, W - 20, H - 20, sw=0.35)
    # title block (bottom right)
    x0, y0, w, h = 240.0, 249.0, 170.0, 38.0
    sc.rect(x0, y0, w, h, sw=0.5, fill="#ffffff")
    sc.line(x0, y0 + 9, x0 + w, y0 + 9, sw=0.3)
    sc.line(x0, y0 + 20, x0 + w, y0 + 20, sw=0.3)
    sc.line(x0 + 108, y0 + 20, x0 + 108, y0 + h, sw=0.3)
    sc.line(x0 + 138, y0 + 20, x0 + 138, y0 + h, sw=0.3)
    sc.line(x0 + 108, y0 + 29, x0 + w, y0 + 29, sw=0.3)
    sc.text(x0 + 2, y0 + 6.2, fit_text(meta.company or meta.software, 3.6, w - 4, True), 3.6, bold=True)
    proj = f"Project: {meta.project}" + (f"   Client: {meta.client}" if meta.client else "")
    sc.text(x0 + 2, y0 + 13.2, fit_text(proj, 2.9, w - 4), 2.9)
    sc.text(x0 + 2, y0 + 18.2, fit_text(meta.address, 2.5, w - 4), 2.5, color=GREY)
    sc.text(x0 + 2, y0 + 25.2, "TITLE", 2.0, color=GREY)
    sc.text(x0 + 2, y0 + 32.2, fit_text(SHEET_TITLES[key].upper(), 4.0, 102, True), 4.0, bold=True)
    sc.text(x0 + 110, y0 + 25.2, f"DWG {meta.drawing_no}-{number:02d}", 2.8, bold=True)
    sc.text(x0 + 110, y0 + 33.5, f"REV {meta.revision}   {meta.date}", 2.5)
    sc.text(x0 + 140, y0 + 25.2, f"SHEET {number} / {total}", 2.8, bold=True)
    sc.text(x0 + 140, y0 + 33.5, f"SCALE {scale}", 2.5)
    sc.text(x0 + 2, y0 + 36.6, "PRELIMINARY - NOT FOR CONSTRUCTION - subject to review by a competent person",
            2.0, color=RED, bold=True)
    return sc


def heading(sc: Scene, title: str, sub: str = ""):
    sc.text(16, 22, title, 6.0, bold=True)
    if sub:
        sc.text(16, 27, fit_text(sub, 2.8, 380), 2.8, color=GREY)


def watermark(sc: Scene, text: str = "PREVIEW - NOT FOR CONSTRUCTION") -> Scene:
    wm = Scene(sc.width, sc.height)
    wm.items = list(sc.items)
    for cx, cy in [(110, 95), (310, 95), (210, 150), (110, 215), (310, 215)]:
        wm.text(cx, cy, text, 13, anchor="middle", bold=True, rot=-24, color="#b00020", alpha=0.13)
    return wm


# ---------------------------------------------------------------- symbols (horizontal flow)
def sym_earth(sc, x, y):
    sc.line(x, y, x, y + 2.2, sw=0.3)
    for i, w in enumerate((6.0, 4.0, 2.0)):
        yy = y + 2.2 + i * 1.3
        sc.line(x - w / 2, yy, x + w / 2, yy, sw=0.35)


def sym_isolator(sc, cx, cy, label="", rating="", tag=""):
    sc.line(cx - 7, cy, cx - 3, cy, sw=0.4)
    sc.line(cx + 3, cy, cx + 7, cy, sw=0.4)
    sc.circle(cx - 3, cy, 0.7, sw=0.3, fill="#ffffff")
    sc.circle(cx + 3, cy, 0.7, sw=0.3, fill="#ffffff")
    sc.line(cx - 3, cy, cx + 2.2, cy - 4.2, sw=0.4)
    _tags(sc, cx, cy, label, rating, tag)


def sym_breaker(sc, cx, cy, label="", rating="", tag=""):
    sym_isolator(sc, cx, cy, label, rating, tag)
    sc.line(cx + 1.2, cy - 5.4, cx + 3.6, cy - 3.0, sw=0.35)
    sc.line(cx + 1.2, cy - 3.0, cx + 3.6, cy - 5.4, sw=0.35)


def sym_fuse(sc, cx, cy, label="", rating="", tag=""):
    sc.line(cx - 7, cy, cx + 7, cy, sw=0.4)
    sc.rect(cx - 4, cy - 1.8, 8, 3.6, sw=0.4, fill="#ffffff")
    sc.line(cx - 4, cy, cx + 4, cy, sw=0.3)
    one_line = " ".join(t for t in (tag, rating) if t)
    if one_line:   # single line above the body so stacked strings never collide
        sc.text(cx, cy - 3.6, one_line, 2.3, anchor="middle", bold=bool(tag))
    if label:
        sc.text(cx, cy + 5.4, label, 2.3, anchor="middle")


def _tags(sc, cx, cy, label, rating, tag):
    if tag:
        sc.text(cx, cy - 7.2, tag, 2.4, anchor="middle", bold=True)
    if label:
        sc.text(cx, cy + 5.4, label, 2.3, anchor="middle")
    if rating:
        sc.text(cx, cy + 8.2, rating, 2.3, anchor="middle", color=GREY)


def sym_spd(sc, x, y, tag="SPD", rating="", left=False, below=False):
    """Surge protective device hanging below a line at (x, y)."""
    sc.line(x, y, x, y + 2.5, sw=0.4)
    sc.circle(x, y, 0.55, sw=0.3, fill=INK)
    sc.rect(x - 3.2, y + 2.5, 6.4, 7.0, sw=0.4, fill="#ffffff")
    sc.poly([(x - 1.4, y + 4.0), (x + 1.4, y + 4.0), (x, y + 6.8)], sw=0.3, fill=INK)
    sc.line(x, y + 9.5, x, y + 10.5, sw=0.3)
    sym_earth(sc, x, y + 10.5)
    if below:
        sc.text(x, y + 18.6, tag, 2.2, bold=True, anchor="middle")
        if rating:
            sc.text(x, y + 21.2, rating, 2.0, color=GREY, anchor="middle")
        return
    lx = x - 4.6 if left else x + 4.6
    anc = "end" if left else "start"
    sc.text(lx, y + 5.0, tag, 2.2, bold=True, anchor=anc)
    if rating:
        sc.text(lx, y + 7.6, rating, 2.0, color=GREY, anchor=anc)


def sym_meter(sc, cx, cy, label="kWh"):
    sc.circle(cx, cy, 5.2, sw=0.45, fill="#ffffff")
    sc.text(cx, cy + 1.0, label, 2.8, anchor="middle", bold=True)


def sym_pv(sc, x, y, w, h):
    sc.rect(x, y, w, h, sw=0.4, fill="#ffffff")
    sc.line(x, y + h, x + w, y, sw=0.3)
    sc.text(x + w * 0.27, y + h * 0.40, "+", 3.0, anchor="middle")
    sc.text(x + w * 0.73, y + h * 0.88, "-", 3.0, anchor="middle")


def sym_battery(sc, x, y, w, h):
    sc.rect(x, y, w, h, sw=0.5, fill="#ffffff")
    n = 4
    for i in range(n):
        px = x + 4 + i * 4.2
        sc.line(px, y + 3, px, y + h - 3, sw=0.9 if i % 2 == 0 else 0.4)
    sc.text(x + 3, y + 2.6, "+", 2.4)


def sym_inverter(sc, x, y, w, h):
    sc.rect(x, y, w, h, sw=0.7, fill="#fbfbfb")


# ---------------------------------------------------------------- SLD
def sld(meta: Meta, d: dict, lay: dict | None, number: int, total: int) -> Scene:
    inp = d["input"]
    inv, mod, site = inp.inverter, inp.module, inp.site
    sc = new_sheet(meta, "sld", number, total, "NTS")
    heading(sc, "SINGLE LINE DIAGRAM",
            "Each DC line represents + and - conductors. All earth symbols connect to the main earth terminal (MET).")

    s = d["string"]
    groups = d["mppt"]
    n_strings_total = sum(g["n"] for g in groups)
    sh = 13.0
    sg = 4.0
    gg = 12.0
    avail = 190.0
    need = n_strings_total * sh + max(0, n_strings_total - len(groups)) * sg + (len(groups) - 1) * gg
    if need > avail:
        sh = max(8.0, sh * avail / need)
    elif len(groups) > 1:
        gg = min(40.0, gg + (avail - need) / (len(groups) - 1) * 0.45)
    y = 40.0
    layout_groups = []
    for g in groups:
        n = max(g["n"], 1)
        gh = n * sh + (n - 1) * sg
        layout_groups.append({**g, "y0": y, "h": gh, "yc": y + gh / 2})
        y += gh + gg
    y_end = y - gg

    # --- PV strings
    x_box, w_box = 20.0, 72.0
    bond_x = 16.5
    first_string_y = None
    last_string_y = None
    for g in layout_groups:
        yc = g["yc"]
        if g["n"] == 0:
            sc.text(x_box, yc + 1, f"MPPT {g['mppt']}: not used", 2.8, italic=True, color=GREY)
            continue
        n = g["n"]
        ys = []
        for k, sid in enumerate(g["strings"]):
            ytop = g["y0"] + k * (sh + sg)
            ys.append(ytop + sh / 2)
            color = STRING_COLORS[(sid - 1) % len(STRING_COLORS)]
            sc.rect(x_box, ytop, w_box, sh, sw=0.4, fill=color)
            sym_pv(sc, x_box + 2, ytop + 2.2, 11, sh - 4.4)
            sc.text(x_box + 16, ytop + 4.2, f"STRING {sid}", 3.0, bold=True)
            sc.text(x_box + 16, ytop + 7.6, f"{s['modules']} x {mod.watts:.0f} W  ({s['modules'] * mod.watts / 1000:.2f} kWp)", 2.5)
            if sh >= 11:
                sc.text(x_box + 16, ytop + 10.6, f"Voc cold {s['voc_cold_v']:.0f} V   Isc {mod.isc:.1f} A", 2.5, color=GREY)
            if first_string_y is None:
                first_string_y = ytop + sh / 2
            last_string_y = ytop + sh / 2
            sc.line(bond_x, ytop + sh / 2, x_box, ytop + sh / 2, sw=0.35, color=GREEN, dash=[1.4, 0.8])
        # string conductors -> bus
        x_f = 104.0
        x_bus = 116.0
        for k, sid in enumerate(g["strings"]):
            yy = ys[k]
            if g["fuse_a"]:
                sc.line(x_box + w_box, yy, x_f - 7, yy, sw=0.45)
                sym_fuse(sc, x_f, yy, rating=f"{g['fuse_a']} A gPV", tag=f"F{sid}") if sh >= 11 else sym_fuse(sc, x_f, yy)
                sc.line(x_f + 7, yy, x_bus, yy, sw=0.45)
            else:
                sc.line(x_box + w_box, yy, x_bus, yy, sw=0.45)
            if n > 1:
                sc.circle(x_bus, yy, 0.65, sw=0.3, fill=INK)
        if n > 1:
            sc.line(x_bus, ys[0], x_bus, ys[-1], sw=0.45)
        yc = (ys[0] + ys[-1]) / 2
        g["yc"] = yc
        sc.line(x_bus, yc, 122, yc, sw=0.45)
        sc.circle(x_bus, yc, 0.65, sw=0.3, fill=INK)
        sym_isolator(sc, 129, yc, "DC isolator", f"{g['isolator_a']} A / {s['voc_cold_v'] * 1.0:.0f} V+", f"QD{g['mppt']}")
        sc.line(136, yc, 172, yc, sw=0.45)
        sc.circle(146, yc, 0.65, sw=0.3, fill=INK)
        sym_spd(sc, 146, yc, f"SPD-DC{g['mppt']}", "Type 2")
        sc.text(158, yc - 2.2, f"MPPT {g['mppt']}", 2.6, bold=True, anchor="middle")
    # frame bonding rail
    if first_string_y is not None:
        sc.line(bond_x, first_string_y, bond_x, last_string_y + 8, sw=0.35, color=GREEN, dash=[1.4, 0.8])
        sym_earth(sc, bond_x, last_string_y + 8)
        sc.text(bond_x + 3, last_string_y + 12.5, "PV frame bonding", 2.0, color=GREEN)
    cab = d["cables"]["dc_string"]
    sc.text(94.0, layout_groups[0]["y0"] - 3.0, f"DC cable: {cab['mm2']:g} mm2 Cu solar, {cab['length_m_each']:g} m per string",
            2.4, color=BLUE, bold=True)

    # --- inverter
    ix0, ix1 = 172.0, 254.0
    iy0 = 33.0
    iy1 = max(y_end + 14, iy0 + 110)
    sym_inverter(sc, ix0, iy0, ix1 - ix0, iy1 - iy0)
    sc.line(ix0 + 1, iy1 - 1, ix1 - 1, iy0 + 1, sw=0.2, color=LIGHT)
    sc.text((ix0 + ix1) / 2, iy0 + 7, "INVERTER", 4.0, anchor="middle", bold=True)
    sc.text((ix0 + ix1) / 2, iy0 + 12, fit_text(inv.name, 2.7, ix1 - ix0 - 4), 2.7, anchor="middle")
    sc.text((ix0 + ix1) / 2, iy0 + 16.2, f"{inv.ac_kw:g} kW AC, {inv.phases}-phase", 2.5, anchor="middle")
    sc.text((ix0 + ix1) / 2, iy0 + 20.2, f"Max DC {inv.max_dc_v:.0f} V; MPPT {inv.mppt_min_v:.0f}-{inv.mppt_max_v:.0f} V", 2.3, anchor="middle", color=GREY)
    sc.text(ix0 + 4, iy1 - 4, "DC", 3.0, bold=True)
    sc.text(ix1 - 4, iy1 - 4, "AC", 3.0, bold=True, anchor="end")
    sym_earth(sc, (ix0 + ix1) / 2, iy1)
    sc.text((ix0 + ix1) / 2 + 5, iy1 + 3.6, "chassis earth", 2.0, color=GREY)

    # --- AC chain
    y_ac = iy0 + 14.0
    ac = d["ac"]
    sc.line(ix1, y_ac, 258, y_ac, sw=0.6)
    lab3 = "3P+N" if inv.phases == 3 else "L+N"
    sym_breaker(sc, 264, y_ac, f"AC MCB {ac['poles']}P", f"{ac['breaker_a']} A", "QA1")
    sc.line(271, y_ac, 276, y_ac, sw=0.6)
    sc.rect(276, y_ac - 4, 15, 8, sw=0.45, fill="#ffffff")
    sc.text(283.5, y_ac - 0.4, "RCD", 2.6, anchor="middle", bold=True)
    sc.text(283.5, y_ac + 2.9, f"{ac['rcd_ma']} mA", 2.3, anchor="middle")
    sc.line(291, y_ac, 303, y_ac, sw=0.6)
    sc.circle(297, y_ac, 0.65, sw=0.3, fill=INK)
    sym_spd(sc, 297, y_ac, "SPD-AC", "Type 2", below=True)
    sc.rect(303, y_ac - 15, 36, 30, sw=0.7, fill="#fbfbfb")
    sc.text(321, y_ac - 7.5, "AC DISTRIBUTION", 2.7, anchor="middle", bold=True)
    sc.text(321, y_ac - 4.0, "BOARD", 2.7, anchor="middle", bold=True)
    sc.text(321, y_ac + 0.5, "(PV supply + loads)", 2.2, anchor="middle", color=GREY)
    sc.text(321, y_ac + 4.6, f"{ac['voltage_v']:.0f} V  {lab3}+E", 2.3, anchor="middle")
    sc.text(321, y_ac + 8.6, "SANS 10142-1", 2.0, anchor="middle", color=GREY)
    sc.line(339, y_ac, 348 - 5.2, y_ac, sw=0.6)
    sym_meter(sc, 348, y_ac, "kWh")
    sc.text(348, y_ac + 9.4, "Bi-directional", 2.1, anchor="middle")
    sc.text(348, y_ac + 12.2, "meter (EEC)", 2.1, anchor="middle")
    sc.line(353.2, y_ac, 366, y_ac, sw=0.6)
    sc.rect(366, y_ac - 11, 36, 22, sw=0.7, fill="#fbfbfb")
    sc.text(384, y_ac - 4.0, "UTILITY GRID", 2.8, anchor="middle", bold=True)
    sc.text(384, y_ac + 0.2, "EEC supply", 2.4, anchor="middle")
    sc.text(384, y_ac + 4.2, f"{site.grid_v_ln:.0f}/{site.grid_v_ll:.0f} V, 50 Hz", 2.3, anchor="middle")
    cac = d["cables"]["ac"]
    sc.text(ix1 + 3, y_ac - 17.5, f"AC cable: {cac['mm2']:g} mm2 Cu, {cac['length_m']:g} m", 2.4, color=BLUE, bold=True)
    sc.text(ix1 + 3, y_ac - 14.7, f"({cac['type']})", 2.0, color=GREY)
    sym_earth(sc, 321, y_ac + 15)

    # --- battery
    b = d.get("battery")
    if b:
        y_bat = iy0 + 0.75 * (iy1 - iy0)
        sc.line(ix1, y_bat, 262, y_bat, sw=0.8)
        sym_breaker(sc, 269, y_bat, "Battery CB", f"{b['breaker_a']} A DC", "QB1")
        sc.line(276, y_bat, 296, y_bat, sw=0.8)
        sym_battery(sc, 296, y_bat - 13, 78, 26)
        sc.text(320, y_bat - 6.5, "BATTERY BANK", 3.0, bold=True)
        sc.text(320, y_bat - 2.5, f"{b['kwh']:g} kWh, {b['voltage_v']:g} V nominal", 2.5)
        sc.text(320, y_bat + 1.4, f"Max current {b['max_current_a']:g} A" + (f", {b['modules']} modules" if b["modules"] else ""), 2.4, color=GREY)
        sc.text(320, y_bat + 5.0, "Use BMS-communicating cable per manual", 2.1, color=GREY)
        sc.text(ix1 + 3, y_bat - 11.5, f"Battery cable: {b['cable_mm2']:g} mm2 Cu, {b['cable_m']:g} m", 2.4, color=BLUE, bold=True)
        sym_earth(sc, 335, y_bat + 13)
    else:
        sc.text(ix1 + 6, iy0 + 0.75 * (iy1 - iy0), "No battery storage in this design", 2.6, italic=True, color=GREY)

    # --- string / MPPT data table and general notes (lower area)
    ty = max(iy1 + 22, 172.0)
    if b:
        ty = max(ty, y_bat + 30)
    ty = min(ty, 196.0)
    sc.text(16, ty - 3, "STRING AND MPPT DATA", 2.8, bold=True)
    mrows = []
    for g in groups:
        if g["n"]:
            mrows.append([f"MPPT {g['mppt']}", g["n"], s["modules"], f"{s['voc_cold_v']:.0f}", f"{s['vmp_v']:.0f}",
                          f"{g['i_sc_a']:.1f}", f"{g['i_op_a']:.1f}",
                          f"{inv.max_current_per_mppt_a:g} / {inv.max_isc_per_mppt_a:g}", "OK" if g["ok"] else "CHECK"])
        else:
            mrows.append([f"MPPT {g['mppt']}", 0, "-", "-", "-", "-", "-", "-", "unused"])
    _table(sc, 16, ty, [18, 14, 22, 24, 20, 20, 20, 36, 22],
           ["Input", "Strings", "Mod/string", "Voc cold V", "Vmp V", "Isc A", "Imp A", "Limit Iop/Isc A", "Check"], mrows)
    sc.text(250, ty - 3, "GENERAL NOTES", 2.8, bold=True)
    gnotes = [
        "1. DC cables: double-insulated PV cable, UV resistant, routed in conduit or trunking.",
        "2. Label all isolators, breakers and the DC/AC warning signs per SANS 10142-1.",
        "3. Install AC and DC SPDs as close as practical to the inverter.",
        "4. Fit a lockable AC isolator for the utility if the EEC requires it.",
        "5. Confirm connection approval and metering requirements with EEC before installing.",
    ]
    ny = ty + 2
    for t in gnotes:
        for ln in wrap(t, 2.3, 152):
            sc.text(250, ny, ln, 2.3, color=GREY)
            ny += 3.6
        ny += 0.6
    # --- legend (bottom-left band)
    ly = 252.0
    sc.rect(15, ly - 3, 218, 36, sw=0.3, fill="#ffffff")
    sc.text(18, ly + 1.5, "LEGEND", 2.6, bold=True)
    items = [("PV string", None), ("DC isolator", "iso"), ("Fuse (gPV)", "fuse"), ("Breaker", "mcb"), ("SPD", "spd"), ("Earth", "earth")]
    xx = 22.0
    for name, kind in items:
        cy = ly + 12
        if kind == "iso":
            sym_isolator(sc, xx + 6, cy)
        elif kind == "fuse":
            sym_fuse(sc, xx + 6, cy)
        elif kind == "mcb":
            sym_breaker(sc, xx + 6, cy)
        elif kind == "spd":
            sym_spd(sc, xx + 6, cy - 5)
        elif kind == "earth":
            sym_earth(sc, xx + 6, cy - 3)
        else:
            sym_pv(sc, xx + 1, cy - 4, 10, 8)
        sc.text(xx + 6, ly + 28, name, 2.2, anchor="middle")
        xx += 34
    sc.text(18, ly + 31.2, "Blue text = cable. Dashed green = earth bonding.", 2.1, color=GREY)
    return sc


# ---------------------------------------------------------------- layout plan
def _std_scale(w_m: float, h_m: float, box_w: float, box_h: float) -> int:
    need = max(w_m * 1000.0 / box_w, h_m * 1000.0 / box_h)
    for den in (10, 20, 25, 30, 40, 50, 75, 100, 125, 150, 200, 250, 300, 400, 500, 750, 1000):
        if den >= need:
            return den
    return 2000


def _dim_h(sc, x1, x2, y, text, size=2.6):
    sc.line(x1, y, x2, y, sw=0.3)
    for xx, d in ((x1, 1), (x2, -1)):
        sc.poly([(xx, y), (xx + d * 2.2, y - 0.8), (xx + d * 2.2, y + 0.8)], sw=0.2, fill=INK)
        sc.line(xx, y - 2.5, xx, y + 2.5, sw=0.25)
    sc.text((x1 + x2) / 2, y - 1.4, text, size, anchor="middle")


def _dim_v(sc, x, y1, y2, text, size=2.6):
    sc.line(x, y1, x, y2, sw=0.3)
    for yy, d in ((y1, 1), (y2, -1)):
        sc.poly([(x, yy), (x - 0.8, yy + d * 2.2), (x + 0.8, yy + d * 2.2)], sw=0.2, fill=INK)
        sc.line(x - 2.5, yy, x + 2.5, yy, sw=0.25)
    sc.text(x - 1.6, (y1 + y2) / 2, text, size, anchor="middle", rot=-90)


def _north_arrow(sc, cx, cy, az_facing: float, r=10.0):
    ang = (180.0 - az_facing) % 360.0   # clockwise from sheet-up
    a = math.radians(ang)
    dx, dy = math.sin(a), -math.cos(a)
    sc.circle(cx, cy, r, sw=0.35, fill="#ffffff")
    tip = (cx + dx * (r - 1), cy + dy * (r - 1))
    base_l = (cx - dy * 2.6 - dx * 3.0, cy + dx * 2.6 - dy * 3.0)
    base_r = (cx + dy * 2.6 - dx * 3.0, cy - dx * 2.6 - dy * 3.0)
    sc.poly([tip, base_l, (cx - dx * 1.0, cy - dy * 1.0), base_r], sw=0.3, fill=INK)
    sc.text(cx + dx * (r + 3.6), cy + dy * (r + 3.6) + 1.0, "N", 3.4, anchor="middle", bold=True)


def layout_sheet(meta: Meta, d: dict, lay: dict, number: int, total: int) -> Scene:
    inp = lay["input"]
    Wm, Dm = lay["area"]
    box_x, box_y, box_w, box_h = 22.0, 40.0, 290.0, 176.0
    den = _std_scale(Wm, Dm, box_w - 20, box_h - 22)
    k = 1000.0 / den  # mm per metre
    sc = new_sheet(meta, "layout", number, total, f"1:{den} (A3)")
    kind = {"Pitched roof (flush)": "ROOF PLAN", "Flat roof (tilted frames)": "FLAT ROOF PLAN",
            "Ground mount (tilted frames)": "GROUND MOUNT PLAN"}[inp.mount]
    heading(sc, f"ARRAY LAYOUT - {kind}",
            f"{inp.mount}. Modules coloured by string. Dashed lines = rails. Plan view; arrays face down the sheet.")
    ox = box_x + 14 + (box_w - 20 - Wm * k) / 2
    oy = box_y + 6
    # area outline & setback
    sc.rect(ox, oy, Wm * k, Dm * k, sw=0.8, fill="#f7f7f2")
    sb = inp.setback_m
    sc.rect(ox + sb * k, oy + sb * k, (Wm - 2 * sb) * k, (Dm - 2 * sb) * k, sw=0.25, stroke=GREY, dash=[2.0, 1.2])
    sc.text(ox, oy - 2.0, f"Usable area {Wm:g} x {Dm:g} m, setback {sb:g} m (dashed)", 2.4, color=GREY)
    # modules
    show_nums = lay["module_w"] * k >= 9
    for m in lay["modules"]:
        col = STRING_COLORS[(m["string"] - 1) % len(STRING_COLORS)] if m["string"] else "#dddddd"
        sc.rect(ox + m["x"] * k, oy + m["y"] * k, m["w"] * k, m["h"] * k, sw=0.25, fill=col)
        if show_nums:
            sc.text(ox + (m["x"] + m["w"] / 2) * k, oy + (m["y"] + m["h"] / 2) * k + 1.0,
                    f"{m['i'] + 1}", 2.4, anchor="middle", color=GREY)
    # rails
    for r in lay["rails"]:
        sc.line(ox + r["x1"] * k, oy + r["y"] * k, ox + r["x2"] * k, oy + r["y"] * k, sw=0.5, color="#222222", dash=[3.0, 1.0])
    # supports
    for p in lay["supports"]:
        px, py = ox + p["x"] * k, oy + p["y"] * k
        if p["kind"] == "attachment":
            sc.circle(px, py, 0.9, sw=0.25, fill=INK)
        elif p["kind"] == "front post":
            sc.rect(px - 1.0, py - 1.0, 2.0, 2.0, sw=0.25, fill=INK)
        else:
            sc.circle(px, py, 1.0, sw=0.25, fill="#ffffff")
    # dimensions
    _dim_h(sc, ox, ox + Wm * k, oy + Dm * k + 7, f"{Wm:g} m")
    _dim_v(sc, ox - 7, oy, oy + Dm * k, f"{Dm:g} m")
    if lay["rows_info"]:
        r0 = lay["rows_info"][0]
        _dim_h(sc, ox + r0["x"] * k, ox + (r0["x"] + r0["w"]) * k, oy + Dm * k + 14, f"Array width {r0['w']:.2f} m")
    geo = lay["geo"]
    if "pitch" in geo and len(lay["rows_info"]) >= 2:
        r0, r1 = lay["rows_info"][0], lay["rows_info"][1]
        xx = ox + Wm * k + 7
        _dim_v(sc, xx, oy + r1["y_bot"] * k, oy + r0["y_bot"] * k, f"Row pitch {geo['pitch']:.2f} m")
    # north arrow, facing
    _north_arrow(sc, 325.0, 55.0, inp.facing_az_deg)
    sc.text(325.0, 77.0, "Modules face down the sheet", 2.2, anchor="middle", color=GREY)

    # right panel
    px0 = 322.0
    py = 92.0
    sc.text(px0, py, "LEGEND", 2.8, bold=True)
    py += 5
    for sid in range(1, d["strings"]["n_strings"] + 1):
        if py > 150:
            sc.text(px0, py + 2, "...", 2.4)
            break
        sc.rect(px0, py - 2.6, 6, 3.6, sw=0.25, fill=STRING_COLORS[(sid - 1) % len(STRING_COLORS)])
        sc.text(px0 + 8, py + 0.4, f"String {sid} ({d['strings']['modules_per_string']} modules)", 2.4)
        py += 5
    sc.line(px0, py - 1, px0 + 6, py - 1, sw=0.5, color="#222222", dash=[3, 1])
    sc.text(px0 + 8, py + 0.4, "Mounting rail", 2.4)
    py += 5
    if inp.mount == "Pitched roof (flush)":
        sc.circle(px0 + 3, py - 1, 0.9, sw=0.25, fill=INK)
        sc.text(px0 + 8, py + 0.4, "Roof attachment", 2.4)
    else:
        sc.rect(px0 + 2, py - 2, 2, 2, sw=0.25, fill=INK)
        sc.text(px0 + 8, py + 0.4, "Front post / foundation", 2.4)
        py += 5
        sc.circle(px0 + 3, py - 1, 1.0, sw=0.25, fill="#ffffff")
        sc.text(px0 + 8, py + 0.4, "Rear post / foundation", 2.4)
    py += 9
    q = lay["qty"]
    sc.text(px0, py, "QUANTITIES", 2.8, bold=True)
    py += 5
    rows = [
        f"Modules placed: {q['modules_placed']}",
        f"Layout: {lay['cols']} per row x {lay['rows']} row(s)" + (f", {lay['stack']}-high" if lay["stack"] > 1 else ""),
        f"Orientation: {'portrait' if lay['portrait'] else 'landscape'}",
        f"Rail pieces: {q['rails']} x {q['rail_length_m']:g} m",
        f"Splices: {q['splices']}   End clamps: {q['end_clamps']}",
        f"Mid clamps: {q['mid_clamps']}",
        f"Tilt: {inp.tilt_deg:g} deg",
    ]
    for t in rows:
        sc.text(px0, py, t, 2.4)
        py += 4.2
    py += 3
    for n in (lay["notes"] + lay["warnings"])[:5]:
        for ln in wrap(n, 2.1, 80):
            sc.text(px0, py, ln, 2.1, color=RED if n in lay["warnings"] else GREY)
            py += 3.2
        py += 0.8
    sc.rect(px0 - 4, 86.0, 88, py - 86.0, sw=0.3)
    return sc


# ---------------------------------------------------------------- mounting detail
def _clamp_detail(sc, x, y, thk_mm):
    """Typical mid-clamp section, drawn at roughly 1:1.5 (NTS)."""
    s = 0.6
    t = thk_mm * s
    sc.text(x, y - 4, "TYPICAL MID CLAMP AND RAIL DETAIL (NTS)", 2.6, bold=True)
    # rail (hollow) 40 x 40
    sc.rect(x + 30, y + 30, 24, 24, sw=0.5, fill="#eeeeee")
    sc.rect(x + 35, y + 35, 14, 14, sw=0.3, stroke=GREY)
    # modules each side
    sc.rect(x + 2, y + 30 - t, 26, t, sw=0.5, fill="#d5e6f5")
    sc.rect(x + 56, y + 30 - t, 26, t, sw=0.5, fill="#d5e6f5")
    # clamp
    sc.rect(x + 36, y + 30 - t - 3, 12, 3, sw=0.5, fill="#c9c9c9")
    sc.rect(x + 40, y + 30 - t, 4, t + 6, sw=0.3, fill="#c9c9c9")
    sc.line(x + 42, y + 30 - t - 6, x + 42, y + 36, sw=0.4)
    sc.rect(x + 39, y + 30 - t - 6, 6, 3, sw=0.4, fill="#ffffff")
    sc.text(x + 90, y + 8, "Mid clamp (20 mm gap)", 2.3)
    sc.text(x + 90, y + 17, "Module frame", 2.3)
    sc.text(x + 90, y + 42, "Aluminium rail", 2.3)
    sc.line(x + 88, y + 7, x + 45, y + 24 - t, sw=0.2, color=GREY)
    sc.line(x + 88, y + 16, x + 70, y + 28 - t / 2, sw=0.2, color=GREY)
    sc.line(x + 88, y + 41, x + 54, y + 42, sw=0.2, color=GREY)
    sc.text(x, y + 66, "Torque, clamp zone and frame depth per module and clamp manufacturer.", 2.1, color=GREY)


def _front_elevation(sc, lay, x, y, w_avail, h_avail):
    """First (front) row seen from the front, to scale."""
    inp = lay["input"]
    ri = lay["rows_info"][0]
    pw = lay["module_w"]
    geo = lay["geo"]
    tilted = "pitch" in geo
    vert = 0.0
    if tilted:
        vert = geo["front_height_m"] + geo["h"]
        title = "FRONT ELEVATION - FRONT ROW (seen from the front, to scale)"
    else:
        vert = lay["module_d"]
        title = "ROOF FACE - FRONT ROW (looking at the modules, not foreshortened)"
    den = _std_scale(ri["w"] + 0.6, vert + 0.4, w_avail, h_avail - 14)
    k = 1000.0 / den
    sc.text(x, y, title, 2.8, bold=True)
    sc.text(x + w_avail, y, f"1:{den}", 2.6, anchor="end", color=GREY)
    gx = x + 3
    gy = y + 8 + vert * k
    n_r = ri["n"]
    stack = lay["stack"]
    if not tilted:
        top = gy - vert * k
        for c in range(n_r):
            mx = gx + c * (pw + inp.gap_mm / 1000.0) * k
            sc.rect(mx, top, pw * k, vert * k, sw=0.35, fill="#d5e6f5")
            sc.text(mx + pw * k / 2, top + vert * k / 2 + 1, f"{c + 1}", 2.4, anchor="middle", color=GREY)
        for frac in (0.25, 0.75):
            yy = top + frac * vert * k
            sc.line(gx, yy, gx + ri["w"] * k, yy, sw=0.5, color="#222222", dash=[3, 1])
        pts = [p for p in lay["supports"] if p["row"] == 0 and abs(p["y"] - (ri["y_top"] + 0.25 * lay["module_d"])) < 1e-6]
        for p in pts:
            sc.circle(gx + (p["x"] - ri["x"]) * k, top + 0.25 * vert * k, 0.9, sw=0.25, fill=INK)
            sc.circle(gx + (p["x"] - ri["x"]) * k, top + 0.75 * vert * k, 0.9, sw=0.25, fill=INK)
        if len(pts) >= 2:
            _dim_h(sc, gx + (pts[0]["x"] - ri["x"]) * k, gx + (pts[1]["x"] - ri["x"]) * k, gy + 7,
                   f"attachments @ {pts[1]['x'] - pts[0]['x']:.2f} m")
        _dim_h(sc, gx, gx + ri["w"] * k, gy + 15, f"Row width {ri['w']:.2f} m")
    else:
        fc, h = geo["front_height_m"], geo["h"]
        sc.line(gx - 3, gy, gx + ri["w"] * k + 3, gy, sw=0.7)
        cols_r = math.ceil(ri["n"] / stack)
        for c in range(cols_r):
            mx = gx + c * (pw + inp.gap_mm / 1000.0) * k
            sc.rect(mx, gy - (fc + h) * k, pw * k, h * k, sw=0.35, fill="#d5e6f5")
        posts = [p for p in lay["supports"] if p["row"] == 0 and p["kind"] == "front post"]
        for p in posts:
            px = gx + (p["x"] - ri["x"]) * k
            sc.line(px, gy, px, gy - fc * k, sw=1.0)
        if len(posts) >= 2:
            _dim_h(sc, gx + (posts[0]["x"] - ri["x"]) * k, gx + (posts[1]["x"] - ri["x"]) * k, gy + 7,
                   f"posts @ {posts[1]['x'] - posts[0]['x']:.2f} m")
        _dim_h(sc, gx, gx + ri["w"] * k, gy + 15, f"Row width {ri['w']:.2f} m")


def mount_sheet(meta: Meta, d: dict, lay: dict, number: int, total: int) -> Scene:
    import layout as _layout

    inp = lay["input"]
    sc = new_sheet(meta, "mount", number, total, "see views")
    heading(sc, "MOUNTING STRUCTURE DETAIL", f"{inp.mount}. Side and front views to scale; clamp detail not to scale.")
    geo = lay["geo"]
    tilt = math.radians(inp.tilt_deg)
    base_y = 128.0
    box_w, box_h = 238.0, 70.0
    if inp.mount == "Pitched roof (flush)":
        Dm = inp.area_d_m
        rise, run = Dm * math.sin(tilt), Dm * math.cos(tilt)
        den = _std_scale(run + 0.8, rise + 0.8, box_w - 20, box_h - 8)
        k = 1000.0 / den
        x0 = 32.0
        ex, ey = x0, base_y
        rx, ry = ex + run * k, ey - rise * k
        sc.line(ex - 6, ey + 6 * math.tan(tilt), rx + 6, ry - 6 * math.tan(tilt), sw=0.8)
        sc.line(ex, ey, ex + 42, ey, sw=0.25, color=GREY, dash=[2, 1.2])
        sc.arc(ex, ey, 34, 0, inp.tilt_deg, sw=0.3)
        sc.text(ex + 37, ey - 1.2, f"{inp.tilt_deg:g} deg pitch", 2.6)
        sc.text(ex, ey + 9, "EAVE (modules face this way)", 2.4, bold=True)
        sc.text(rx, ry + 9, "RIDGE", 2.4, anchor="middle", bold=True)
        standoff_m = 0.12
        ux, uy = math.cos(tilt), -math.sin(tilt)
        nx, ny = -math.sin(tilt), -math.cos(tilt)
        for ri in lay["rows_info"]:
            s0 = inp.setback_m + ri["row"] * (lay["module_d"] + inp.gap_mm / 1000.0)
            s1 = s0 + lay["module_d"]
            p0 = (ex + s0 * ux * k + standoff_m * nx * k, ey + s0 * uy * k + standoff_m * ny * k)
            p1 = (ex + s1 * ux * k + standoff_m * nx * k, ey + s1 * uy * k + standoff_m * ny * k)
            sc.line(p0[0], p0[1], p1[0], p1[1], sw=max(0.9, inp.module_thk_mm / 1000 * k), color="#3b6ea5")
            for frac in (0.25, 0.75):
                s = s0 + frac * lay["module_d"]
                a = (ex + s * ux * k, ey + s * uy * k)
                b = (a[0] + standoff_m * nx * k, a[1] + standoff_m * ny * k)
                sc.line(a[0], a[1], b[0], b[1], sw=0.5)
        sc.text(x0, 40, "FLUSH MOUNT ON PITCHED ROOF", 3.6, bold=True)
        sc.text(x0, 46, f"Slope length {Dm:g} m, {lay['rows']} row(s) along the slope. Section drawn at 1:{den}.", 2.5, color=GREY)
        sc.text(x0, 50.6, f"Modules sit about {int(standoff_m * 1000)} mm above the roof covering (minimum ventilation gap).", 2.5, color=GREY)
        sc.text(x0, 55.2, f"Attachment: {_layout.ROOF_TYPES[inp.roof_type]}", 2.5, color=GREY)
        sc.text(x0, 59.8, f"Attachments at max {inp.support_span_m:g} m centres, fixed into rafters / purlins.", 2.5, color=GREY)
    else:
        Lt, dp, h, pitch = geo["Lt"], geo["dp"], geo["h"], geo["pitch"]
        fc = geo["front_height_m"]
        nrows = len(lay["rows_info"])
        shown = min(nrows, 3)
        total_w = (shown - 1) * pitch + dp + 0.6
        den = _std_scale(total_w + 2.0, fc + h + 0.6, box_w - 25, box_h - 6)
        k = 1000.0 / den
        gx = 40.0
        gy = base_y
        sc.line(gx - 18, gy, gx + (total_w + 1.8) * k, gy, sw=0.8)
        for i in range(shown):
            xf = gx + i * pitch * k
            xr = xf + dp * k
            yf = gy - fc * k
            yr = gy - (fc + h) * k
            sc.line(xf, gy, xf, yf, sw=0.8)
            sc.line(xr, gy, xr, yr, sw=0.8)
            sc.line(xf, yf, xr, yr, sw=max(1.0, inp.module_thk_mm / 1000 * k * 3), color="#3b6ea5")
            sc.line(xr, yr + 0.15 * k, xf, gy, sw=0.25, color=GREY, dash=[1.5, 1.0])
        if nrows > shown:
            sc.text(gx + ((shown - 1) * pitch + dp + 0.5) * k, gy - 6, f"... {nrows - shown} more row(s)", 2.5)
        # shading check: ray at the profile angle from the top of row 1 must clear the bottom edge of row 2
        fac = geo["shadow_factor"]
        rx0 = gx + dp * k
        ry0 = gy - (fc + h) * k
        run_len = (fc + h) * fac * k
        sc.line(rx0, ry0, rx0 + run_len, gy, sw=0.4, color="#e08a00", dash=[2.5, 1.2])
        sc.text(rx0 + 4, ry0 - 2.5, f"Winter-solstice sun ray ({12 - geo['sun_hours']:.0f}:00), profile angle {geo['profile_deg']:.0f} deg", 2.3, color="#b36b00")
        _dim_v(sc, gx - 8, gy - fc * k, gy, f"{fc:.2f}")
        _dim_v(sc, gx - 17, gy - (fc + h) * k, gy, f"{fc + h:.2f}")
        if nrows >= 2:
            _dim_h(sc, gx, gx + pitch * k, gy + 12, f"Row pitch {pitch:.2f} m")
        _dim_h(sc, gx, gx + dp * k, gy + 20, f"Plan depth {dp:.2f} m")
        sc.line(gx, gy - fc * k, gx + 40, gy - fc * k, sw=0.25, color=GREY, dash=[2, 1.2])
        sc.arc(gx, gy - fc * k, 30, 0, inp.tilt_deg, sw=0.3)
        sc.text(gx + 32, gy - fc * k - 1.2, f"{inp.tilt_deg:g} deg", 2.5)
        sc.text(gx - 18, gy + 29, "<- FRONT: modules face this way", 2.4, bold=True)
        kind = "GROUND MOUNT" if inp.mount == "Ground mount (tilted frames)" else "FLAT ROOF"
        sc.text(25, 40, f"TILTED FRAMES - {kind}", 3.6, bold=True)
        sc.text(25, 46, f"{lay['stack']} module(s) high, tilt {inp.tilt_deg:g} deg, front clearance {fc:.2f} m, rear height {fc + h:.2f} m. Section at 1:{den}.", 2.5, color=GREY)
        sc.text(25, 50.6, f"Row pitch {pitch:.2f} m (ground cover ratio {geo['gcr']}) keeps rows clear of shade from about "
                          f"{12 - geo['sun_hours']:.0f}:00 to {12 + geo['sun_hours']:.0f}:00 solar time on the winter solstice.", 2.5, color=GREY)
        sc.text(25, 55.2, "Foundations, post sizes and ballast: by structural engineer (wind uplift is not calculated).", 2.5, color=RED)
    _clamp_detail(sc, 275.0, 46.0, inp.module_thk_mm)
    if lay["rows_info"]:
        _front_elevation(sc, lay, 16.0, 184.0, 215.0, 62.0)
    sc.text(250, 184, "NOTES", 2.8, bold=True)
    notes = [
        "1. Rail positions are generic (about 1/4 and 3/4 of the module). Use the clamping zone in the module manual.",
        "2. Bond all rails, clamps and module frames; bond across rail splices.",
        "3. Use stainless fasteners (A2/A4); avoid contact between dissimilar metals.",
        "4. Check roof or ground structure capacity before installation. Wind and snow loads per SANS 10160.",
    ]
    ny = 189.5
    for t in notes:
        for ln in wrap(t, 2.4, 150):
            sc.text(250, ny, ln, 2.4, color=GREY)
            ny += 3.8
        ny += 0.8
    return sc


# ---------------------------------------------------------------- BOM + schedules
def _table(sc, x, y, widths, header, rows, size=2.5, rh=5.0):
    xs = [x]
    for w in widths:
        xs.append(xs[-1] + w)
    sc.rect(x, y, sum(widths), rh, sw=0.3, fill="#e9e9e9")
    for i, htxt in enumerate(header):
        sc.text(xs[i] + 1.2, y + rh - 1.5, htxt, size, bold=True)
    yy = y + rh
    for r in rows:
        sc.line(x, yy + rh, x + sum(widths), yy + rh, sw=0.15, color="#bbbbbb")
        for i, cell in enumerate(r):
            sc.text(xs[i] + 1.2, yy + rh - 1.5, fit_text(str(cell), size, widths[i] - 2.0), size)
        yy += rh
    sc.rect(x, y, sum(widths), yy - y, sw=0.3)
    for xx in xs[1:-1]:
        sc.line(xx, y, xx, yy, sw=0.15, color="#999999")
    return yy


def bom_sheet(meta: Meta, d: dict, lay: dict | None, number: int, total: int) -> Scene:
    sc = new_sheet(meta, "bom", number, total, "NTS")
    heading(sc, "BILL OF MATERIALS AND SCHEDULES", "Quantities are preliminary take-offs. Add wastage and confirm against final product choice.")
    rows = []
    n = 1
    items = list(d["bom"]) + (lay["bom"] if lay and lay.get("ok") else [])
    for it in items:
        rows.append([n, it["category"], it["item"], it["spec"], it["qty"], it["unit"]])
        n += 1
    max_rows = 38
    truncated = len(rows) > max_rows
    rows = rows[:max_rows]
    _table(sc, 15, 34, [8, 20, 62, 92, 10, 12], ["No", "Category", "Description", "Specification", "Qty", "Unit"], rows)
    if truncated:
        sc.text(15, 34 + 5 * (max_rows + 1) + 5, "List truncated. See the design summary for the complete set.", 2.4, color=RED)

    # cable schedule
    x0 = 232.0
    cab = d["cables"]
    inp = d["input"]
    crow = []
    dcs = cab["dc_string"]
    crow.append(["C1", f"DC strings (x{d['strings']['n_strings']})", f"{dcs['mm2']:g} mm2", f"{dcs['length_m_each']:g} m", f"{dcs['design_current_a']:g} A", f"{dcs['drop_pct']} %"])
    ac = cab["ac"]
    crow.append(["C2", "AC inverter-DB", f"{ac['mm2']:g} mm2", f"{ac['length_m']:g} m", f"{ac['design_current_a']:g} A", f"<= {inp.ac_drop_pct:g} %"])
    if "battery" in cab:
        bt = cab["battery"]
        crow.append(["C3", "Battery", f"{bt['mm2']:g} mm2", f"{bt['length_m_each']:g} m", f"{bt['design_current_a']:g} A", "<= 1 %"])
    crow.append(["E1", "PV frame bonding", "6 / 16 mm2", "-", "-", "-"])
    sc.text(x0, 31, "CABLE SCHEDULE", 3.0, bold=True)
    yend = _table(sc, x0, 34, [10, 40, 24, 16, 18, 20], ["Tag", "Circuit", "Size", "Length", "I design", "V drop"], crow)
    sc.text(x0, yend + 4, "Sizes use a voltage-drop check plus a conservative current rating.", 2.1, color=GREY)
    sc.text(x0, yend + 7.4, "Verify installation method, grouping, ambient temperature.", 2.1, color=GREY)

    # protection schedule
    prow = []
    for g in d["mppt"]:
        if g["n"]:
            prow.append([f"QD{g['mppt']}", "DC isolator", f"{g['isolator_a']} A, {d['string']['voc_cold_v']:.0f} V DC min"])
            if g["fuse_a"]:
                prow.append([f"F{g['strings'][0]}-{g['strings'][-1]}", "String fuses gPV", f"{g['fuse_a']} A, 1000 V DC"])
            prow.append([f"SPD-DC{g['mppt']}", "DC surge protector", f"Type 2, Uc >= {d['spd']['dc_uc_v']} V"])
    a = d["ac"]
    prow.append(["QA1", f"AC MCB {a['poles']}P", f"{a['breaker_a']} A, curve C"])
    prow.append(["RCD1", "Residual current dev.", f"{a['rcd_ma']} mA (type per inverter)"])
    prow.append(["SPD-AC", "AC surge protector", "Type 2"])
    if d.get("battery"):
        prow.append(["QB1", "Battery DC breaker", f"{d['battery']['breaker_a']} A DC"])
    py = yend + 19
    sc.text(x0, py - 3, "PROTECTION SCHEDULE", 3.0, bold=True)
    _table(sc, x0, py, [20, 48, 60], ["Tag", "Device", "Rating"], prow)
    return sc


# ---------------------------------------------------------------- cover
def cover_sheet(meta: Meta, d: dict, lay: dict | None, number: int, total: int, sheets: list[str]) -> Scene:
    sc = new_sheet(meta, "cover", number, total, "NTS")
    inp = d["input"]
    sc.text(16, 30, "PHOTOVOLTAIC SYSTEM", 11, bold=True)
    sc.text(16, 40, "PRELIMINARY DESIGN DRAWINGS", 6.5, bold=True, color=GREY)
    y = 54.0
    for lab, val in [("Project", meta.project), ("Client", meta.client), ("Site", meta.address),
                     ("Drawn by", meta.drawn_by), ("Date / revision", f"{meta.date}  /  {meta.revision}")]:
        sc.text(16, y, lab.upper(), 2.2, color=GREY)
        sc.text(52, y, fit_text(val or "-", 3.2, 170), 3.2, bold=True)
        y += 6.2
    # summary
    y += 6
    sc.text(16, y, "DESIGN SUMMARY", 3.6, bold=True)
    y += 3
    s = d["string"]
    mod = inp.module
    inv = inp.inverter
    summ = [
        ("Array", f"{d['strings']['used']} x {mod.watts:.0f} W = {d['kwp']} kWp"),
        ("Modules", mod.name),
        ("Inverter", inv.name),
        ("DC/AC ratio", f"{d['dc_ac_ratio']}"),
        ("Strings", f"{d['strings']['n_strings']} x {s['modules']} modules"),
        ("String voltage", f"Voc cold {s['voc_cold_v']} V, Vmp {s['vmp_v']} V (limit {inv.max_dc_v:.0f} V)"),
        ("AC protection", f"{d['ac']['breaker_a']} A {d['ac']['poles']}P MCB, {d['ac']['rcd_ma']} mA RCD"),
        ("Battery", f"{d['battery']['kwh']:g} kWh, {d['battery']['voltage_v']:g} V" if d.get("battery") else "None"),
    ]
    if lay and lay.get("ok"):
        summ.append(("Mounting", f"{lay['input'].mount}, {lay['input'].tilt_deg:g} deg, {lay['cols']} x {lay['rows']}"))
    for lab, val in summ:
        y += 6.0
        sc.text(16, y, lab, 2.8, color=GREY)
        sc.text(52, y, fit_text(val, 3.0, 170), 3.0)
    # drawing index
    sc.text(250, 54, "DRAWING INDEX", 3.6, bold=True)
    yy = 62.0
    for i, key in enumerate(sheets, start=1):
        sc.text(250, yy, f"{meta.drawing_no}-{i:02d}", 3.0, bold=True)
        sc.text(278, yy, SHEET_TITLES[key], 3.0)
        yy += 6.2
    # warnings
    yy += 8
    sc.text(250, yy, "DESIGN CHECKS", 3.6, bold=True)
    yy += 6
    msgs = list(d["warnings"]) + (lay["warnings"] if lay and lay.get("ok") else [])
    if not msgs:
        sc.text(250, yy, "No warnings raised by the checks.", 2.8, color=GREEN)
        yy += 6
    for m in msgs[:7]:
        for j, ln in enumerate(wrap(m, 2.6, 150)):
            sc.text(250, yy, ("- " if j == 0 else "  ") + ln, 2.6, color=RED)
            yy += 4.0
        yy += 0.8
    # notes & disclaimer
    ny = 183.0
    sc.rect(16, ny - 5, 218, 56, sw=0.3, fill="#fffdf2")
    sc.text(19, ny, "IMPORTANT", 3.0, bold=True, color=RED)
    disclaimer = [
        "These drawings are generated automatically from the inputs shown and are PRELIMINARY.",
        "They are a design aid, not certified or stamped designs, and must not be used for construction until checked and signed off by a registered engineer or competent electrician.",
        "Module and inverter values are taken from user input or generic defaults; replace them with datasheet values.",
        "Compliance with SANS 10142-1, IEC 60364-7-712, IEC 62548, SANS 10160 and the local utility (EEC) requirements must be confirmed. Structural loading (wind, snow, foundations) is not calculated.",
    ]
    ty = ny + 5
    for p in disclaimer:
        for ln in wrap(p, 2.5, 210):
            sc.text(19, ty, ln, 2.5)
            ty += 3.7
        ty += 0.6
    # sign-off boxes
    sx = 16.0
    for lab in ("Designed by", "Checked by", "Approved (registered engineer)"):
        sc.rect(sx, 240.0, 72, 7, sw=0.3)
        sc.text(sx + 1.2, 237.8, lab, 2.1, color=GREY)
        sx += 74
    return sc


# ---------------------------------------------------------------- public API
def build_sheets(meta: Meta, d: dict, lay: dict | None) -> dict[str, Scene]:
    """All sheets keyed by name. Layout-dependent sheets are skipped if there is no valid layout."""
    keys = list(SHEET_ORDER)
    if not (lay and lay.get("ok")):
        keys = [k for k in keys if k not in ("layout", "mount")]
    total = len(keys)
    out: dict[str, Scene] = {}
    for i, key in enumerate(keys, start=1):
        if key == "cover":
            out[key] = cover_sheet(meta, d, lay, i, total, keys)
        elif key == "sld":
            out[key] = sld(meta, d, lay, i, total)
        elif key == "layout":
            out[key] = layout_sheet(meta, d, lay, i, total)
        elif key == "mount":
            out[key] = mount_sheet(meta, d, lay, i, total)
        elif key == "bom":
            out[key] = bom_sheet(meta, d, lay, i, total)
    return out


def pdf_for(sheets: dict[str, Scene], keys: list[str], meta: Meta) -> bytes:
    scenes = [sheets[k] for k in keys if k in sheets]
    return build_pdf(scenes, title=f"{meta.project} - PV drawings", author=meta.drawn_by or meta.software,
                     subject="Preliminary PV system drawings")
