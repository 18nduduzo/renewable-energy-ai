"""Streamlit screen for the paid drawing pack.

Everyone sees the numbers and watermarked previews. The clean vector PDFs are only handed
to the browser after a valid unlock code (see paywall.py).
"""

from __future__ import annotations

import base64
import re
from dataclasses import replace

import streamlit as st

import design as D
import drawings as DR
import layout as L
import paywall as PW

MODULE_PRESETS = {
    "Generic 450 W (1.91 x 1.13 m)": D.Module(
        name="Generic 450 W mono", watts=450, voc=41.5, vmp=34.6, isc=13.9, imp=13.0,
        length_mm=1910, width_mm=1134, thickness_mm=30, weight_kg=23.5),
    "Generic 550 W (2.28 x 1.13 m)": D.Module(),
    "Generic 600 W (2.38 x 1.13 m)": D.Module(
        name="Generic 600 W mono", watts=600, voc=52.9, vmp=44.0, isc=14.5, imp=13.65,
        length_mm=2384, width_mm=1134, thickness_mm=35, weight_kg=32),
}
FACING = {"North (0)": 0, "North-East (45)": 45, "East (90)": 90, "South-East (135)": 135,
          "South (180)": 180, "South-West (225)": 225, "West (270)": 270, "North-West (315)": 315}
SHEET_LABELS = {
    "cover": "Cover sheet", "sld": "Single line diagram", "layout": "Array layout",
    "mount": "Mounting detail", "bom": "BOM and schedules",
}


def keep_state():
    """Streamlit forgets widget values for widgets that are not drawn. Call this on the other
    pages so the Drawings inputs survive switching between Chat / Calculators / Drawings."""
    for k in list(st.session_state.keys()):
        if isinstance(k, str) and k.startswith("dw_"):
            st.session_state[k] = st.session_state[k]


def _num(label, key, value, lo, hi, step, help=None, fmt=None):
    return st.number_input(label, min_value=lo, max_value=hi, value=value, step=step, key=key, help=help, format=fmt)


def _svg_html(svg: str) -> str:
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return (f'<img src="data:image/svg+xml;base64,{b64}" '
            'style="width:100%;border:1px solid #8884;border-radius:6px;background:#fff" alt="drawing preview"/>')


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", s or "project").strip("-")[:40] or "project"


def _module_inputs() -> D.Module:
    names = list(MODULE_PRESETS) + ["Custom (enter datasheet values)"]
    pick = st.selectbox("Solar module", names, key="dw_mod_pick")
    base = MODULE_PRESETS.get(pick, replace(D.Module(), name="Custom module"))
    with st.expander("Module datasheet values", expanded=pick.startswith("Custom")):
        st.caption("Presets are generic placeholders. Enter the datasheet values of the real module.")
        k = pick[:12]
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Name", base.name, key=f"dw_mn_{k}")
        watts = c2.number_input("Power Pmax (W)", 100.0, 800.0, float(base.watts), 5.0, key=f"dw_mw_{k}")
        voc = c3.number_input("Voc (V)", 10.0, 100.0, float(base.voc), 0.1, key=f"dw_mvoc_{k}")
        vmp = c1.number_input("Vmp (V)", 10.0, 100.0, float(base.vmp), 0.1, key=f"dw_mvmp_{k}")
        isc = c2.number_input("Isc (A)", 1.0, 30.0, float(base.isc), 0.1, key=f"dw_misc_{k}")
        imp = c3.number_input("Imp (A)", 1.0, 30.0, float(base.imp), 0.1, key=f"dw_mimp_{k}")
        ln = c1.number_input("Length (mm)", 800.0, 3000.0, float(base.length_mm), 1.0, key=f"dw_ml_{k}")
        wd = c2.number_input("Width (mm)", 500.0, 1800.0, float(base.width_mm), 1.0, key=f"dw_mwd_{k}")
        th = c3.number_input("Frame depth (mm)", 20.0, 60.0, float(base.thickness_mm), 1.0, key=f"dw_mt_{k}")
        tc = c1.number_input("Voc temp. coeff (%/C)", -0.6, -0.1, float(base.temp_coeff_voc_pct), 0.01, key=f"dw_mtc_{k}")
        tp = c2.number_input("Pmax temp. coeff (%/C)", -0.6, -0.1, float(base.temp_coeff_pmax_pct), 0.01, key=f"dw_mtp_{k}")
        fz = c3.number_input("Max series fuse (A)", 10.0, 40.0, float(base.max_series_fuse_a), 1.0, key=f"dw_mf_{k}")
    return D.Module(name=name, watts=watts, voc=voc, vmp=vmp, isc=isc, imp=imp, temp_coeff_voc_pct=tc,
                    temp_coeff_pmax_pct=tp, length_mm=ln, width_mm=wd, thickness_mm=th, weight_kg=base.weight_kg,
                    max_series_fuse_a=fz)


