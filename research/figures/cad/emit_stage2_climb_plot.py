#!/usr/bin/env python3
"""Emit Stage 2 climb smoke figure → research/figures/stage2_climb_check.png."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

CAD = Path(__file__).resolve().parent
sys.path.insert(0, str(CAD))

from constants_model import (  # noqa: E402
    Params,
    _GAMMA_AIR,
    _R_AIR,
    compute,
    drag_coefficient,
    us_standard_atmosphere,
    wing_reference_area_m2,
)

OUT = CAD.parent / "stage2_climb_check.png"  # research/figures/


def main() -> int:
    p = Params()
    v = compute(p).values
    thrust = float(np.asarray(v["stage.t2_kn"]).reshape(-1)[0]) * 1e3
    h_seal = float(np.asarray(v["stage.h_seal_km"]).reshape(-1)[0])
    S = wing_reference_area_m2()

    v_grid = np.linspace(p.v1_m_s, p.v_ab_m_s, 800)
    h_atm = np.linspace(0.0, 84000.0, 20000)
    rho_grid, T_grid, _ = us_standard_atmosphere(h_atm)
    target_rho = 2.0 * p.q_ascent_pa / v_grid**2
    h_of_v = np.interp(target_rho, rho_grid[::-1], h_atm[::-1])
    T_of_v = np.interp(h_of_v, h_atm, T_grid)
    mach = v_grid / np.sqrt(_GAMMA_AIR * _R_AIR * T_of_v)
    drag = p.q_ascent_pa * S * drag_coefficient(mach)

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0), dpi=160)
    fig.patch.set_facecolor("#f7f8fa")
    ax = axes[0]
    ax.plot(v_grid / 1000, np.full_like(v_grid, thrust / 1e3), color="#1f4e79", lw=2.0, label=r"$T_2$")
    ax.plot(v_grid / 1000, drag / 1e3, color="#c0392b", lw=2.0, label=r"$D=Q C_D S$")
    ax.fill_between(
        v_grid / 1000,
        drag / 1e3,
        thrust / 1e3,
        where=thrust > drag,
        color="#27ae60",
        alpha=0.18,
        label="excess",
    )
    ax.set_xlabel(r"$v$ (km/s)")
    ax.set_ylabel("Force (kN)")
    ax.set_title("Stage 2 climb: thrust vs drag")
    ax.grid(True, alpha=0.35)
    ax.legend(frameon=False, fontsize=9)

    ax = axes[1]
    ax.plot(v_grid / 1000, h_of_v / 1000, color="#1f4e79", lw=2.0)
    ax.set_xlabel(r"$v$ (km/s)")
    ax.set_ylabel(r"$h$ (km)")
    ax.set_title(rf"Constant-$Q$ path → $h_{{\mathrm{{seal}}}}\approx{h_seal:.1f}$ km")
    ax.grid(True, alpha=0.35)
    fig.suptitle("Stage 2 energy/climb smoke (constants_model)", fontsize=11)
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
