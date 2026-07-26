#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Emit the §10.9 schematic orbital-ascent diagram: Statesville Regional
Airport (KSVH), NC -> ISS-altitude LEO, colored by flight stage.

This is a **schematic**, not a navigation chart or an orbit-determination
product. What IS grounded in the model:

  - Stage durations (t1, t2, t3) are the same `constants_model.compute()`
    numbers used throughout §10.3-10.6 -- not re-guessed here.
  - The Stage-2 h(v) climb path is re-derived with the *exact* constant-Q
    quadrature `integrate_stage2_climb()` uses internally (same equations,
    kept as full t(v)/h(v) arrays here instead of just the endpoint it
    returns), so the Stage-2 curve on both panels is the real climb path,
    not an interpolation.
  - The Stage-1 end altitude is h(v1) on that *same* constant-Q schedule
    (Stage 1 flies the identical Q=25 kPa profile up to v1 before Stage 2
    takes over, per §10.3/§10.4) -- also not a new assumption.
  - The spiral's azimuthal rate at each instant is the real local
    circular-orbit rate 2*pi/T(h) (T from mu_earth, own vis-viva), not a
    decorative winding -- so the ~3 visible loops during Stage 3 are a
    genuine consequence of t3~4.3 h versus an ~88-90 min LEO period at
    this altitude band, not an arbitrary choice.
  - ISS altitude/inclination (400 km, 51.6 deg) are the same reference
    numbers cited at [15] elsewhere in the paper.

What is illustrative (flagged on the figure itself, not hidden):

  - Stage-1 (ground roll) and Stage-3 (vacuum spiral-up) altitude-vs-time
    *pacing* is a smooth interpolation between known endpoints -- neither
    is separately time-integrated anywhere else in the model (only
    Stage 2 has a real h(t)).
  - The radial axis on the spiral panel is exaggerated relative to
    Earth's own radius for legibility: true LEO-altitude/R_earth ~ 0.06,
    which would be an invisible sliver at true scale.
  - Statesville Regional Airport (KSVH), NC is a notional departure point
    (its real 2,135 m runway is shorter than the 3,500 m municipal runway
    assumed for the reference GLOW closure elsewhere in the paper) -- it
    is the town this study is written from, not a claim that this exact
    field supports the takeoff roll.

Outputs: research/figures/orbital_ascent_profile.png

Run directly::

    poetry run python research/figures/cad/emit_orbital_ascent_diagram.py