def _inverter_inputs() -> D.Inverter:
    pick = st.selectbox("Inverter", list(D.INVERTER_PRESETS), key="dw_inv_pick")
    base = D.INVERTER_PRESETS[pick]
    with st.expander("Inverter datasheet values"):
        st.caption("Presets are generic placeholders. Enter the datasheet values of the real inverter.")
        k = pick[:10]
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Name", base.name, key=f"dw_in_{k}")
        kw = c2.number_input("AC power (kW)", 1.0, 100.0, float(base.ac_kw), 0.5, key=f"dw_ikw_{k}")
        ph = c3.selectbox("Phases", [1, 3], index=0 if base.phases == 1 else 1, key=f"dw_iph_{k}")
        mdc = c1.number_input("Max DC voltage (V)", 100.0, 1500.0, float(base.max_dc_v), 10.0, key=f"dw_imdc_{k}")
        mlo = c2.number_input("MPPT min (V)", 50.0, 600.0, float(base.mppt_min_v), 5.0, key=f"dw_imlo_{k}")
        mhi = c3.number_input("MPPT max (V)", 100.0, 1500.0, float(base.mppt_max_v), 5.0, key=f"dw_imhi_{k}")
        nm = c1.number_input("MPPT inputs", 1, 6, int(base.n_mppt), 1, key=f"dw_inm_{k}")
        ims = c2.number_input("Max strings per MPPT", 1, 6, int(base.max_strings_per_mppt), 1, key=f"dw_ims_{k}")
        imi = c3.number_input("Max input current per MPPT (A)", 5.0, 60.0, float(base.max_current_per_mppt_a), 1.0, key=f"dw_imi_{k}")
        isc = c1.number_input("Max Isc per MPPT (A)", 5.0, 80.0, float(base.max_isc_per_mppt_a), 1.0, key=f"dw_iis_{k}")
        mdk = c2.number_input("Max DC array power (kW)", 1.0, 150.0, float(base.max_dc_kw), 0.5, key=f"dw_imk_{k}")
        hyb = c3.checkbox("Hybrid (battery port)", base.hybrid, key=f"dw_ihy_{k}")
        bv = c1.number_input("Battery voltage (V)", 12.0, 800.0, float(base.battery_v), 0.4, key=f"dw_ibv_{k}")
        bc = c2.number_input("Max battery current (A)", 0.0, 400.0, float(base.max_battery_charge_a), 5.0, key=f"dw_ibc_{k}")
    return D.Inverter(name=name, ac_kw=kw, phases=int(ph), max_dc_v=mdc, mppt_min_v=mlo, mppt_max_v=mhi,
                      n_mppt=int(nm), max_current_per_mppt_a=imi, max_isc_per_mppt_a=isc,
                      max_strings_per_mppt=int(ims), max_dc_kw=mdk, hybrid=hyb, battery_v=bv, max_battery_charge_a=bc)


