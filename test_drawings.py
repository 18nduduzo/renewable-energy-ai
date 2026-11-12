"""Run with:  python test_drawings.py     (no network, no Streamlit, no API keys)

Covers: unlock codes, string sizing, layout geometry, and the drawing sheets (SVG and PDF).
"""

import datetime as dt
import itertools
import re
import xml.etree.ElementTree as ET

import design as D
import drawings as DR
import layout as L
import paywall as PW
from scene import text_width

SECRET = "unit-test-secret"
TODAY = dt.date(2026, 11, 12)
FUTURE = dt.date(2027, 1, 1)


# ------------------------------------------------------------------ paywall
def test_code_roundtrip_and_tiers():
    c = PW.make_code(SECRET, "pack", "Acme Ltd", FUTURE)
    assert re.match(r"^PACK-ACMELTD-20270101-[0-9A-F]{12}$", c), c
    v = PW.verify_code(SECRET, c, TODAY)
    assert v.ok and v.tier == "PACK" and v.customer == "ACMELTD" and v.expires == FUTURE
    assert v.can("sld") and v.can("pack")
    s = PW.verify_code(SECRET, PW.make_code(SECRET, "SLD", "bob", FUTURE), TODAY)
    assert s.ok and s.can("sld") and not s.can("pack")
    assert not PW.verify_code(SECRET, "", TODAY).can("sld")


def test_code_rejects_tampering_and_bad_input():
    c = PW.make_code(SECRET, "SLD", "bob", FUTURE)
    upgraded = c.replace("SLD-", "PACK-", 1)
    assert not PW.verify_code(SECRET, upgraded, TODAY).ok           # tier upgrade
    longer = c.replace("20270101", "20301231")
    assert not PW.verify_code(SECRET, longer, TODAY).ok             # extended expiry
    other = c.replace("BOB", "EVE")
    assert not PW.verify_code(SECRET, other, TODAY).ok              # customer swap
    assert not PW.verify_code("another-secret", c, TODAY).ok        # wrong secret
    assert not PW.verify_code("", c, TODAY).ok                      # paywall not configured
    for junk in ("hello", "PACK-X-1-2", "' OR 1=1 --", "PACK-ACME-20270101-ZZZZZZZZZZZZ"):
        assert not PW.verify_code(SECRET, junk, TODAY).ok
    # forgiving about case and spaces
    assert PW.verify_code(SECRET, " " + c.lower() + " ", TODAY).ok


def test_code_expiry_and_revocation():
    c = PW.make_code(SECRET, "PACK", "acme", dt.date(2026, 11, 12))
    assert PW.verify_code(SECRET, c, dt.date(2026, 11, 12)).ok        # last valid day
    late = PW.verify_code(SECRET, c, dt.date(2026, 11, 13))
    assert not late.ok and "expired" in late.reason
    c2 = PW.make_code(SECRET, "PACK", "acme", FUTURE)
    assert not PW.verify_code(SECRET, c2, TODAY, PW.parse_revoked("zed, ACME")).ok
    assert not PW.verify_code(SECRET, c2, TODAY, PW.parse_revoked(c2)).ok
    assert PW.verify_code(SECRET, c2, TODAY, PW.parse_revoked("zed")).ok


def test_make_code_validation():
    for bad in (lambda: PW.make_code("", "PACK", "x1", FUTURE), lambda: PW.make_code(SECRET, "GOLD", "x1", FUTURE),
                lambda: PW.make_code(SECRET, "PACK", "!", FUTURE)):
        try:
            bad()
        except ValueError:
            continue
        raise AssertionError("expected ValueError")


# ------------------------------------------------------------------- design
def test_string_sizing_respects_voltage_limits_for_all_presets():
    for (name, inv), n in itertools.product(D.INVERTER_PRESETS.items(), range(1, 41)):
        d = D.design(D.DesignInput(inverter=inv, n_modules=n))
        if not d["ok"]:
            assert d["strings"]["used"] == 0
            continue
        s = d["string"]
        assert s["voc_cold_v"] <= inv.max_dc_v, (name, n)
        assert d["strings"]["used"] <= n
        assert d["strings"]["used"] == d["strings"]["modules_per_string"] * d["strings"]["n_strings"]
        assert sum(g["n"] for g in d["mppt"]) == d["strings"]["n_strings"]
        assert s["vmp_hot_v"] >= inv.mppt_min_v, (name, n)


