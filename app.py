import os

import streamlit as st

import calculators as calc
import drawings_ui
from chatstore import MemoryStore, SqliteStore
from mathfmt import normalize_math
from providers import ChatStream, enabled_providers, trim_history

st.set_page_config(page_title="Solar & Electrical Design AI", page_icon="⚡", layout="wide")

# --------------------------------------------------------------------------
# Config (works with Streamlit/Hugging Face "Secrets" or plain environment variables)
# --------------------------------------------------------------------------
def get_secret(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


APP_PASSWORD = get_secret("APP_PASSWORD")  # optional: protects your API quota

# Saving chats to disk is OFF by default. On free hosts the disk is temporary and
# NOT private per visitor. Turn it on (PERSIST_CHATS=true) only when running on your
# own computer/server, or after you have added user login.
PERSIST_CHATS = get_secret("PERSIST_CHATS", "").strip().lower() in ("1", "true", "yes")
CHAT_DB_PATH = get_secret("CHAT_DB_PATH", "chats.db")
OWNER = "local"  # replace with the signed-in user's id once you add login

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

Maths formatting (the app renders KaTeX; follow this exactly):
- Inline maths: wrap in single dollar signs, e.g. $I_{dc} = P/V$.
- Standalone equations: put on their own line wrapped in double dollar signs, e.g.
  $$P_{cond} = I_{rms}^{2}\\,R_{ds(on)}$$
- NEVER use [ ... ], ( ... ), \\[ ... \\] or \\( ... \\) to wrap maths.
- Write units with \\text{}, with a thin space before them: $5\\,\\text{kW}$, $0.95\\,\\text{A}$,
  $350\\,\\text{V}$, $30\\,\\text{m}\\Omega$. Use \\times, \\approx, \\frac{a}{b}, \\sqrt{x}, \\cdot.
- Use subscripts for symbols ($V_{oc}$, $I_{sc}$, $R_{ds(on)}$), never plain "Voc".
- Put numbers into the formula on one line, then give the result on the next line.
- In tables, wrap each maths cell in $...$. Do not use a literal $ for currency; write "SZL".
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

PROVIDERS = enabled_providers(get_secret)
if not PROVIDERS:
    st.error(
        "No AI key is set. Add at least one secret: GROQ_API_KEY (free), GEMINI_API_KEY (free tier), "
        "XAI_API_KEY or OPENAI_API_KEY (paid). Use .streamlit/secrets.toml locally, or your host's Secrets page."
    )
    st.stop()

# --------------------------------------------------------------------------
# Chat storage
# --------------------------------------------------------------------------
if PERSIST_CHATS:

    @st.cache_resource
    def _sqlite_store(path: str) -> SqliteStore:
        return SqliteStore(path)

    store = _sqlite_store(CHAT_DB_PATH)
else:
    store = MemoryStore(st.session_state.setdefault("_chat_data", {}))

st.session_state.setdefault("chat_id", None)
CONTINUE_PROMPT = "Please continue exactly where you stopped. Do not repeat what you already wrote."
CHAT_PAGE = "💬 Chat"
CALC_PAGE = "🧮 Calculators"
DRAW_PAGE = "📐 Drawings"


def queue_prompt(text: str):
    """Callback: send text (example question, design review) to the chat."""
    st.session_state.pending_prompt = text
    st.session_state.page = CHAT_PAGE


def queue_action(name: str):
    st.session_state.pending_action = name


def open_chat(cid: str):
    st.session_state.chat_id = cid
    st.session_state.page = CHAT_PAGE


def new_chat():
    st.session_state.chat_id = None
    st.session_state.page = CHAT_PAGE


def delete_chat(cid: str):
    store.delete_chat(cid, OWNER)
    if st.session_state.get("chat_id") == cid:
        st.session_state.chat_id = None


def make_title(text: str) -> str:
    line = " ".join(text.strip().split())
    return line if len(line) <= 40 else line[:39] + "…"


def export_markdown(chat_id: str) -> str:
    parts = []
    for m in store.get_messages(chat_id, OWNER):
        who = "You" if m["role"] == "user" else "Assistant"
        parts.append(f"### {who}\n\n{m['content']}\n")
    return "\n".join(parts)


# --------------------------------------------------------------------------
# Sidebar (top part: provider choice)
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("⚡ Solar & Electrical AI")
    labels = {p.key: p.label for p in PROVIDERS}
    provider_key = st.selectbox("AI provider", list(labels), format_func=lambda k: labels[k], key="provider_key")
    selected = next(p for p in PROVIDERS if p.key == provider_key)
    st.caption(f"Model: `{selected.models[0]}`")
    st.caption(selected.spec.note)
    if len(PROVIDERS) > 1:
        st.caption("If this provider fails or hits its limit, the others are tried automatically.")

st.title("⚡ Solar & Electrical Design AI")
st.caption("For installers, consultants and students in Eswatini & Southern Africa")

page = st.radio(
    "View", [CHAT_PAGE, CALC_PAGE, DRAW_PAGE], horizontal=True, label_visibility="collapsed", key="page"
)
if page != DRAW_PAGE:
    drawings_ui.keep_state()  # keep drawing inputs while the user visits other views

# ------------------------------------------------------------------ chat tab
if page == CHAT_PAGE:  # page level (not in a tab) so the input stays pinned to the bottom
    chat_id = st.session_state.chat_id
    action = st.session_state.pop("pending_action", None)
    prompt = st.session_state.pop("pending_prompt", None)

    if action == "regen" and chat_id:
        msgs = store.get_messages(chat_id, OWNER)
        if msgs and msgs[-1]["role"] == "assistant":
            store.pop_last_message(chat_id, OWNER)
    elif action == "continue" and chat_id:
        prompt = CONTINUE_PROMPT

    history = store.get_messages(chat_id, OWNER) if chat_id else []
    regenerate = action == "regen" and bool(history) and history[-1]["role"] == "user"

    if not history and not prompt:
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

    for m in history:
        with st.chat_message(m["role"]):
            st.markdown(normalize_math(m["content"]))
            if m["role"] == "assistant" and m.get("meta"):
                st.caption(m["meta"])

    typed = st.chat_input("Ask about solar, batteries, inverters, cables, transformers...")
    prompt = prompt or typed

    if prompt or regenerate:
        if chat_id is None:
            chat_id = store.create_chat(OWNER, make_title(prompt))
            st.session_state.chat_id = chat_id
        if prompt:
            store.add_message(chat_id, OWNER, "user", prompt)
            with st.chat_message("user"):
                st.markdown(prompt)

        convo = store.get_messages(chat_id, OWNER)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + trim_history(convo)
        stream = ChatStream(PROVIDERS, provider_key, messages)

        with st.chat_message("assistant"):
            box = st.empty()
            answer = ""
            for piece in stream:
                answer += piece
                box.markdown(normalize_math(answer) + " ▌")
            if answer:
                box.markdown(normalize_math(answer))
                meta = f"Answered by {stream.used_provider} · {stream.used_model}"
                st.caption(meta)
                store.add_message(chat_id, OWNER, "assistant", answer, meta)
            else:
                box.empty()
            if stream.error_text:
                msg = f"⚠️ {stream.error_text}"
                (st.warning if answer else st.error)(msg)
        st.session_state[f"cut_{chat_id}"] = bool(answer) and stream.finish_reason == "length"

    # Action buttons under the latest message (like ChatGPT's regenerate / continue)
    if chat_id:
        final = store.get_messages(chat_id, OWNER)
        if final:
            b1, b2, b3, _ = st.columns([1, 1, 1, 3])
            if final[-1]["role"] == "assistant":
                b1.button("🔄 Regenerate", key="regen_btn", on_click=queue_action, args=("regen",))
                if st.session_state.get(f"cut_{chat_id}"):
                    b2.button("➡️ Continue", key="cont_btn", on_click=queue_action, args=("continue",))
            else:
                b1.button("🔄 Try again", key="retry_btn", on_click=queue_action, args=("regen",))
            b3.download_button(
                "⬇️ Export", export_markdown(chat_id), file_name="chat.md", mime="text/markdown", key="export_btn"
            )

# --------------------------------------------------------------------------
# Sidebar (chat list). Rendered after the chat runs so new chats appear at once.
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("---")
    st.button("➕ New chat", on_click=new_chat)
    st.markdown("**Your chats**")
    chats = store.list_chats(OWNER)
    if not chats:
        st.caption("No chats yet.")
    for c in chats:
        col_a, col_b = st.columns([5, 1])
        mark = "▶ " if c["id"] == st.session_state.chat_id else ""
        col_a.button(mark + (c["title"] or "New chat"), key=f"open_{c['id']}", on_click=open_chat, args=(c["id"],))
        col_b.button("🗑", key=f"del_{c['id']}", on_click=delete_chat, args=(c["id"],))
    st.caption(
        "Chats are saved on this server." if PERSIST_CHATS else "Chats last until you refresh or close this tab."
    )
    st.markdown("---")
    st.caption(
        "Results are first-pass design estimates. Verify against manufacturer "
        "datasheets, local codes and have a qualified person sign off installations."
    )

if page == CALC_PAGE:
    tab_solar, tab_batt, tab_cable, tab_pf, tab_roi = st.tabs(
        ["☀️ Solar + Inverter", "🔋 Battery", "🔌 Cable", "📉 Power Factor", "💰 ROI"]
    )

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
            st.caption("This sends the design to the AI and opens the chat.")
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

if page == DRAW_PAGE:
    drawings_ui.render(get_secret)
