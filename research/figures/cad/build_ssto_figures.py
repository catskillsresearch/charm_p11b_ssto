#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build CATSKILLS-SSTO figures from a real Shuttle orbiter base.

Pipeline: import FlightGear ``shuttle_o2.ac`` → orient to (+X aft, +Y port, +Z up)
→ piecewise nose-biased stretch to ``stations.json`` → graft aft plant markers →
ortho floorplan + profile.

Open interactively::

    /snap/bin/blender research/figures/cad/catskills_ssto.blend

Rebuild::

    make cad-figures
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

CAD_DIR = Path(__file__).resolve().parent
ROOT = CAD_DIR.parents[2]
FIGURES = ROOT / "research" / "figures"
STATIONS_PATH = CAD_DIR / "stations.json"
BLEND_OUT = CAD_DIR / "catskills_ssto.blend"
CACHE_DIR = CAD_DIR / "cache"
ORBITER_CACHE = CACHE_DIR / "shuttle_o2_base.blend"
GEAR_CACHE = CACHE_DIR / "shuttle_landing_gears.blend"

AIRCRAFT = Path("/home/catskills/Desktop/Aircraft/CatskillsFusionSSTO")
SHUTTLE_AC = AIRCRAFT / "Models" / "shuttle_o2.ac"
LANDING_GEARS_AC = AIRCRAFT / "Models" / "LandingGears.ac"
SSME_AC = AIRCRAFT / "Models" / "SSME.ac"

sys.path.insert(0, str(CAD_DIR))
from import_ac3d import import_ac3d  # noqa: E402


# ---------------------------------------------------------------------------
# Scene / collection helpers
# ---------------------------------------------------------------------------


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def col(name: str, parent: bpy.types.Collection | None = None, *, link_to_scene: bool = False) -> bpy.types.Collection:
    existing = bpy.data.collections.get(name)
    if existing:
        return existing
    c = bpy.data.collections.new(name)
    if parent is not None:
        parent.children.link(c)
    elif link_to_scene:
        bpy.context.scene.collection.children.link(c)
    return c


def empty(name: str, collection: bpy.types.Collection, loc=(0.0, 0.0, 0.0), size=1.0) -> bpy.types.Object:
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = "PLAIN_AXES"
    ob.empty_display_size = size
    ob.location = loc
    collection.objects.link(ob)
    return ob


def to_col(ob: bpy.types.Object, collection: bpy.types.Collection) -> bpy.types.Object:
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    collection.objects.link(ob)
    return ob


def set_hide(collection: bpy.types.Collection, hide: bool) -> None:
    collection.hide_render = hide
    collection.hide_viewport = hide


def mat(name: str, color, *, roughness=0.4, metallic=0.05) -> bpy.types.Material:
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


def assign(ob, material) -> None:
    if ob.data and hasattr(ob.data, "materials"):
        if ob.data.materials:
            ob.data.materials[0] = material
        else:
            ob.data.materials.append(material)


def box(name, size, loc, material, collection, *, parent=None) -> bpy.types.Object:
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