"""

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
    _GAMMA_AIR,
    _R_AIR,
    Params,
    compute,
    drag_coefficient,
    us_standard_atmosphere,
    wing_reference_area_m2,
)

OUT = CAD.parent / "orbital_ascent_profile.png"

R_EARTH_KM = 6371.0  # WGS84 mean radius
MU_EARTH_KM3_S2 = 398600.4418  # standard gravitational parameter
ISS_ALT_KM = 400.0  # [15]
ISS_INCL_DEG = 51.6  # [15]

STATESVILLE_LABEL = "Statesville Regional\nAirport (KSVH), NC"

C_S1 = "#27ae60"  # green -- Stage 1, EDF
C_S2 = "#1f4e79"  # blue  -- Stage 2, microwave air plasma
C_S3 = "#c0392b"  # red   -- Stage 3, water plasma / vacuum
C_EARTH = "#2f6690"

# Radial mapping for the spiral panel only: r=1 is Earth's surface, r=R_MAX
# is the final ISS-altitude orbit. Exaggerated (power<1) so Stage 1/2
# altitudes are still visible next to Stage 3's -- flagged in-figure.
R_MAX = 1.6
R_EXPONENT = 0.4


def orbital_period_s(h_km: np.ndarray) -> np.ndarray:
    a_km = R_EARTH_KM + np.maximum(h_km, 0.0)
    return 2.0 * np.pi * np.sqrt(a_km**3 / MU_EARTH_KM3_S2)


def stage2_h_of_v(v_grid: np.ndarray, q_ascent_pa: float) -> np.ndarray:
    h_grid = np.linspace(0.0, 84000.0, 20000)
    rho_grid, _, _ = us_standard_atmosphere(h_grid)
    target_rho = 2.0 * q_ascent_pa / v_grid**2
    return np.interp(target_rho, rho_grid[::-1], h_grid[::-1])


def stage2_arrays(p: Params, v: dict, n_steps: int = 4000):
    """Re-derive the same constant-Q climb as `integrate_stage2_climb`, but
    keep the full (t, h) arrays instead of only the (t2, h_seal) endpoint."""
    S = wing_reference_area_m2()
    v_grid = np.linspace(p.v1_m_s, p.v_ab_m_s, n_steps + 1)
    h_of_v = stage2_h_of_v(v_grid, p.q_ascent_pa)
    h_grid = np.linspace(0.0, 84000.0, 20000)
    _, T_grid, _ = us_standard_atmosphere(h_grid)
    T_of_v = np.interp(h_of_v, h_grid, T_grid)
    mach = v_grid / np.sqrt(_GAMMA_AIR * _R_AIR * T_of_v)
    drag_n = p.q_ascent_pa * S * drag_coefficient(mach)
    dh_dv = np.gradient(h_of_v, v_grid)
    thrust_n = v["stage.t2_n"]
    mass_kg = v["mass.m0_kg"]
    excess_n = np.maximum(thrust_n - drag_n, 1.0)
    dt_dv = mass_kg * (p.g0 * dh_dv + v_grid) / (excess_n * v_grid)
    trapz = getattr(np, "trapezoid", None) or np.trapz
    t_of_v = np.concatenate([[0.0], np.cumsum(0.5 * (dt_dv[1:] + dt_dv[:-1]) * np.diff(v_grid))])
    return t_of_v, h_of_v / 1e3  # seconds, km


def smoothstep(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def build_profile(p: Params, v: dict, n_each: int = 400):
    """Assemble one continuous (t_s, h_km, stage) ascent profile from
    Statesville (t=0, h=0) to ISS altitude (t=t1+t2+t3, h=400 km)."""
    t1_s = float(v["stage.t1_s"])
    t2_s = float(v["stage.t2_s"])
    t3_s = float(v["stage.t3_s"])
    h_seal_km = float(v["stage.h_seal_km"])

    # Stage 1: ground roll + climb-out to v1 on the same constant-Q
    # schedule Stage 2 continues -- h(v1) is not a new number.
    h1_end_km = float(stage2_h_of_v(np.array([p.v1_m_s]), p.q_ascent_pa)[0]) / 1e3
    t1 = np.linspace(0.0, t1_s, n_each)
    h1 = h1_end_km * smoothstep(t1 / t1_s)

    # Stage 2: real constant-Q climb quadrature, offset to start at t1_s.
    t2_rel, h2 = stage2_arrays(p, v, n_steps=n_each - 1)
    t2 = t1_s + t2_rel

    # Stage 3: vacuum spiral-up, h_seal -> ISS altitude. No separate h(t)
    # integrator exists for this stage in constants_model; illustrative
    # smooth interpolation between known, grounded endpoints.
    t3 = t1_s + t2_s + np.linspace(0.0, t3_s, n_each)
    h3 = h_seal_km + (ISS_ALT_KM - h_seal_km) * smoothstep(np.linspace(0.0, 1.0, n_each))

    t_all = np.concatenate([t1, t2, t3])
    h_all = np.concatenate([h1, h2, h3])
    stage_all = np.concatenate([np.full(n_each, 1), np.full(len(t2), 2), np.full(n_each, 3)])
    return t_all, h_all, stage_all, (t1_s, t2_s, t3_s, h_seal_km)


def main() -> int:
    p = Params()
    v = compute(p).values
    t_all, h_all, stage_all, (t1_s, t2_s, t3_s, h_seal_km) = build_profile(p, v)
    t3_h = t3_s / 3600.0
    t2_min = t2_s / 60.0
    mach_seal = float(v["stage.mach_seal"])

    # ----- Spiral panel geometry: real local orbital angular rate, exaggerated radius -----
    T_local = orbital_period_s(h_all)
    dtheta_dt = 2.0 * np.pi / T_local
    theta = np.concatenate([[0.0], np.cumsum(0.5 * (dtheta_dt[1:] + dtheta_dt[:-1]) * np.diff(t_all))])
    r = 1.0 + (R_MAX - 1.0) * (np.clip(h_all, 0.0, None) / ISS_ALT_KM) ** R_EXPONENT
    x = r * np.cos(theta)
    y = r * np.sin(theta)
    n_rev = theta[-1] / (2 * np.pi)

    fig = plt.figure(figsize=(12.5, 7.0), dpi=160)
    fig.patch.set_facecolor("#f7f8fa")
    gs = fig.add_gridspec(1, 2, top=0.70, bottom=0.11, left=0.04, right=0.93, wspace=0.22)
    axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])]

    # ----- Left: schematic spiral -----
    ax = axes[0]
    ax.set_facecolor("#f7f8fa")
    earth = plt.Circle((0, 0), 1.0, color=C_EARTH, zorder=2)
    ax.add_patch(earth)
    ax.text(0, 0, "Earth\n$R_\\oplus\\!\\approx\\!6371$ km", color="white", ha="center", va="center",
             fontsize=8.5, zorder=3, fontweight="bold")

    colors = {1: C_S1, 2: C_S2, 3: C_S3}
    for sid in (1, 2, 3):
        mask = stage_all == sid
        idx = np.where(mask)[0]
        # include one point of overlap with the next stage so segments join
        if sid < 3:
            idx = np.append(idx, idx[-1] + 1)
        ax.plot(x[idx], y[idx], color=colors[sid], lw=2.4, zorder=4, solid_capstyle="round")

    # reference circles: sealing altitude and final orbit
    for r_ref, style, lbl in (
        (1.0 + (R_MAX - 1.0) * (h_seal_km / ISS_ALT_KM) ** R_EXPONENT, ":", None),
        (R_MAX, "--", None),
    ):
        circ = plt.Circle((0, 0), r_ref, fill=False, ls=style, lw=1.0, color="#666666", zorder=1, alpha=0.7)
        ax.add_patch(circ)

    ax.plot([1.0], [0.0], marker="o", color="black", ms=7, zorder=5)
    ax.annotate(
        STATESVILLE_LABEL,
        xy=(1.0, 0.0),
        xytext=(1.0, -0.34),
        ha="center",
        va="top",
        fontsize=8,
        zorder=5,
        arrowprops=dict(arrowstyle="-", lw=0.7, color="#444444"),
    )
    # Arrowhead at the trajectory terminus, pointing in the direction of travel.
    ax.annotate(
        "",
        xy=(x[-1], y[-1]),
        xytext=(x[-2], y[-2]),
        zorder=5,
        arrowprops=dict(arrowstyle="-|>", color="black", lw=1.6, mutation_scale=18, shrinkA=0, shrinkB=0),
    )
    ax.annotate(
        f"ISS-alt LEO\n{ISS_ALT_KM:.0f} km, {ISS_INCL_DEG:.1f}$^\\circ$ [15]",
        xy=(x[-1], y[-1]),
        xytext=(x[-1] * 1.18, y[-1] * 1.18),
        ha="left" if x[-1] >= 0 else "right",
        va="center",
        fontsize=8,
        zorder=5,
    )

    handles = [
        plt.Line2D([0], [0], color=C_S1, lw=2.4, label=f"Stage 1 — EDF ($t_1\\!\\approx\\!{t1_s:.0f}$ s)"),
        plt.Line2D([0], [0], color=C_S2, lw=2.4,
                   label=f"Stage 2 — air plasma ($t_2\\!\\approx\\!{t2_min:.1f}$ min, $M\\!\\approx\\!{mach_seal:.0f}$ @ seal)"),
        plt.Line2D([0], [0], color=C_S3, lw=2.4, label=f"Stage 3 — water plasma, vacuum ($t_3\\!\\approx\\!{t3_h:.2f}$ h)"),
    ]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.895), ncol=1, frameon=False, fontsize=8.8)

    lim = R_MAX * 1.32
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim * 0.95, lim * 1.05)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(
        f"Schematic ascent spiral — KSVH $\\to$ ISS-altitude LEO ({n_rev:.1f} revolutions)",
        fontsize=10, pad=8,
    )
    ax.text(
        0.5, -0.05,
        "Not to scale: altitude exaggerated vs. $R_\\oplus$ for legibility (true LEO-alt$/R_\\oplus\\!\\approx\\!0.06$).\n"
        "Spin rate = real local $2\\pi/T(h)$ (vis-viva) — loop count is physical, not decorative.",
        transform=ax.transAxes, ha="center", va="top", fontsize=7, color="#555555",
    )

    # ----- Right: altitude vs. mission elapsed time (log time axis) -----
    ax2 = axes[1]
    for sid in (1, 2, 3):
        mask = stage_all == sid
        idx = np.where(mask)[0]
        if sid < 3:
            idx = np.append(idx, idx[-1] + 1)
        ax2.plot(t_all[idx], h_all[idx], color=colors[sid], lw=2.2)

    t1_t2 = t1_s + t2_s
    t_total = t1_s + t2_s + t3_s
    for t_line, lbl in ((t1_s, None), (t1_t2, None)):
        ax2.axvline(t_line, color="#888888", ls="--", lw=0.8)
    ax2.axhline(h_seal_km, color="#888888", ls=":", lw=0.8)
    ax2.axhline(ISS_ALT_KM, color="#888888", ls=":", lw=0.8)
    ax2.text(t1_s * 0.4, h_seal_km * 1.35, f"$t_1\\!\\approx\\!{t1_s:.0f}$ s", color=C_S1, fontsize=8, ha="center")
    ax2.text(np.sqrt(t1_s * t1_t2), h_seal_km * 0.45, f"$t_2\\!\\approx\\!{t2_min:.1f}$ min", color=C_S2, fontsize=8, ha="center")
    ax2.text(np.sqrt(t1_t2 * t_total), ISS_ALT_KM * 0.55, f"$t_3\\!\\approx\\!{t3_h:.2f}$ h", color=C_S3, fontsize=8.5, ha="center")
    ax2.text(t_total * 1.02, h_seal_km, f"$h_\\mathrm{{seal}}\\!\\approx\\!{h_seal_km:.1f}$ km", fontsize=7.5, va="center", color="#555555")
    ax2.text(t_total * 1.02, ISS_ALT_KM, f"ISS $\\approx\\!{ISS_ALT_KM:.0f}$ km", fontsize=7.5, va="center", color="#555555")

    ax2.set_xscale("log")
    ax2.set_xlim(1.0, t_total * 1.9)
    ax2.set_ylim(0, ISS_ALT_KM * 1.12)
    ax2.set_xlabel("Mission elapsed time (s, log scale)")
    ax2.set_ylabel("Altitude (km)")
    ax2.set_title("Altitude vs. elapsed time (true relative durations)", fontsize=10, pad=8)
    ax2.grid(True, which="both", alpha=0.3)

    fig.suptitle(
        f"CATSKILLS SSTO ascent profile — total $\\approx\\!{t_total/3600.0:.2f}$ h, Statesville, NC $\\to$ ISS-altitude LEO",
        fontsize=12, y=0.985,
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT)
    print(f"wrote {OUT}")
    print(f"  t1={t1_s:.1f}s  t2={t2_min:.1f}min  t3={t3_h:.2f}h  total={t_total/3600.0:.2f}h")
    print(f"  h_seal={h_seal_km:.1f}km  revolutions={n_rev:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
