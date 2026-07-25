#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build crew-capsule top-down cutaway from assembly.json (Blender).

Frame: +X aft (station), +Y port, +Z up. Open-top pressure vessel with
primitive interiors; orthographic top render for the paper.

Shared primitives, hatch/shell kits, and camera setup live in `lib/`
(shared with build_airlock_blender.py and build_cargo_skid_blender.py) —
this script only places crew-capsule-specific hardware.

Run::

    /snap/bin/blender -b -P research/figures/cad/build_crew_capsule_blender.py

Or::

    make cad-crew-capsule
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler

CAD_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CAD_DIR))

from lib.assembly_parser import find_node_in_doc, load_assembly  # noqa: E402
from lib.procedural_geometry import (  # noqa: E402
    box,
    callout,
    col,
    cylinder,
    dimension_line,
    import_glb_centered,
    legend,
    mat,
    text_label,
)
from lib.render_utils import clear_scene, render_to, setup_topdown_camera  # noqa: E402

ROOT = CAD_DIR.parents[2]
FIGURES = ROOT / "research" / "figures"
ASSEMBLY_PATH = CAD_DIR / "assembly.json"
BLEND_OUT = CAD_DIR / "crew_capsule_cutaway.blend"
PNG_OUT = FIGURES / "crew_capsule_top.png"
CREW_LOCK_BAG = CAD_DIR / "assets" / "nasa" / "crew_lock_bag.glb"


# ---------------------------------------------------------------------------
# Geometry from assembly.json
# ---------------------------------------------------------------------------


