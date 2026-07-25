#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build cargo-skid top-down cutaway from assembly.json (Blender).

Frame: +X aft (station), +Y port, +Z up. Semi-circular skid with its own
left/right clamshell bay doors swung open (roof-hinge ports), a tie-down
grid, a generic payload envelope block, and the forward interface to the
airlock's aft hatch. No pressure door aft — the well is open toward the
CHARM/engine bays for maintenance, per assembly.json.

Run::

    /snap/bin/blender -b -P research/figures/cad/build_cargo_skid_blender.py

Or::

    make cad-cargo-skid
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
    clamshell_bay_door,
    col,
    dimension_line,
    legend,
    mat,
    text_label,
    tie_down_grid,
)
from lib.render_utils import clear_scene, render_to, setup_topdown_camera  # noqa: E402

ROOT = CAD_DIR.parents[2]
FIGURES = ROOT / "research" / "figures"
ASSEMBLY_PATH = CAD_DIR / "assembly.json"
BLEND_OUT = CAD_DIR / "cargo_skid_cutaway.blend"
PNG_OUT = FIGURES / "cargo_skid_top.png"


def build_cargo_skid(asm: dict) -> dict:
    bay = find_node_in_doc(asm, "cargo_bay")
    if not bay:
        raise SystemExit("cargo_bay not found in assembly.json")

    env = bay["envelope"]
    x0 = float(env["x0"])
    x1 = float(env["x1"])
    width = float(env["width_m"])
    length = x1 - x0
    wall_h = 1.6  # low skid rim, not a pressure shell
    floor_z = 0.0
    wall_t = 0.10
    cx = (x0 + x1) / 2.0
    y_half = width / 2.0

    scene_root = col("00_CargoSkid")
    c_shell = col("01_Shell", scene_root)
    c_int = col("02_Interior", scene_root)
    c_door = col("03_Doors", scene_root)
    c_lab = col("04_Labels", scene_root)
    c_lights = col("05_Lights", scene_root)

    m_shell = mat("cs_shell", (0.62, 0.64, 0.68), roughness=0.4)
    m_floor = mat("cs_floor", (0.35, 0.37, 0.40), roughness=0.7)
    m_door = mat("cs_door", (0.90, 0.91, 0.93), roughness=0.35)
    m_payload = mat("cs_payload", (0.35, 0.55, 0.72), roughness=0.4)
    m_interface = mat("cs_interface", (0.55, 0.58, 0.62), roughness=0.65, metallic=0.05)
    m_tiedown = mat("cs_tiedown", (0.15, 0.15, 0.17), roughness=0.65, metallic=0.05)

    # --- Skid floor + low rim rails (semi-circular skid, flattened for top view) ---
    box(
        "Skid_Floor",
        (length, width, 0.08),
        (cx, 0.0, floor_z + 0.04),
        m_floor,
        c_shell,
    )
    for name, y_sign in (("Skid_Rail_Port", 1.0), ("Skid_Rail_Stbd", -1.0)):
        box(
            name,
            (length, wall_t, wall_h),
            (cx, y_sign * (y_half - wall_t / 2.0), floor_z + wall_h / 2.0),
            m_shell,
            c_shell,
        )

    # --- Tie-down grid across the floor ---
    tie_down_grid(
        x0,
        x1,
        width,
        material=m_tiedown,
        collection=c_int,
        spacing=2.4,
        floor_z=floor_z,
        margin=0.7,
    )

    # --- Generic payload envelope (24.4 t max) ---
    box(
        "Payload_Envelope",
        (length * 0.72, width * 0.55, 0.18),
        (cx, 0.0, floor_z + 0.13),
        m_payload,
        c_int,
    )

    # --- Forward interface: airlock's aft hatch mates here (door lives on the airlock) ---
    box(
        "Fwd_Hatch_Interface",
        (0.10, width * 0.5, wall_h * 0.7),
        (x0 + 0.05, 0.0, floor_z + wall_h * 0.35),
        m_interface,
        c_shell,
    )

    # --- Left/right clamshell bay doors, swung open about their roof-hinge lines ---
    panel_width = y_half * 0.95
    clamshell_bay_door(
        "Left_Cargo_Door",
        hinge_x0=x0,
        hinge_x1=x1,
        hinge_y=y_half,
        panel_width=panel_width,
        thickness=wall_t,
        open_deg=20.0,
        material=m_door,
        collection=c_door,
        z=wall_h,
    )
    clamshell_bay_door(
        "Right_Cargo_Door",
        hinge_x0=x0,
        hinge_x1=x1,
        hinge_y=-y_half,
        panel_width=panel_width,
        thickness=wall_t,
        open_deg=20.0,
        material=m_door,
        collection=c_door,
        z=wall_h,
    )

    door_outer = y_half + panel_width
    z_lab = wall_h + 0.15

    # World-space text must be large: this station is ~18 m long and the ortho
    # camera spans ~28 m, so 0.15 m letters render at ~20 px (microtype in the
    # paper). Target ~55–70 px body at 3600 px render width.
    callout(
        "CO_fwd",
        anchor_xyz=(x0, 0.0, 0.0),
        label_xyz=(x0 - 1.2, door_outer + 0.85, 0.0),
        text="Fwd interface\n(airlock aft hatch)",
        collection=c_lab,
        z=z_lab,
        text_size=0.48,
    )
    callout(
        "CO_aft",
        anchor_xyz=(x1, 0.0, 0.0),
        label_xyz=(x1 + 1.4, door_outer + 0.85, 0.0),
        text="Open aft — no pressure door\n(EVA to CHARM/engine wells)",
        collection=c_lab,
        z=z_lab,
        text_size=0.48,
    )
    text_label("LBL_payload", "Payload envelope (≤24.4 t)", (cx, 0.0, z_lab), c_lab, size=0.52)
    text_label("LBL_left", "Left cargo door (open)", (cx, door_outer * 0.55, z_lab), c_lab, size=0.50)
    text_label("LBL_right", "Right cargo door (open)", (cx, -door_outer * 0.55, z_lab), c_lab, size=0.50)
    # Kept entirely below y_half (never crosses under the tilted door panels,
    # whose rotated outer edge rises in Z and would occlude a top-side label).
    callout(
        "CO_tie",
        anchor_xyz=(x0 + 2.2, -(y_half - 0.7), 0.0),
        label_xyz=(x0 + 2.2, -(y_half + 0.05), 0.0),
        text="Tie-down grid",
        collection=c_lab,
        z=z_lab,
        text_size=0.42,
    )
    dimension_line(
        "DIM_length",
        p0=(x0, -door_outer),
        p1=(x1, -door_outer),
        offset=-0.75,
        text=f"{length:.1f} m",
        collection=c_lab,
        z=z_lab,
        text_size=0.55,
        line_t=0.035,
    )
    # Width dim on the aft end so it does not collide with the forward
    # callout / legend cluster.
    dimension_line(
        "DIM_width",
        p0=(x1, -door_outer),
        p1=(x1, door_outer),
        offset=-2.4,
        text=f"{width:.1f} m",
        collection=c_lab,
        z=z_lab,
        text_size=0.55,
        line_t=0.035,
    )

    legend(
        [
            (m_shell, "Structure / rails"),
            (m_door, "Bay doors"),
            (m_payload, "Payload envelope"),
            (m_interface, "Hatch interface"),
            (m_tiedown, "Tie-down points"),
        ],
        (x0 - 6.4, door_outer * 0.35, z_lab),
        c_lab,
        title="LEGEND",
        swatch=0.40,
        row_gap=0.78,
        label_dx=0.70,
        text_size=0.42,
    )

    return {
        "root": scene_root,
        "lights": c_lights,
        "length": length,
        "cx": cx,
        "door_outer": door_outer,
    }


