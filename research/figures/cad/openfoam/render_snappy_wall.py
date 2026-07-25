#!/usr/bin/env python3
"""Render snappyHexMesh WALL — full airframe, tight frame."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyvista as pv

from camera_full_airframe import frame_full_airframe

CASE = Path(__file__).resolve().parent / "ssto_snappy"
OUT = Path(__file__).resolve().parents[1].parent / "stage1_snappy_wall.png"


def _latest_wall() -> Path:
    hits = sorted((CASE / "VTK").glob("**/boundary/WALL.vtp"))
    if not hits:
        raise SystemExit(f"No WALL.vtp under {CASE / 'VTK'}; run foamToVTK")
    return hits[-1]


def main() -> int:
    pv.OFF_SCREEN = True
    wall = pv.read(str(_latest_wall()))

    plotter = pv.Plotter(off_screen=True, window_size=(1600, 1000))
    plotter.set_background("white")

    scalars = None
    for key in ("nSurfaceLayers", "thicknessFraction", "thickness", "nut"):
        if key in wall.array_names:
            scalars = key
            break

    if scalars:
        vals = np.asarray(wall[scalars], dtype=float).ravel()
        if scalars == "nSurfaceLayers":
            clim = [0, max(1.0, float(vals.max()))]
        else:
            lo, hi = np.percentile(vals, [5, 95]) if vals.size else (0.0, 1.0)
            clim = [float(lo), float(hi)]
        plotter.add_mesh(
            wall,
            scalars=scalars,
            cmap="viridis",
            clim=clim,
            show_scalar_bar=True,
            scalar_bar_args={"title": scalars, "color": "#1a1a1a"},
            smooth_shading=True,
        )
    else:
        plotter.add_mesh(wall, color="#8a939e", smooth_shading=True)

    plotter.add_axes(color="#333333")
    frame_full_airframe(plotter, wall)
    plotter.add_text(
        "CHARM SSTO · snappyHexMesh WALL · full airframe",
        font_size=10,
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
