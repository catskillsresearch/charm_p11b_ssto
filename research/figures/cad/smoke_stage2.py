#!/usr/bin/env python3
"""Stage 2 smoke test — climb / energy bookkeeping go/no-go (§10.4).

Re-runs the constant-Q climb quadrature from ``constants_model.py`` and
checks that thrust exceeds drag along the path (without the integrator's
stall guard masking a failure). Packaging specific power is reported as
an expected FAIL / unobtainium (does not fail the energy smoke).

Exit 0 = Stage 2 energy/climb PASS.
Exit 1 = FAIL (trajectory or T/P physics broken).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

CAD_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CAD_DIR))

from constants_model import (  # noqa: E402
    Params,
    compute,
    drag_coefficient,
    us_standard_atmosphere,
    wing_reference_area_m2,
    _GAMMA_AIR,
    _R_AIR,
)


def climb_margin(p: Params, thrust_n: float, mass_kg: float, n_steps: int = 2000):
    """Return (t2_s, h_seal_m, mach_seal, min_excess_n, min_T_over_D)."""
    S = wing_reference_area_m2()
    v_grid = np.linspace(p.v1_m_s, p.v_ab_m_s, n_steps + 1)
    h_grid = np.linspace(0.0, 84000.0, 20000)
    rho_grid, T_grid, _ = us_standard_atmosphere(h_grid)
    target_rho = 2.0 * p.q_ascent_pa / v_grid**2
    h_of_v = np.interp(target_rho, rho_grid[::-1], h_grid[::-1])
    T_of_v = np.interp(h_of_v, h_grid, T_grid)
    a_of_v = np.sqrt(_GAMMA_AIR * _R_AIR * T_of_v)
    mach = v_grid / a_of_v
    drag_n = p.q_ascent_pa * S * drag_coefficient(mach)
    excess = thrust_n - drag_n
    dh_dv = np.gradient(h_of_v, v_grid)
    # Integrator uses max(excess, 1); smoke uses raw excess for the go/no-go.
    dt_dv = mass_kg * (p.g0 * dh_dv + v_grid) / (np.maximum(excess, 1.0) * v_grid)
    trapz = getattr(np, "trapezoid", None) or np.trapz
    t2_s = float(trapz(dt_dv, v_grid))
    min_excess = float(np.min(excess))
    min_td = float(np.min(thrust_n / np.maximum(drag_n, 1e-9)))
    return t2_s, float(h_of_v[-1]), float(mach[-1]), min_excess, min_td


def main() -> int:
    p = Params()
    r = compute(p)
    v = r.values
    m0_kg = v["mass.m0_t"] * 1e3
    t2_n = v["stage.t2_n"]
    p2_w = v["stage.p2_star_w"]

    t2_s, h_seal_m, mach_seal, min_excess, min_td = climb_margin(p, t2_n, m0_kg)

    # Electrothermal T/P (N/kW): 2*eta_mu*eta_j2/v_j2 * 1000
    t_over_p = 2.0 * p.eta_mu * p.eta_j2 / p.v_j2_m_s * 1e3
    ye_rejected = t_over_p < 5.0  # Ye-class ~28 N/kW is the rejected claim

    e2_mwh = v["stage.e2_mwh"]
    kappa = v.get("stage.kappa_e_implied", float("nan"))

    # Packaging unobtainium report (informational)
    m_stage2_t = 4.4
    alpha_pkg = (p2_w / 1e3) / (m_stage2_t * 1e3)  # kW/kg

    checks: list[tuple[str, bool, str]] = []
    checks.append(
        (
            "climb quadrature finite",
            np.isfinite(t2_s) and 60.0 < t2_s < 7200.0,
            f"t2={t2_s/60:.1f} min",
        )
    )
    checks.append(
        (
            "h_seal in atmosphere",
            20e3 < h_seal_m < 80e3,
            f"h_seal={h_seal_m/1e3:.1f} km, M_seal={mach_seal:.1f}",
        )
    )
    checks.append(
        (
            "T2 > D along path (raw, no stall guard)",
            min_excess > 0.0,
            f"min(T-D)={min_excess/1e3:.1f} kN, min T/D={min_td:.2f}",
        )
    )
    checks.append(
        (
            "electrothermal T/P (not Ye N/kW)",
            ye_rejected and 0.1 < t_over_p < 5.0,
            f"T/P={t_over_p:.2f} N/kW",
        )
    )
    checks.append(
        (
            "E2 = P2* t2 positive",
            e2_mwh > 10.0,
            f"E2={e2_mwh:.0f} MWh",
        )
    )
    ok_kappa = np.isfinite(kappa) and 2.0 <= kappa <= 4.0
    checks.append(
        (
            "κ_E,implied in [2,4] (soft)",
            ok_kappa,
            f"κ_E={kappa:.2f}" if np.isfinite(kappa) else "κ_E=nan",
        )
    )

    print("Stage 2 smoke (climb / energy / §10.4)")
    hard_fail = False
    for name, ok, note in checks:
        soft = name.startswith("κ_E")
        if soft:
            mark = "SOFT-PASS" if ok else "SOFT-FAIL"
        else:
            mark = "PASS" if ok else "FAIL"
            if not ok:
                hard_fail = True
        print(f"  [{mark}] {name}: {note}")

    print(
        f"  [UNOBTAINIUM] packaging α≈{alpha_pkg:.0f} kW/kg in {m_stage2_t} t "
        f"(expected fail — not part of energy smoke)"
    )

    if hard_fail:
        print("VERDICT: Stage 2 FAIL (energy/climb)")
        return 1
    print("VERDICT: Stage 2 PASS (energy/climb); packaging remains unobtainium")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