def build_crew_capsule(asm: dict) -> dict:
    capsule = find_node_in_doc(asm, "crew_capsule")
    if not capsule:
        raise SystemExit("crew_capsule not found in assembly.json")

    env = capsule["envelope"]
    x0 = float(env["x0"])
    x1 = float(env["x1"])
    width = float(env["width_m"])
    length = x1 - x0
    # Single-deck cutaway height (OML height_m is full stack; cabin clear ~2.4 m)
    wall_h = 2.4
    floor_z = 0.0
    y_half = width / 2.0
    wall_t = 0.08
    locker_d = 0.60
    aisle_half = 0.40

    scene_root = col("00_CrewCapsule")
    c_shell = col("01_Shell", scene_root)
    c_int = col("02_Interior", scene_root)
    c_hatch = col("03_Hatches", scene_root)
    c_lab = col("04_Labels", scene_root)
    c_roof = col("05_RoofCover", scene_root)
    c_lights = col("06_Lights", scene_root)

    m_shell = mat("shell", (0.90, 0.91, 0.93), roughness=0.35)
    m_floor = mat("floor", (0.35, 0.37, 0.40), roughness=0.7)
    m_seat = mat("seat", (0.12, 0.14, 0.18), roughness=0.55)
    m_locker = mat("locker", (0.78, 0.80, 0.84), roughness=0.45)
    m_sys = mat("systems", (0.25, 0.45, 0.35), roughness=0.4)
    m_tank = mat("tank", (0.20, 0.55, 0.30), roughness=0.7, metallic=0.05)
    m_food = mat("food", (0.85, 0.82, 0.70), roughness=0.5)
    m_wcs = mat("wcs", (0.75, 0.78, 0.82), roughness=0.4)
    m_hatch = mat("hatch", (0.55, 0.58, 0.62), roughness=0.65, metallic=0.05)
    m_rcs = mat("rcs", (0.15, 0.15, 0.17), roughness=0.65, metallic=0.05)
    m_panel = mat("panel", (0.10, 0.12, 0.18), roughness=0.25)

    # --- Floor (open top: no roof on vessel) ---
    cx = (x0 + x1) / 2.0
    box(
        "PV_Floor",
        (length, width, 0.06),
        (cx, 0.0, floor_z + 0.03),
        m_floor,
        c_shell,
    )

    # Side walls (port +Y, starboard -Y)
    for name, y_sign in (("PV_Wall_Port", 1.0), ("PV_Wall_Stbd", -1.0)):
        box(
            name,
            (length, wall_t, wall_h),
            (cx, y_sign * (y_half - wall_t / 2.0), floor_z + wall_h / 2.0),
            m_shell,
            c_shell,
        )

    # Nose bulkhead (forward, thin) + aft bulkhead
    box(
        "PV_Bulkhead_Fwd",
        (wall_t, width, wall_h),
        (x0 + wall_t / 2.0, 0.0, floor_z + wall_h / 2.0),
        m_shell,
        c_shell,
    )
    box(
        "PV_Bulkhead_Aft",
        (wall_t, width, wall_h),
        (x1 - wall_t / 2.0, 0.0, floor_z + wall_h / 2.0),
        m_shell,
        c_shell,
    )

    # Nose RCS pod (outside fwd of vessel tip)
    rcs = cylinder(
        "Forward_Steering_RCS",
        0.35,
        0.9,
        (x0 - 0.55, 0.0, floor_z + 1.1),
        m_rcs,
        c_shell,
        axis="X",
    )
    # Small thruster nubs
    for i, ang in enumerate((0.0, 0.7, 1.4, 2.1, 2.8, 3.5, 4.2, 4.9)):
        nub = cylinder(
            f"RCS_nub_{i}",
            0.06,
            0.15,
            (
                x0 - 0.95,
                0.25 * math.cos(ang),
                floor_z + 1.1 + 0.25 * math.sin(ang),
            ),
            m_rcs,
            c_shell,
            axis="X",
        )
        nub.parent = rcs

    # Instrument panel at nose (inside)
    box(
        "Glare_Shield",
        (0.25, 2.2, 0.9),
        (x0 + 0.55, 0.0, floor_z + 1.0),
        m_panel,
        c_int,
    )

    # Flight deck seats — open cabin, NO bulkhead behind
    seat_w, seat_d, seat_h = 0.55, 0.70, 1.05
    deck_x = x0 + 2.2
    for name, y in (("Captain_Chair", 0.55), ("Pilot_Chair", -0.55)):
        box(
            name,
            (seat_d, seat_w, seat_h),
            (deck_x, y, floor_z + seat_h / 2.0 + 0.03),
            m_seat,
            c_int,
        )

    # Six passenger seats: 3 rows × 2, facing forward (-X), clear aisle
    row_xs = [x0 + 4.6, x0 + 5.7, x0 + 6.8]
    for ri, rx in enumerate(row_xs):
        for si, y in enumerate((0.55, -0.55)):
            box(
                f"Passenger_Seat_r{ri}_s{si}",
                (seat_d, seat_w, seat_h),
                (rx, y, floor_z + seat_h / 2.0 + 0.03),
                m_seat,
                c_int,
            )

    # Deep luggage lockers along sidewalls (doors face aisle)
    locker_len = 5.5
    locker_x = x0 + 4.0 + locker_len / 2.0
    for name, y_sign in (("Luggage_Port", 1.0), ("Luggage_Stbd", -1.0)):
        y_c = y_sign * (y_half - wall_t - locker_d / 2.0)
        box(
            name,
            (locker_len, locker_d, 1.4),
            (locker_x, y_c, floor_z + 0.7 + 0.03),
            m_locker,
            c_int,
        )

    # Food stowage (pouches + warmer) — starboard aft, inside shell
    food_x = x0 + 9.0
    food_y = -(y_half - wall_t - 0.45)
    box(
        "Food_Pouch_Stowage",
        (1.2, 0.7, 0.9),
        (food_x, food_y, floor_z + 0.5),
        m_food,
        c_int,
    )
    box(
        "Food_Warmer",
        (0.45, 0.35, 0.25),
        (food_x + 0.9, food_y, floor_z + 0.35),
        m_panel,
        c_int,
    )
    if CREW_LOCK_BAG.is_file():
        import_glb_centered(
            CREW_LOCK_BAG,
            name="NASA_Crew_Lock_Bag",
            target_max_m=0.55,
            loc=(food_x - 0.45, food_y, floor_z + 0.35),
            collection=c_int,
        )
    else:
        print(f"warning: optional NASA asset missing: {CREW_LOCK_BAG}")

    # WCS — port aft, aisle access
    wcs_x = x0 + 9.0
    wcs_y = y_half - wall_t - 0.55
    box(
        "WCS_Enclosure",
        (1.0, 0.9, 1.6),
        (wcs_x, wcs_y, floor_z + 0.85),
        m_wcs,
        c_int,
    )
    cylinder(
        "WCS_Bowl",
        0.22,
        0.35,
        (wcs_x, wcs_y, floor_z + 0.45),
        m_shell,
        c_int,
        axis="Z",
    )

    # ECLSS + tanks inside aft corners (port systems, stbd tanks cluster)
    box(
        "ECLSS_Rack",
        (0.9, 0.7, 1.5),
        (x0 + 10.0, y_half - wall_t - 0.55, floor_z + 0.8),
        m_sys,
        c_int,
    )
    for i, dy in enumerate((-0.35, 0.0, 0.35)):
        cylinder(
            f"O2_tank_{i}",
            0.18,
            0.9,
            (x0 + 10.15, -y_half + wall_t + 0.55 + dy * 0.15, floor_z + 0.7),
            m_tank,
            c_int,
            axis="Z",
        )
    for i, dy in enumerate((-0.25, 0.25)):
        cylinder(
            f"N2_tank_{i}",
            0.16,
            0.85,
            (x0 + 10.55, -y_half + wall_t + 0.9 + dy, floor_z + 0.65),
            mat("tank_n2", (0.65, 0.68, 0.72), roughness=0.7, metallic=0.05),
            c_int,
            axis="Z",
        )

    # --- Earth side hatch (port wall): vertical door, ajar into cabin ---
    hatch_x = 6.5  # matches assembly side_hatch_port xyz
    door_w, door_h, door_t = 0.9, 1.7, 0.06
    # Closed pose would sit in the port wall; rotate ~40° about Z into cabin
    earth = box(
        "Earth_Side_Hatch_Door",
        (door_w, door_t, door_h),
        (hatch_x, y_half - wall_t - door_t / 2.0 - 0.15, floor_z + door_h / 2.0 + 0.15),
        m_hatch,
        c_hatch,
    )
    earth.rotation_euler = Euler((0.0, 0.0, -math.radians(40.0)), "XYZ")

    box(
        "Earth_Hatch_Frame",
        (door_w + 0.12, wall_t + 0.04, door_h + 0.12),
        (hatch_x, y_half - wall_t / 2.0, floor_z + door_h / 2.0 + 0.15),
        m_hatch,
        c_hatch,
    )

    # --- Aft pressure hatch: vertical door in aft bulkhead, ajar into cabin ---
    aft_door_r = 0.55
    aft = box(
        "Aft_Airlock_Hatch_Door",
        (door_t, aft_door_r * 2.0, aft_door_r * 2.0),
        (x1 - wall_t - 0.35, 0.35, floor_z + 1.15),
        m_hatch,
        c_hatch,
    )
    aft.rotation_euler = Euler((0.0, 0.0, math.radians(55.0)), "XYZ")

    cylinder(
        "Aft_Hatch_Frame",
        aft_door_r + 0.08,
        wall_t + 0.06,
        (x1 - wall_t / 2.0, 0.0, floor_z + 1.15),
        m_hatch,
        c_hatch,
        axis="X",
    )

    # Roof cover — same plan footprint as capsule, parked beside (starboard)
    cover_y = -(y_half + width * 0.65)
    box(
        "Roof_Cover",
        (length, width, 0.12),
        (cx, cover_y, floor_z + 0.06),
        m_shell,
        c_roof,
    )
    # Nose taper hint on cover
    box(
        "Roof_Cover_Nose",
        (1.2, width * 0.55, 0.12),
        (x0 + 0.4, cover_y, floor_z + 0.06),
        m_shell,
        c_roof,
    )

    # Leader-line callouts (dot on the part, line out to readable text) instead
    # of bare floating labels — keeps each label visibly tied to its part.
    z_lab = wall_h + 0.05
    callout(
        "CO_rcs",
        anchor_xyz=(x0 - 0.55, 0.0, 0.0),
        label_xyz=(x0 - 1.0, 1.9, 0.0),
        text="Forward RCS",
        collection=c_lab,
        z=z_lab,
        text_size=0.15,
    )
    callout(
        "CO_cdr",
        anchor_xyz=(deck_x, 0.55, 0.0),
        label_xyz=(deck_x, 1.5, 0.0),
        text="CDR",
        collection=c_lab,
        z=z_lab,
        text_size=0.13,
    )
    callout(
        "CO_plt",
        anchor_xyz=(deck_x, -0.55, 0.0),
        label_xyz=(deck_x, -1.5, 0.0),
        text="PLT",
        collection=c_lab,
        z=z_lab,
        text_size=0.13,
    )
    text_label("LBL_pax", "6 passenger seats", (row_xs[1], 1.55, z_lab), c_lab, size=0.15)
    callout(
        "CO_earth",
        anchor_xyz=(hatch_x, y_half, 0.0),
        label_xyz=(hatch_x, y_half + 0.9, 0.0),
        text="Earth hatch",
        collection=c_lab,
        z=z_lab,
        text_size=0.14,
    )
    callout(
        "CO_aft",
        anchor_xyz=(x1, 0.35, 0.0),
        label_xyz=(x1 + 0.7, 1.4, 0.0),
        text="Aft hatch → airlock",
        collection=c_lab,
        z=z_lab,
        text_size=0.13,
    )
    callout(
        "CO_food",
        anchor_xyz=(food_x, food_y, 0.0),
        label_xyz=(food_x, food_y - 1.1, 0.0),
        text="Food pouches + warmer",
        collection=c_lab,
        z=z_lab,
        text_size=0.12,
    )
    callout(
        "CO_wcs",
        anchor_xyz=(wcs_x, wcs_y, 0.0),
        label_xyz=(wcs_x - 0.7, wcs_y + 0.55, 0.0),
        text="WCS",
        collection=c_lab,
        z=z_lab,
        text_size=0.13,
    )
    callout(
        "CO_eclss",
        anchor_xyz=(x0 + 10.2, -y_half + 0.6, 0.0),
        label_xyz=(x0 + 10.2, -y_half - 0.55, 0.0),
        text="ECLSS + O2/N2",
        collection=c_lab,
        z=z_lab,
        text_size=0.12,
    )
    callout(
        "CO_lock",
        anchor_xyz=(locker_x, -(y_half - wall_t - locker_d / 2.0), 0.0),
        label_xyz=(locker_x, -y_half - 0.55, 0.0),
        text="Luggage 0.6 m deep",
        collection=c_lab,
        z=z_lab,
        text_size=0.12,
    )
    text_label("LBL_roof", "Roof cover (same footprint)", (cx, cover_y - 0.55, z_lab), c_lab, size=0.14)
    text_label(
        "LBL_title",
        "CREW CAPSULE (assembly.json)",
        (cx, cover_y - width * 0.55, z_lab),
        c_lab,
        size=0.26,
    )

    # Dimension lines: length along the top, width ahead of the nose.
    dimension_line(
        "DIM_length",
        p0=(x0, y_half),
        p1=(x1, y_half),
        offset=1.1,
        text=f"{length:.1f} m",
        collection=c_lab,
        z=z_lab,
        text_size=0.18,
    )
    dimension_line(
        "DIM_width",
        p0=(x0, -y_half),
        p1=(x0, y_half),
        offset=1.8,
        text=f"{width:.1f} m",
        collection=c_lab,
        z=z_lab,
        text_size=0.18,
    )

    # Subsystem color legend, clear of the vessel in the left margin.
    legend(
        [
            (m_shell, "Structure / shell"),
            (m_hatch, "Hatches"),
            (m_seat, "Seats"),
            (m_locker, "Stowage / luggage"),
            (m_sys, "ECLSS systems"),
            (m_tank, "Gas tanks"),
        ],
        (x0 - 5.4, 1.2, z_lab),
        c_lab,
        title="LEGEND",
    )

    # Keep aisle visually empty (no geometry in |Y| < aisle_half for furniture)
    _ = aisle_half

    return {
        "root": scene_root,
        "shell": c_shell,
        "int": c_int,
        "hatch": c_hatch,
        "lab": c_lab,
        "roof": c_roof,
        "lights": c_lights,
        "length": length,
        "width": width,
        "cx": cx,
        "wall_h": wall_h,
        "y_half": y_half,
        "cover_y": cover_y,
    }


def main() -> int:
    if not ASSEMBLY_PATH.is_file():
        print(f"missing {ASSEMBLY_PATH}", file=sys.stderr)
        return 1

    asm = load_assembly(ASSEMBLY_PATH)
    print("==> clear scene / build crew capsule from assembly.json")
    clear_scene()
    meta = build_crew_capsule(asm)

    # Composition is asymmetric in both axes (legend in the left margin,
    # dimension lines above, parked roof cover + title well below; camera x
    # is pinned to cx), so fit content bounds explicitly.
    render_w, render_h = 3200, 2000
    y_top = meta["y_half"] + 1.5
    y_bottom = meta["cover_y"] - meta["width"] * 0.55 - 0.3
    cam_y = (y_top + y_bottom) / 2.0
    half_height_needed = (y_top - y_bottom) / 2.0

    x0 = meta["cx"] - meta["length"] / 2.0
    x1 = meta["cx"] + meta["length"] / 2.0
    x_left = x0 - 5.7  # legend origin (x0 - 5.4) minus swatch/text margin
    x_right = x1 + 1.8  # aft-hatch callout label margin
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