def cylinder(name, radius, depth, loc, material, collection, *, axis="Z", parent=None) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=loc, vertices=32)
    ob = bpy.context.active_object
    ob.name = name
    if axis == "X":
        ob.rotation_euler = (0.0, math.pi / 2, 0.0)
    elif axis == "Y":
        ob.rotation_euler = (math.pi / 2, 0.0, 0.0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    assign(ob, material)
    to_col(ob, collection)
    if parent is not None:
        ob.parent = parent
    return ob


def label_mesh(name, body, loc, collection, *, size=0.5, rot=(0, 0, 0), parent=None, color=(0.0, 0.0, 0.0)) -> bpy.types.Object:
    curve = bpy.data.curves.new(name + "_curve", type="FONT")
    curve.body = body
    curve.size = size
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.extrude = 0.02
    ob = bpy.data.objects.new(name, curve)
    ob.location = loc
    ob.rotation_euler = rot
    collection.objects.link(ob)
    assign(ob, mat(f"{name}_mat", color, roughness=0.95))
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.convert(target="MESH")
    ob = bpy.context.active_object
    ob.name = name
    if parent is not None:
        ob.parent = parent
    return ob


def world_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    for o in objects:
        if o.type != "MESH":
            continue
        for corner in o.bound_box:
            w = o.matrix_world @ Vector(corner)
            mn = Vector((min(mn.x, w.x), min(mn.y, w.y), min(mn.z, w.z)))
            mx = Vector((max(mx.x, w.x), max(mx.y, w.y), max(mx.z, w.z)))
    return mn, mx


# ---------------------------------------------------------------------------
# Hierarchy
# ---------------------------------------------------------------------------


def build_hierarchy() -> dict[str, bpy.types.Collection]:
    root = col("CATSKILLS_SSTO", link_to_scene=True)
    base = col("00_Base_Orbiter", root)
    rig = col("00_Deform_Rig", root)
    ref = col("00_Reference_Assets", root)
    edits = col("01_Exterior_Edits", root)
    gear = col("02_Landing_Gear", root)
    interior = col("03_Interior", root)
    ann = col("04_Annotations", root)
    return {
        "root": root,
        "base": base,
        "rig": rig,
        "ref": ref,
        "ref_gear": col("00b_Shuttle_LandingGears", ref),
        "ref_ssme": col("00c_Shuttle_SSME", ref),
        "edits": edits,
        "aft": col("01a_Aft_Plant_Graft", edits),
        "gear": gear,
        "gear_nose": col("02a_Nose_Gear", gear),
        "gear_main": col("02b_Main_Gear", gear),
        "int": interior,
        "crew": col("03a_Crew_ECLSS", interior),
        "airlock": col("03b_Airlock", interior),
        "cargo": col("03c_Cargo_Bay", interior),
        "batt": col("03d_Flight_Battery", interior),
        "fuel": col("03e_Fuel", interior),
        "charm": col("03f_CHARM", interior),
        "water": col("03g_Water", interior),
        "engbay": col("03h_Engine_Bay", interior),
        "ann": ann,
        "lab_top": col("04a_Labels_Floorplan", ann),
        "lab_side": col("04b_Labels_Profile", ann),
        "dims": col("04c_Dimensions", ann),
        "cams": col("05_Cameras", root),
        "lights": col("06_Lights", root),
    }


# ---------------------------------------------------------------------------
# Import / orient / deform
# ---------------------------------------------------------------------------


def ensure_orbiter_cache() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if ORBITER_CACHE.is_file() and ORBITER_CACHE.stat().st_mtime >= SHUTTLE_AC.stat().st_mtime:
        return ORBITER_CACHE
    bpy.ops.wm.read_factory_settings(use_empty=True)
    c = bpy.data.collections.new("OrbiterCache")
    bpy.context.scene.collection.children.link(c)
    import_ac3d(SHUTTLE_AC, collection=c, name_prefix="ORB_")
    bpy.ops.wm.save_as_mainfile(filepath=str(ORBITER_CACHE.resolve()))
    print(f"cached orbiter → {ORBITER_CACHE}")
    return ORBITER_CACHE


def append_orbiter(collection: bpy.types.Collection) -> bpy.types.Object:
    """Append cached orbiter meshes into collection; return root empty."""
    ensure_orbiter_cache()
    # Fresh scene assumed by caller
    with bpy.data.libraries.load(str(ORBITER_CACHE), link=False) as (data_from, data_to):
        data_to.objects = [n for n in data_from.objects if n.startswith("ORB_")]
    root = empty("EMPTY_Orbiter_Root", collection, size=3.0)
    for ob in data_to.objects:
        if ob is None:
            continue
        to_col(ob, collection)
        if ob.parent is None:
            ob.parent = root
        elif ob.parent.name not in {o.name for o in data_to.objects if o}:
            ob.parent = root
    return root


def orient_orbiter_to_vehicle_frame(root: bpy.types.Object, mesh_objs: list[bpy.types.Object]) -> tuple[float, float, float]:
    """AC file: +X length, +Y up-ish, +Z span → Blender: +X aft, +Y port, +Z up.

    Returns (length, span, height) with nose at X≈0.
    """
    # Detach, apply existing transforms, then explicit axis remap on verts
    for o in mesh_objs:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Remap: (x, y, z)_ac → (x, -z, y)_blender  so span→Y, up→Z
    for o in mesh_objs:
        mesh = o.data
        for v in mesh.vertices:
            x, y, z = v.co
            v.co = Vector((x, -z, y))
        mesh.update()

    bpy.context.view_layer.update()
    mn, mx = world_bounds(mesh_objs)
    # If height > span, axes still wrong — swap Y/Z
    if (mx.z - mn.z) > (mx.y - mn.y) * 1.2:
        for o in mesh_objs:
            mesh = o.data
            for v in mesh.vertices:
                x, y, z = v.co
                v.co = Vector((x, z, -y))
            mesh.update()
        bpy.context.view_layer.update()
        mn, mx = world_bounds(mesh_objs)

    # Nose at X=0, center Y, belly at Z=0
    dx, dy, dz = -mn.x, -(mn.y + mx.y) * 0.5, -mn.z
    for o in mesh_objs:
        mesh = o.data
        for v in mesh.vertices:
            v.co += Vector((dx, dy, dz))
        mesh.update()
        o.parent = root
        o.location = (0, 0, 0)
        o.rotation_euler = (0, 0, 0)
        o.scale = (1, 1, 1)

    bpy.context.view_layer.update()
    mn, mx = world_bounds(mesh_objs)
    length = mx.x - mn.x
    span = mx.y - mn.y
    height = mx.z - mn.z
    print(f"oriented orbiter L={length:.2f} span={span:.2f} H={height:.2f}  boundsX=[{mn.x:.1f},{mx.x:.1f}]")
    return length, span, height


def piecewise_map(x: float, src: list[float], dst: list[float]) -> float:
    """Map x through piecewise-linear breakpoints (src → dst), same length."""
    if x <= src[0]:
        return dst[0]
    if x >= src[-1]:
        return dst[-1]
    for i in range(len(src) - 1):
        if src[i] <= x <= src[i + 1]:
            t = (x - src[i]) / max(src[i + 1] - src[i], 1e-9)
            return dst[i] + t * (dst[i + 1] - dst[i])
    return dst[-1]


def deform_orbiter_to_stations(
    mesh_objs: list[bpy.types.Object],
    *,
    L0: float,
    span0: float,
    cfg: dict,
    rig_col: bpy.types.Collection,
    root: bpy.types.Object,
) -> None:
    """Nose-biased stretch along X to target stations; mild span scale to wingspan_m."""
    L1 = cfg["length_m"]
    span1 = cfg["wingspan_m"]
    stations = cfg["stations"]

    # Source breakpoints as fractions of original orbiter length (Shuttle-like layout)
    src_frac = [0.0, 0.22, 0.30, 0.79, 0.84, 0.88, 0.94, 0.97, 1.0]
    src = [f * L0 for f in src_frac]
    dst = [0.0] + [s["x1"] for s in stations]
    # stations x1: 11,15,33.3,35.5,37.5,45,49,52 — 8 values + 0 = 9 points
    assert len(src) == len(dst), (len(src), len(dst), dst)

    span_scale = span1 / max(span0, 1e-6)

    # Station empties (deform-rig visualization / muteable)
    for i, (sx, dx) in enumerate(zip(src, dst)):
        e = empty(f"STATION_{i:02d}_{dx:.1f}m", rig_col, loc=(dx, 0, 8.0), size=0.6)
        e.parent = root
        e["src_x"] = sx
        e["dst_x"] = dx

    # Lattice for documentation / further hand edits (also applies mild deformation aid)
    bpy.ops.object.add(type="LATTICE", location=(L1 * 0.5, 0.0, height_guess(mesh_objs) * 0.5))
    lat_ob = bpy.context.active_object
    lat_ob.name = "LATTICE_StationStretch"
    lat = lat_ob.data
    lat.points_u = 9
    lat.points_v = 3
    lat.points_w = 3
    # Size lattice to target bbox
    lat_ob.scale = (L1 * 0.55, span1 * 0.55, 6.0)
    to_col(lat_ob, rig_col)
    lat_ob.parent = root

    # Direct vertex remap (authoritative). Skip speedbrake/rudder — stretched into a giant fin.
    skip_x_stretch = {"ORB_SpeedBrakeL", "ORB_SpeedBrakeR"}
    for o in mesh_objs:
        if o.type != "MESH":
            continue
        mesh = o.data
        if o.name in skip_x_stretch:
            # Span-scale only; leave X for later reposition onto new aft
            for v in mesh.vertices:
                v.co = Vector((v.co.x, v.co.y * span_scale, v.co.z))
        else:
            for v in mesh.vertices:
                co = v.co
                new_x = piecewise_map(co.x, src, dst)
                new_y = co.y * span_scale
                v.co = Vector((new_x, new_y, co.z))
        mesh.update()

    print(f"deformed orbiter → L={L1} m, span≈{span1} m (piecewise nose-biased)")


def _delete_verts_aft_engines_and_noodle(obj: bpy.types.Object, *, engine_x: float, tip_x: float, half_width: float) -> int:
    """Remove old SSME face (centerline aft) and stretched aft noodle tip."""
    import bmesh

    mw = obj.matrix_world
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    doomed = []
    for v in bm.verts:
        w = mw @ v.co
        # Stretched tip past real structure
        if w.x > tip_x:
            doomed.append(v)
        # Old engine bulkhead on centerbody (keep wings outboard)
        elif w.x > engine_x and abs(w.y) < half_width:
            doomed.append(v)
    n = len(doomed)
    if doomed:
        bmesh.ops.delete(bm, geom=doomed, context="VERTS")
        bm.to_mesh(obj.data)
        obj.data.update()
    bm.free()
    return n


def rebuild_sensible_aft(tree, cfg, root_empty) -> None:
    """Cut stretched aft noodle + old SSME face; add real aft hull; tame vertical fin."""
    W = cfg["fuselage_width_m"]
    H = cfg["fuselage_height_m"]
    cargo_end = next(s["x1"] for s in cfg["stations"] if s["id"] == "cargo")
    L = cfg["length_m"]
    # Keep wing structure; carve only centerbody aft of cargo + delete noodle tip
    engine_x = cargo_end - 0.5  # ~32.8
    tip_x = 40.0
    half_w = 4.2

    fuse = bpy.data.objects.get("ORB_fuselage")
    if fuse:
        n = _delete_verts_aft_engines_and_noodle(fuse, engine_x=engine_x, tip_x=tip_x, half_width=half_w)
        print(f"cut ORB_fuselage aft engines/noodle (removed {n} verts) — old SSME mounts gone")

    # Body flap was the flat 'skid' plate under old engines — remove
    flap = bpy.data.objects.get("ORB_BodyFlap")
    if flap:
        bpy.data.objects.remove(flap, do_unlink=True)

    # Old speedbrakes became a 14 m fin — remove and replace
    for name in ("ORB_SpeedBrakeL", "ORB_SpeedBrakeR"):
        ob = bpy.data.objects.get(name)
        if ob:
            bpy.data.objects.remove(ob, do_unlink=True)

    m_skin = mat("aft_skin", (0.88, 0.89, 0.91), roughness=0.42)
    m_tps = mat("aft_tps", (0.05, 0.05, 0.06), roughness=0.62)
    cut = cargo_end
    aft_len = L - cut
    cx = 0.5 * (cut + L)

    # Sensible aft fuselage continuation (not a flatbed)
    upper = box(
        "Aft_Fuselage_Upper",
        (aft_len - 0.3, W * 0.92, H * 0.42),
        (cx, 0.0, H * 0.48),
        m_skin,
        tree["edits"],
        parent=root_empty,
    )
    # bevel
    mod = upper.modifiers.new("Bevel", "BEVEL")
    mod.width = 0.2
    mod.segments = 3
    bpy.context.view_layer.objects.active = upper
    bpy.ops.object.modifier_apply(modifier=mod.name)

    belly = box(
        "Aft_Fuselage_TPS",
        (aft_len - 0.2, W * 0.95, H * 0.22),
        (cx, 0.0, H * 0.14),
        m_tps,
        tree["edits"],
        parent=root_empty,
    )
    paint_part_label("LBL_AFT_HULL", "AFT FUSELAGE", upper, tree["edits"], size=0.22)

    # Compact vertical fin (not gigantic)
    fin = box(
        "VTail_Fin",
        (3.2, 0.28, 5.2),
        (L - 2.8, 0.0, H * 0.55 + 2.6),
        m_skin,
        tree["edits"],
        parent=root_empty,
    )
    rudder = box(
        "VTail_Rudder",
        (1.2, 0.22, 4.0),
        (L - 1.2, 0.0, H * 0.55 + 2.4),
        m_tps,
        tree["edits"],
        parent=root_empty,
    )
    paint_part_label("LBL_VTAIL", "VERTICAL FIN", fin, tree["edits"], size=0.18)
    paint_part_label("LBL_RUDDER", "RUDDER", rudder, tree["edits"], size=0.14)

    # Extend black belly under aft
    box(
        "Aft_Heatshield_Ext",
        (aft_len, W * 0.9, 0.12),
        (cx, 0.0, 0.08),
        m_tps,
        tree["edits"],
        parent=root_empty,
    )
    print(f"rebuilt aft hull {cut:.1f}→{L:.0f} m + compact fin")


def height_guess(mesh_objs: list[bpy.types.Object]) -> float:
    mn, mx = world_bounds(mesh_objs)
    return max(mx.z - mn.z, 1.0)


# ---------------------------------------------------------------------------
# Gear, aft graft, interior, annotations
# ---------------------------------------------------------------------------


def paint_part_label(
    name: str,
    text: str,
    target: bpy.types.Object,
    collection: bpy.types.Collection,
    *,
    size: float = 0.18,
) -> bpy.types.Object:
    """Tiny on-surface label (astronaut scale), parented to the part."""
    # Place slightly above local +Z of target bbox
    if target.type == "MESH":
        local_z = max(v.co.z for v in target.data.vertices) + 0.08
        local_x = sum(v.co.x for v in target.data.vertices) / max(len(target.data.vertices), 1)
        local_y = sum(v.co.y for v in target.data.vertices) / max(len(target.data.vertices), 1)
        loc = (local_x, local_y, local_z)
    else:
        loc = (0.0, 0.0, 0.4)
    lab = label_mesh(
        name,
        text,
        loc,
        collection,
        size=size,
        parent=target,
        color=(0.0, 0.0, 0.0),
    )
    return lab


def _apply_ac_axis_remap(mesh_objs: list[bpy.types.Object]) -> None:
    """AC (x, y_up, z_span) → vehicle (x, -z, y)."""
    for o in mesh_objs:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        for v in o.data.vertices:
            x, y, z = v.co
            v.co = Vector((x, -z, y))
        o.data.update()


def _gear_bank(name: str) -> str:
    base = name[3:] if name.startswith("LG_") else name
    if base in {"Cube", "Shock", "Axel", "Rim", "Tire"}:
        return "nose"
    if base.endswith("L") or ".L" in base:
        return "main_L"
    if base.endswith("R") or ".R" in base:
        return "main_R"
    return "other"


def mount_shuttle_landing_gear(tree, root_empty) -> bpy.types.Object:
    """Import FG LandingGears.ac, orient, mount under vehicle. No dummy gear."""
    lg_root = import_ac3d(LANDING_GEARS_AC, collection=tree["gear"], name_prefix="LG_")
    mesh_objs = [o for o in bpy.data.objects if o.name.startswith("LG_") and o.type == "MESH"]
    _apply_ac_axis_remap(mesh_objs)

    # Clear parents; bank into nose / main_L / main_R empties
    nose_e = empty("EMPTY_NoseGear_Good", tree["gear_nose"], size=0.8)
    main_l = empty("EMPTY_MainGear_L", tree["gear_main"], size=0.8)
    main_r = empty("EMPTY_MainGear_R", tree["gear_main"], size=0.8)
    nose_e.parent = root_empty
    main_l.parent = root_empty
    main_r.parent = root_empty

    banks = {"nose": nose_e, "main_L": main_l, "main_R": main_r}
    for o in mesh_objs:
        bank = _gear_bank(o.name)
        if bank not in banks:
            o.hide_viewport = True
            o.hide_render = True
            continue
        # keep world position while re-parenting
        mw = o.matrix_world.copy()
        o.parent = banks[bank]
        o.matrix_world = mw
        to_col(o, tree["gear_nose"] if bank == "nose" else tree["gear_main"])

    def tire_center(predicate) -> Vector:
        pts = []
        for o in mesh_objs:
            if o.type != "MESH" or not predicate(o.name):
                continue
            for c in o.bound_box:
                pts.append(o.matrix_world @ Vector(c))
        if not pts:
            return Vector((0, 0, 0))
        return sum(pts, Vector()) / len(pts)

    nose_c = tire_center(lambda n: n in {"LG_Tire", "LG_Rim", "LG_Cube"})
    main_l_c = tire_center(lambda n: _gear_bank(n) == "main_L")
    main_r_c = tire_center(lambda n: _gear_bank(n) == "main_R")

    # Targets under stretched orbiter (belly ~ Z=0)
    def move_bank(empty_ob, current_c, target: Vector):
        delta = target - current_c
        empty_ob.location += delta

    move_bank(nose_e, nose_c, Vector((5.0, 0.0, 0.15)))
    move_bank(main_l, main_l_c, Vector((28.0, 2.4, 0.15)))
    move_bank(main_r, main_r_c, Vector((28.0, -2.4, 0.15)))

    # Drop so lowest mesh point sits near Z=0; re-measure after XY place
    bpy.context.view_layer.update()
    all_gear = [o for o in mesh_objs if not o.hide_render and o.type == "MESH"]
    mn, _mx = world_bounds(all_gear)
    drop = -mn.z + 0.05
    for e in (nose_e, main_l, main_r):
        e.location.z += drop
    bpy.context.view_layer.update()
    # Second pass: each bank independently to ground
    for e, pred in (
        (nose_e, lambda n: _gear_bank(n) == "nose"),
        (main_l, lambda n: _gear_bank(n) == "main_L"),
        (main_r, lambda n: _gear_bank(n) == "main_R"),
    ):
        bank_meshes = [o for o in mesh_objs if pred(o.name) and o.type == "MESH"]
        if not bank_meshes:
            continue
        bmn, _ = world_bounds(bank_meshes)
        e.location.z += -bmn.z + 0.02

    paint_part_label("LBL_NOSE_GEAR", "NOSE GEAR", nose_e, tree["gear_nose"], size=0.22)
    paint_part_label("LBL_MAIN_GEAR_L", "MAIN GEAR L", main_l, tree["gear_main"], size=0.22)
    paint_part_label("LBL_MAIN_GEAR_R", "MAIN GEAR R", main_r, tree["gear_main"], size=0.22)

    # Hide unused importer empties
    for o in list(bpy.data.objects):
        if o.name.startswith("LG_") and o.type == "EMPTY":
            o.hide_viewport = True
            o.hide_render = True

    print("mounted Shuttle LandingGears (dummy gear not created)")
    return lg_root


def graft_aft_plant(tree, cfg, root_empty) -> None:
    """Seat aft plant into stretched hull aft of cargo; one SSME nozzle only."""
    m_batt = mat("graft_batt", (0.25, 0.55, 0.30), roughness=0.4)
    m_fuel = mat("graft_fuel", (0.55, 0.40, 0.75), roughness=0.35)
    m_charm = mat("graft_charm", (0.85, 0.40, 0.25), roughness=0.35, metallic=0.2)
    m_water = mat("graft_water", (0.25, 0.50, 0.85), roughness=0.25)
    m_metal = mat("graft_metal", (0.5, 0.5, 0.52), roughness=0.3, metallic=0.5)

    stations = {s["id"]: s for s in cfg["stations"]}
    # Origin empty — child coords are world/station absolute (do NOT offset parent)
    graft = empty("EMPTY_AftGraft", tree["aft"], loc=(0.0, 0.0, 0.0), size=1.5)
    graft.parent = root_empty

    z_bay = 2.2  # inside fuselage height

    b = stations["battery"]
    mid = 0.5 * (b["x0"] + b["x1"])
    for i in range(2):
        for j in range(2):
            ob = box(
                f"Graft_Batt_{i}_{j}",
                (0.55, 0.7, 0.4),
                (mid - 0.35 + i * 0.7, -0.8 + j * 1.6, z_bay),
                m_batt,
                tree["aft"],
                parent=graft,
            )
            paint_part_label(f"LBL_BATT_{i}_{j}", "BATTERY", ob, tree["aft"], size=0.12)

    f = stations["fuel"]
    mid = 0.5 * (f["x0"] + f["x1"])
    for j, y in enumerate((-0.95, 0.0, 0.95)):
        ob = cylinder(f"Graft_Fuel_{j}", 0.4, 0.85, (mid, y, z_bay), m_fuel, tree["aft"], parent=graft)
        paint_part_label(f"LBL_FUEL_{j}", "p-11B FUEL", ob, tree["aft"], size=0.11)

    c = stations["charm"]
    mid = 0.5 * (c["x0"] + c["x1"])
    core = cylinder("Graft_CHARM_Core", 1.25, 2.0, (mid, 0, z_bay + 0.2), m_charm, tree["aft"], parent=graft)
    ring = cylinder("Graft_CHARM_Ring", 1.7, 0.3, (mid, 0, z_bay + 0.2), m_metal, tree["aft"], parent=graft)
    paint_part_label("LBL_CHARM", "CHARM", core, tree["aft"], size=0.2)
    paint_part_label("LBL_CHARM_RING", "CHARM RING", ring, tree["aft"], size=0.12)

    w = stations["water"]
    mid = 0.5 * (w["x0"] + w["x1"])
    for j, y in enumerate((-1.0, 0.0, 1.0)):
        ob = cylinder(f"Graft_Water_{j}", 0.5, 1.8, (mid, y, z_bay), m_water, tree["aft"], axis="X", parent=graft)
        paint_part_label(f"LBL_WATER_{j}", "WATER", ob, tree["aft"], size=0.12)

    # Aft hull / fin come from rebuild_sensible_aft(); plant sits inside that volume

    # One SSME only — longest axis must be +X (aft), never +Z (up)
    e = stations["engine"]
    mid = 0.5 * (e["x0"] + e["x1"])
    if SSME_AC.is_file():
        import_ac3d(SSME_AC, collection=tree["ref_ssme"], name_prefix="SSME_")
        ssme_meshes = [o for o in bpy.data.objects if o.name.startswith("SSME_") and o.type == "MESH"]
        for o in ssme_meshes:
            mw = o.matrix_world.copy()
            o.parent = None
            o.matrix_world = mw
            bpy.ops.object.select_all(action="DESELECT")
            o.select_set(True)
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            to_col(o, tree["ref_ssme"])
            for _ in range(4):
                dx, dy, dz = float(o.dimensions.x), float(o.dimensions.y), float(o.dimensions.z)
                if dx >= dy and dx >= dz:
                    break
                o.rotation_euler = (0.0, -math.pi / 2, 0.0)
                bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

        mount = empty("EMPTY_SSME_Mount", tree["ref_ssme"], loc=(mid + 1.2, 0.0, 2.1), size=0.6)
        mount.parent = root_empty
        for o in ssme_meshes:
            o.parent = mount
            o.location = (0.0, 0.0, 0.0)
            o.rotation_euler = (0.0, 0.0, 0.0)
        bpy.context.view_layer.update()
        if ssme_meshes:
            mn, mx = world_bounds(ssme_meshes)
            cen = (mn + mx) * 0.5
            mount.location += Vector((mid + 1.2 - cen.x, -cen.y, 2.1 - cen.z))
            bpy.context.view_layer.update()
            mn, mx = world_bounds(ssme_meshes)
            size = mx - mn
            if size.z > size.x * 1.05:
                mount.rotation_euler = (0.0, math.pi / 2, 0.0)
                bpy.context.view_layer.update()
            paint_part_label("LBL_SSME", "COMBINED-CYCLE NOZZLE", ssme_meshes[0], tree["ref_ssme"], size=0.16)
        for o in list(bpy.data.objects):
            if o.name.startswith("SSME_") and o.type == "EMPTY" and "Mount" not in o.name:
                o.hide_viewport = True
                o.hide_render = True
        print("mounted single SSME nozzle pointing aft; no dummy bell; no triple cluster")


def build_interior_cutaway(tree, cfg, root_empty) -> None:
    """Floorplan-only station cutaway (separate from orbiter exterior)."""
    W = cfg["fuselage_width_m"]
    BW = cfg["bay_width_m"]
    m_deck = mat("deck", (0.82, 0.84, 0.88), roughness=0.55)
    m_seat = mat("seat", (0.18, 0.28, 0.48), roughness=0.45)
    m_metal = mat("int_metal", (0.5, 0.5, 0.52), roughness=0.3, metallic=0.5)
    m_water = mat("int_o2", (0.25, 0.55, 0.9), roughness=0.25)
    m_al = mat("int_al", (0.9, 0.82, 0.55), roughness=0.45)
    m_door = mat("int_door", (0.9, 0.7, 0.15), roughness=0.4)
    m_line = mat("int_line", (0.12, 0.18, 0.35), roughness=0.8)
    m_batt = mat("int_batt", (0.2, 0.55, 0.28), roughness=0.4)
    m_fuel = mat("int_fuel", (0.5, 0.35, 0.75), roughness=0.35)
    m_charm = mat("int_charm", (0.85, 0.35, 0.22), roughness=0.35, metallic=0.25)
    m_eng = mat("int_eng", (0.15, 0.15, 0.18), roughness=0.3, metallic=0.55)

    box("Deck_Plate", (cfg["length_m"] - 1.0, W, 0.06), (cfg["length_m"] / 2, 0, 0.0), m_deck, tree["int"], parent=root_empty)

    target = {
        "crew": tree["crew"],
        "airlock": tree["airlock"],
        "cargo": tree["cargo"],
        "battery": tree["batt"],
        "fuel": tree["fuel"],
        "charm": tree["charm"],
        "water": tree["water"],
        "engine": tree["engbay"],
    }
    for st in cfg["stations"]:
        mid = 0.5 * (st["x0"] + st["x1"])
        length = max(st["x1"] - st["x0"] - 0.1, 0.3)
        wy = BW if st["id"] == "cargo" else W * 0.82
        m = mat(f"slab_{st['id']}", tuple(st["color"]), roughness=0.55)
        box(f"Slab_{st['id']}", (length, wy, 0.05), (mid, 0, 0.08), m, target[st["id"]], parent=root_empty)
        box(f"BH_{st['id']}", (0.05, wy, 0.55), (st["x0"], 0, 0.35), m_line, target[st["id"]], parent=root_empty)

    for name, y in (("CDR", 0.8), ("PLT", -0.8)):
        box(f"Seat_{name}", (0.7, 0.55, 0.85), (2.4, y, 0.5), m_seat, tree["crew"], parent=root_empty)
    for i, x in enumerate((4.5, 6.2)):
        for j, y in enumerate((0.8, -0.8)):
            box(f"Nap_{i}_{j}", (0.6, 0.5, 0.75), (x, y, 0.45), m_seat, tree["crew"], parent=root_empty)
    for i, x in enumerate((7.5, 8.1, 8.7, 9.3)):
        cylinder(f"O2_{i}", 0.17, 0.7, (x, 1.5, 0.45), m_water, tree["crew"], parent=root_empty)
        cylinder(f"N2_{i}", 0.13, 0.55, (x, 1.0, 0.4), m_metal, tree["crew"], parent=root_empty)
    cylinder("HatchMark", 0.55, 0.1, (5.6, W * 0.38, 0.4), m_door, tree["crew"], parent=root_empty)

    box("Airlock", (3.4, 2.3, 1.3), (13.0, 0, 0.8), m_al, tree["airlock"], parent=root_empty)
    box("AL_Aft", (0.1, 1.5, 1.15), (14.75, 0, 0.8), m_door, tree["airlock"], parent=root_empty)
    box("AL_Fwd", (0.1, 1.5, 1.15), (11.25, 0, 0.8), m_door, tree["airlock"], parent=root_empty)

    cargo = next(s for s in cfg["stations"] if s["id"] == "cargo")
    cx = 0.5 * (cargo["x0"] + cargo["x1"])
    dx = cargo["x1"] - cargo["x0"]
    box("Hinge_P", (dx * 0.98, 0.05, 0.05), (cx, BW * 0.48, 0.5), m_line, tree["cargo"], parent=root_empty)
    box("Hinge_S", (dx * 0.98, 0.05, 0.05), (cx, -BW * 0.48, 0.5), m_line, tree["cargo"], parent=root_empty)

    for i in range(2):
        for j in range(3):
            box(f"Batt_{i}_{j}", (0.65, 0.85, 0.45), (34.05 + i * 0.85, -1.15 + j * 1.15, 0.45), m_batt, tree["batt"], parent=root_empty)
    for i, y in enumerate((-1.15, 0.0, 1.15)):
        cylinder(f"Fuel_{i}", 0.48, 0.95, (36.5, y, 0.7), m_fuel, tree["fuel"], parent=root_empty)
    cylinder("CHARM", 1.45, 1.8, (41.25, 0, 1.0), m_charm, tree["charm"], parent=root_empty)
    for i, y in enumerate((-1.2, 0.0, 1.2)):
        cylinder(f"H2O_{i}", 0.6, 2.1, (47.0, y, 0.85), m_water, tree["water"], axis="X", parent=root_empty)
    cylinder("Eng", 1.05, 2.2, (50.6, 0, 0.9), m_eng, tree["engbay"], axis="X", parent=root_empty)


def build_annotations(tree, cfg, root_empty) -> None:
    span = cfg["wingspan_m"]
    L = cfg["length_m"]
    dark = (0.0, 0.0, 0.0)
    for st in cfg["stations"]:
        mid = 0.5 * (st["x0"] + st["x1"])
        label_mesh(f"LT_{st['id']}", st["label"], (mid, span * 0.55, 0.3), tree["lab_top"], size=0.45, parent=root_empty, color=dark)
        label_mesh(
            f"LS_{st['id']}",
            st["label"],
            (mid, -span * 0.55 - 2.0, 10.0),
            tree["lab_side"],
            size=0.48,
            rot=(math.pi / 2, 0, 0),
            parent=root_empty,
            color=dark,
        )
    label_mesh("Title_Top", "CATSKILLS-SSTO FLOORPLAN", (26, -span * 0.62, 0.3), tree["lab_top"], size=0.75, parent=root_empty, color=dark)
    label_mesh(
        "Sub_Top",
        "SHUTTLE BASE  ·  DEFORMED TO STATION MAP  ·  NO LANDING GEAR",
        (26, -span * 0.72, 0.3),
        tree["lab_top"],
        size=0.30,
        parent=root_empty,
        color=dark,
    )
    label_mesh("Title_Side", "CATSKILLS-SSTO", (26, -span * 0.7, 13.5), tree["lab_side"], size=0.9, rot=(math.pi / 2, 0, 0), parent=root_empty, color=dark)
    label_mesh(
        "Note_Hatch",
        "FORWARD CREW SIDE HATCH (ground)",
        (5.6, -span * 0.7, 7.5),
        tree["lab_side"],
        size=0.36,
        rot=(math.pi / 2, 0, 0),
        parent=root_empty,
        color=dark,
    )
    label_mesh(
        "Note_AL",
        "INTERNAL AIRLOCK → BAY ONLY",
        (13, -span * 0.7, 7.5),
        tree["lab_side"],
        size=0.36,
        rot=(math.pi / 2, 0, 0),
        parent=root_empty,
        color=dark,
    )
    label_mesh(
        "Note_Doors",
        "CARGO BAY DOORS (TOP CLAMSHELL)",
        (24, -span * 0.7, 7.5),
        tree["lab_side"],
        size=0.36,
        rot=(math.pi / 2, 0, 0),
        parent=root_empty,
        color=dark,
    )
    m_line = mat("dim_line", (0.0, 0.0, 0.0), roughness=0.9)
    box("Scale_10m", (10.0, 0.14, 0.08), (8.0, -span * 0.85, 0.2), m_line, tree["dims"], parent=root_empty)
    label_mesh("Scale_Label", "10 m", (8.0, -span * 0.95, 0.3), tree["dims"], size=0.42, parent=root_empty, color=dark)
    label_mesh("Len_Label", f"L = {L:.0f} m", (30.0, -span * 0.95, 0.3), tree["dims"], size=0.45, parent=root_empty, color=dark)


def setup_world_lights_cams(tree, cfg):
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.92, 0.93, 0.95, 1.0)
    bg.inputs[1].default_value = 0.85

    bpy.ops.object.light_add(type="SUN", location=(26, -10, 55))
    sun = bpy.context.active_object
    sun.name = "Sun"
    sun.data.energy = 4.5
    sun.rotation_euler = (0.55, 0.25, 0.35)
    to_col(sun, tree["lights"])

    bpy.ops.object.light_add(type="AREA", location=(26, -45, 30))
    key = bpy.context.active_object
    key.name = "Key"
    key.data.energy = 1100
    key.data.size = 55
    to_col(key, tree["lights"])

    def add_cam(name, loc, rot, ortho):
        data = bpy.data.cameras.new(name)
        data.type = "ORTHO"
        data.ortho_scale = ortho
        cam = bpy.data.objects.new(name, data)
        cam.location = loc
        cam.rotation_euler = rot
        tree["cams"].objects.link(cam)
        return cam

    cam_top = add_cam("Cam_Floorplan", Vector((26, -2.0, 75)), (0, 0, 0), 64)
    cam_side = add_cam("Cam_Profile", Vector((26, -55, 4.0)), (math.pi / 2, 0, 0), 62)
    return cam_top, cam_side


