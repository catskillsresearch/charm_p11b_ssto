#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build crew-capsule top-down cutaway from assembly.json (Blender).

Frame: +X aft (station), +Y port, +Z up. Open-top pressure vessel with
primitive interiors; orthographic top render for the paper.

Run::

    /snap/bin/blender -b -P research/figures/cad/build_crew_capsule_blender.py

Or::

    make cad-crew-capsule
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Vector

CAD_DIR = Path(__file__).resolve().parent
ROOT = CAD_DIR.parents[2]
FIGURES = ROOT / "research" / "figures"
ASSEMBLY_PATH = CAD_DIR / "assembly.json"
BLEND_OUT = CAD_DIR / "crew_capsule_cutaway.blend"
PNG_OUT = FIGURES / "crew_capsule_top.png"
CREW_LOCK_BAG = CAD_DIR / "assets" / "nasa" / "crew_lock_bag.glb"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def col(name: str, parent: bpy.types.Collection | None = None) -> bpy.types.Collection:
    existing = bpy.data.collections.get(name)
    if existing:
        return existing
    c = bpy.data.collections.new(name)
    if parent is not None:
        parent.children.link(c)
    else:
        bpy.context.scene.collection.children.link(c)
    return c


def to_col(ob: bpy.types.Object, collection: bpy.types.Collection) -> bpy.types.Object:
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    collection.objects.link(ob)
    return ob


def mat(name: str, color, *, roughness=0.45, metallic=0.05) -> bpy.types.Material:
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name=name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
    return m


def assign(ob: bpy.types.Object, material: bpy.types.Material) -> None:
    if ob.data and hasattr(ob.data, "materials"):
        if ob.data.materials:
            ob.data.materials[0] = material
        else:
            ob.data.materials.append(material)


def box(
    name: str,
    size: tuple[float, float, float],
    loc: tuple[float, float, float],
    material: bpy.types.Material,
    collection: bpy.types.Collection,
    *,
    parent: bpy.types.Object | None = None,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign(ob, material)
    to_col(ob, collection)
    if parent is not None:
        ob.parent = parent
    return ob


def cylinder(
    name: str,
    radius: float,
    depth: float,
    loc: tuple[float, float, float],
    material: bpy.types.Material,
    collection: bpy.types.Collection,
    *,
    axis: str = "Z",
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=loc, vertices=24)
    ob = bpy.context.active_object
    ob.name = name
    if axis == "X":
        ob.rotation_euler = (0.0, math.pi / 2.0, 0.0)
    elif axis == "Y":
        ob.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    assign(ob, material)
    to_col(ob, collection)
    return ob


def text_label(
    name: str,
    body: str,
    loc: tuple[float, float, float],
    collection: bpy.types.Collection,
    *,
    size: float = 0.18,
) -> bpy.types.Object:
    curve = bpy.data.curves.new(name=name, type="FONT")
    curve.body = body
    curve.size = size
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    ob = bpy.data.objects.new(name, curve)
    ob.location = loc
    ob.rotation_euler = (0.0, 0.0, 0.0)  # flat on XY for top view
    to_col(ob, collection)
    assign(ob, mat("label_ink", (0.05, 0.05, 0.08), roughness=0.9))
    return ob


def find_node(root: dict, nid: str) -> dict | None:
    if root.get("id") == nid:
        return root
    for c in root.get("children") or []:
        hit = find_node(c, nid)
        if hit:
            return hit
    return None


def set_engine(scene: bpy.types.Scene) -> None:
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "EEVEE"):
        try:
            scene.render.engine = eng
            return
        except TypeError:
            continue


def render_to(cam: bpy.types.Object, path: Path, *, width: int, height: int) -> None:
    scene = bpy.context.scene
    scene.camera = cam
    set_engine(scene)
    scene.render.use_freestyle = False
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.render.filepath = str(path.with_suffix(""))
    bpy.ops.render.render(write_still=True)
    print(f"wrote {path} ({path.stat().st_size} bytes)")


def import_glb_centered(
    path: Path,
    *,
    name: str,
    target_max_m: float,
    loc: tuple[float, float, float],
    collection: bpy.types.Collection,
) -> bpy.types.Object:
    """Import a GLB and normalize its largest extent for placement."""
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    imported = list(set(bpy.context.scene.objects) - before)
    if not imported:
        raise RuntimeError(f"Blender imported no objects from {path}")

    bpy.context.view_layer.update()
    corners = [
        ob.matrix_world @ Vector(corner)
        for ob in imported
        if ob.type == "MESH"
        for corner in ob.bound_box
    ]
    if not corners:
        raise RuntimeError(f"No mesh geometry in {path}")

    lo = Vector((min(c[i] for c in corners) for i in range(3)))
    hi = Vector((max(c[i] for c in corners) for i in range(3)))
    extent = hi - lo
    scale = target_max_m / max(extent)
    center = (lo + hi) / 2.0

    root = bpy.data.objects.new(name, None)
    collection.objects.link(root)
    root.location = Vector(loc) - center * scale
    root.scale = (scale, scale, scale)
    for ob in imported:
        ob.parent = root
    return root


