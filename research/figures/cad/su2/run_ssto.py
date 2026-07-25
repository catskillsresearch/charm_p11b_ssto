#!/usr/bin/env python3
"""Mesh + run coarse 3D Euler on CHARM SSTO, then render a ¾ airflow view."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pyvista as pv

ROOT = Path(__file__).resolve().parents[4]
SU2_BIN = ROOT / "third_party/su2/bin"
CASE = Path(__file__).resolve().parent / "ssto"
CFG = CASE / "inv_ssto.cfg"
MESH = CASE / "ssto_farfield.su2"
MESH_SCRIPT = Path(__file__).resolve().parent / "mesh_ssto_gmsh.py"
PLOT = CASE / "ssto_euler_cp.png"


def _ensure_mesh() -> None:
    if MESH.is_file() and MESH.stat().st_size > 1_000_000:
        return
    print("==> building exterior mesh")
    subprocess.check_call([sys.executable, str(MESH_SCRIPT)])


def _run_su2(threads: int) -> None:
    exe = SU2_BIN / "SU2_CFD"
    if not exe.is_file():
        raise SystemExit(f"Missing {exe}; see research/figures/cad/su2/README.md")
    env = os.environ.copy()
    env["PATH"] = f"{SU2_BIN}:{env.get('PATH', '')}"
    env["SU2_RUN"] = str(SU2_BIN)
    log = CASE / "su2_run.log"
    print(f"==> SU2_CFD -t {threads} {CFG.name}")
    with log.open("w", encoding="utf-8") as fh:
        subprocess.check_call(
            [str(exe), "-t", str(threads), CFG.name],
            cwd=CASE,
            env=env,
            stdout=fh,
            stderr=subprocess.STDOUT,
        )
    print(f"  log → {log}")


def _find_solution() -> tuple[Path | None, Path | None]:
    """SU2 v8 writes surface.vtu / vol_solution.vtu; older tutorials used surface_flow/flow."""
    surf_candidates = [CASE / "surface.vtu", CASE / "surface_flow.vtu"]
    vol_candidates = [CASE / "vol_solution.vtu", CASE / "flow.vtu"]
    surf = next((p for p in surf_candidates if p.is_file()), None)
    vol = next((p for p in vol_candidates if p.is_file()), None)
    return surf, vol


def _render() -> Path:
    pv.OFF_SCREEN = True
    surf_vtu, vol_vtu = _find_solution()
    body = CASE / "body_voxel.stl"

    plotter = pv.Plotter(off_screen=True, window_size=(1600, 1000))
    plotter.set_background("#0b1220")

    if surf_vtu is not None:
        surf = pv.read(str(surf_vtu))
        if "Pressure_Coefficient" in surf.array_names:
            scalars = "Pressure_Coefficient"
            clim = [-1.5, 1.5]
        elif "Mach" in surf.array_names:
            scalars = "Mach"
            clim = None
        else:
            scalars = surf.array_names[0] if surf.array_names else None
            clim = None
        plotter.add_mesh(
            surf,
            scalars=scalars,
            cmap="coolwarm",
            clim=clim,
            smooth_shading=True,
            show_scalar_bar=True,
            scalar_bar_args={
                "title": "Cp" if scalars == "Pressure_Coefficient" else (scalars or ""),
                "color": "white",
                "n_labels": 5,
            },
        )
    elif body.is_file():
        plotter.add_mesh(pv.read(str(body)), color="#9aa7b5", smooth_shading=True)

    if vol_vtu is not None:
        vol = pv.read(str(vol_vtu))
        # Keep field viz near the airframe (hide the far-field box faces).
        near = vol.clip_box(bounds=(-10.0, 70.0, -25.0, 25.0, -12.0, 25.0), invert=False)
        sl = near.slice(normal="y", origin=(27.0, 0.0, 3.0))
        if "Mach" in sl.array_names and sl.n_points > 0:
            plotter.add_mesh(
                sl,
                scalars="Mach",
                cmap="viridis",
                opacity=0.40,
                show_scalar_bar=False,
            )
        try:
            seeds = pv.Plane(
                center=(-8.0, 0.0, 3.0),
                direction=(1.0, 0.0, 0.0),
                i_size=22.0,
                j_size=12.0,
                i_resolution=8,
                j_resolution=5,
            )
            if "Velocity" in near.array_names:
                streams = near.streamlines_from_source(
                    seeds,
                    vectors="Velocity",
                    max_length=120.0,
                    integration_direction="forward",
                )
                plotter.add_mesh(
                    streams,
                    color="#7ec8e3",
                    line_width=2.0,
                    opacity=0.9,
                )
        except Exception as exc:  # noqa: BLE001 — viz is best-effort
            print(f"  streamline skip: {exc}")

    plotter.add_axes(color="white")
    # Nose-left ¾ view.
    plotter.camera_position = [
        (95.0, -75.0, 40.0),
        (27.0, 0.0, 3.0),
        (0.0, 0.0, 1.0),
    ]
    plotter.add_text(
        "CHARM SSTO · SU2 Euler · M=0.3 α=4° (coarse exterior)",
        font_size=11,
        color="white",
        position="upper_left",
    )
    plotter.show(screenshot=str(PLOT))
    plotter.close()
    print(f"wrote {PLOT}")
    return PLOT


def main() -> int:
    threads = int(os.environ.get("SU2_THREADS", "8"))
    render_only = "--render-only" in sys.argv
    CASE.mkdir(parents=True, exist_ok=True)
    if not render_only:
        _ensure_mesh()
        _run_su2(threads)
    _render()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
