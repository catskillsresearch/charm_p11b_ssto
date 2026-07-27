#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""High-fidelity, fully-connected SpaceX Crew Dragon seat assembly matching
``../spacex_crew_dragon_seat.png``.

Every subsystem is parented into a single structural hierarchy so parts are
not free-floating — bars meet at a central hub, the seat bucket bolts to the
pivot collar, footrest arms hinge from the pan clevises, and the carbon loop
terminates on those arms.

Hierarchy::

    Seat_Assembly
    ├── Mount_Floor_Base          (floor attachment plane)
    │   ├── Floor_Clevis_*        (3 floor plates + bolts)
    │   └── Mount_Bars_*            (bars run hub → floor, parented at hub)
    ├── Mount_Hub                 (central pivot / housing cluster)
    │   ├── Pivot_Tube, Housing, Saddle_*, LED recess
    │   └── (bar roots parent here)
    ├── Seat_Bucket               (shell + cushion + wings + arms)
    │   ├── Shell_*, Cushion_*, Trim, Arm_Pads
    │   └── Footrest_Assembly
    │       ├── Clevis_*, Hinge_Pin_*
    │       ├── Footrest_Arm_*
    │       └── Footrest_Loop

Run::

    /snap/bin/blender -b -P seat/composer_25/build_composer_25.py

