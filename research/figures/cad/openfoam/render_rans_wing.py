#!/usr/bin/env python3
"""Render turbulent flow around the full airframe (paper figure)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyvista as pv

from camera_full_airframe import frame_full_airframe

CASE = Path(__file__).resolve().parent / "ssto_snappy"
OUT = Path(__file__).resolve().parents[1].parent / "stage1_rans_wing.png"


def _latest(pattern: str) -> Path:
    hits = sorted((CASE / "VTK").glob(pattern))
    if not hits:
        raise SystemExit(f"No {pattern} under VTK/; run Allrun.rans")
    return hits[-1]


def main() -> int:
    pv.OFF_SCREEN = True
    vol = pv.read(str(_latest("**/internal.vtu"))).cell_data_to_point_data()
    wall = pv.read(str(_latest("**/boundary/WALL.vtp")))

    if "U" not in vol.array_names:
        raise SystemExit(f"No U in volume; arrays={vol.array_names}")
    U = np.asarray(vol["U"], dtype=float)
    if float(U[:, 0].mean()) < 0:
        U = -U
        vol["U"] = U
    vol["U_mag"] = np.linalg.norm(U, axis=1)

    turb_key = next((k for k in ("nut", "nuTilda", "k") if k in wall.array_names), None)

    plotter = pv.Plotter(off_screen=True, window_size=(1600, 1000))
    plotter.set_background("white")

    # Colour the body itself by eddy viscosity — avoids an internal slice
    # plane, which (being paper-thin) gets badly foreshortened into a giant
    # phantom slab when viewed near edge-on by the ¾ camera.
    if turb_key:
        vals = np.asarray(wall[turb_key], dtype=float).ravel()
        lo_t, hi_t = np.percentile(vals, [5, 95]) if vals.size else (0.0, 1.0)
        plotter.add_mesh(
            wall,
            scalars=turb_key,
            cmap="inferno",
            clim=[float(lo_t), float(hi_t)],
            smooth_shading=True,
            specular=0.12,
            show_scalar_bar=True,
            scalar_bar_args={
                "title": f"{turb_key} on WALL (turbulent viscosity)",
                "color": "#1a1a1a",
            },
        )
    else:
        plotter.add_mesh(wall, color="#9aa3ad", smooth_shading=True, specular=0.12)

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
    if streams.n_points and "U" in streams.array_names:
        um = np.linalg.norm(np.asarray(streams["U"]), axis=1)
        streams["U_mag"] = um
        lo, hi = np.percentile(um, [5, 95]) if um.size else (0.0, 1.0)
        plotter.add_mesh(
            streams,
            scalars="U_mag",
            cmap="coolwarm",
            clim=[float(lo), float(hi)],
            line_width=2.0,
            show_scalar_bar=not turb_key,
            scalar_bar_args={"title": "|U| (m/s)", "color": "#1a1a1a"},
        )

    plotter.add_axes(color="#333333")
    frame_full_airframe(plotter, wall)
    plotter.add_text(
        "CHARM SSTO · simpleFoam Spalart–Allmaras · ~M=0.3 α=4° · full airframe",
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