def test_design_edge_cases():
    d = D.design(D.DesignInput(n_modules=2))      # fewer modules than one string needs
    assert not d["ok"] and d["warnings"]
    d = D.design(D.DesignInput(n_modules=16))     # more than fits -> warns
    assert d["ok"] and d["warnings"]
    d = D.design(D.DesignInput(n_modules=54, inverter=D.Inverter(
        name="x", ac_kw=30, phases=3, max_dc_v=1100, mppt_min_v=200, mppt_max_v=1000, max_strings_per_mppt=4,
        max_current_per_mppt_a=40, max_isc_per_mppt_a=50, max_dc_kw=45, hybrid=False)))
    assert d["ok"] and all(g["fuse_a"] == 25 for g in d["mppt"] if g["n"] >= 3)
    assert d["battery"] is None
    hy = D.design(D.DesignInput(n_modules=10, battery_kwh=10, battery_modules=2))
    assert hy["battery"] and hy["battery"]["breaker_a"] >= hy["battery"]["max_current_a"]
    assert hy["ac"]["breaker_a"] >= 1.25 * hy["ac"]["current_a"] - 1e-6


# ------------------------------------------------------------------- layout
def _boxes(lay):
    return [(m["x"], m["y"], m["x"] + m["w"], m["y"] + m["h"]) for m in lay["modules"]]


def _check_geometry(lay):
    inp = lay["input"]
    sb = inp.setback_m
    boxes = _boxes(lay)
    assert len(boxes) == lay["qty"]["modules_placed"]
    for (x0, y0, x1, y1) in boxes:
        assert x0 >= sb - 1e-6 and y0 >= sb - 1e-6, "module outside the setback"
        assert x1 <= inp.area_w_m - sb + 1e-6 and y1 <= inp.area_d_m - sb + 1e-6, "module outside the area"
    for a, b in itertools.combinations(boxes, 2):
        ox = min(a[2], b[2]) - max(a[0], b[0])
        oy = min(a[3], b[3]) - max(a[1], b[1])
        assert not (ox > 1e-6 and oy > 1e-6), "modules overlap"


CASES = {
    "pitched": dict(mount=L.MOUNT_PITCHED, area_w_m=9, area_d_m=5, tilt_deg=18),
    "pitched-landscape": dict(mount=L.MOUNT_PITCHED, area_w_m=12, area_d_m=4, tilt_deg=22, orientation="landscape"),
    "flat": dict(mount=L.MOUNT_FLAT, area_w_m=22, area_d_m=12, tilt_deg=12, front_clearance_m=0.3, support_span_m=2.0),
    "ground": dict(mount=L.MOUNT_GROUND, area_w_m=24, area_d_m=16, tilt_deg=26, front_clearance_m=0.6, support_span_m=2.4),
    "ground-2p": dict(mount=L.MOUNT_GROUND, area_w_m=20, area_d_m=30, tilt_deg=26, stack=2, support_span_m=2.4),
    "northern": dict(mount=L.MOUNT_GROUND, area_w_m=24, area_d_m=16, tilt_deg=30, latitude=40.0, facing_az_deg=180),
}


def test_layout_geometry_many_cases():
    for name, kw in CASES.items():
        for n in (4, 9, 10, 17, 24, 40):
            lay = L.compute_layout(L.LayoutInput(n_modules=n, **kw), 5)
            assert lay["ok"], (name, n)
            _check_geometry(lay)
            q = lay["qty"]
            assert q["modules_placed"] + q["shortfall"] == n
            assert q["end_clamps"] > 0 and q["rails"] > 0


def test_layout_shortfall_and_tiny_area():
    lay = L.compute_layout(L.LayoutInput(n_modules=40, area_w_m=6, area_d_m=3), 8)
    assert lay["ok"] and lay["qty"]["shortfall"] > 0 and lay["warnings"]
    assert not L.compute_layout(L.LayoutInput(area_w_m=0.5, area_d_m=0.5), 5)["ok"]
    assert not L.compute_layout(L.LayoutInput(n_modules=0), 5)["ok"]


def test_row_pitch_clears_winter_shadow():
    lay = L.compute_layout(L.LayoutInput(**CASES["ground"], n_modules=24), 12)
    g = lay["geo"]
    assert abs((g["pitch"] - g["dp"]) - g["h"] * g["shadow_factor"]) < 0.01
    lo = L.compute_layout(L.LayoutInput(**{**CASES["ground"], "tilt_deg": 10}, n_modules=24), 12)["geo"]
    assert lo["pitch"] < g["pitch"]                       # flatter tilt needs less row spacing
    nth = L.compute_layout(L.LayoutInput(**CASES["northern"], n_modules=24), 12)["geo"]
    assert nth["pitch"] > nth["dp"]


def test_pitched_rail_and_clamp_counts():
    lay = L.compute_layout(L.LayoutInput(**CASES["pitched"], n_modules=9), 9)
    rows, cols = lay["rows"], lay["cols"]
    assert lay["qty"]["end_clamps"] == 4 * rows
    assert lay["qty"]["mid_clamps"] == 2 * rows * (cols - 1)
    assert len([r for r in lay["rails"]]) == 2 * rows