def main() -> int:
    if not ASSEMBLY_PATH.is_file():
        print(f"missing {ASSEMBLY_PATH}", file=sys.stderr)
        return 1

    asm = load_assembly(ASSEMBLY_PATH)
    print("==> clear scene / build cargo skid from assembly.json")
    clear_scene()
    meta = build_cargo_skid(asm)

    # Composition is asymmetric: doors extend +/-door_outer, the legend sits
    # in the fwd-left margin — fit content bounds explicitly. No in-figure
    # title: the LaTeX \caption already names the figure.
    door_outer = meta["door_outer"]
    # Slightly taller aspect so door panels + callouts fill more of the frame
    # (less empty side gutter → lettering reads larger on the page).
    render_w, render_h = 3600, 2000
    y_top = door_outer + 2.0  # forward/aft callouts sit above the open doors
    y_bottom = -(door_outer + 1.5)  # length dimension
    cam_y = (y_top + y_bottom) / 2.0
    half_height_needed = (y_top - y_bottom) / 2.0

    x0 = meta["cx"] - meta["length"] / 2.0
    x1 = meta["cx"] + meta["length"] / 2.0
    x_left = x0 - 8.8  # legend margin
    x_right = x1 + 4.0  # aft callout + width dim
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
        width=door_outer * 2.0,
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