Outputs ``seat/composer_25/composer_25.blend`` and verification renders.
"""

from __future__ import annotations

import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

SEAT_DIR = Path(__file__).resolve().parent
BLEND_OUT = SEAT_DIR / "composer_25.blend"
PNG_OUT = SEAT_DIR / "composer_25_render.png"
PNG_OUT_SIDE = SEAT_DIR / "composer_25_render_side.png"
PNG_OUT_MOUNT = SEAT_DIR / "composer_25_render_mount.png"

# Pivot / attachment coordinates in unreclined local frame (Y fwd, Z up).
PIVOT = Vector((0.0, 0.12, -0.10))
FOOTREST_ATTACH_L = Vector((0.175, 0.375, 0.002))
FOOTREST_ATTACH_R = Vector((-0.175, 0.375, 0.002))
HUB_FLOOR = Vector((0.0, 0.05, -0.54))

# ---------------------------------------------------------------------------
# Scene helpers
# ---------------------------------------------------------------------------


def col(name: str, parent: bpy.types.Collection | None = None) -> bpy.types.Collection:
    existing = bpy.data.collections.get(name)
    if existing:
        return existing
    c = bpy.data.collections.new(name)
    if parent:
        parent.children.link(c)
    else:
        bpy.context.scene.collection.children.link(c)
    return c


def empty(name: str, loc: Vector, collection: bpy.types.Collection) -> bpy.types.Object:
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = "PLAIN_AXES"
    ob.empty_display_size = 0.08
    ob.location = loc
    collection.objects.link(ob)
    return ob


def parent_keep(child: bpy.types.Object, parent: bpy.types.Object) -> None:
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


def link_only(ob: bpy.types.Object, collection: bpy.types.Collection) -> bpy.types.Object:
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    collection.objects.link(ob)
    return ob


def assign(ob: bpy.types.Object, material: bpy.types.Material) -> None:
    if ob.data and hasattr(ob.data, "materials"):
        if ob.data.materials:
            ob.data.materials[0] = material
        else:
            ob.data.materials.append(material)


def shade_auto_smooth(ob: bpy.types.Object, angle_deg: float = 40.0) -> None:
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    try:
        bpy.ops.object.shade_auto_smooth(angle=math.radians(angle_deg))
    except AttributeError:
        bpy.ops.object.shade_smooth()


def add_subsurf(ob: bpy.types.Object, levels: int = 1) -> None:
    mod = ob.modifiers.new("Smooth", "SUBSURF")
    mod.levels = levels
    mod.render_levels = levels
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=mod.name)


def add_solidify(ob: bpy.types.Object, thickness: float, *, offset: float = -1.0) -> None:
    mod = ob.modifiers.new("Shell", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = offset
    mod.use_rim = True
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=mod.name)


def add_bevel(ob: bpy.types.Object, width: float = 0.003, segments: int = 2) -> None:
    mod = ob.modifiers.new("Bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(30.0)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=mod.name)


def mat(
    name: str,
    color,
    *,
    roughness=0.45,
    metallic=0.0,
    clearcoat=0.0,
    sheen=0.0,
    emission=None,
) -> bpy.types.Material:
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
        for key in ("Coat Weight", "Clearcoat"):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = clearcoat
                break
        for key in ("Sheen Weight", "Sheen"):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = sheen
                break
        if emission is not None:
            for key in ("Emission Color", "Emission"):
                if key in bsdf.inputs:
                    bsdf.inputs[key].default_value = (*emission, 1.0)
                    break
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = 2.5
    return m


def carbon_mat() -> bpy.types.Material:
    name = "carbon_fiber"
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name=name)
    m.use_nodes = True
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.04, 0.041, 0.043, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.22
    bsdf.inputs["Metallic"].default_value = 0.25
    for key in ("Coat Weight", "Clearcoat"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = 0.7
    tex = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (22.0, 22.0, 22.0)
    mapping.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(45.0))
    wu = nodes.new("ShaderNodeTexWave")
    wu.wave_type, wu.bands_direction = "BANDS", "X"
    wu.inputs["Scale"].default_value = 5.0
    wv = nodes.new("ShaderNodeTexWave")
    wv.wave_type, wv.bands_direction = "BANDS", "Y"
    wv.inputs["Scale"].default_value = 5.0
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "FLOAT"
    mix.inputs["Factor"].default_value = 0.5
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.025, 0.026, 0.028, 1.0)
    ramp.color_ramp.elements[1].color = (0.07, 0.072, 0.075, 1.0)
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.7
    bump.inputs["Distance"].default_value = 0.006
    links.new(tex.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], wu.inputs["Vector"])
    links.new(mapping.outputs["Vector"], wv.inputs["Vector"])
    links.new(wu.outputs["Fac"], mix.inputs["A"])
    links.new(wv.outputs["Fac"], mix.inputs["B"])
    links.new(mix.outputs["Result"], ramp.inputs["Fac"])
    links.new(mix.outputs["Result"], bump.inputs["Height"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


# ---------------------------------------------------------------------------
# Loft geometry
# ---------------------------------------------------------------------------


def _catmull_rom(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return 0.5 * (
        2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3
    )


def resample_spline(controls, n):
    pts = [Vector(c) for c in controls]
    padded = [pts[0]] + pts + [pts[-1]]
    segs = len(pts) - 1
    out = []
    for i in range(n):
        u = (i / (n - 1)) * segs
        seg = min(int(u), segs - 1)
        t = u - seg
        p0, p1, p2, p3 = padded[seg], padded[seg + 1], padded[seg + 2], padded[seg + 3]
        out.append(_catmull_rom(p0, p1, p2, p3, t))
    return out


def resample_scalar(values, n):
    m = len(values)
    return [
        values[int(math.floor(u))] * (1 - (u - math.floor(u)))
        + values[min(int(math.floor(u)) + 1, m - 1)] * (u - math.floor(u))
        for u in ((i / (n - 1)) * (m - 1) for i in range(n))
    ]


def loft_channel(
    name, spine_controls, halfwidths, depths, rims, *, ref_axis, n_rings, profile_n,
    material, collection, seed_out, center_offset=0.0,
) -> bpy.types.Object:
    spine = resample_spline(spine_controls, n_rings)
    hw, dp, rm = resample_scalar(halfwidths, n_rings), resample_scalar(depths, n_rings), resample_scalar(rims, n_rings)
    tangents = []
    for i in range(n_rings):
        if i == 0:
            tangents.append((spine[1] - spine[0]).normalized())
        elif i == n_rings - 1:
            tangents.append((spine[-1] - spine[-2]).normalized())
        else:
            tangents.append((spine[i + 1] - spine[i - 1]).normalized())

    rings, prev_up = [], None
    for i in range(n_rings):
        t = tangents[i]
        right = ref_axis - t * ref_axis.dot(t)
        if right.length < 1e-6:
            alt = Vector((0, 0, 1)) if abs(ref_axis.z) < 0.9 else Vector((1, 0, 0))
            right = alt - t * alt.dot(t)
        right.normalize()
        up = t.cross(right).normalized()
        if prev_up is None:
            if up.dot(seed_out) < 0:
                up, right = -up, -right
        elif up.dot(prev_up) < 0:
            up, right = -up, -right
        prev_up = up
        center = spine[i] + up * center_offset
        rings.append([
            center + right * (-1 + 2 * j / (profile_n - 1)) * hw[i]
            + up * (-dp[i] * (1 - ((-1 + 2 * j / (profile_n - 1)) ** 2)) + rm[i] * ((-1 + 2 * j / (profile_n - 1)) ** 2))
            for j in range(profile_n)
        ])

    bm = bmesh.new()
    bm_rings = [[bm.verts.new(p) for p in ring] for ring in rings]
    faces = []
    for i in range(n_rings - 1):
        for j in range(profile_n - 1):
            try:
                f = bm.faces.new((bm_rings[i][j], bm_rings[i][j + 1], bm_rings[i + 1][j + 1], bm_rings[i + 1][j]))
                faces.append(f)
            except ValueError:
                pass
    bm.normal_update()
    avg = sum((f.normal for f in faces), Vector())
    if avg.dot(seed_out) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    ob = bpy.data.objects.new(name, mesh)
    collection.objects.link(ob)
    assign(ob, material)
    return ob


# ---------------------------------------------------------------------------
# Mesh primitives (world-space placement, then parented)
# ---------------------------------------------------------------------------


def make_cylinder_between(
    name, p0: Vector, p1: Vector, radius: float, material, collection, parent=None, verts=28,
) -> bpy.types.Object:
    """Cylinder whose ends land exactly on p0 and p1."""
    mid = (p0 + p1) / 2
    delta = p1 - p0
    length = delta.length
    if length < 1e-6:
        raise ValueError(f"{name}: zero length")
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=length, location=mid, vertices=verts)
    ob = bpy.context.active_object
    ob.name = name
    ob.rotation_euler = delta.normalized().to_track_quat("Z", "Y").to_euler()
    assign(ob, material)
    link_only(ob, collection)
    add_bevel(ob, width=min(0.002, radius * 0.12), segments=2)
    shade_auto_smooth(ob)
    if parent:
        parent_keep(ob, parent)
    return ob


def make_box(name, size, loc, material, collection, rotation=(0, 0, 0), parent=None) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.rotation_euler = rotation
    assign(ob, material)
    link_only(ob, collection)
    add_bevel(ob, width=0.0025, segments=2)
    shade_auto_smooth(ob)
    if parent:
        parent_keep(ob, parent)
    return ob


def make_cylinder(name, radius, depth, loc, material, collection, axis="Z", parent=None, verts=32):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=loc, vertices=verts)
    ob = bpy.context.active_object
    ob.name = name
    if axis == "X":
        ob.rotation_euler = (0, math.pi / 2, 0)
    elif axis == "Y":
        ob.rotation_euler = (math.pi / 2, 0, 0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    assign(ob, material)
    link_only(ob, collection)
    add_bevel(ob, width=min(0.002, radius * 0.12), segments=2)
    shade_auto_smooth(ob)
    if parent:
        parent_keep(ob, parent)
    return ob


def make_rounded_rect_tube(name, width, height, tube_r, loc, material, collection, rotation, corner_r=0.08, parent=None):
    hw, hh, cr = width / 2, height / 2, min(corner_r, width / 2 - tube_r * 1.2, height / 2 - tube_r * 1.2)
    curve = bpy.data.curves.new(name + "_crv", "CURVE")
    curve.dimensions, curve.bevel_depth, curve.bevel_resolution = "3D", tube_r, 6
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(7)
    k = cr * 0.55
    pts = [
        (-hw + cr, -hh, k, 0), (hw - cr, -hh, k, 0), (hw, -hh + cr, 0, k), (hw, hh - cr, 0, k),
        (hw - cr, hh, -k, 0), (-hw + cr, hh, -k, 0), (-hw, hh - cr, 0, -k), (-hw, -hh + cr, 0, -k),
    ]
    for i, (x, y, hx, hy) in enumerate(pts):
        bp = spline.bezier_points[i]
        bp.co = (x, y, 0)
        bp.handle_left, bp.handle_right = (x - hx, y - hy, 0), (x + hx, y + hy, 0)
        bp.handle_left_type = bp.handle_right_type = "ALIGNED"
    spline.use_cyclic_u = True
    ob = bpy.data.objects.new(name, curve)
    collection.objects.link(ob)
    ob.location, ob.rotation_euler = loc, rotation
    assign(ob, material)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.convert(target="MESH")
    ob = bpy.context.active_object
    ob.name = name
    shade_auto_smooth(ob, 50)
    if parent:
        parent_keep(ob, parent)
    return ob


def make_bolt(name, loc, material, collection, parent, axis="Z"):
    bolt = make_cylinder(name, 0.007, 0.010, loc, material, collection, axis=axis, parent=parent, verts=8)
    washer = make_cylinder(name + "_Washer", 0.011, 0.002, loc + Vector((0, 0, -0.006 if axis == "Z" else 0)), material, collection, axis=axis, parent=parent, verts=20)
    return bolt, washer


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------


def build_materials():
    return {
        "shell": mat("shell_composite", (0.745, 0.752, 0.760), roughness=0.32, clearcoat=0.22),
        "cushion": mat("cushion_suede", (0.016, 0.016, 0.019), roughness=0.88, sheen=0.25),
        "trim": mat("trim_gasket", (0.12, 0.13, 0.14), roughness=0.75),
        "carbon": carbon_mat(),
        "alum": mat("aluminum_white", (0.82, 0.83, 0.85), roughness=0.38, metallic=0.18, clearcoat=0.12),
        "alum_dark": mat("aluminum_dark", (0.42, 0.43, 0.45), roughness=0.42, metallic=0.35),
        "metal": mat("hardware_metal", (0.62, 0.63, 0.65), roughness=0.25, metallic=0.90),
        "metal_dark": mat("hardware_dark", (0.18, 0.18, 0.20), roughness=0.35, metallic=0.85),
        "led": mat("led_glow", (0.85, 0.90, 0.95), roughness=0.2, emission=(0.7, 0.85, 1.0)),
    }


# ---------------------------------------------------------------------------
# Subsystems — each returns objects and accepts parent empties
# ---------------------------------------------------------------------------


def build_bucket(parent: bpy.types.Object, c_shell, c_cushion, c_hw, mats) -> list[bpy.types.Object]:
    objs = []
    X, Y = Vector((1, 0, 0)), Vector((0, 1, 0))
    main_spine = [
        (0, -0.055, 0.560), (0, -0.035, 0.470), (0, -0.010, 0.360), (0, 0.015, 0.240),
        (0, 0.038, 0.130), (0, 0.052, 0.055), (0, 0.062, 0.010), (0, 0.075, -0.010),
        (0, 0.150, -0.020), (0, 0.300, -0.010), (0, 0.420, 0.010), (0, 0.480, 0.025),
    ]
    main_hw = [0.148, 0.195, 0.228, 0.252, 0.268, 0.274, 0.276, 0.274, 0.255, 0.210, 0.125, 0.030]
    main_dp = [0.018, 0.030, 0.048, 0.064, 0.078, 0.072, 0.062, 0.054, 0.042, 0.028, 0.016, 0.006]
    main_rim = [0.038, 0.055, 0.078, 0.095, 0.100, 0.090, 0.072, 0.055, 0.036, 0.022, 0.012, 0.004]

    shell = loft_channel("Shell_Main", main_spine, main_hw, main_dp, main_rim, ref_axis=X, n_rings=76, profile_n=25,
                         material=mats["shell"], collection=c_shell, seed_out=Vector((0, -1, 0.15)))
    add_solidify(shell, 0.014)
    add_subsurf(shell, 1)
    shade_auto_smooth(shell)
    parent_keep(shell, parent)
    objs.append(shell)

    cushion = loft_channel("Cushion_Main", main_spine, [max(w - 0.048, 0) for w in main_hw],
                           [d * 0.55 + 0.010 for d in main_dp], [r * 0.22 for r in main_rim],
                           ref_axis=X, n_rings=68, profile_n=21, material=mats["cushion"], collection=c_cushion,
                           seed_out=Vector((0, -1, 0.15)), center_offset=-0.024)
    add_solidify(cushion, 0.032)
    add_subsurf(cushion, 1)
    shade_auto_smooth(cushion, 50)
    parent_keep(cushion, parent)
    objs.append(cushion)

    for side, sign in (("L", 1.0), ("R", -1.0)):
        wing_spine = [
            (sign * 0.155, -0.045, 0.520), (sign * 0.210, -0.005, 0.610),
            (sign * 0.260, 0.050, 0.690), (sign * 0.290, 0.120, 0.740),
        ]
        wh, wd, wr = [0.130, 0.115, 0.078, 0.024], [0.022, 0.024, 0.018, 0.006], [0.026, 0.030, 0.020, 0.006]
        sw = loft_channel(f"Shell_Wing_{side}", wing_spine, wh, wd, wr, ref_axis=Y, n_rings=36, profile_n=17,
                          material=mats["shell"], collection=c_shell, seed_out=Vector((sign * 0.55, -0.55, 0.35)))
        add_solidify(sw, 0.009)
        add_subsurf(sw, 1)
        shade_auto_smooth(sw)
        parent_keep(sw, parent)
        objs.append(sw)

        cw = loft_channel(f"Cushion_Wing_{side}", wing_spine, [max(w - 0.032, 0) for w in wh],
                          [d * 0.5 + 0.004 for d in wd], [r * 0.24 for r in wr], ref_axis=Y, n_rings=30, profile_n=13,
                          material=mats["cushion"], collection=c_cushion, seed_out=Vector((sign * 0.55, -0.55, 0.35)),
                          center_offset=-0.014)
        add_solidify(cw, 0.016)
        add_subsurf(cw, 1)
        shade_auto_smooth(cw, 50)
        parent_keep(cw, parent)
        objs.append(cw)

        # Arm bolster pad (integrated lateral support)
        pad = make_box(f"Arm_Pad_{side}", (0.058, 0.115, 0.030), (sign * 0.198, 0.16, 0.14), mats["cushion"], c_cushion,
                       rotation=(math.radians(-12), math.radians(sign * -8), 0), parent=parent)
        objs.append(pad)
        trim = make_box(f"Trim_{side}", (0.008, 0.165, 0.012), (sign * 0.272, 0.14, 0.16), mats["trim"], c_hw,
                        rotation=(math.radians(15), 0, 0), parent=parent)
        objs.append(trim)
        inset = make_box(f"Bolster_Inset_{side}", (0.018, 0.012, 0.006), (sign * 0.288, 0.22, 0.08), mats["metal"], c_hw,
                         rotation=(math.radians(-8), 0, 0), parent=parent)
        objs.append(inset)

    plate = make_box("Front_Lip_Plate", (0.048, 0.022, 0.006), (0, 0.400, 0.016), mats["metal"], c_hw,
                     rotation=(math.radians(-6), 0, 0), parent=parent)
    objs.append(plate)
    return objs


def build_footrest(parent: bpy.types.Object, c_foot, mats) -> list[bpy.types.Object]:
    """Footrest loop + arms hinged at FOOTREST_ATTACH_* on the seat pan."""
    objs = []
    m_c, m_m = mats["carbon"], mats["metal_dark"]

    # Loop center: forward/down from attach points; arms meet loop at inner top edge
    loop_center = Vector((0.0, 0.82, -0.15))
    loop = make_rounded_rect_tube("Footrest_Loop", 0.50, 0.64, 0.021, loop_center, m_c, c_foot,
                                  rotation=(math.radians(52), 0, 0), corner_r=0.085, parent=parent)
    objs.append(loop)

    loop_attach_l = Vector((0.155, 0.74, -0.12))
    loop_attach_r = Vector((-0.155, 0.74, -0.12))

    for side, sign, attach, loop_pt in (
        ("L", 1.0, FOOTREST_ATTACH_L, loop_attach_l),
        ("R", -1.0, FOOTREST_ATTACH_R, loop_attach_r),
    ):
        # Clevis bracket welded to seat pan underside
        clevis = make_box(f"Footrest_Clevis_{side}", (0.036, 0.044, 0.020), attach, m_c, c_foot,
                          rotation=(math.radians(8), 0, 0), parent=parent)
        objs.append(clevis)

        pin = make_cylinder(f"Footrest_Pin_{side}", 0.009, 0.050, attach, m_m, c_foot, axis="X", parent=parent, verts=20)
        objs.append(pin)

        # Arm: exact endpoint at clevis hinge center → loop attach point
        arm = make_cylinder_between(f"Footrest_Arm_{side}", attach + Vector((0, 0, -0.008)), loop_pt, 0.023, m_c, c_foot, parent=parent, verts=28)
        objs.append(arm)

        bolt = make_cylinder(f"Footrest_LoopBolt_{side}", 0.007, 0.012, loop_pt, m_m, c_foot, axis="X", parent=parent, verts=12)
        objs.append(bolt)

    return objs


def build_mount(hub_parent: bpy.types.Object, floor_parent: bpy.types.Object, c_mount, mats) -> list[bpy.types.Object]:
    """White aluminum mount: hub at PIVOT, bars run hub ↔ floor clevises."""
    objs = []
    ma, md, mm = mats["alum"], mats["alum_dark"], mats["metal"]

    pivot = make_cylinder("Mount_Pivot_Tube", 0.043, 0.40, PIVOT, ma, c_mount, axis="X", parent=hub_parent, verts=40)
    objs.append(pivot)

    housing = make_box("Mount_Housing", (0.24, 0.20, 0.11), PIVOT + Vector((0, 0, -0.08)), ma, c_mount,
                     rotation=(math.radians(8), 0, 0), parent=hub_parent)
    objs.append(housing)
    housing_l = make_box("Mount_Housing_Lower", (0.17, 0.15, 0.13), PIVOT + Vector((0, -0.04, -0.22)), ma, c_mount,
                       rotation=(math.radians(12), 0, 0), parent=hub_parent)
    objs.append(housing_l)

    # Hub collar where bars meet (physical junction geometry)
    collar = make_cylinder("Mount_Hub_Collar", 0.055, 0.025, PIVOT + Vector((0, 0, -0.04)), ma, c_mount, axis="Z", parent=hub_parent, verts=36)
    objs.append(collar)

    for side, sign in (("L", 1.0), ("R", -1.0)):
        cap = make_cylinder(f"Mount_Pivot_Cap_{side}", 0.046, 0.018, PIVOT + Vector((sign * 0.20, 0, 0)), ma, c_mount, axis="X", parent=hub_parent, verts=32)
        objs.append(cap)
        recess = make_cylinder(f"Mount_Recess_{side}", 0.019, 0.007, PIVOT + Vector((sign * 0.212, 0, 0)), md, c_mount, axis="X", parent=hub_parent, verts=28)
        objs.append(recess)
        led = make_cylinder(f"Mount_LED_{side}", 0.011, 0.004, PIVOT + Vector((sign * 0.216, 0, 0)),
                            mats["led"] if side == "R" else md, c_mount, axis="X", parent=hub_parent, verts=20)
        objs.append(led)

        saddle = make_box(f"Mount_Saddle_{side}", (0.058, 0.075, 0.022), PIVOT + Vector((sign * 0.095, 0, 0.048)), ma, c_mount,
                          rotation=(math.radians(8), 0, 0), parent=hub_parent)
        objs.append(saddle)
        for j, dy in enumerate((-0.020, 0.020)):
            b = make_cylinder(f"Mount_SaddleBolt_{side}_{j}", 0.005, 0.014, PIVOT + Vector((sign * 0.095, dy, 0.062)), mm, c_mount, axis="Z", parent=hub_parent, verts=8)
            objs.append(b)

    # Floor clevises + bars that physically connect hub to floor
    floor_pts = [
        ("Aft_L", Vector((-0.11, -0.08, -0.54))),
        ("Aft_R", Vector((0.11, -0.08, -0.54))),
        ("Fwd_C", Vector((0.0, 0.20, -0.52))),
    ]
    hub_bar_roots = [
        ("Bar_Aft_L", PIVOT + Vector((-0.06, -0.02, -0.06)), floor_pts[0][1]),
        ("Bar_Aft_R", PIVOT + Vector((0.06, -0.02, -0.06)), floor_pts[1][1]),
        ("Bar_Fwd", PIVOT + Vector((0, 0.06, -0.08)), floor_pts[2][1]),
        ("Bar_Cross", PIVOT + Vector((-0.10, 0.12, -0.12)), PIVOT + Vector((0.10, 0.12, -0.12))),
        ("Bar_Diag", PIVOT + Vector((0.04, 0.02, -0.10)), PIVOT + Vector((0.04, 0.18, -0.34))),
    ]

    for fname, loc in floor_pts:
        plate = make_box(f"Floor_Clevis_{fname}", (0.06, 0.07, 0.020), loc, ma, c_mount, parent=floor_parent)
        objs.append(plate)
        objs.extend(make_bolt(f"Floor_Bolt_{fname}", loc + Vector((0, 0, 0.012)), mm, c_mount, floor_parent))

    for bname, p0, p1 in hub_bar_roots:
        bar = make_cylinder_between(bname, p0, p1, 0.017 if "Cross" not in bname else 0.014, ma, c_mount, parent=hub_parent)
        objs.append(bar)
        # Junction gusset at hub end
        gusset = make_cylinder(f"{bname}_Gusset", 0.022, 0.012, p0, md, c_mount, axis="Z", parent=hub_parent, verts=16)
        objs.append(gusset)

    # Spring/strut under seat (photo detail)
    strut = make_cylinder_between("Mount_Spring_Strut", PIVOT + Vector((0.05, 0.08, -0.06)), PIVOT + Vector((0.05, 0.22, -0.30)), 0.011, md, c_mount, parent=hub_parent, verts=20)
    objs.append(strut)
    for i in range(5):
        t = i / 4
        coil = make_cylinder(f"Mount_Coil_{i}", 0.017, 0.007,
                             PIVOT + Vector((0.05 + 0.02 * t, 0.08 + 0.04 * t, -0.10 - 0.05 * t)), mm, c_mount, axis="Z", parent=hub_parent, verts=16)
        objs.append(coil)

    return objs


# ---------------------------------------------------------------------------
# Assembly + render
# ---------------------------------------------------------------------------


def build_assembly() -> dict:
    root_col = col("Seat_Assembly")
    c_shell = col("01_Shell", root_col)
    c_cushion = col("02_Cushion", root_col)
    c_foot = col("03_Footrest", root_col)
    c_mount = col("04_Mount", root_col)
    c_hw = col("05_Hardware", root_col)
    c_lights = col("06_Lights", root_col)

    mats = build_materials()
    all_objs: list[bpy.types.Object] = []

    # --- Structural empties (connection graph) ---
    assembly = empty("Seat_Assembly", Vector((0, 0, 0)), root_col)
    floor_base = empty("Mount_Floor_Base", HUB_FLOOR, root_col)
    parent_keep(floor_base, assembly)

    mount_hub = empty("Mount_Hub", PIVOT, root_col)
    parent_keep(mount_hub, assembly)

    seat_bucket = empty("Seat_Bucket", PIVOT + Vector((0, 0, 0.048)), root_col)
    parent_keep(seat_bucket, mount_hub)

    footrest_asm = empty("Footrest_Assembly", Vector((0, 0, 0)), root_col)
    parent_keep(footrest_asm, seat_bucket)

    # Build subsystems parented into hierarchy
    all_objs += build_mount(mount_hub, floor_base, c_mount, mats)
    all_objs += build_bucket(seat_bucket, c_shell, c_cushion, c_hw, mats)
    all_objs += build_footrest(footrest_asm, c_foot, mats)

    all_objs.extend([assembly, floor_base, mount_hub, seat_bucket, footrest_asm])
    return {"objects": all_objs, "root": assembly, "lights": c_lights}


def setup_lights(lights_col, center, scale):
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.05, 0.053, 0.06, 1.0)
    bg.inputs[1].default_value = 1.0
    for lname, energy, size, off, rot in [
        ("Key", 50, 1.1 * scale, Vector((1.2, -1.4, 1.6)) * scale, (55, 0, 35)),
        ("Fill", 20, 1.4 * scale, Vector((-1.5, -0.4, 0.9)) * scale, (70, 0, -60)),
        ("Rim", 30, 0.9 * scale, Vector((0.2, 1.4, 1.1)) * scale, (-55, 0, 10)),
        ("Bounce", 16, 1.5 * scale, Vector((0.2, 1.5, -0.5)) * scale, (-100, 0, 0)),
    ]:
        light = bpy.data.objects.new(lname, bpy.data.lights.new(lname, "AREA"))
        light.data.energy, light.data.size = energy, size
        light.location = center + off
        light.rotation_euler = tuple(math.radians(d) for d in rot)
        bpy.context.scene.collection.objects.link(light)
        lights_col.objects.link(light)
        bpy.context.scene.collection.objects.unlink(light)


def add_camera(name, direction, center, radius, lens=40.0, margin=1.25, wh=(1600, 1200)):
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    hfov = 2 * math.atan(cam_data.sensor_width / (2 * lens))
    vfov = 2 * math.atan(math.tan(hfov / 2) * (wh[1] / wh[0]))
    dist = (radius / math.sin(min(hfov, vfov) / 2)) * margin
    cam = bpy.data.objects.new(name, cam_data)
    cam.location = center + direction.normalized() * dist
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(cam)
    return cam


def bbox_meshes(objects):
    bpy.context.view_layer.update()
    corners = []
    for ob in objects:
        if ob.type != "MESH":
            continue
        for c in ob.bound_box:
            corners.append(ob.matrix_world @ Vector(c))
    lo = Vector((min(c[i] for c in corners) for i in range(3)))
    hi = Vector((max(c[i] for c in corners) for i in range(3)))
    return lo, hi, (hi - lo).length


def main() -> int:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    print("==> building connected Crew Dragon seat assembly")
    meta = build_assembly()

    # Recline entire assembly via root empty
    assembly = bpy.data.objects["Seat_Assembly"]
    recline_pivot = bpy.data.objects.new("Seat_Recline_Pivot", None)
    bpy.context.scene.collection.objects.link(recline_pivot)
    parent_keep(assembly, recline_pivot)
    recline_pivot.rotation_euler = (math.radians(-10), 0, 0)

    lo, hi, diag = bbox_meshes(meta["objects"])
    center = (lo + hi) / 2
    radius = diag / 2
    print(f"bbox diag={diag:.3f}  objects={len([o for o in bpy.data.objects if o.type=='MESH'])}")

    setup_lights(meta["lights"], center, diag)
    scene = bpy.context.scene
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "EEVEE", "CYCLES"):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            continue
    if "EEVEE" in scene.render.engine:
        try:
            scene.eevee.use_raytracing = True
        except AttributeError:
            pass

    def render(cam, path):
        scene.camera = cam
        scene.render.resolution_x, scene.render.resolution_y = 1600, 1200
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = str(path.with_suffix(""))
        bpy.ops.render.render(write_still=True)
        print(f"wrote {path}")

    render(add_camera("Cam_Front", Vector((1.15, 1.20, 0.35)), center + Vector((0, 0.05, -0.05)), radius, lens=36, margin=1.22), PNG_OUT)
    render(add_camera("Cam_Side", Vector((1.7, 0.25, 0.10)), center, radius, lens=40), PNG_OUT_SIDE)
    render(add_camera("Cam_Mount", Vector((1.2, 0.85, -0.25)), center + Vector((0, 0.20, -0.18)), radius * 0.70, lens=45, margin=1.12), PNG_OUT_MOUNT)

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT))
    print(f"saved {BLEND_OUT}")

    # Verify hierarchy connectivity
    print("==> parent hierarchy (root → leaves):")
    def walk(ob, depth=0):
        print("  " * depth + ob.name + (f"  [{ob.type}]" if ob.type != "EMPTY" else "  (pivot)"))
        for ch in sorted(ob.children, key=lambda o: o.name):
            walk(ch, depth + 1)
    walk(recline_pivot)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(1)