# ---------------------------------------------------------------------------
# Geometry from assembly.json
# ---------------------------------------------------------------------------


def build_crew_capsule(asm: dict) -> dict[str, bpy.types.Collection]:
    root = asm["root"] if "root" in asm else asm
    capsule = find_node(root, "crew_capsule")
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
    m_tank = mat("tank", (0.20, 0.55, 0.30), roughness=0.35, metallic=0.2)
    m_food = mat("food", (0.85, 0.82, 0.70), roughness=0.5)
    m_wcs = mat("wcs", (0.75, 0.78, 0.82), roughness=0.4)
    m_hatch = mat("hatch", (0.55, 0.58, 0.62), roughness=0.3, metallic=0.35)
    m_rcs = mat("rcs", (0.15, 0.15, 0.17), roughness=0.4, metallic=0.5)
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
            mat("tank_n2", (0.65, 0.68, 0.72), roughness=0.35, metallic=0.25),
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

    # Labels (flat text, readable in top ortho)
    z_lab = wall_h + 0.05
    labels = [
        ("LBL_title", "CREW CAPSULE (assembly.json)", (cx, cover_y - 1.2, z_lab), 0.28),
        ("LBL_rcs", "Forward RCS", (x0 - 0.3, 1.6, z_lab), 0.16),
        ("LBL_cdr", "CDR", (deck_x, 1.3, z_lab), 0.14),
        ("LBL_plt", "PLT", (deck_x, -1.3, z_lab), 0.14),
        ("LBL_pax", "6 passenger seats", (x0 + 5.7, 1.55, z_lab), 0.15),
        ("LBL_earth", "Earth hatch", (hatch_x, y_half + 0.7, z_lab), 0.14),
        ("LBL_aft", "Aft hatch → airlock", (x1 + 0.15, 1.4, z_lab), 0.13),
        ("LBL_food", "Food pouches + warmer", (food_x, food_y - 1.05, z_lab), 0.12),
        ("LBL_wcs", "WCS", (wcs_x - 0.2, wcs_y + 1.0, z_lab), 0.12),
        ("LBL_eclss", "ECLSS + O2/N2", (x0 + 10.0, -1.6, z_lab), 0.12),
        ("LBL_lock", "Luggage 0.6 m deep", (locker_x, -y_half - 0.55, z_lab), 0.12),
        ("LBL_roof", "Roof cover (same footprint)", (cx, cover_y - 0.55, z_lab), 0.14),
        ("LBL_dim", f"{length:.1f} m × {width:.1f} m", (cx, y_half + 1.25, z_lab), 0.18),
    ]
    for name, body, loc, sz in labels:
        text_label(name, body, loc, c_lab, size=sz)

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
    }


def setup_view(meta: dict) -> bpy.types.Object:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.88, 0.89, 0.91, 1.0)
    bg.inputs[1].default_value = 1.0

    bpy.ops.object.light_add(type="SUN", location=(meta["cx"], -4.0, 40.0))
    sun = bpy.context.active_object
    sun.name = "Sun"
    sun.data.energy = 3.5
    sun.rotation_euler = (0.3, 0.2, 0.1)
    to_col(sun, meta["lights"])

    bpy.ops.object.light_add(type="AREA", location=(meta["cx"], 0.0, 25.0))
    area = bpy.context.active_object
    area.name = "Fill"
    area.data.energy = 800
    area.data.size = 40
    to_col(area, meta["lights"])

    data = bpy.data.cameras.new("Cam_Top")
    data.type = "ORTHO"
    # Fit length + parked roof cover
    data.ortho_scale = max(meta["length"] * 1.35, meta["width"] * 3.2)
    cam = bpy.data.objects.new("Cam_Top", data)
    cam.location = (meta["cx"], -meta["width"] * 0.35, 40.0)
    cam.rotation_euler = (0.0, 0.0, 0.0)  # look down -Z? Blender cam looks -Z local
    # Camera default looks along local -Z; with rot 0 at high Z looking down works
    to_col(cam, meta["root"])
    return cam


def main() -> int:
    if not ASSEMBLY_PATH.is_file():
        print(f"missing {ASSEMBLY_PATH}", file=sys.stderr)
        return 1

    asm = json.loads(ASSEMBLY_PATH.read_text(encoding="utf-8"))
    print("==> clear scene / build crew capsule from assembly.json")
    clear_scene()
    meta = build_crew_capsule(asm)
    cam = setup_view(meta)

    FIGURES.mkdir(parents=True, exist_ok=True)
    print("==> render top-down")
    render_to(cam, PNG_OUT, width=3200, height=2000)

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
