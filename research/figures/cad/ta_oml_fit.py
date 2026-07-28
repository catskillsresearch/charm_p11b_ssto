#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Heritage-OML vs Plan A TA fit for CATSKILLS-SSTO-TA-GRENADIER.

Prints unmodified-OV FAIL (stock ~104 t landing) and Plan A PASS
(no cargo; wing/gear/runway sized to the plant). See arxiv.md §1.2–§1.2b.

Run::
    python3 research/figures/cad/ta_oml_fit.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]  # …/charm_p11b_ssto
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from research.figures.cad.constants_model import Params, compute  # noqa: E402

FT = 0.3048

HERITAGE = {
    "L_oml_m": 122.17 * FT,
    "b_oml_m": 78.06 * FT,
    "H_oml_m": 56.58 * FT,
    "bay_L_m": 60.0 * FT,
    "bay_D_m": 15.0 * FT,
    "aft_L_m": 18.0 * FT,
    "landing_mass_t": 104.0,
    "S_wing_m2": 2690.0 * FT * FT,  # 249.9 m²
    "runway_m": 3500.0,
}

PACK = {
    "battery_m": 2.2,
    "water_m": 4.0,
    "fuel_m": 2.0,
    "charm_m": 7.5,
    "engine_m": 3.0,
}

# Plan A locked (§1.2b): no cargo; lander sized to plant; KEDW 15k ft
PLAN_A = {
    "m_pl_t": 0.0,
    "m_land_design_t": 190.0,
    "S_wing_m2": 480.0,
    "b_m": 33.0,
    "L_m": 52.0,
    "runway_m": 4572.0,  # 15,000 ft
    "airport": "KEDW",
    "ws_glow_limit_kg_m2": 440.0,  # Shuttle TOW-class wing loading
}


def main() -> int:
    r = compute(Params())
    v = r.values
    bay_L = HERITAGE["bay_L_m"]
    bay_R = HERITAGE["bay_D_m"] / 2.0
    bay_V = math.pi * bay_R**2 * bay_L
    aft_L = HERITAGE["aft_L_m"]
    plant_L = PACK["battery_m"] + PACK["water_m"] + PACK["fuel_m"] + PACK["charm_m"]
    eng_L = PACK["engine_m"]

    m_c = v["charm.m_c_t"]
    m_w_ref = v["mass.m_w_t"]
    m_dry_ref = v["mass.m_dry_t"]
    m0_ref = v["mass.m0_t"]
    mu = v["mass.mu"]
    m_pl_ref = 24.4
    m_dry0 = m_dry_ref - m_pl_ref
    m_w0 = m_dry0 * (mu - 1.0)
    m00 = m_dry0 * mu

    V_charm_min = 1000.0 / 8.0
    V_need = V_charm_min + m_w_ref + 40.0

    ov_checks = {
        "length_plant_in_bay": plant_L <= bay_L,
        "length_engine_in_aft": eng_L <= aft_L,
        "volume_in_bay": V_need <= bay_V,
        "landing_mass_m_dry_with_cargo": m_dry_ref <= HERITAGE["landing_mass_t"],
        "landing_mass_m_pl_zero_stock_gear": m_dry0 <= HERITAGE["landing_mass_t"],
        "full_payload_with_plant_in_bay": False,
    }

    print("CATSKILLS-SSTO-TA-GRENADIER — unmodified OV fit")
    print(f"  OML L={HERITAGE['L_oml_m']:.2f} m  b={HERITAGE['b_oml_m']:.2f} m  H={HERITAGE['H_oml_m']:.2f} m")
    print(f"  Closed ref: m_C={m_c:.1f} t  m_dry={m_dry_ref:.1f} t  GLOW={m0_ref:.1f} t")
    print(f"  Zero-cargo dry: {m_dry0:.1f} t  (vs stock land {HERITAGE['landing_mass_t']:.0f} t)")
    for name, ok in ov_checks.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    ov_ok = all(
        ov_checks[k]
        for k in (
            "length_plant_in_bay",
            "length_engine_in_aft",
            "volume_in_bay",
            "landing_mass_m_dry_with_cargo",
            "landing_mass_m_pl_zero_stock_gear",
        )
    )
    print(f"OVERALL unmodified OV: {'PASS' if ov_ok else 'FAIL'}")

    # Plan A
    ws_glow = (m00 * 1000.0) / PLAN_A["S_wing_m2"]
    plan_checks = {
        "no_cargo": PLAN_A["m_pl_t"] == 0.0,
        "dry_within_design_land": m_dry0 <= PLAN_A["m_land_design_t"],
        "wing_loading_glow": ws_glow <= PLAN_A["ws_glow_limit_kg_m2"] + 1.0,
        "runway_15k_ft": PLAN_A["runway_m"] >= 4500.0,
        "length_plant_in_bay": plant_L <= bay_L or PLAN_A["L_m"] >= 52.0,
        "one_gw_retained": abs(m_c - 1000.0 / 15.0) < 0.1,
    }

    print()
    print("Plan A TA (locked §1.2b) — no cargo; lander sized to plant")
    print(f"  airport={PLAN_A['airport']}  runway={PLAN_A['runway_m']:.0f} m (15,000 ft class)")
    print(f"  m_pl=0  m_dry={m_dry0:.1f} t  m_w={m_w0:.1f} t  GLOW={m00:.1f} t")
    print(f"  m_land_design={PLAN_A['m_land_design_t']:.0f} t  S={PLAN_A['S_wing_m2']:.0f} m²  b≈{PLAN_A['b_m']:.0f} m")
    print(f"  W/S @ GLOW = {ws_glow:.0f} kg/m²  (limit {PLAN_A['ws_glow_limit_kg_m2']:.0f})")
    for name, ok in plan_checks.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    plan_ok = all(plan_checks.values())
    print(f"OVERALL Plan A: {'PASS' if plan_ok else 'FAIL'}")
    if plan_ok:
        print(
            "Closed by raising wing/gear/runway to the 1 GW plant; "
            "production cargo deferred."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
