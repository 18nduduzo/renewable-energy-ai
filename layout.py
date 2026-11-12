"""Array layout and mounting-structure take-off for roof and ground mounts.

Plan-view coordinates are in metres: x across the array, y DOWN the sheet. The array
faces DOWN the sheet (toward larger y), so for a pitched roof the eave is at the bottom
and the ridge at the top. Rows are numbered from the front (bottom) upward.

PRELIMINARY ONLY. Wind/snow loading, rafter/purlin capacity, foundations and ballast are
NOT calculated here: they need a structural engineer (SANS 10160-3 for wind actions).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

MOUNT_PITCHED = "Pitched roof (flush)"
MOUNT_FLAT = "Flat roof (tilted frames)"
MOUNT_GROUND = "Ground mount (tilted frames)"
MOUNTS = [MOUNT_PITCHED, MOUNT_FLAT, MOUNT_GROUND]

ROOF_TYPES = {
    "IBR / corrugated sheet": "Roof-sheet bracket / seam clamp with sealing washer",
    "Concrete tile": "Adjustable tile hook",
    "Clay tile": "Adjustable tile hook",
    "Slate / fibre-cement": "Slate hook / flashed bracket",
    "Flat concrete slab": "Slab anchor / ballast foot (engineer to specify)",
}


@dataclass
class LayoutInput:
    mount: str = MOUNT_PITCHED
    n_modules: int = 10
    module_len_mm: float = 2278
    module_wid_mm: float = 1134
    module_thk_mm: float = 35
    orientation: str = "auto"          # "portrait" | "landscape" | "auto"
    area_w_m: float = 8.0              # usable width (across the roof / field)
    area_d_m: float = 4.0              # slope length (roof) or depth (flat / ground)
    setback_m: float = 0.4
    gap_mm: float = 20.0
    tilt_deg: float = 20.0             # roof pitch (pitched) or frame tilt
    facing_az_deg: float = 0.0         # direction the modules face, 0 = north
    latitude: float = -26.3
    stack: int = 1                     # modules stacked on a tilted frame (1P / 2P)
    front_clearance_m: float = 0.5     # lowest edge above ground / roof
    support_span_m: float = 1.2        # max distance between roof attachments / posts
    rail_length_m: float = 4.2
    roof_type: str = "IBR / corrugated sheet"
    min_row_gap_m: float = 0.3


def winter_shadow_factor(latitude_deg: float, hours_before_noon: float = 3.0) -> dict:
    """Shadow length behind a row, per metre of row height, on the winter solstice.

    Uses 09:00 solar time by default. Works in a mirrored northern-hemisphere frame so the
    same formula serves both hemispheres (arrays face the equator).
    """
    phi = math.radians(min(abs(latitude_deg), 66.0))
    delta = math.radians(-23.44)
    chosen = None
    for hrs in (hours_before_noon, 2.0, 1.0, 0.0):
        H = math.radians(-15.0 * hrs)
        sin_alt = math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.cos(H)
        alt = math.asin(max(-1.0, min(1.0, sin_alt)))
        if math.degrees(alt) >= 8.0:
            chosen = (hrs, alt, H)
            break
    if chosen is None:
        return {"factor": 6.0, "alt_deg": 0.0, "hours": 0.0}
    hrs, alt, H = chosen
    cos_an = (math.sin(delta) - math.sin(alt) * math.sin(phi)) / (math.cos(alt) * math.cos(phi))
    cos_an = max(-1.0, min(1.0, cos_an))
    cos_psi = -cos_an  # angle from the equator-facing direction
    factor = max(cos_psi, 0.0) / math.tan(alt)
    return {"factor": factor, "alt_deg": math.degrees(alt), "hours": hrs}


def _fit_grid(n: int, cols_cap: int, rows_cap: int):
    """Balanced rows: fewest rows that fit, then even row lengths."""
    if cols_cap < 1 or rows_cap < 1:
        return 0, 0
    rows = math.ceil(n / cols_cap)
    if rows > rows_cap:
        return cols_cap, rows_cap
    cols = math.ceil(n / rows)
    return cols, rows


def _arrange(inp: LayoutInput, portrait: bool) -> dict:
    """Compute geometry for one orientation. Returns capacity and module positions."""
    L = inp.module_len_mm / 1000.0
    W = inp.module_wid_mm / 1000.0
    gap = inp.gap_mm / 1000.0
    pw = W if portrait else L          # across the row
    pd = L if portrait else W          # along the slope
    sb = inp.setback_m
    usable_w = inp.area_w_m - 2 * sb
    usable_d = inp.area_d_m - 2 * sb
    tilt = math.radians(inp.tilt_deg)
    tilted = inp.mount != MOUNT_PITCHED

    cols_cap = int((usable_w + gap) // (pw + gap)) if usable_w > 0 else 0
    if tilted:
        stack = max(1, inp.stack)
        Lt = stack * pd + (stack - 1) * gap
        dp = Lt * math.cos(tilt)
        h = Lt * math.sin(tilt)
        sh = winter_shadow_factor(inp.latitude)
        shadow = h * sh["factor"]
        pitch = dp + max(shadow, inp.min_row_gap_m)
        rows_cap = int((usable_d - dp) // pitch) + 1 if usable_d >= dp else 0
        tables_needed = math.ceil(inp.n_modules / stack)
        cols, rows = _fit_grid(tables_needed, cols_cap, rows_cap)
        capacity = cols_cap * rows_cap * stack
        geo = {"Lt": Lt, "dp": dp, "h": h, "pitch": pitch, "shadow": shadow, "sun": sh, "stack": stack}
    else:
        rows_cap = int((usable_d + gap) // (pd + gap)) if usable_d > 0 else 0
        cols, rows = _fit_grid(inp.n_modules, cols_cap, rows_cap)
        capacity = cols_cap * rows_cap
        stack = 1
        geo = {}
    return {"portrait": portrait, "pw": pw, "pd": pd, "cols": cols, "rows": rows, "cols_cap": cols_cap,
            "rows_cap": rows_cap, "capacity": capacity, "stack": stack, "geo": geo, "gap": gap, "sb": sb}


def compute_layout(inp: LayoutInput, modules_per_string: int | None = None) -> dict:
    warnings: list[str] = []
    notes: list[str] = []
    tilted = inp.mount != MOUNT_PITCHED
    if inp.n_modules < 1:
        return {"ok": False, "warnings": ["No modules to place."]}
    if inp.area_w_m <= 2 * inp.setback_m or inp.area_d_m <= 2 * inp.setback_m:
        return {"ok": False, "warnings": ["The area is smaller than the edge setbacks. Increase the area or reduce setbacks."]}

    if inp.orientation == "auto":
        cand = [_arrange(inp, True), _arrange(inp, False)]
        cand.sort(key=lambda c: (c["capacity"] >= inp.n_modules, c["capacity"], c["portrait"]), reverse=True)
        a = cand[0]
    else:
        a = _arrange(inp, inp.orientation == "portrait")

    if a["cols"] < 1 or a["rows"] < 1:
        return {"ok": False, "warnings": ["No module fits in this area. Check the area size and setbacks."]}

    stack = a["stack"]
    per_row = a["cols"] * stack
    n_place = min(inp.n_modules, a["capacity"])
    shortfall = inp.n_modules - n_place
    if shortfall > 0:
        warnings.append(
            f"The area only fits {a['capacity']} modules; {shortfall} do not fit. Enlarge the area, "
            f"use more rows, a smaller tilt, or another roof face.")

    pw, pd, gap, sb = a["pw"], a["pd"], a["gap"], a["sb"]
    tilt = math.radians(inp.tilt_deg)
    row_w = a["cols"] * pw + (a["cols"] - 1) * gap
    usable_w = inp.area_w_m - 2 * sb
    x0 = sb + max(0.0, (usable_w - row_w) / 2)
    Da = inp.area_d_m

    modules: list[dict] = []
    rails: list[dict] = []
    supports: list[dict] = []   # roof attachments (pitched) or posts (tilted)
    rows_info: list[dict] = []
    span = inp.support_span_m

    def n_support_points(length: float) -> int:
        return max(2, math.ceil(max(length - 0.3, 0.01) / span) + 1)

    idx = 0
    if not tilted:
        rows = a["rows"]
        rem = n_place
        for r in range(rows):
            n_r = min(a["cols"], rem)
            if n_r <= 0:
                break
            rem -= n_r
            y_bot = Da - sb - r * (pd + gap)
            y_top = y_bot - pd
            rw = n_r * pw + (n_r - 1) * gap
            xr = x0 + (row_w - rw) / 2 if n_r < a["cols"] else x0
            for c in range(n_r):
                modules.append({"i": idx, "x": xr + c * (pw + gap), "y": y_top, "w": pw, "h": pd, "row": r, "col": c})
                idx += 1
            ys = [y_top + 0.25 * pd, y_top + 0.75 * pd]
            for yy in ys:
                rails.append({"x1": xr, "x2": xr + rw, "y": yy, "row": r})
                n = n_support_points(rw)
                xs = [xr + 0.15 + (rw - 0.3) * k / (n - 1) for k in range(n)]
                supports += [{"x": xx, "y": yy, "row": r, "kind": "attachment"} for xx in xs]
            rows_info.append({"row": r, "n": n_r, "x": xr, "w": rw, "y_top": y_top, "y_bot": y_bot})
    else:
        geo = a["geo"]
        dp, Lt, h, pitch = geo["dp"], geo["Lt"], geo["h"], geo["pitch"]
        tables = a["rows"]
        rem_modules = n_place
        for r in range(tables):
            m_r = min(per_row, rem_modules)
            if m_r <= 0:
                break
            rem_modules -= m_r
            cols_r = math.ceil(m_r / stack)
            y_bot = Da - sb - r * pitch
            y_top = y_bot - dp
            rw = cols_r * pw + (cols_r - 1) * gap
            xr = x0 + (row_w - rw) / 2 if cols_r < a["cols"] else x0
            placed_here = 0
            for s_i in range(stack):
                for c in range(cols_r):
                    if placed_here >= m_r:
                        break
                    sub_top = y_top + s_i * (pd + gap) * math.cos(tilt)
                    modules.append({"i": idx, "x": xr + c * (pw + gap), "y": sub_top, "w": pw,
                                    "h": pd * math.cos(tilt), "row": r, "col": c})
                    idx += 1
                    placed_here += 1
            for s_i in range(stack):
                base = s_i * (pd + gap)
                for frac in (0.25, 0.75):
                    yy = y_top + (base + frac * pd) * math.cos(tilt)
                    rails.append({"x1": xr, "x2": xr + rw, "y": yy, "row": r})
            n = n_support_points(rw)
            xs = [xr + 0.1 + (rw - 0.2) * k / (n - 1) for k in range(n)]
            for xx in xs:
                supports.append({"x": xx, "y": y_bot, "row": r, "kind": "front post"})
                supports.append({"x": xx, "y": y_top, "row": r, "kind": "rear post"})
            rows_info.append({"row": r, "n": m_r, "x": xr, "w": rw, "y_top": y_top, "y_bot": y_bot, "posts_per_line": n})

    # string numbers for colouring
    for m in modules:
        m["string"] = (m["i"] // modules_per_string + 1) if modules_per_string else 0

    # ---- quantities
    rail_len = inp.rail_length_m
    rail_pieces = 0
    splices = 0
    for rl in rails:
        L = rl["x2"] - rl["x1"]
        p = max(1, math.ceil(L / rail_len - 1e-9))
        rail_pieces += p
        splices += p - 1
    rail_total_m = sum(rl["x2"] - rl["x1"] for rl in rails)
    end_clamps = 0
    mid_clamps = 0
    if not tilted:
        for ri in rows_info:
            end_clamps += 4
            mid_clamps += 2 * (ri["n"] - 1)
    else:
        for ri in rows_info:
            cols_r = math.ceil(ri["n"] / stack)
            end_clamps += 4 * stack
            mid_clamps += 2 * stack * (cols_r - 1)
    qty = {
        "rails": rail_pieces, "rail_total_m": round(rail_total_m, 1), "rail_length_m": rail_len,
        "splices": splices, "end_clamps": end_clamps, "mid_clamps": mid_clamps,
        "modules_placed": n_place, "shortfall": shortfall,
    }
    bom: list[dict] = []

    def add(item, q, unit="pcs", spec=""):
        bom.append({"category": "Mounting", "item": item, "qty": q, "unit": unit, "spec": spec})

    add("Aluminium mounting rail", rail_pieces, "pcs", f"{rail_len} m lengths, anodised ({rail_total_m:.1f} m needed before offcuts)")
    if splices:
        add("Rail splice", splices)
    add("End clamp", end_clamps, "pcs", f"to suit {inp.module_thk_mm:.0f} mm frame")
    add("Mid clamp", mid_clamps, "pcs", f"{inp.gap_mm:.0f} mm gap")

    geo_out: dict = {}
    if not tilted:
        n_att = len(supports)
        add("Roof attachment", n_att, "pcs", ROOF_TYPES[inp.roof_type])
        add("Earthing lug / bonding jumper (rails and splices)", len(rows_info) * 2 + splices, "pcs", "")
        notes.append(f"Roof attachments at max {span:.1f} m centres; confirm they land on rafters/purlins.")
        notes.append("Check roof structure capacity and the manufacturer's wind/snow load tables before installing.")
        geo_out = {"roof_pitch_deg": inp.tilt_deg}
        if abs(((inp.facing_az_deg + 180) % 360) - 180) > 60:
            warnings.append("The roof faces more than 60 degrees away from the equator. Expect noticeably lower yield.")
    else:
        geo = a["geo"]
        posts = [s for s in supports]
        front = sum(1 for s in posts if s["kind"] == "front post")
        rear = sum(1 for s in posts if s["kind"] == "rear post")
        fc = inp.front_clearance_m
        front_h = fc
        rear_h = fc + geo["h"]
        add("Front post", front, "pcs", f"{front_h:.2f} m above {'ground' if inp.mount == MOUNT_GROUND else 'roof'}")
        add("Rear post", rear, "pcs", f"{rear_h:.2f} m above {'ground' if inp.mount == MOUNT_GROUND else 'roof'}")
        add("Inclined rafter (frame leg to leg)", front, "pcs", f"{geo['Lt'] + 0.1:.2f} m, {inp.tilt_deg:.0f} deg")
        add("Diagonal brace", front, "pcs", "one per frame")
        if inp.mount == MOUNT_GROUND:
            add("Foundation (pile / ground screw / concrete footing)", front + rear, "pcs", "size and depth to be set by soil/wind design")
        else:
            add("Roof support foot / ballast block set", front + rear, "pcs", "ballast or anchor design by structural engineer")
        add("Earthing lug / bonding jumper", len(rows_info) * 2 + splices, "pcs", "")
        notes.append(f"Row pitch {geo['pitch']:.2f} m keeps rows shade-free from about "
                     f"{12 - geo['sun']['hours']:.0f}:00 to {12 + geo['sun']['hours']:.0f}:00 solar time on the winter solstice.")
        notes.append("Wind uplift and foundations are not calculated. A structural engineer must size posts, "
                     "foundations or ballast (SANS 10160-3 wind actions).")
        geo_out = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in geo.items() if k != "sun"}
        geo_out.update({"tilt_deg": inp.tilt_deg, "front_height_m": round(front_h, 2), "rear_height_m": round(rear_h, 2),
                        "sun_alt_deg": round(geo["sun"]["alt_deg"], 1), "sun_hours": geo["sun"]["hours"],
                        "shadow_factor": round(geo["sun"]["factor"], 4),
                        "profile_deg": round(math.degrees(math.atan2(1.0, max(geo["sun"]["factor"], 1e-6))), 1),
                        "gcr": round(geo["dp"] / geo["pitch"], 2)})
        if rear_h > 2.5:
            warnings.append(f"Rear post height is {rear_h:.1f} m. Tall frames carry high wind loads; consider a "
                            "single-module-high frame or a lower tilt.")
        if inp.tilt_deg > 35:
            warnings.append("Tilt above 35 degrees is unusual for this latitude and increases wind load and row spacing.")

    return {
        "ok": True, "portrait": a["portrait"], "cols": a["cols"], "rows": a["rows"], "stack": stack,
        "capacity": a["capacity"], "modules": modules, "rails": rails, "supports": supports, "rows_info": rows_info,
        "row_width_m": round(row_w, 3), "array_x0": x0, "qty": qty, "bom": bom, "geo": geo_out,
        "module_w": pw, "module_d": pd, "warnings": warnings, "notes": notes, "input": inp,
        "area": (inp.area_w_m, inp.area_d_m),
    }