def render(get_secret):
    st.subheader("📐 Drawings: single line diagram, array layout and mounting")
    st.caption("Enter the project. Numbers and watermarked previews are free. "
               "The clean PDF drawings are unlocked with a code.")

    # ------------------------------------------------------------ project
    with st.expander("1. Project details", expanded=True):
        c1, c2 = st.columns(2)
        project = c1.text_input("Project name", "Residential solar system", key="dw_project")
        client = c2.text_input("Client", "", key="dw_client")
        address = c1.text_input("Site address", "", key="dw_address")
        drawn_by = c2.text_input("Drawn by", "", key="dw_drawn")
        company = c1.text_input("Company (title block)", "", key="dw_company")
        revision = c2.text_input("Revision", "A", key="dw_rev")

    # ---------------------------------------------------------- equipment
    with st.expander("2. Equipment and system", expanded=True):
        module = _module_inputs()
        inverter = _inverter_inputs()
        c1, c2, c3 = st.columns(3)
        n_modules = int(c1.number_input("Number of modules", 1, 500, 10, 1, key="dw_nmod"))
        lat = c2.number_input("Site latitude (negative = south)", -60.0, 60.0, -26.3, 0.1, key="dw_lat",
                              help="Mbabane is about -26.3. Used for row spacing and orientation.")
        tmin = c3.number_input("Lowest expected temperature (C)", -30.0, 30.0, 0.0, 1.0, key="dw_tmin",
                               help="Cold weather raises string voltage. Use a conservative low.")
        battery_kwh = 0.0
        battery_modules = 0
        if inverter.hybrid:
            b1, b2 = st.columns(2)
            battery_kwh = b1.number_input("Battery capacity (kWh), 0 = none", 0.0, 500.0, 0.0, 0.5, key="dw_bkwh")
            battery_modules = int(b2.number_input("Number of battery modules", 0, 50, 0, 1, key="dw_bmod"))
        r1, r2, r3 = st.columns(3)
        dc_run = r1.number_input("Array to inverter cable run (m, one way)", 1.0, 300.0, 20.0, 1.0, key="dw_dcrun")
        ac_run = r2.number_input("Inverter to DB cable run (m)", 1.0, 200.0, 10.0, 1.0, key="dw_acrun")
        bat_run = r3.number_input("Battery cable run (m)", 0.5, 20.0, 2.0, 0.5, key="dw_batrun")

    # ----------------------------------------------------------- mounting
    with st.expander("3. Mounting and site area", expanded=True):
        mount = st.radio("Mounting type", L.MOUNTS, horizontal=True, key="dw_mount")
        tilted = mount != L.MOUNT_PITCHED
        mk = mount[:6]
        c1, c2, c3 = st.columns(3)
        area_w = c1.number_input("Usable width (m)" if tilted else "Roof width along the eave (m)",
                                 1.0, 300.0, 20.0 if tilted else 8.0, 0.5, key=f"dw_aw_{mk}")
        area_d = c2.number_input("Usable depth (m)" if tilted else "Roof slope length, eave to ridge (m)",
                                 1.0, 300.0, 12.0 if tilted else 4.5, 0.5, key=f"dw_ad_{mk}")
        setback = c3.number_input("Edge setback (m)", 0.0, 3.0, 0.4 if not tilted else 0.6, 0.1, key=f"dw_sb_{mk}",
                                  help="Keep clear of roof edges, ridge and obstacles (fire / wind / access).")
        d1, d2, d3 = st.columns(3)
        default_tilt = 18.0 if not tilted else (12.0 if mount == L.MOUNT_FLAT else 26.0)
        tilt = d1.number_input("Roof pitch (deg)" if not tilted else "Frame tilt (deg)", 0.0, 60.0, default_tilt, 1.0,
                               key=f"dw_tilt_{mk}")
        face_default = 0 if lat < 0 else 4
        face_label = d2.selectbox("Direction the modules face", list(FACING), index=face_default, key=f"dw_face_{mk}_{'s' if lat < 0 else 'n'}")
        orient = d3.selectbox("Module orientation", ["auto", "portrait", "landscape"], key=f"dw_orient_{mk}")
        roof_type = "IBR / corrugated sheet"
        stack = 1
        fclear = 0.5
        span = 1.2
        if not tilted:
            e1, e2 = st.columns(2)
            roof_type = e1.selectbox("Roof covering", list(L.ROOF_TYPES), key="dw_roof_type")
            span = e2.number_input("Max attachment spacing (m)", 0.6, 2.4, 1.2, 0.1, key="dw_span_roof")
        else:
            e1, e2, e3 = st.columns(3)
            stack = int(e1.selectbox("Modules high on each frame", [1, 2], key=f"dw_stack_{mk}"))
            fclear = e2.number_input("Front clearance (m)", 0.1, 2.0, 0.6 if mount == L.MOUNT_GROUND else 0.3, 0.05,
                                     key=f"dw_fc_{mk}")
            span = e3.number_input("Post spacing (m)", 1.0, 4.0, 2.4 if mount == L.MOUNT_GROUND else 2.0, 0.1,
                                   key=f"dw_post_{mk}")

    # ------------------------------------------------------------ compute
    try:
        site = D.Site(project=project, client=client, address=address, latitude=lat, t_min_c=tmin)
        inp = D.DesignInput(module=module, inverter=inverter, site=site, n_modules=n_modules,
                            battery_kwh=battery_kwh, battery_modules=battery_modules,
                            dc_run_m=dc_run, ac_run_m=ac_run, battery_run_m=bat_run)
        d = D.design(inp)
    except Exception as e:  # defensive: never show a stack trace to customers
        st.error(f"Could not calculate the design: {e}")
        return
    if not d.get("ok"):
        for w in d["warnings"]:
            st.error(w)
        st.info("Adjust the module, inverter or number of modules.")
        return

    used = d["strings"]["used"]
    lay = None
    try:
        li = L.LayoutInput(
            mount=mount, n_modules=used, module_len_mm=module.length_mm, module_wid_mm=module.width_mm,
            module_thk_mm=module.thickness_mm, orientation=orient, area_w_m=area_w, area_d_m=area_d,
            setback_m=setback, tilt_deg=tilt, facing_az_deg=float(FACING[face_label]), latitude=lat,
            stack=stack, front_clearance_m=fclear, support_span_m=span, roof_type=roof_type)
        lay = L.compute_layout(li, d["strings"]["modules_per_string"])
    except Exception as e:
        st.error(f"Could not calculate the layout: {e}")
    meta = DR.Meta(project=project, client=client, address=address, drawn_by=drawn_by, company=company,
                   revision=revision or "A")
    sheets = DR.build_sheets(meta, d, lay)

    # ------------------------------------------------------------ results
    st.markdown("### Design results")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Array", f"{d['kwp']} kWp", f"{used} modules")
    m2.metric("Strings", f"{d['strings']['n_strings']} x {d['string']['modules']}")
    m3.metric("DC/AC ratio", d["dc_ac_ratio"])
    m4.metric("AC breaker", f"{d['ac']['breaker_a']} A")
    for w in d["warnings"]:
        st.warning(w)
    if lay and lay.get("ok"):
        for w in lay["warnings"]:
            st.warning(w)
    elif lay is not None:
        for w in lay.get("warnings", []):
            st.error(w)
        st.info("The layout and mounting sheets are left out until the area is valid.")
    with st.expander("Protection, cables and bill of materials"):
        st.write(f"String Voc (cold) **{d['string']['voc_cold_v']} V**, Vmp **{d['string']['vmp_v']} V**. "
                 f"DC cable **{d['cables']['dc_string']['mm2']:g} mm2**, AC cable **{d['cables']['ac']['mm2']:g} mm2**, "
                 f"AC breaker **{d['ac']['breaker_a']} A**, RCD **{d['ac']['rcd_ma']} mA**.")
        items = list(d["bom"]) + (lay["bom"] if lay and lay.get("ok") else [])
        st.dataframe(items, hide_index=True)
        for n in d["notes"] + (lay["notes"] if lay and lay.get("ok") else []):
            st.caption("• " + n)

    # ------------------------------------------------------------ preview
    st.markdown("### Preview (watermarked)")
    keys = list(sheets)
    pick = st.radio("Sheet", keys, format_func=lambda k: SHEET_LABELS[k], horizontal=True, key="dw_sheet")
    pick = pick if pick in sheets else keys[0]
    st.markdown(_svg_html(DR.watermark(sheets[pick]).to_svg()), unsafe_allow_html=True)

    # ----------------------------------------------------------- download
    st.markdown("### Download the PDF drawings")
    secret = get_secret("UNLOCK_SECRET")
    revoked = PW.parse_revoked(get_secret("REVOKED_CODES"))
    c1, c2 = st.columns([3, 1])
    code_in = c1.text_input("Unlock code", key="dw_code_in", placeholder="e.g. PACK-ACME-20261231-9F2C41D07AB3")
    if c2.button("Apply code", key="dw_apply"):
        st.session_state["dw_applied"] = code_in
    verdict = PW.verify_code(secret, st.session_state.get("dw_applied", ""), revoked=revoked) \
        if st.session_state.get("dw_applied") else None
    if verdict is not None and not verdict.ok:
        st.error(verdict.reason)
    if verdict is not None and verdict.ok:
        st.success(f"Unlocked: {'complete pack' if verdict.tier == PW.TIER_PACK else 'single line diagram'} "
                   f"for {verdict.customer}, valid until {verdict.expires:%d %b %Y}.")
        base = _slug(project)
        if verdict.can("sld"):
            st.download_button("⬇️ Single line diagram (PDF)", DR.pdf_for(sheets, ["sld"], meta),
                               file_name=f"{base}-single-line-diagram.pdf", mime="application/pdf", key="dw_dl_sld")
        if verdict.can("pack"):
            st.download_button("⬇️ Complete drawing pack (PDF)", DR.pdf_for(sheets, DR.TIERS["pack"], meta),
                               file_name=f"{base}-drawing-pack.pdf", mime="application/pdf", key="dw_dl_pack")
        else:
            st.info("Your code covers the single line diagram only. Ask for the complete pack to also get "
                    "the array layout, mounting detail, bill of materials and schedules.")
    else:
        p_sld = get_secret("PRICE_SLD")
        p_pack = get_secret("PRICE_PACK")
        st.markdown(
            "**Single line diagram PDF**" + (f": {p_sld}" if p_sld else "") + "  \n"
            "**Complete pack PDF** (cover, single line diagram, array layout, mounting detail, BOM and "
            "schedules)" + (f": {p_pack}" if p_pack else ""))
        pay = get_secret("PAY_INSTRUCTIONS")
        st.caption(pay or "Contact the site owner to buy an unlock code.")
    st.caption("Drawings are preliminary and must be checked and signed off by a registered engineer or "
               "competent electrician before construction.")
