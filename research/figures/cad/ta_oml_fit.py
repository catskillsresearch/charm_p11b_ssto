#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Heritage-OML TA fit check for CATSKILLS-SSTO-TA-GRENADIER.

Compares closed CHARM + 3-cycle + water packaging (constants_model) against
NASA orbiter midfuselage bay + aft fuselage envelopes.

Run::
    python3 research/figures/cad/ta_oml_fit.py

Exit 0 always (report tool); prints PASS/FAIL lines. Overall FAIL is expected
at the reference 1 GW / 15 kW/kg closure — see arxiv.md §1.2.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]  # …/charm_p11b_ssto (cad→figures→research→root)
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from research.figures.cad.constants_model import Params, compute  # noqa: E402

FT = 0.3048

# NASA orbiter fact-sheet class envelopes [arxiv.md §1.1 / NASA Shuttle reference]
HERITAGE = {
    "L_oml_m": 122.17 * FT,
    "b_oml_m": 78.06 * FT,
    "H_oml_m": 56.58 * FT,
    "bay_L_m": 60.0 * FT,
    "bay_D_m": 15.0 * FT,
    "aft_L_m": 18.0 * FT,
    "aft_W_m": 22.0 * FT,
    "aft_H_m": 20.0 * FT,
    "landing_mass_t": 104.0,  # ~230 klb class landing weight
    "empty_orbiter_t": 78.0,
}

# Packaging-study station lengths (assembly.json / arxiv profile)
PACK = {
    "battery_m": 2.2,
    "water_m": 4.0,
    "fuel_m": 2.0,
    "charm_m": 7.5,
    "engine_m": 3.0,
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
    m_w = v["mass.m_w_t"]
    m_dry = v["mass.m_dry_t"]
    m0 = v["mass.m0_t"]

    V_charm_min = 1000.0 / 8.0  # P_star MW / p_bar MW/m³
    V_need = V_charm_min + m_w + 40.0  # +ancillaries rough

    m_pl = 24.4  # reference payload included in m_dry
    m_dry0 = m_dry - m_pl

    checks = {
        "length_plant_in_bay": plant_L <= bay_L,
        "length_engine_in_aft": eng_L <= aft_L,
        "volume_in_bay": V_need <= bay_V,
        "landing_mass_m_dry": m_dry <= HERITAGE["landing_mass_t"],
        "landing_mass_m_pl_zero": m_dry0 <= HERITAGE["landing_mass_t"],
        "full_payload_with_plant_in_bay": False,
    }

    print("CATSKILLS-SSTO-TA-GRENADIER — heritage OML fit")
    print(f"  OML L={HERITAGE['L_oml_m']:.2f} m  b={HERITAGE['b_oml_m']:.2f} m  H={HERITAGE['H_oml_m']:.2f} m")
    print(f"  Bay {bay_L:.2f} m × ⌀{HERITAGE['bay_D_m']:.2f} m  V={bay_V:.0f} m³")
    print(f"  Aft length {aft_L:.2f} m")
    print(f"  Closed: m_C={m_c:.1f} t  m_w={m_w:.1f} t  m_dry={m_dry:.1f} t  GLOW={m0:.1f} t")
    print(f"  Zero-payload TA: m_dry(m_pl=0)={m_dry0:.1f} t  (still vs landing {HERITAGE['landing_mass_t']:.0f} t)")
    print(f"  Plant length need {plant_L:.1f} m (bay margin {bay_L - plant_L:+.1f} m)")
    print(f"  Engine length need {eng_L:.1f} m (aft margin {aft_L - eng_L:+.1f} m)")
    print(f"  Volume need ≈{V_need:.0f} m³ vs bay {bay_V:.0f} m³")
    print(f"  Landing proxy m_dry vs {HERITAGE['landing_mass_t']:.0f} t limit")
    for name, ok in checks.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    overall = all(
        checks[k]
        for k in (
            "length_plant_in_bay",
            "length_engine_in_aft",
            "volume_in_bay",
            "landing_mass_m_dry",
            "landing_mass_m_pl_zero",
        )
    )
    print(f"OVERALL: {'PASS' if overall else 'FAIL'}")
    if not overall:
        print(
            "Rethink drivers: m_dry "
            f"{m_dry:.0f} t (m_pl=0 → {m_dry0:.0f} t) ≫ landing {HERITAGE['landing_mass_t']:.0f} t; "
            "bay length/volume can host plant+water only if payload is sacrificed; "
            "zero payload is necessary but insufficient; GW-class m_C cannot land on an unmodified orbiter."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
