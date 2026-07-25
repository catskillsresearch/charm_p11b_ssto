#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build airlock top-down cutaway from assembly.json (Blender).

Frame: +X aft (station), +Y port, +Z up. Suited standing chamber with two
ring pressure hatches (cabin side, cargo-bay side), the repress/depress air
tank, and the pressurization equipment rack — orthographic top render.

Run::

    /snap/bin/blender -b -P research/figures/cad/build_airlock_blender.py

Or::

    make cad-airlock
"""

from __future__ import annotations

import sys
from pathlib import Path

import bpy

CAD_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CAD_DIR))

from lib.assembly_parser import find_node_in_doc, load_assembly  # noqa: E402
from lib.procedural_geometry import (  # noqa: E402
    box,
    callout,
    col,
    dimension_line,
    legend,
    mat,
    pressure_shell,
    ring_hatch,
    tank,
    text_label,
)
from lib.render_utils import clear_scene, render_to, setup_topdown_camera  # noqa: E402

ROOT = CAD_DIR.parents[2]
FIGURES = ROOT / "research" / "figures"
ASSEMBLY_PATH = CAD_DIR / "assembly.json"
BLEND_OUT = CAD_DIR / "airlock_cutaway.blend"
PNG_OUT = FIGURES / "airlock_top.png"


def build_airlock(asm: dict) -> dict:
    airlock = find_node_in_doc(asm, "airlock")
    if not airlock:
        raise SystemExit("airlock not found in assembly.json")

    env = airlock["envelope"]
    x0 = float(env["x0"])
    x1 = float(env["x1"])
    width = float(env["width_m"])
    length = x1 - x0
    wall_h = 2.2  # cabin clear height inside the 2.5 m OML shell
    floor_z = 0.0
    cx = (x0 + x1) / 2.0

    scene_root = col("00_Airlock")
    c_shell = col("01_Shell", scene_root)
    c_int = col("02_Interior", scene_root)
    c_hatch = col("03_Hatches", scene_root)
    c_lab = col("04_Labels", scene_root)
    c_roof = col("05_RoofCover", scene_root)
    c_lights = col("06_Lights", scene_root)

    m_shell = mat("al_shell", (0.90, 0.91, 0.93), roughness=0.35)
    m_hatch = mat("al_hatch", (0.55, 0.58, 0.62), roughness=0.65, metallic=0.05)
    m_tank = mat("al_tank", (0.20, 0.55, 0.30), roughness=0.7, metallic=0.05)
    m_pack = mat("al_pack", (0.25, 0.45, 0.35), roughness=0.4)

    shell = pressure_shell(
        x0,
        x1,
        width,
        wall_h,
        material=m_shell,
        collection=c_shell,
        floor_z=floor_z,
        name_prefix="AL_PV",
    )
    y_half = shell["y_half"]
    wall_t = shell["wall_t"]

    # Two ring pressure hatches: cabin side (fwd) and cargo-bay side (aft).
    # direction = -1 * port outward normal (crew-side hatch opens toward +X
    # into the chamber; bay-side hatch opens toward -X into the chamber).
    ring_hatch(
        "Hatch_Cabin",
        x=x0 + wall_t / 2.0,
        z=floor_z + wall_h * 0.5,
        radius=0.5,
        direction=1.0,
        wall_t=wall_t,
        material=m_hatch,
        collection=c_hatch,
    )
    ring_hatch(
        "Hatch_Bay",
        x=x1 - wall_t / 2.0,
        z=floor_z + wall_h * 0.5,
        radius=0.5,
        direction=-1.0,
        wall_t=wall_t,
        material=m_hatch,
        collection=c_hatch,
    )

    # Air tank (repress/depress) — mounted vertically against the port wall.
    tank_x = cx - 0.5
    tank_y = y_half - wall_t - 0.35
    tank(
        "Airlock_Air_Tank",
        0.28,
        1.3,
        (tank_x, tank_y, floor_z + wall_h * 0.5),
        m_tank,
        c_int,
        axis="Z",
    )

    # Pressurization gadgets (valves/pump/gauges) — starboard wall rack.
    pack_x = cx + 0.5
    pack_y = -(y_half - wall_t - 0.35)
    box(
        "Airlock_Cycle_Pack",
        (0.55, 0.4, 1.5),
        (pack_x, pack_y, floor_z + 0.75),
        m_pack,
        c_int,
    )

    # Roof cover — same footprint, parked beside (starboard).
    cover_y = -(y_half + width * 0.65)
    box(
        "Roof_Cover",
        (length, width, 0.12),
        (cx, cover_y, floor_z + 0.06),
        m_shell,
        c_roof,
    )

    z_lab = wall_h + 0.05
    callout(
        "CO_cabin",
        anchor_xyz=(x0, 0.3, 0.0),
        label_xyz=(x0 - 1.6, 0.85, 0.0),
        text="Hatch → cabin",
        collection=c_lab,
        z=z_lab,
        text_size=0.32,
    )
    callout(
        "CO_bay",
        anchor_xyz=(x1, 0.3, 0.0),
        label_xyz=(x1 + 1.6, 0.85, 0.0),
        text="Hatch → cargo bay",
        collection=c_lab,
        z=z_lab,
        text_size=0.32,
    )
    callout(
        "CO_tank",
        anchor_xyz=(tank_x, tank_y, 0.0),
        label_xyz=(tank_x - 0.1, tank_y + 0.85, 0.0),
        text="Air tank (press/depress)",
        collection=c_lab,
        z=z_lab,
        text_size=0.28,
    )
    callout(
        "CO_pack",
        anchor_xyz=(pack_x, pack_y, 0.0),
        label_xyz=(pack_x + 0.1, pack_y - 0.85, 0.0),
        text="Cycle gadgets",
        collection=c_lab,
        z=z_lab,
        text_size=0.28,
    )
    text_label("LBL_roof", "Roof cover", (cx, cover_y - width * 0.15, z_lab), c_lab, size=0.28)

    dimension_line(
        "DIM_length",
        p0=(x0, y_half),
        p1=(x1, y_half),
        offset=1.4,
        text=f"{length:.1f} m",
        collection=c_lab,
        z=z_lab,
        text_size=0.36,
    )
    # Width dim on the aft (cargo-bay) end so it does not cross the legend.
    dimension_line(
        "DIM_width",
        p0=(x1, -y_half),
        p1=(x1, y_half),
        offset=-2.0,
        text=f"{width:.1f} m",
        collection=c_lab,
        z=z_lab,
        text_size=0.36,
    )

    legend(
        [
            (m_shell, "Structure / shell"),
            (m_hatch, "Hatches"),
            (m_tank, "Air tank"),
            (m_pack, "Cycle gadgets"),
        ],
        (x0 - 3.6, y_half + 0.5, z_lab),
        c_lab,
        title="LEGEND",
        swatch=0.32,
        row_gap=0.55,
        label_dx=0.55,
        text_size=0.28,
    )

    return {
        "root": scene_root,
        "lights": c_lights,
        "length": length,
        "width": width,
        "cx": cx,
        "y_half": y_half,
        "cover_y": cover_y,
    }


def main() -> int:
    if not ASSEMBLY_PATH.is_file():
        print(f"missing {ASSEMBLY_PATH}", file=sys.stderr)
        return 1

    asm = load_assembly(ASSEMBLY_PATH)
    print("==> clear scene / build airlock from assembly.json")
    clear_scene()
    meta = build_airlock(asm)

    # Legend (left), dimension lines (above), parked roof cover (below)
    # make this asymmetric — fit content bounds explicitly. No in-figure
    # title: the LaTeX \caption already names the figure.
    render_w, render_h = 2400, 2000
    y_half = meta["y_half"]
    y_top = y_half + 1.9
    y_bottom = meta["cover_y"] - meta["width"] * 0.25 - 0.25
    cam_y = (y_top + y_bottom) / 2.0
    half_height_needed = (y_top - y_bottom) / 2.0

    x0 = meta["cx"] - meta["length"] / 2.0
    x1 = meta["cx"] + meta["length"] / 2.0
    x_left = x0 - 5.2  # legend margin
    x_right = x1 + 4.0  # hatch callout + width dim
    half_width_needed = max(meta["cx"] - x_left, x_right - meta["cx"])

    ortho_scale = max(
        half_width_needed * 2.0,
        half_height_needed * 2.0 * (render_w / render_h),
    )

    cam = setup_topdown_camera(
        meta["root"],
        meta["lights"],
        cx=meta["cx"],
        length=meta["length"],
        width=meta["width"],
        cam_y=cam_y,
        ortho_scale=ortho_scale,
    )

    FIGURES.mkdir(parents=True, exist_ok=True)
    print("==> render top-down")
    render_to(cam, PNG_OUT, width=render_w, height=render_h)

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT))
    print(f"saved {BLEND_OUT}")
    print(f"Open: /snap/bin/blender {BLEND_OUT}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback

        traceback.print_exc()
        raise SystemExit(1)