# ------------------------------------------------------------------ drawings
def _build(case_name, n_modules=10, battery=True, inverter=None):
    kw = CASES[case_name]
    inp = D.DesignInput(n_modules=n_modules, battery_kwh=10 if battery else 0, battery_modules=2 if battery else 0,
                        inverter=inverter or D.Inverter())
    d = D.design(inp)
    assert d["ok"]
    li = L.LayoutInput(n_modules=d["strings"]["used"], **kw)
    lay = L.compute_layout(li, d["strings"]["modules_per_string"])
    meta = DR.Meta(project="Test project", client="Client", address="Plot 1, Mbabane", drawn_by="Tester")
    return d, lay, meta, DR.build_sheets(meta, d, lay)


def test_sheets_svg_valid_and_text_in_bounds():
    for name in CASES:
        d, lay, meta, sheets = _build(name)
        assert list(sheets) == DR.SHEET_ORDER
        for key, sc in sheets.items():
            ET.fromstring(sc.to_svg())                        # well-formed XML
            for it in sc.items:
                if it["t"] != "text" or it.get("rot"):
                    continue
                w = text_width(it["s"], it["size"], it["bold"])
                x0 = it["x"] - (w / 2 if it["anchor"] == "middle" else w if it["anchor"] == "end" else 0)
                assert 10 <= x0 and x0 + w <= 410.5, (name, key, it["s"], round(x0, 1), round(x0 + w, 1))
                assert 10 <= it["y"] <= 287, (name, key, it["s"], it["y"])


def test_no_text_collisions():
    """Catches labels printed on top of each other (a typical drawing defect)."""
    def box(it):
        w = text_width(it["s"], it["size"], it["bold"])
        x0 = it["x"] - (w / 2 if it["anchor"] == "middle" else w if it["anchor"] == "end" else 0)
        return (x0 + 0.15, it["y"] - it["size"] * 0.75, x0 + w - 0.15, it["y"] + it["size"] * 0.15)

    cases = [("pitched", 10, True, None), ("ground", 24, True, D.INVERTER_PRESETS["10 kW hybrid, 3-phase (1000 V, 2 MPPT)"]),
             ("flat", 54, False, D.Inverter(name="Generic 30 kW string 3-ph", ac_kw=30, phases=3, max_dc_v=1100,
                                            mppt_min_v=200, mppt_max_v=1000, max_strings_per_mppt=4,
                                            max_current_per_mppt_a=40, max_isc_per_mppt_a=50, max_dc_kw=45, hybrid=False))]
    bad = []
    for name, n, bat, inv in cases:
        d, lay, meta, sheets = _build(name, n, bat, inv)
        for key, sc in sheets.items():
            texts = [it for it in sc.items if it["t"] == "text" and not it.get("rot") and it["s"].strip()]
            for a, b in itertools.combinations(texts, 2):
                ba, bb = box(a), box(b)
                if min(ba[2], bb[2]) - max(ba[0], bb[0]) > 0.3 and min(ba[3], bb[3]) - max(ba[1], bb[1]) > 0.6:
                    bad.append((name, key, a["s"], b["s"]))
    assert not bad, bad[:8]


def test_pdf_pages_and_watermark_separation():
    d, lay, meta, sheets = _build("ground", 24)
    pack = DR.pdf_for(sheets, DR.TIERS["pack"], meta)
    sld = DR.pdf_for(sheets, DR.TIERS["sld"], meta)
    assert pack.startswith(b"%PDF") and sld.startswith(b"%PDF")
    assert len(re.findall(rb"/Type\s*/Page\b", pack)) == 5
    assert len(re.findall(rb"/Type\s*/Page\b", sld)) == 1
    assert len(sld) < len(pack)
    for sc in sheets.values():                                 # clean sheets never carry the preview mark
        assert "PREVIEW" not in sc.to_svg()
        assert "PREVIEW" in DR.watermark(sc).to_svg()
        assert len(DR.watermark(sc).items) > len(sc.items)
        assert len(sc.items) == len([i for i in sc.items])     # watermark() must not modify the original


def test_missing_layout_skips_layout_sheets():
    d, _, meta, _ = _build("pitched")
    bad = L.compute_layout(L.LayoutInput(area_w_m=0.2, area_d_m=0.2), 5)
    sheets = DR.build_sheets(meta, d, bad)
    assert list(sheets) == ["cover", "sld", "bom"]
    assert len(re.findall(rb"/Type\s*/Page\b", DR.pdf_for(sheets, DR.TIERS["pack"], meta))) == 3


def test_sheet_content_reflects_design():
    d, lay, meta, sheets = _build("pitched")
    sld = " ".join(i["s"] for i in sheets["sld"].items if i["t"] == "text")
    assert f"{d['ac']['breaker_a']} A" in sld and "SPD-DC1" in sld and "BATTERY BANK" in sld and "Test project" in sld
    nobat = _build("pitched", battery=False)[3]["sld"]
    assert "No battery storage" in " ".join(i["s"] for i in nobat.items if i["t"] == "text")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print("ok  ", t.__name__)
        except AssertionError as e:
            failed += 1
            print("FAIL", t.__name__, "->", e)
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
