#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build fusion-plant-skid top-down cutaway from assembly.json (Blender).

Frame: +X aft (station), +Y port, +Z up. Semi-circular skid (roof cut off,
like the cargo/airlock/crew-capsule drop-ins) carrying, fore to aft: flight
battery, p-\u00b9\u00b9B fuel tanks, then the CHARM reactor island itself (left
fusion chamber | heat-exchange chamber | right fusion chamber) with its
6 WHAM-anchored mirror magnets, 6-unit AL630-class cryo compressor bay,
Magnet PSU, RF racks, and DEC \u2014 flanked by clamshell bay doors swung open.

Magnet/cryo counts and masses are pulled live from `constants_model.py`
(the same numpy source that drives arxiv.md \u00a79.6 and assembly.json's
`mirror_magnets`/`cryocooler` nodes), so this figure can never numerically
disagree with the paper or the JSON single source of truth.

Run::

    /snap/bin/blender -b -P research/figures/cad/build_fusion_plant_skid_blender.py

Or::

    make cad-fusion-skid
"""

from __future__ import annotations

import sys
from pathlib import Path

import bpy

CAD_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CAD_DIR))

from constants_model import Params, compute  # noqa: E402
from lib.assembly_parser import find_node_in_doc, load_assembly  # noqa: E402
from lib.procedural_geometry import (  # noqa: E402
    box,
    callout,
    clamshell_bay_door,
    col,
    cylinder,
    dimension_line,
    legend,
    mat,
    tank,
    text_label,
)
from lib.render_utils import clear_scene, render_to, setup_topdown_camera  # noqa: E402

ROOT = CAD_DIR.parents[2]
FIGURES = ROOT / "research" / "figures"
ASSEMBLY_PATH = CAD_DIR / "assembly.json"
BLEND_OUT = CAD_DIR / "fusion_plant_skid_cutaway.blend"
PNG_OUT = FIGURES / "fusion_plant_skid_top.png"

SKID_WIDTH = 7.0  # m; not in assembly.json's fusion_plant_skid envelope (no width_m yet)


def build_fusion_plant_skid(asm: dict, gen: dict) -> dict:
    skid = find_node_in_doc(asm, "charm_skid")
    if not skid:
        raise SystemExit("charm_skid not found in assembly.json")

    env = skid["envelope"]
    x0 = float(env["x0"])
    x1 = float(env["x1"])
    width = SKID_WIDTH
    length = x1 - x0
    wall_h = 1.6
    floor_z = 0.0
    wall_t = 0.10
    y_half = width / 2.0

    n_coil = int(gen["charm.n_coil"])
    m_magnet_each_t = gen["charm.m_magnet_each_t"]
    m_magnets_t = gen["charm.m_magnets_t"]
    n_al630 = int(gen["charm.n_al630"])
    m_cryo_t = gen["charm.m_cryo_t"]
    p_cryo_kw = gen["charm.p_cryo_kw"]
    m_w_t = gen["mass.m_w_t"]
    shield_thickness_m = gen["shield.b1_thickness_m"]
    shield_mass_t = gen["shield.b1_mass_t"]

    scene_root = col("00_FusionPlantSkid")
    c_shell = col("01_Shell", scene_root)
    c_reactor = col("02_Reactor", scene_root)
    c_systems = col("03_Systems", scene_root)
    c_door = col("04_Doors", scene_root)
    c_lab = col("05_Labels", scene_root)
    c_lights = col("06_Lights", scene_root)

    m_shell = mat("fp_shell", (0.62, 0.64, 0.68), roughness=0.4)
    m_floor = mat("fp_floor", (0.35, 0.37, 0.40), roughness=0.7)
    m_door = mat("fp_door", (0.90, 0.91, 0.93), roughness=0.35)
    m_chamber = mat("fp_chamber", (0.90, 0.55, 0.45), roughness=0.4)
    m_hex = mat("fp_hex", (0.80, 0.42, 0.34), roughness=0.4)
    m_magnet = mat("fp_magnet", (0.30, 0.35, 0.75), roughness=0.35, metallic=0.15)
    m_cryo = mat("fp_cryo", (0.45, 0.80, 0.85), roughness=0.35)
    m_psu = mat("fp_psu", (0.90, 0.75, 0.30), roughness=0.4)
    m_rf = mat("fp_rf", (0.40, 0.75, 0.45), roughness=0.4)
    m_dec = mat("fp_dec", (0.85, 0.35, 0.55), roughness=0.4)
    m_fuel = mat("fp_fuel", (0.70, 0.65, 0.85), roughness=0.4)
    m_battery = mat("fp_battery", (0.55, 0.70, 0.55), roughness=0.4)
    m_water = mat("fp_water", (0.45, 0.65, 0.90), roughness=0.25, metallic=0.05)
    m_shield = mat("fp_shield", (0.88, 0.88, 0.80), roughness=0.55)

    cx = (x0 + x1) / 2.0

    # --- Skid floor + low rim rails ---
    box("Skid_Floor", (length, width, 0.08), (cx, 0.0, floor_z + 0.04), m_floor, c_shell)
    for name, y_sign in (("Skid_Rail_Port", 1.0), ("Skid_Rail_Stbd", -1.0)):
        box(
            name,
            (length, wall_t, wall_h),
            (cx, y_sign * (y_half - wall_t / 2.0), floor_z + wall_h / 2.0),
            m_shell,
            c_shell,
        )

    # --- Station layout along X: battery | water | fuel | reactor island
    # (§9.9: water relocated ahead of CHARM as a supplemental shield; the
    # island's own forward slice is the permanent shield bulkhead) ---
    battery_x0, battery_x1 = x0, x0 + 2.2
    water_x0, water_x1 = battery_x1, battery_x1 + 4.0
    fuel_x0, fuel_x1 = water_x1, water_x1 + 2.0
    island_x0, island_x1 = fuel_x1, x1

    # Forward slice of the island is the permanent shield bulkhead; the rest
    # is the actual chamber string + magnets/racks.
    shield_x0, shield_x1 = island_x0, island_x0 + shield_thickness_m
    reactor_x0, reactor_x1 = shield_x1, island_x1
    island_len = reactor_x1 - reactor_x0

    # Split the reactor span into left-fusion / HEX / right-fusion spans.
    lf_frac, hex_frac, rf_frac = 0.347, 0.306, 0.347
    lf_x0, lf_x1 = reactor_x0, reactor_x0 + island_len * lf_frac
    hex_x0, hex_x1 = lf_x1, lf_x1 + island_len * hex_frac
    rfc_x0, rfc_x1 = hex_x1, reactor_x1
    lf_cx, hex_cx, rfc_cx = (lf_x0 + lf_x1) / 2.0, (hex_x0 + hex_x1) / 2.0, (rfc_x0 + rfc_x1) / 2.0
    lf_r, hex_r, rfc_r = 1.1, 0.95, 1.1

    z_axis = floor_z + wall_h * 0.5

    # --- Flight battery ---
    battery_cx = (battery_x0 + battery_x1) / 2.0
    box(
        "Flight_Battery",
        (battery_x1 - battery_x0 - 0.3, width * 0.7, wall_h * 0.6),
        (battery_cx, 0.0, floor_z + wall_h * 0.3),
        m_battery,
        c_systems,
    )

    # --- Water tanks (space propellant, relocated ahead of CHARM as a
    # supplemental radiation shield when full, arxiv.md §9.9 B2) ---
    water_cx = (water_x0 + water_x1) / 2.0
    # Capped well below z_lab so the "WATER TANKS" label (on the centerline,
    # like the battery/fuel labels) never sits underneath the tank's own
    # top-down silhouette.
    water_r = min((water_x1 - water_x0) * 0.42, y_half * 0.42, 0.65)
    tank(
        "Water_Tank",
        water_r,
        water_x1 - water_x0 - 0.3,
        (water_cx, 0.0, z_axis),
        m_water,
        c_systems,
        axis="X",
    )

    # --- Permanent shield bulkhead (poly, §9.9 B1) — forward slice of the
    # CHARM envelope, spans almost the full skid width; holds even empty ---
    shield_cx = (shield_x0 + shield_x1) / 2.0
    box(
        "Shield_Bulkhead",
        (shield_x1 - shield_x0, width * 0.92, wall_h * 0.96),
        (shield_cx, 0.0, floor_z + wall_h * 0.48),
        m_shield,
        c_reactor,
    )

    # --- p-11B fuel tanks (proton + boron feed, side by side) ---
    fuel_cx = (fuel_x0 + fuel_x1) / 2.0
    tank_r = min((fuel_x1 - fuel_x0) * 0.42, 0.55)
    for name, y_sign in (("Fuel_Tank_Proton", 1.0), ("Fuel_Tank_Boron", -1.0)):
        tank(
            name,
            tank_r,
            fuel_x1 - fuel_x0 - 0.3,
            (fuel_cx, y_sign * (width * 0.22), z_axis),
            m_fuel,
            c_systems,
            axis="X",
        )

    # --- Chamber string: left fusion | heat exchange | right fusion ---
    cylinder("Left_Fusion_Chamber", lf_r, lf_x1 - lf_x0 - 0.15, (lf_cx, 0.0, z_axis), m_chamber, c_reactor, axis="X")
    cylinder("Heat_Exchange_Chamber", hex_r, hex_x1 - hex_x0 - 0.15, (hex_cx, 0.0, z_axis), m_hex, c_reactor, axis="X")
    cylinder("Right_Fusion_Chamber", rfc_r, rfc_x1 - rfc_x0 - 0.15, (rfc_cx, 0.0, z_axis), m_chamber, c_reactor, axis="X")

    # --- 6 mirror magnets (WHAM-anchored): 2 per fusion chamber (own mirror
    # pair) + 2 HEX shaping coils at its necks ---
    coil_positions = [
        lf_x0 + (lf_x1 - lf_x0) * 0.16,   # left-fusion outer (plug) end
        lf_x1 - (lf_x1 - lf_x0) * 0.10,   # left-fusion inner (HEX) neck
        hex_x0 + (hex_x1 - hex_x0) * 0.18,  # HEX left shaping coil
        hex_x1 - (hex_x1 - hex_x0) * 0.18,  # HEX right shaping coil
        rfc_x0 + (rfc_x1 - rfc_x0) * 0.10,  # right-fusion inner (HEX) neck
        rfc_x1 - (rfc_x1 - rfc_x0) * 0.16,  # right-fusion outer (plug) end
    ]
    coil_radii = [lf_r, lf_r, hex_r, hex_r, rfc_r, rfc_r]
    for i, (xc, rc) in enumerate(zip(coil_positions, coil_radii)):
        cylinder(f"Mirror_Magnet_{i + 1}", rc + 0.14, 0.22, (xc, 0.0, z_axis), m_magnet, c_reactor, axis="X")

    # --- RF racks at the two necks (launchers + amplifiers, simplified) ---
    rf_y = y_half * 0.55
    for i, xc in enumerate((coil_positions[1] + 0.15, coil_positions[4] - 0.15)):
        box(f"RF_Rack_{i + 1}", (0.7, 0.6, wall_h * 0.55), (xc, rf_y, floor_z + wall_h * 0.28), m_rf, c_systems)

    # --- DEC (alpha/charged-product collector), near the HEX ash face ---
    box("DEC", (1.1, 0.9, wall_h * 0.6), (hex_cx, y_half * 0.55, floor_z + wall_h * 0.3), m_dec, c_systems)

    # --- Magnet PSU bay (inner row, opposite RF/DEC side) ---
    psu_y = -y_half * 0.45
    box(
        "Magnet_PSU_Bay",
        (island_len * 0.55, 0.9, wall_h * 0.55),
        (reactor_x0 + island_len * 0.5, psu_y, floor_z + wall_h * 0.28),
        m_psu,
        c_systems,
    )

    # --- Cryo compressor bay: N_AL630 units in a row (outer row, same side as PSU) ---
    cryo_y = -y_half * 0.78
    cryo_x0 = reactor_x0 + 0.5
    cryo_x1 = reactor_x1 - 0.5
    cryo_step = (cryo_x1 - cryo_x0) / max(n_al630 - 1, 1)
    for i in range(n_al630):
        xc = cryo_x0 + i * cryo_step if n_al630 > 1 else (cryo_x0 + cryo_x1) / 2.0
        box(f"Cryocooler_{i + 1}", (0.7, 0.55, wall_h * 0.45), (xc, cryo_y, floor_z + wall_h * 0.22), m_cryo, c_systems)

    # --- Left/right clamshell bay doors, swung open about their roof-hinge lines ---
    panel_width = y_half * 0.95
    clamshell_bay_door(
        "Left_Plant_Door",
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
        "Right_Plant_Door",
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

    # --- Label rows: MUST stay within |y| < y_half. Anything beyond y_half
    # sits under the swung-open clamshell doors' XY footprint and gets
    # occluded by the door panel geometry at this z (the same failure mode
    # fixed for the cargo skid's tie-down callout) ---
    safe_y_top = y_half - 0.3
    safe_y_bot = -(y_half - 0.3)

    # Lettering sized for paper readability. Narrow forward stations get short
    # on-center names (long strings at this size would collide across bay
    # boundaries); detail lives in the callouts.
    text_label("LBL_battery", "BATTERY", (battery_cx, 0.0, z_lab), c_lab, size=0.36)
    text_label(
        "LBL_water",
        f"WATER\n{m_w_t:.0f} t",
        (water_cx, 0.0, z_lab),
        c_lab,
        size=0.36,
    )
    text_label("LBL_fuel", "FUEL", (fuel_cx, 0.0, z_lab), c_lab, size=0.36)

    callout(
        "CO_magnets",
        anchor_xyz=(coil_positions[2], hex_r + 0.14, 0.0),
        label_xyz=(lf_cx - 0.8, safe_y_top, 0.0),
        text=(
            f"Mirror magnets \u00d7{n_coil}\n"
            f"({m_magnets_t:.1f} t) \u2014 \u00a79.6"
        ),
        collection=c_lab,
        z=z_lab,
        text_size=0.34,
    )
    callout(
        "CO_rf_rack",
        anchor_xyz=(coil_positions[1] + 0.15, rf_y, 0.0),
        label_xyz=(hex_cx - 0.3, safe_y_top, 0.0),
        text="RF racks",
        collection=c_lab,
        z=z_lab,
        text_size=0.34,
    )
    callout(
        "CO_dec",
        anchor_xyz=(hex_cx, rf_y, 0.0),
        label_xyz=(rfc_cx + 0.5, safe_y_top, 0.0),
        text="DEC",
        collection=c_lab,
        z=z_lab,
        text_size=0.34,
    )

    callout(
        "CO_shield",
        anchor_xyz=(shield_cx, width * 0.46, 0.0),
        label_xyz=(fuel_cx - 1.2, safe_y_top - 0.05, 0.0),
        text=(
            f"Shield bulkhead\n"
            f"({shield_thickness_m:.2f} m, {shield_mass_t:.1f} t)"
        ),
        collection=c_lab,
        z=z_lab,
        text_size=0.32,
    )
    callout(
        "CO_lf",
        anchor_xyz=(lf_cx, -lf_r, 0.0),
        label_xyz=(island_x0 - 0.4, safe_y_bot, 0.0),
        text="Left fusion\nchamber",
        collection=c_lab,
        z=z_lab,
        text_size=0.34,
    )
    callout(
        "CO_cryo",
        anchor_xyz=(cryo_x0 + cryo_step, cryo_y, 0.0),
        label_xyz=(lf_cx + 0.7, safe_y_bot, 0.0),
        text=(
            f"Cryo \u00d7{n_al630} AL630\n"
            f"({m_cryo_t:.1f} t, {p_cryo_kw:.0f} kW)"
        ),
        collection=c_lab,
        z=z_lab,
        text_size=0.32,
    )
    callout(
        "CO_hex",
        anchor_xyz=(hex_cx, -hex_r, 0.0),
        label_xyz=(hex_cx + 1.1, safe_y_bot, 0.0),
        text="Heat-exchange\nchamber",
        collection=c_lab,
        z=z_lab,
        text_size=0.34,
    )
    callout(
        "CO_psu",
        anchor_xyz=(reactor_x0 + island_len * 0.5, psu_y, 0.0),
        label_xyz=(rfc_cx - 0.2, safe_y_bot, 0.0),
        text="Magnet\nPSU bay",
        collection=c_lab,
        z=z_lab,
        text_size=0.34,
    )
    callout(
        "CO_rf_chamber",
        anchor_xyz=(rfc_cx, -rfc_r, 0.0),
        label_xyz=(island_x1 + 1.1, safe_y_bot, 0.0),
        text="Right fusion\nchamber",
        collection=c_lab,
        z=z_lab,
        text_size=0.34,
    )

    dimension_line(
        "DIM_length",
        p0=(x0, -door_outer),
        p1=(x1, -door_outer),
        offset=-0.65,
        text=f"{length:.1f} m",
        collection=c_lab,
        z=z_lab,
        text_size=0.48,
        line_t=0.035,
    )
    dimension_line(
        "DIM_width",
        p0=(x1, -door_outer),
        p1=(x1, door_outer),
        offset=-2.6,
        text=f"{width:.1f} m",
        collection=c_lab,
        z=z_lab,
        text_size=0.48,
        line_t=0.035,
    )

    legend(
        [
            (m_battery, "Flight battery"),
            (m_water, "Water tanks (shield bonus)"),
            (m_shield, "Permanent shield bulkhead"),
            (m_fuel, "p-\u00b9\u00b9B fuel"),
            (m_chamber, "Fusion chambers"),
            (m_hex, "Heat-exchange chamber"),
            (m_magnet, "Mirror magnets (\u00d76)"),
            (m_cryo, f"Cryo compressors (\u00d7{n_al630})"),
            (m_psu, "Magnet PSU"),
            (m_rf, "RF racks"),
            (m_dec, "DEC"),
            (m_door, "Bay doors"),
        ],
        (x0 - 6.2, door_outer + 1.2, z_lab),
        c_lab,
        title="LEGEND",
        swatch=0.36,
        row_gap=0.58,
        label_dx=0.65,
        text_size=0.32,
    )

    return {
        "root": scene_root,
        "lights": c_lights,
        "length": length,
        "cx": cx,
        "door_outer": door_outer,
        "x0": x0,
        "x1": x1,
    }


def main() -> int:
    if not ASSEMBLY_PATH.is_file():
        print(f"missing {ASSEMBLY_PATH}", file=sys.stderr)
        return 1

    asm = load_assembly(ASSEMBLY_PATH)
    gen = compute(Params()).values
    print("==> clear scene / build fusion plant skid from assembly.json + constants_model.py")
    clear_scene()
    meta = build_fusion_plant_skid(asm, gen)

    door_outer = meta["door_outer"]
    render_w, render_h = 3600, 2000
    y_top = door_outer + 3.4  # legend margin (larger lettering)
    y_bottom = -(door_outer + 1.5)  # length dimension (no in-figure title)
    cam_y = (y_top + y_bottom) / 2.0
    half_height_needed = (y_top - y_bottom) / 2.0

    x_left = meta["x0"] - 8.0  # legend margin
    x_right = meta["x1"] + 4.2  # aft callouts + width dim
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
