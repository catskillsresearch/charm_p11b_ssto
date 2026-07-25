#!/usr/bin/env python3
"""Emit Stage 1 takeoff closure figure → research/figures/stage1_takeoff_check.png."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

CAD = Path(__file__).resolve().parent
sys.path.insert(0, str(CAD))

from constants_model import Params, _ground_roll_m, compute, wing_reference_area_m2  # noqa: E402

OUT = CAD.parent / "stage1_takeoff_check.png"  # research/figures/


def main() -> int:
    p = Params()
    r = compute(p).values
    S = wing_reference_area_m2()
    m0 = float(np.asarray(r["mass.m0_t"]).reshape(-1)[0]) * 1e3
    t1 = float(np.asarray(r["stage.t1_n"]).reshape(-1)[0])
    v_lof = float(r["stage.v_lof_m_s"])
    s_g = float(r["stage.ground_roll_m"])
    rw = float(r["stage.runway_available_m"])

    vs = np.linspace(0.5, v_lof, 80)
    dist = np.array(
        [
            _ground_roll_m(
                m0,
                t1,
                v,
                S,
                p.rho_sl_kg_m3,
                p.cl_ground_roll,
                p.cd_ground_roll,
                p.mu_roll,
                p.g0,
            )[0]
            for v in vs
        ]
    )

    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.1), dpi=160)
    fig.patch.set_facecolor("#f7f8fa")

    ax = axes[0]
    ax.plot(dist / 1000, vs, color="#1f4e79", lw=2.2, label="ground roll")
    ax.axhline(v_lof, color="#c0392b", ls="--", lw=1.2, label=rf"$V_{{\mathrm{{lof}}}}={v_lof:.0f}$ m/s")
    ax.axvline(rw / 1000, color="#27ae60", ls="--", lw=1.2, label=rf"runway={rw/1000:.1f} km")
    ax.set_xlabel("Ground roll distance (km)")
    ax.set_ylabel("Speed (m/s)")
    ax.set_title("Stage 1 takeoff roll (high-lift)")
    ax.grid(True, alpha=0.35)
    ax.legend(frameon=False, fontsize=8)

    ax = axes[1]
    labels = [
        rf"clean $C_L$={p.cl_clean_vspaero:.2f}",
        rf"TO $C_{{L,\max}}$={p.cl_max_takeoff:.2f}",
    ]
    rolls = [float(r["stage.ground_roll_clean_m"]) / 1000, s_g / 1000]
    colors = ["#c0392b", "#1f4e79"]
    bars = ax.bar(labels, rolls, color=colors, width=0.55)
    ax.axhline(rw / 1000, color="#27ae60", ls="--", lw=1.4, label="runway available")
    ax.set_ylabel("Ground roll (km)")
    ax.set_title("Clean wing vs high-lift takeoff")
    ax.set_ylim(0, max(rolls[0] * 1.05, rw / 1000 * 1.35))
    ax.grid(True, axis="y", alpha=0.35)
    ax.legend(frameon=False, fontsize=8)
    for b, val in zip(bars, rolls):
        ax.text(b.get_x() + b.get_width() / 2, val + 0.2, f"{val:.1f} km", ha="center", fontsize=9)

    fig.suptitle(
        rf"Takeoff closure: $V_{{\mathrm{{lof}}}}$={v_lof:.0f} m/s, "
        rf"$s_g$={s_g/1000:.2f} km, margin={float(r['stage.runway_margin_m']):.0f} m",
        fontsize=11,
    )
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