def set_engine(scene) -> None:
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "EEVEE"):
        try:
            scene.render.engine = eng
            return
        except TypeError:
            continue


def render_to(cam, path: Path, *, width: int, height: int) -> None:
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    cfg = json.loads(STATIONS_PATH.read_text(encoding="utf-8"))

    print("==> cache / clear / hierarchy")
    ensure_orbiter_cache()
    clear_scene()
    tree = build_hierarchy()
    vehicle = empty("EMPTY_Vehicle_Root", tree["root"], size=3.0)

    print("==> append + orient Shuttle orbiter base")
    orb_root = append_orbiter(tree["base"])
    orb_root.parent = vehicle
    mesh_objs = [o for o in tree["base"].objects if o.type == "MESH"]
    # Also collect nested? collections only hold direct objects — get all ORB meshes
    mesh_objs = [o for o in bpy.data.objects if o.name.startswith("ORB_") and o.type == "MESH"]
    L0, span0, _H0 = orient_orbiter_to_vehicle_frame(orb_root, mesh_objs)

    print("==> piecewise deform to stations.json")
    deform_orbiter_to_stations(mesh_objs, L0=L0, span0=span0, cfg=cfg, rig_col=tree["rig"], root=vehicle)

    print("==> rebuild sensible aft hull (cut old engines / giant fin)")
    rebuild_sensible_aft(tree, cfg, vehicle)
    mesh_objs = [o for o in bpy.data.objects if o.name.startswith("ORB_") and o.type == "MESH"]

    # Soft materials on orbiter: white upper / dark heatshield if named
    m_skin = mat("orb_skin", (0.88, 0.89, 0.91), roughness=0.42)
    m_tps = mat("orb_tps", (0.05, 0.05, 0.06), roughness=0.62)
    for o in mesh_objs:
        n = o.name.lower()
        if "heatshield" in n or "elevon" in n or "bodyflap" in n:
            assign(o, m_tps)
        elif "glass" in n:
            assign(o, mat("orb_glass", (0.25, 0.40, 0.55), roughness=0.08, metallic=0.1))
        elif "door" in n and "payload" in n:
            assign(o, mat("orb_plbd", (0.75, 0.76, 0.78), roughness=0.4))
        else:
            assign(o, m_skin)

    # On-mesh labels for key orbiter parts
    label_map = {
        "ORB_fuselage": "FUSELAGE",
        "ORB_heatshield": "TPS BELLY",
        "ORB_payload-bay": "CARGO BAY",
        "ORB_payload-bay-door-left": "PLBD L",
        "ORB_payload-bay-door-right": "PLBD R",
        "ORB_inboard-elevon-left": "ELEVON",
        "ORB_outboard-elevon-left": "ELEVON",
        "ORB_GearDoorL": "GEAR DOOR",
        "ORB_NoseDoorL": "NOSE GEAR DOOR",
        "Aft_Fuselage_Upper": "AFT FUSELAGE",
        "VTail_Fin": "VERTICAL FIN",
    }
    for oname, text in label_map.items():
        ob = bpy.data.objects.get(oname)
        if ob:
            paint_part_label(f"LBL_{oname}", text, ob, tree["base"], size=0.2)

    print("==> mount good gear + aft plant + interior + annotations")
    mount_shuttle_landing_gear(tree, vehicle)
    graft_aft_plant(tree, cfg, vehicle)
    build_interior_cutaway(tree, cfg, vehicle)
    build_annotations(tree, cfg, vehicle)
    cam_top, cam_side = setup_world_lights_cams(tree, cfg)

    FIGURES.mkdir(parents=True, exist_ok=True)
    floor_path = FIGURES / "charm_ssto_interior_floorplan.png"
    profile_path = FIGURES / "charm_ssto_exterior_profile.png"

    # Floorplan: interior + top labels + orbiter ghost; hide gear/side/rig
    for k in ("gear", "lab_side", "ref", "rig"):
        set_hide(tree[k], True)
    for k in ("int", "lab_top", "dims", "base", "aft"):
        set_hide(tree[k], False)
    for o in tree["rig"].objects:
        if o.type == "LATTICE":
            o.hide_render = True
    render_to(cam_top, floor_path, width=3400, height=1700)

    # Profile: orbiter + aft hull edits + good gear + SSME + plant + side labels
    for k in ("int", "lab_top", "rig"):
        set_hide(tree[k], True)
    for k in ("base", "edits", "gear", "aft", "lab_side", "dims", "ref_ssme"):
        set_hide(tree[k], False)
    set_hide(tree["ref"], False)
    set_hide(tree["ref_gear"], True)
    render_to(cam_side, profile_path, width=3400, height=1500)

    # Restore for interactive editing
    for k, c in tree.items():
        if k != "root":
            set_hide(c, False)
    for o in tree["rig"].objects:
        if o.type == "LATTICE":
            o.hide_render = True

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT))
    print(f"saved {BLEND_OUT}")
    print()
    print("Open in Blender GUI:")
    print(f"  /snap/bin/blender {BLEND_OUT}")
    print("Mute: 00_Base_Orbiter / 00_Deform_Rig / 03_Interior / 04_Annotations as needed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback

        traceback.print_exc()
        raise SystemExit(1)
