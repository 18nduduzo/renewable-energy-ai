import os

import streamlit as st
from groq import Groq

import calculators as calc

st.set_page_config(page_title="Solar & Electrical Design AI", page_icon="⚡", layout="wide")

# --------------------------------------------------------------------------
# Config (works with Hugging Face "Secrets" or plain environment variables)
# --------------------------------------------------------------------------
def get_secret(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


API_KEY = get_secret("GROQ_API_KEY")
# Groq retires models regularly. Change MODEL in Secrets, no code edit needed.
MODEL = get_secret("MODEL", "openai/gpt-oss-120b")
FALLBACK_MODEL = get_secret("FALLBACK_MODEL", "openai/gpt-oss-20b")
APP_PASSWORD = get_secret("APP_PASSWORD")  # optional: protects your API quota

SYSTEM_PROMPT = """You are a senior electrical engineer and renewable energy consultant
supporting installers, technicians and students in Eswatini and Southern Africa.

Expertise: solar PV, battery storage (LiFePO4 and lead-acid), hybrid/off-grid/grid-tied
inverters, MPPT charge controllers, power electronics (including GaN and SiC devices),
transformers, motors, power factor correction, protection and earthing, grid systems,
industrial automation.

How to answer:
- Show the formula, the numbers substituted in, and the result. State every assumption.
- Use SI units. Local context: 230 V single-phase / 400 V three-phase, 50 Hz.
  Currency is the lilangeni (SZL, pegged to the South African rand).
  Mbabane/Manzini get roughly 4.5-5.5 peak sun hours depending on season; say when you are estimating.
- Reference standards where relevant (IEC 62109, IEC 61215, IEC 60364, SANS 10142-1) and
  remind the user to confirm local utility (EEC) and regulatory requirements.
- Prefer clear steps and small tables. Be concise, practical and honest about uncertainty.
- For anything involving mains voltage, DC arrays or batteries, include the key safety points
  (isolation, DC-rated protection, correct fusing, qualified person sign-off).
- If key inputs are missing, ask for them or state sensible defaults.
- Never invent datasheet values, prices or standard clauses; say when you are unsure."""


# --------------------------------------------------------------------------
# Optional password gate
# --------------------------------------------------------------------------
if APP_PASSWORD and not st.session_state.get("authed"):
    st.title("⚡ Solar & Electrical Design AI")
    pw = st.text_input("Password", type="password")
    if pw:
        if pw == APP_PASSWORD:
            st.session_state.authed = True
            st.rerun()
        else:
            st.error("Wrong password.")
    st.stop()

if not API_KEY:
    st.error("GROQ_API_KEY is not set. Add it under Settings → Secrets (Hugging Face) or as an environment variable.")
    st.stop()

client = Groq(api_key=API_KEY)


# --------------------------------------------------------------------------
# Chat helpers
# --------------------------------------------------------------------------
def stream_answer(history):
    """Yield text chunks; fall back to a second model if the first fails."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history[-12:]
    last_error = None
    for model in (MODEL, FALLBACK_MODEL):
        try:
            stream = client.chat.completions.create(
                model=model, messages=messages, temperature=0.3, stream=True
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            return
        except Exception as e:  # rate limit, retired model, network
            last_error = e
    yield f"\n\n⚠️ The AI service returned an error: `{last_error}`"


def queue_prompt(text: str):
    """Callback: send a calculator result to the chat tab for review."""
    st.session_state.pending_prompt = text


if "messages" not in st.session_state:
    st.session_state.messages = []

# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("⚡ Solar & Electrical AI")
    st.caption(f"Model: `{MODEL}`")
    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()
    st.markdown("---")
    st.caption(
        "Results are first-pass design estimates. Verify against manufacturer "
        "datasheets, local codes and have a qualified person sign off installations."
    )

st.title("⚡ Solar & Electrical Design AI")
st.caption("For installers, consultants and students in Eswatini & Southern Africa")

tab_chat, tab_solar, tab_batt, tab_cable, tab_pf, tab_roi = st.tabs(
    ["💬 Ask the AI", "☀️ Solar + Inverter", "🔋 Battery", "🔌 Cable", "📉 Power Factor", "💰 ROI"]
)

# ------------------------------------------------------------------ chat tab
with tab_chat:
    if not st.session_state.messages:
        st.write("Try one of these:")
        examples = [
            "How do I size a solar system for 20 kWh/day with 2 days of backup?",
            "Explain MPPT and how it differs from PWM.",
            "Why use GaN transistors in a solar micro-inverter?",
            "How do I choose between a 24 V and 48 V battery bank?",
        ]
        cols = st.columns(2)
        for i, ex in enumerate(examples):
            cols[i % 2].button(ex, key=f"ex{i}", on_click=queue_prompt, args=(ex,))

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    typed = st.chat_input("Ask about solar, batteries, inverters, cables, transformers...")
    prompt = st.session_state.pop("pending_prompt", None) or typed
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            answer = st.write_stream(stream_answer(st.session_state.messages))
        st.session_state.messages.append({"role": "assistant", "content": answer})

# ----------------------------------------------------------- solar + inverter
with tab_solar:
    c1, c2 = st.columns(2)
    with c1:
        daily = st.number_input("Daily energy use (kWh)", 0.1, 1000.0, 20.0, 0.5, key="s_daily")
        psh = st.number_input("Peak sun hours", 1.0, 8.0, 5.0, 0.1, key="s_psh",
                              help="Roughly 4.5-5.5 for Eswatini; use the winter value for off-grid.")
        pr = st.slider("System performance ratio", 0.60, 0.90, 0.75, 0.01, key="s_pr",
                       help="Covers temperature, cable, inverter and soiling losses.")
        pw_panel = st.selectbox("Panel size (W)", [400, 450, 550, 600, 700], index=2, key="s_panel")
    with c2:
        load_w = st.number_input("Peak continuous load (W)", 100, 500000, 5000, 100, key="i_load")
        motor_w = st.number_input("Largest motor / compressor (W)", 0, 100000, 0, 100, key="i_motor")
        vbat = st.selectbox("Battery voltage (V)", [12, 24, 48, 96], index=2, key="i_vbat")

    try:
        pv = calc.size_solar_system(daily, psh, pr, pw_panel)
        inv = calc.size_inverter(load_w, motor_w)
        mppt = calc.size_mppt_controller(pv["installed_kwp"], vbat)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Array required", f"{pv['required_kwp']} kWp")
        m2.metric("Panels", f"{pv['panels']} × {pw_panel} W")
        m3.metric("Inverter", f"{inv['recommended_continuous_w'] / 1000:.1f} kW")
        m4.metric("Inverter surge", f"{inv['required_surge_w'] / 1000:.1f} kW")
        st.write(
            f"Installed **{pv['installed_kwp']} kWp** → about **{pv['daily_generation_kwh']} kWh/day** "
            f"and **{pv['annual_generation_kwh']:,} kWh/year**. "
            f"MPPT controller (battery side) needs at least **{mppt['min_charge_current_a']} A** at {vbat} V."
        )
        summary = (
            f"Please review this solar design: {daily} kWh/day, {psh} peak sun hours, PR {pr}. "
            f"Array {pv['installed_kwp']} kWp ({pv['panels']} x {pw_panel} W). "
            f"Peak load {load_w} W, largest motor {motor_w} W, inverter {inv['recommended_continuous_w']} W "
            f"with {inv['required_surge_w']} W surge, {vbat} V battery, MPPT {mppt['min_charge_current_a']} A. "
            "Point out risks, missing items (string configuration, DC protection, earthing) and improvements."
        )
        st.button("Ask the AI to review this design", on_click=queue_prompt, args=(summary,), key="rev_solar")
        st.caption("Then switch to the 💬 Ask the AI tab to read the review.")
    except ValueError as e:
        st.warning(str(e))

# --------------------------------------------------------------------- battery
with tab_batt:
    c1, c2 = st.columns(2)
    with c1:
        b_daily = st.number_input("Daily energy use (kWh)", 0.1, 1000.0, 20.0, 0.5, key="b_daily")
        days = st.number_input("Backup days (autonomy)", 0.1, 10.0, 2.0, 0.5, key="b_days")
    with c2:
        b_v = st.selectbox("System voltage (V)", [12, 24, 48, 96], index=2, key="b_v")
        chem = st.selectbox("Chemistry", list(calc.BATTERY_CHEMISTRY), key="b_chem")
    try:
        b = calc.size_battery_bank(b_daily, days, b_v, chem)
        m1, m2, m3 = st.columns(3)
        m1.metric("Nominal capacity", f"{b['nominal_kwh']} kWh")
        m2.metric(f"Capacity at {b_v} V", f"{b['amp_hours']:,} Ah")
        m3.metric("Usable energy", f"{b['usable_kwh_needed']} kWh")
        st.caption(
            f"Assumes {int(b['dod_used'] * 100)}% usable depth of discharge and "
            f"{int(b['efficiency_used'] * 100)}% round-trip efficiency. "
            "Check the battery's maximum continuous discharge current against your inverter."
        )
    except ValueError as e:
        st.warning(str(e))

# ----------------------------------------------------------------------- cable
with tab_cable:
    c1, c2 = st.columns(2)
    with c1:
        kind = st.radio("Circuit type", ["DC", "AC single-phase", "AC three-phase"], horizontal=True)
        amps = st.number_input("Current (A)", 0.1, 2000.0, 40.0, 1.0, key="c_i")
        length = st.number_input("One-way length (m)", 0.5, 1000.0, 15.0, 0.5, key="c_l")
    with c2:
        default_v = {"DC": 48.0, "AC single-phase": 230.0, "AC three-phase": 400.0}[kind]
        volts = st.number_input("System voltage (V)", 1.0, 1500.0, default_v, 1.0, key=f"c_v_{kind}")
        drop = st.slider("Max voltage drop (%)", 0.5, 5.0, 3.0, 0.5, key="c_d")
        mat = st.radio("Conductor", ["Copper", "Aluminium"], horizontal=True)
        pf = st.slider("Power factor (3-phase)", 0.5, 1.0, 0.9, 0.01, key="c_pf") if kind == "AC three-phase" else 1.0
    try:
        r = calc.size_cable(
            amps, length, volts, drop,
            phases=3 if kind == "AC three-phase" else 1, power_factor=pf, material=mat, dc=(kind == "DC"),
        )
        if r["chosen_mm2"]:
            m1, m2, m3 = st.columns(3)
            m1.metric("Minimum area", f"{r['min_area_mm2']} mm²")
            m2.metric("Select", f"{r['chosen_mm2']} mm²")
            m3.metric("Actual drop", f"{r['actual_drop_pct']} %", f"{r['actual_drop_v']} V", delta_color="off")
        else:
            st.error("Needs more than 240 mm². Use parallel runs or raise the system voltage.")
        st.warning(
            "This only checks **voltage drop**. Also verify the cable's current rating for your "
            "installation method and ambient temperature, plus short-circuit withstand and protection."
        )
    except ValueError as e:
        st.warning(str(e))

# ---------------------------------------------------------------- power factor
with tab_pf:
    c1, c2 = st.columns(2)
    with c1:
        p_kw = st.number_input("Real power (kW)", 1.0, 10000.0, 100.0, 1.0, key="p_kw")
        pf1 = st.slider("Existing power factor", 0.30, 0.99, 0.75, 0.01, key="pf1")
    with c2:
        pf2 = st.slider("Target power factor", 0.80, 1.00, 0.95, 0.01, key="pf2")
        p_v = st.number_input("Voltage (V, line-to-line)", 100.0, 11000.0, 400.0, 10.0, key="p_v")
    try:
        p = calc.power_factor_correction(p_kw, pf1, pf2, p_v)
        m1, m2, m3 = st.columns(3)
        m1.metric("Capacitor bank", f"{p['capacitor_kvar']} kVAr")
        m2.metric("Apparent power", f"{p['kva_after']} kVA", f"{p['kva_after'] - p['kva_before']:.1f} kVA", delta_color="off")
        m3.metric("Line current", f"{p['current_after_a']} A", f"{p['current_after_a'] - p['current_before_a']:.1f} A", delta_color="off")
        st.caption("Use detuned reactors if the site has significant harmonics (VFDs, inverters, rectifiers).")
    except ValueError as e:
        st.warning(str(e))

# ------------------------------------------------------------------------- ROI
with tab_roi:
    c1, c2 = st.columns(2)
    with c1:
        cost = st.number_input("System cost (SZL)", 1000.0, 1e8, 250000.0, 1000.0, key="r_cost")
        gen = st.number_input("Annual generation (kWh)", 100.0, 1e7, 9000.0, 100.0, key="r_gen",
                              help="Copy from the Solar tab (kWh/year).")
        tariff = st.number_input("Electricity tariff (SZL/kWh)", 0.1, 50.0, 2.50, 0.05, key="r_tar",
                                 help="Replace with your actual current tariff from your bill.")
    with c2:
        esc = st.slider("Tariff escalation (%/year)", 0.0, 15.0, 8.0, 0.5, key="r_esc")
        deg = st.slider("Panel degradation (%/year)", 0.0, 1.5, 0.5, 0.1, key="r_deg")
        om = st.number_input("Annual O&M (SZL)", 0.0, 1e6, 2000.0, 500.0, key="r_om")
    try:
        roi = calc.solar_roi(cost, gen, tariff, esc, deg, annual_om_cost=om)
        m1, m2, m3 = st.columns(3)
        m1.metric("Simple payback", f"{roi['payback_years']} yrs" if roi["payback_years"] else "> 25 yrs")
        m2.metric("Year-1 saving", f"SZL {roi['year1_saving']:,}")
        m3.metric("25-year net gain", f"SZL {roi['net_gain_over_period']:,}")
        st.line_chart({"Cumulative position (SZL)": [r["cumulative"] for r in roi["table"]]})
        st.caption("Undiscounted. Excludes battery/inverter replacement, financing and net-metering rules.")
    except ValueError as e:
        st.warning(str(e))
