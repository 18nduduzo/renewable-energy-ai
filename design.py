"""PV system design engine: string sizing, protection, cables and bill of materials.

Pure Python (no Streamlit, no drawing) so it can be tested and reused.

IMPORTANT: everything here is a PRELIMINARY design aid. Default module and inverter
values are generic placeholders, replace them with the datasheet values of the real
products. Results must be checked by a registered/competent person against
SANS 10142-1, IEC 60364-7-712, IEC 62548 and the local utility (EEC) rules.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict

import calculators as calc

STD_BREAKERS_A = [6, 10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 200, 250]
STD_FUSES_A = [10, 12, 15, 16, 20, 25, 30]
STD_DC_BREAKERS_A = [16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400]

# Conservative generic current ratings for copper cable (installed in conduit / clipped,
# ~40 C ambient, derated). Use the cable maker's tables for the real installation method.
AMPACITY_CU = {1.5: 14, 2.5: 19, 4: 25, 6: 32, 10: 44, 16: 59, 25: 77, 35: 94, 50: 112, 70: 142, 95: 172, 120: 198}


@dataclass
class Module:
    name: str = "Generic 550 W mono PERC"
    watts: float = 550
    voc: float = 49.9
    vmp: float = 41.8
    isc: float = 13.9
    imp: float = 13.16
    temp_coeff_voc_pct: float = -0.26   # %/degC
    temp_coeff_pmax_pct: float = -0.30  # %/degC (also used for Vmp)
    length_mm: float = 2278
    width_mm: float = 1134
    thickness_mm: float = 35
    weight_kg: float = 28
    max_series_fuse_a: float = 25


@dataclass
class Inverter:
    name: str = "Generic 5 kW hybrid, 1-phase"
    ac_kw: float = 5.0
    phases: int = 1
    max_dc_v: float = 500
    mppt_min_v: float = 125
    mppt_max_v: float = 425
    n_mppt: int = 2
    max_current_per_mppt_a: float = 16     # operating input current
    max_isc_per_mppt_a: float = 20         # short-circuit current limit
    max_strings_per_mppt: int = 2
    max_dc_kw: float = 7.5
    hybrid: bool = True
    battery_v: float = 51.2
    max_battery_charge_a: float = 100


INVERTER_PRESETS = {
    "5 kW hybrid, 1-phase (500 V, 2 MPPT)": Inverter(),
    "8 kW hybrid, 1-phase (500 V, 2 MPPT)": Inverter(
        name="Generic 8 kW hybrid, 1-phase", ac_kw=8, max_dc_kw=12, max_current_per_mppt_a=18,
        max_isc_per_mppt_a=24, max_strings_per_mppt=2, max_battery_charge_a=160),
    "10 kW hybrid, 3-phase (1000 V, 2 MPPT)": Inverter(
        name="Generic 10 kW hybrid, 3-phase", ac_kw=10, phases=3, max_dc_v=1000, mppt_min_v=160,
        mppt_max_v=800, max_current_per_mppt_a=26, max_isc_per_mppt_a=34, max_strings_per_mppt=2,
        max_dc_kw=15, max_battery_charge_a=50, battery_v=400),
    "10 kW string, 3-phase (1100 V, 2 MPPT, no battery)": Inverter(
        name="Generic 10 kW string, 3-phase", ac_kw=10, phases=3, max_dc_v=1100, mppt_min_v=200,
        mppt_max_v=1000, max_current_per_mppt_a=26, max_isc_per_mppt_a=40, max_strings_per_mppt=2,
        max_dc_kw=15, hybrid=False, max_battery_charge_a=0),
}


@dataclass
class Site:
    project: str = "Untitled project"
    client: str = ""
    address: str = ""
    latitude: float = -26.3          # Mbabane ~ -26.3
    t_min_c: float = 0.0             # lowest expected ambient (string Voc check)
    t_cell_max_c: float = 70.0       # hot cell temperature (string Vmp check)
    grid_v_ll: float = 400.0
    grid_v_ln: float = 230.0


@dataclass
class DesignInput:
    module: Module = field(default_factory=Module)
    inverter: Inverter = field(default_factory=Inverter)
    site: Site = field(default_factory=Site)
    n_modules: int = 10
    battery_kwh: float = 0.0
    battery_modules: int = 0
    dc_run_m: float = 20.0          # array -> inverter, one way
    ac_run_m: float = 10.0          # inverter -> distribution board, one way
    battery_run_m: float = 2.0
    dc_drop_pct: float = 2.0
    ac_drop_pct: float = 3.0


def next_standard(value: float, table: list[float]) -> float | None:
    return next((s for s in table if s >= value - 1e-9), None)


def string_limits(m: Module, inv: Inverter, site: Site) -> dict:
    """Allowed modules per string from cold Voc and hot Vmp."""
    voc_cold = m.voc * (1 + (m.temp_coeff_voc_pct / 100) * (site.t_min_c - 25))
    vmp_hot = m.vmp * (1 + (m.temp_coeff_pmax_pct / 100) * (site.t_cell_max_c - 25))
    max_series = math.floor(inv.max_dc_v * 0.98 / voc_cold)          # 2% margin
    # also keep below MPPT window top at cold Vmp (approximate with cold Voc not required)
    min_series = math.ceil(inv.mppt_min_v * 1.05 / vmp_hot)          # 5% margin
    return {
        "voc_cold": round(voc_cold, 2),
        "vmp_hot": round(vmp_hot, 2),
        "min_series": min_series,
        "max_series": max_series,
        "max_series_by_mppt_window": math.floor(inv.mppt_max_v / m.vmp),
    }


def plan_strings(n_modules: int, m: Module, inv: Inverter, site: Site) -> dict:
    """Choose modules-per-string and distribute strings over the MPPT inputs.

    Prefers using every module. If that is impossible it uses the largest fitting
    count and reports the leftover modules.
    """
    lim = string_limits(m, inv, site)
    s_lo = lim["min_series"]
    s_hi = min(lim["max_series"], lim["max_series_by_mppt_window"] + 3)  # window top is a soft limit
    warnings: list[str] = []
    if s_lo > s_hi or s_hi < 1:
        return {"ok": False, "limits": lim, "mppt": [], "strings": [], "used": 0, "left": n_modules,
                "warnings": ["No valid string length for this module/inverter pair (check voltages)."]}

    best = None
    max_strings_total = inv.n_mppt * inv.max_strings_per_mppt
    isc_cap = int(inv.max_isc_per_mppt_a // m.isc) if m.isc > 0 else inv.max_strings_per_mppt
    per_mppt_cap = max(1, min(inv.max_strings_per_mppt, isc_cap))
    max_strings_total = inv.n_mppt * per_mppt_cap
    for s in range(s_hi, s_lo - 1, -1):
        k = min(n_modules // s, max_strings_total)
        if k < 1:
            continue
        used = s * k
        # score: most modules used, then more balanced strings, then longer strings
        score = (used, -abs(k - round(k / inv.n_mppt) * inv.n_mppt), s)
        if best is None or score > best[0]:
            best = (score, s, k)
    if best is None:
        return {"ok": False, "limits": lim, "mppt": [], "strings": [], "used": 0, "left": n_modules,
                "warnings": [f"Need at least {s_lo} modules for one string; only {n_modules} entered."]}
    _, s, k = best
    # distribute strings over MPPTs as evenly as possible
    base, extra = divmod(k, inv.n_mppt)
    per = [base + (1 if i < extra else 0) for i in range(inv.n_mppt)]
    mppt = []
    sid = 1
    for i, cnt in enumerate(per):
        ids = list(range(sid, sid + cnt))
        sid += cnt
        mppt.append({"mppt": i + 1, "strings": ids, "n": cnt})
    used = s * k
    left = n_modules - used
    if left:
        warnings.append(f"{left} module(s) cannot be connected with this inverter and are left unused.")
    if base == 0 or any(p == 0 for p in per[: min(k, inv.n_mppt)]):
        pass
    unbalanced = len({p for p in per if p}) > 1
    if unbalanced:
        warnings.append("MPPT inputs carry different numbers of strings. Check inverter derating limits.")
    return {
        "ok": True, "limits": lim, "modules_per_string": s, "n_strings": k, "mppt": mppt,
        "strings": [{"id": i + 1, "modules": s} for i in range(k)], "used": used, "left": left,
        "warnings": warnings,
    }


def design(inp: DesignInput) -> dict:
    m, inv, site = inp.module, inp.inverter, inp.site
    out: dict = {"input": inp, "warnings": [], "notes": []}
    sp = plan_strings(inp.n_modules, m, inv, site)
    out["strings"] = sp
    out["warnings"] += sp["warnings"]
    if not sp["ok"]:
        out["ok"] = False
        return out
    s = sp["modules_per_string"]
    k = sp["n_strings"]
    lim = sp["limits"]
    used = sp["used"]

    kwp = used * m.watts / 1000
    out["kwp"] = round(kwp, 2)
    out["dc_ac_ratio"] = round(kwp / inv.ac_kw, 2)
    if out["dc_ac_ratio"] > 1.5:
        out["warnings"].append(f"DC/AC ratio {out['dc_ac_ratio']} is high; expect clipping losses.")
    elif out["dc_ac_ratio"] < 0.9:
        out["warnings"].append(f"DC/AC ratio {out['dc_ac_ratio']} is low; the inverter is oversized for this array.")
    if kwp > inv.max_dc_kw:
        out["warnings"].append(f"Array {kwp:.2f} kWp exceeds the inverter's max DC input of {inv.max_dc_kw} kW.")

    voc_string = round(s * lim["voc_cold"], 1)
    vmp_string = round(s * m.vmp, 1)
    out["string"] = {
        "modules": s, "voc_cold_v": voc_string, "vmp_v": vmp_string, "vmp_hot_v": round(s * lim["vmp_hot"], 1),
        "isc_a": m.isc, "imp_a": m.imp,
        "voltage_margin_pct": round((inv.max_dc_v - voc_string) / inv.max_dc_v * 100, 1),
    }
    # per-MPPT checks
    mppt_rows = []
    for row in sp["mppt"]:
        n = row["n"]
        i_op = n * m.imp
        i_sc = n * m.isc
        ok_i = i_op <= inv.max_current_per_mppt_a and i_sc <= inv.max_isc_per_mppt_a
        if n and not ok_i:
            out["warnings"].append(
                f"MPPT {row['mppt']}: {n} string(s) give {i_op:.1f} A operating / {i_sc:.1f} A short-circuit, "
                f"above the inverter limits ({inv.max_current_per_mppt_a} / {inv.max_isc_per_mppt_a} A).")
        fuse = None
        if n >= 3:
            fuse = next_standard(1.56 * m.isc, STD_FUSES_A)
            if fuse and fuse > m.max_series_fuse_a:
                out["warnings"].append("Required string fuse exceeds the module's max series fuse rating.")
        isolator_a = next_standard(1.25 * i_sc, STD_DC_BREAKERS_A) if n else None
        mppt_rows.append({**row, "i_op_a": round(i_op, 1), "i_sc_a": round(i_sc, 1),
                          "fuse_a": fuse, "isolator_a": isolator_a, "ok": ok_i})
    out["mppt"] = mppt_rows
    if s < lim["min_series"] or s > lim["max_series"]:
        out["warnings"].append("String length is outside the allowed range.")
    if voc_string > inv.max_dc_v:
        out["warnings"].append("String Voc exceeds the inverter's maximum DC voltage!")

    # ---- cables
    i_string_design = 1.25 * m.isc
    dc = calc.size_cable(i_string_design, inp.dc_run_m, vmp_string, inp.dc_drop_pct, dc=True)
    area_vd = dc["chosen_mm2"] or 240
    area_amp = next((a for a, i in sorted(AMPACITY_CU.items()) if i >= i_string_design * 1.25), 120)
    dc_area = max(area_vd, area_amp, 4)
    out["cables"] = {
        "dc_string": {"mm2": dc_area, "type": "PV1-F / H1Z2Z2-K solar cable, double insulated, UV resistant",
                      "length_m_each": inp.dc_run_m, "design_current_a": round(i_string_design, 1),
                      "drop_pct": round(2 * calc.RHO_COPPER * inp.dc_run_m * i_string_design / dc_area / vmp_string * 100, 2)},
    }
    # AC side
    if inv.phases == 3:
        i_ac = inv.ac_kw * 1000 / (math.sqrt(3) * site.grid_v_ll)
        v_ac = site.grid_v_ll
    else:
        i_ac = inv.ac_kw * 1000 / site.grid_v_ln
        v_ac = site.grid_v_ln
    ac_cur = round(i_ac, 1)
    ac_breaker = next_standard(1.25 * i_ac, STD_BREAKERS_A)
    ac = calc.size_cable(max(i_ac, 0.1), inp.ac_run_m, v_ac, inp.ac_drop_pct,
                         phases=inv.phases, power_factor=1.0)
    ac_vd = ac["chosen_mm2"] or 240
    ac_amp = next((a for a, i in sorted(AMPACITY_CU.items()) if i >= (ac_breaker or i_ac)), 120)
    ac_area = max(ac_vd, ac_amp, 2.5)
    out["ac"] = {"current_a": ac_cur, "breaker_a": ac_breaker, "poles": 4 if inv.phases == 3 else 2,
                 "rcd_ma": 30, "voltage_v": v_ac}
    out["cables"]["ac"] = {"mm2": ac_area, "type": f"{'5' if inv.phases == 3 else '3'}-core Cu, SWA or in conduit",
                           "length_m": inp.ac_run_m, "design_current_a": ac_cur}
    if ac_breaker is None:
        out["warnings"].append("AC current is larger than the standard breaker table; engineer design required.")

    # Battery
    out["battery"] = None
    if inv.hybrid and inp.battery_kwh > 0:
        i_bat = inv.ac_kw * 1000 / (inv.battery_v * 0.92)
        i_bat = min(i_bat, inv.max_battery_charge_a) if inv.max_battery_charge_a else i_bat
        bat_breaker = next_standard(1.25 * i_bat, STD_DC_BREAKERS_A)
        bat_amp = next((a for a, i in sorted(AMPACITY_CU.items()) if i >= (bat_breaker or i_bat)), 120)
        bat = calc.size_cable(max(i_bat, 0.1), inp.battery_run_m, inv.battery_v, 1.0, dc=True)
        bat_area = max(bat["chosen_mm2"] or 240, bat_amp)
        out["battery"] = {"kwh": inp.battery_kwh, "voltage_v": inv.battery_v, "modules": inp.battery_modules,
                          "max_current_a": round(i_bat, 1), "breaker_a": bat_breaker, "cable_mm2": bat_area,
                          "cable_m": inp.battery_run_m}
        out["cables"]["battery"] = {"mm2": bat_area, "type": "Flexible Cu, battery cable",
                                    "length_m_each": inp.battery_run_m, "design_current_a": round(i_bat, 1)}
        if inv.battery_v >= 120:
            out["notes"].append("High-voltage battery: follow the manufacturer's installation manual and DC rules.")
    elif inv.hybrid:
        out["notes"].append("Hybrid inverter selected but no battery entered: drawn without battery.")

    # Earthing
    out["earthing"] = {"pv_bonding_mm2": 6, "pv_bonding_unprotected_mm2": 16,
                       "note": "6 mm2 Cu if mechanically protected, 16 mm2 if not. Bond all module frames and rails."}

    out["spd"] = {"dc_uc_v": 1000 if lim["voc_cold"] * s <= 800 else 1500, "dc_type": "Type 2",
                  "ac_type": "Type 2", "ac_uc_v": 275 if inv.phases == 1 else 275}
    out["bom"] = build_bom(inp, out)
    out["ok"] = True
    out["notes"] += [
        "String voltage uses cold-temperature Voc and hot-cell Vmp with 2% / 5% margins.",
        "Cable sizes combine a voltage-drop check with a conservative current rating. Verify installation "
        "method, grouping and ambient temperature against the cable maker's tables.",
        "Defaults for the module and inverter are generic. Replace them with datasheet values.",
    ]
    return out


def build_bom(inp: DesignInput, d: dict) -> list[dict]:
    m, inv = inp.module, inp.inverter
    k = d["strings"]["n_strings"]
    used = d["strings"]["used"]
    rows: list[dict] = []

    def add(cat, item, qty, unit="pcs", spec=""):
        rows.append({"category": cat, "item": item, "qty": qty, "unit": unit, "spec": spec})

    add("Generation", m.name, used, "pcs", f"{m.watts:.0f} W, Voc {m.voc} V, Isc {m.isc} A, {m.length_mm:.0f}x{m.width_mm:.0f} mm")
    add("Conversion", inv.name, 1, "pcs", f"{inv.ac_kw} kW, {inv.phases}-phase, {inv.n_mppt} MPPT")
    if d["battery"]:
        b = d["battery"]
        add("Storage", f"Battery bank {b['kwh']:.1f} kWh", max(b["modules"], 1), "pcs", f"{b['voltage_v']:.0f} V nominal LiFePO4")
        add("Protection", "Battery DC breaker / fuse", 1, "pcs", f"{b['breaker_a']} A DC")
    for r in d["mppt"]:
        if r["n"]:
            add("Protection", f"DC isolator, MPPT {r['mppt']}", 1, "pcs", f"{r['isolator_a']} A, >= {d['string']['voc_cold_v']:.0f} V DC")
            if r["fuse_a"]:
                add("Protection", f"String fuse gPV, MPPT {r['mppt']}", r["n"] * 2, "pcs", f"{r['fuse_a']} A, 1000 V DC (+/- poles)")
    add("Protection", "DC surge protection", 1, "set", f"Type 2, Uc >= {d['spd']['dc_uc_v']} V DC")
    add("Protection", "AC main breaker", 1, "pcs", f"{d['ac']['breaker_a']} A, {d['ac']['poles']}P")
    add("Protection", "RCD / RCBO", 1, "pcs", f"{d['ac']['rcd_ma']} mA (type per inverter manual)")
    add("Protection", "AC surge protection", 1, "set", "Type 2")
    add("Cabling", "Solar cable (DC strings)", round(k * 2 * inp.dc_run_m * 1.1), "m", f"{d['cables']['dc_string']['mm2']} mm2")
    add("Cabling", "AC cable inverter to DB", round(inp.ac_run_m * 1.1), "m", f"{d['cables']['ac']['mm2']} mm2")
    if d["battery"]:
        add("Cabling", "Battery cable", round(2 * inp.battery_run_m * 1.1, 1), "m", f"{d['battery']['cable_mm2']} mm2")
    add("Cabling", "MC4-type connector pairs", k * 2 + 2, "pairs", "Same make as the modules")
    add("Earthing", "Earth bonding cable", round(used * 1.2 + 10), "m", "6 mm2 Cu green/yellow (16 mm2 if unprotected)")
    add("Earthing", "Earth rod / bar and clamps", 1, "set", "")
    add("Other", "Labels, warning signs and as-built folder", 1, "set", "")
    return rows
