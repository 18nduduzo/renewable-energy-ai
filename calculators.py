"""Engineering calculators for the Solar & Electrical Design Assistant.

Pure functions (no Streamlit) so they can be unit-tested and reused.
All results are first-pass design estimates, not a substitute for a
site survey or a registered engineer's sign-off.
"""

from __future__ import annotations

import math

STANDARD_CABLE_MM2 = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240]
# Copper resistivity at ~70 C operating temperature (ohm * mm^2 / m)
RHO_COPPER = 0.0225
RHO_ALUMINIUM = 0.036


# ----------------------------------------------------------------- solar PV
def size_solar_system(
    daily_kwh: float,
    peak_sun_hours: float = 5.0,
    performance_ratio: float = 0.75,
    panel_watts: int = 550,
) -> dict:
    """Size the PV array for a given daily energy need."""
    if min(daily_kwh, peak_sun_hours, performance_ratio, panel_watts) <= 0:
        raise ValueError("All inputs must be greater than zero.")
    array_kwp = daily_kwh / (peak_sun_hours * performance_ratio)
    panels = math.ceil(array_kwp * 1000 / panel_watts)
    actual_kwp = panels * panel_watts / 1000
    return {
        "required_kwp": round(array_kwp, 2),
        "panels": panels,
        "installed_kwp": round(actual_kwp, 2),
        "daily_generation_kwh": round(actual_kwp * peak_sun_hours * performance_ratio, 1),
        "annual_generation_kwh": round(actual_kwp * peak_sun_hours * performance_ratio * 365),
    }


# ------------------------------------------------------------------ battery
BATTERY_CHEMISTRY = {
    # name: (usable depth of discharge, round-trip efficiency)
    "LiFePO4": (0.90, 0.95),
    "Lead-acid (AGM/Gel)": (0.50, 0.85),
}


def size_battery_bank(
    daily_kwh: float,
    backup_days: float,
    system_voltage: int = 48,
    chemistry: str = "LiFePO4",
) -> dict:
    """Size a battery bank for N days of autonomy."""
    if chemistry not in BATTERY_CHEMISTRY:
        raise ValueError(f"Unknown chemistry: {chemistry}")
    if min(daily_kwh, backup_days, system_voltage) <= 0:
        raise ValueError("All inputs must be greater than zero.")
    dod, eff = BATTERY_CHEMISTRY[chemistry]
    usable_needed = daily_kwh * backup_days
    nominal_kwh = usable_needed / (dod * eff)
    amp_hours = nominal_kwh * 1000 / system_voltage
    return {
        "usable_kwh_needed": round(usable_needed, 1),
        "nominal_kwh": round(nominal_kwh, 1),
        "amp_hours": round(amp_hours),
        "dod_used": dod,
        "efficiency_used": eff,
    }


# ----------------------------------------------------------------- inverter
def size_inverter(
    continuous_load_w: float,
    largest_motor_w: float = 0,
    motor_surge_factor: float = 3.0,
    safety_margin: float = 1.25,
) -> dict:
    """Inverter continuous and surge rating."""
    if continuous_load_w <= 0:
        raise ValueError("Continuous load must be greater than zero.")
    surge_w = continuous_load_w + largest_motor_w * (motor_surge_factor - 1)
    return {
        "recommended_continuous_w": math.ceil(continuous_load_w * safety_margin / 100) * 100,
        "required_surge_w": math.ceil(surge_w / 100) * 100,
    }


def size_mppt_controller(array_kwp: float, battery_voltage: int = 48, margin: float = 1.25) -> dict:
    """Rough charge current for an MPPT controller on the battery side."""
    amps = array_kwp * 1000 / battery_voltage * margin
    return {"min_charge_current_a": round(amps, 1)}


