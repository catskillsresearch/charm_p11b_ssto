#!/usr/bin/env python3
"""Render full-airframe streamlines (potentialFoam) for the paper figure."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pyvista as pv

from camera_full_airframe import frame_full_airframe

CASE = Path(__file__).resolve().parent / "ssto_snappy"
OUT = Path(__file__).resolve().parents[2] / "stage1_wing_flow.png"


def _latest_internal() -> Path:
    cands = sorted((CASE / "VTK").glob("**/internal.vtu"))
    if not cands:
        raise SystemExit(f"No internal.vtu under {CASE / 'VTK'}; run Allrun.flow")
    return cands[-1]


def _latest_wall() -> Path | None:
    cands = sorted((CASE / "VTK").glob("**/boundary/WALL.vtp"))
    return cands[-1] if cands else None


def main() -> int:
    pv.OFF_SCREEN = True
    vol = pv.read(str(_latest_internal())).cell_data_to_point_data()
    if "U" not in vol.array_names:
        print("arrays:", vol.array_names, file=sys.stderr)
        raise SystemExit("No velocity field U in volume VTK")
    U = np.asarray(vol["U"], dtype=float)
    if float(np.mean(U[:, 0])) < 0.0:
        U = -U
        vol["U"] = U
    vol["U_mag"] = np.linalg.norm(U, axis=1)

    wall_path = _latest_wall()
    if wall_path is None:
        raise SystemExit("No WALL.vtp; run foamToVTK")
    wall = pv.read(str(wall_path))

    plotter = pv.Plotter(off_screen=True, window_size=(1600, 1000))
    plotter.set_background("#f4f6f8")
    plotter.add_mesh(
        wall,
        color="#c5ccd4",
        show_edges=False,
        smooth_shading=True,
        specular=0.15,
    )

    # Coarse background mesh + cell→point interpolation makes long traces
    # near the nose curl into non-physical loops. A short, sparse rake just
    # ahead of the wing root reads cleanly without chasing that noise.
    seeds_list = []
    for y0, y1 in ((-12.0, -5.0), (5.0, 12.0)):
        ys = np.linspace(y0, y1, 6)
        zs = np.linspace(-2.5, 0.0, 3)
        xx, yy, zz = np.meshgrid([11.0], ys, zs, indexing="xy")
        seeds_list.append(np.column_stack([xx.ravel(), yy.ravel(), zz.ravel()]))
    seeds = pv.PolyData(np.vstack(seeds_list))

    streams = vol.streamlines_from_source(
        seeds,
        vectors="U",
        max_length=22.0,
        integration_direction="forward",
    )
    if streams.n_points == 0:
        print("warning: empty streamlines", file=sys.stderr)
    elif "U" in streams.array_names:
        um = np.linalg.norm(np.asarray(streams["U"], dtype=float), axis=1)
        streams["U_mag"] = um
        lo, hi = np.percentile(um, [5, 95])
        plotter.add_mesh(
            streams,
            scalars="U_mag",
            cmap="coolwarm",
            clim=[float(lo), float(hi)],
            line_width=2.0,
            show_scalar_bar=True,
            scalar_bar_args={"title": "|U| (m/s)", "color": "#1a1a1a", "n_labels": 4},
        )

    plotter.add_axes(color="#333333")
    frame_full_airframe(plotter, wall)
    plotter.add_text(
        "CHARM SSTO · potentialFoam · ~M=0.3 α=4° · full airframe",
        font_size=11,
        color="#1a1a1a",
        position="upper_left",
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    plotter.show(screenshot=str(OUT))
    plotter.close()
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