# -------------------------------------------------------------------- cable
def size_cable(
    current_a: float,
    length_m: float,
    voltage_v: float,
    max_drop_pct: float = 3.0,
    phases: int = 1,
    power_factor: float = 1.0,
    material: str = "Copper",
    dc: bool = False,
) -> dict:
    """Smallest standard cable size meeting a voltage-drop limit.

    Single-phase / DC : Vd = 2 * rho * L * I / A
    Three-phase       : Vd = sqrt(3) * rho * L * I * cos(phi) / A  (line-to-line)
    Resistance-only approximation; fine for small/medium cross-sections.
    Always verify current-carrying capacity (ampacity) separately.
    """
    if min(current_a, length_m, voltage_v, max_drop_pct) <= 0:
        raise ValueError("All inputs must be greater than zero.")
    rho = RHO_COPPER if material == "Copper" else RHO_ALUMINIUM
    allowed_drop_v = voltage_v * max_drop_pct / 100
    if dc or phases == 1:
        factor = 2.0
    else:
        factor = math.sqrt(3) * power_factor
    min_area = factor * rho * length_m * current_a / allowed_drop_v
    chosen = next((s for s in STANDARD_CABLE_MM2 if s >= min_area), None)
    result = {
        "min_area_mm2": round(min_area, 2),
        "chosen_mm2": chosen,
        "allowed_drop_v": round(allowed_drop_v, 2),
    }
    if chosen:
        actual_drop = factor * rho * length_m * current_a / chosen
        result["actual_drop_v"] = round(actual_drop, 2)
        result["actual_drop_pct"] = round(actual_drop / voltage_v * 100, 2)
    return result


# ------------------------------------------------------------ power factor
def power_factor_correction(
    real_power_kw: float,
    pf_existing: float,
    pf_target: float = 0.95,
    voltage_v: float = 400,
    phases: int = 3,
) -> dict:
    """Capacitor bank size to lift power factor: Qc = P (tan phi1 - tan phi2)."""
    if not (0 < pf_existing < 1) or not (0 < pf_target <= 1):
        raise ValueError("Power factors must be between 0 and 1.")
    if pf_target <= pf_existing:
        raise ValueError("Target power factor must be higher than the existing one.")
    q_kvar = real_power_kw * (math.tan(math.acos(pf_existing)) - math.tan(math.acos(pf_target)))
    kva_before = real_power_kw / pf_existing
    kva_after = real_power_kw / pf_target
    k = math.sqrt(3) if phases == 3 else 1
    return {
        "capacitor_kvar": round(q_kvar, 1),
        "kva_before": round(kva_before, 1),
        "kva_after": round(kva_after, 1),
        "current_before_a": round(kva_before * 1000 / (k * voltage_v), 1),
        "current_after_a": round(kva_after * 1000 / (k * voltage_v), 1),
    }


# ---------------------------------------------------------------------- ROI
def solar_roi(
    system_cost: float,
    annual_generation_kwh: float,
    tariff_per_kwh: float,
    tariff_escalation_pct: float = 8.0,
    degradation_pct: float = 0.5,
    years: int = 25,
    annual_om_cost: float = 0.0,
) -> dict:
    """Simple payback and cumulative savings (no discounting)."""
    if min(system_cost, annual_generation_kwh, tariff_per_kwh) <= 0:
        raise ValueError("Cost, generation and tariff must be greater than zero.")
    cumulative = -system_cost
    payback_year = None
    rows = []
    for y in range(1, years + 1):
        gen = annual_generation_kwh * (1 - degradation_pct / 100) ** (y - 1)
        tariff = tariff_per_kwh * (1 + tariff_escalation_pct / 100) ** (y - 1)
        saving = gen * tariff - annual_om_cost
        prev = cumulative
        cumulative += saving
        if payback_year is None and cumulative >= 0:
            payback_year = round(y - 1 + (-prev / saving), 1) if saving else y
        rows.append({"year": y, "saving": round(saving), "cumulative": round(cumulative)})
    return {
        "payback_years": payback_year,
        "net_gain_over_period": round(cumulative),
        "year1_saving": rows[0]["saving"],
        "table": rows,
    }
