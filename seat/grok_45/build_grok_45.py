#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""High-fidelity procedural reproduction of the SpaceX Crew Dragon seat in
``spacex_crew_dragon_seat.png`` — full assembly, not just the bucket.

Includes every major subsystem visible in the reference:
  * White composite cradle shell + twin head wings + dark suede cushion
  * Side bolsters / arm rails (raised shell rails that cradle the torso)
  * Carbon-fiber footrest loop with twin attachment arms + hinge pins
  * White aluminum mounting bars with pivot collar, attachment clevises,
    fasteners, and the circular recessed side detail

Run::

    /snap/bin/blender -b -P seat/grok_45/build_grok_45.py

Outputs ``seat/grok_45/grok_45.blend`` and verification renders
``seat/grok_45/grok_45_render*.png``.
"""

from __future__ import annotations

import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

SEAT_DIR = Path(__file__).resolve().parent
BLEND_OUT = SEAT_DIR / "grok_45.blend"
PNG_OUT = SEAT_DIR / "grok_45_render.png"
PNG_OUT_SIDE = SEAT_DIR / "grok_45_render_side.png"
PNG_OUT_MOUNT = SEAT_DIR / "grok_45_render_mount.png"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def link_only(ob: bpy.types.Object, collection: bpy.types.Collection) -> bpy.types.Object:
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    collection.objects.link(ob)
    return ob


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
        if "Sheen Roughness" in bsdf.inputs:
            bsdf.inputs["Sheen Roughness"].default_value = 0.5
        if emission is not None:
            for key in ("Emission Color", "Emission"):
                if key in bsdf.inputs:
                    bsdf.inputs[key].default_value = (*emission, 1.0)
                    break
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = 2.5
    return m


def carbon_mat(name: str = "carbon_fiber") -> bpy.types.Material:
    """Dark glossy carbon with a procedural twill weave normal."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name=name)
    m.use_nodes = True
    nt = m.node_tree
    nodes = nt.nodes
    links = nt.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (700, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (400, 0)
    bsdf.inputs["Base Color"].default_value = (0.04, 0.041, 0.043, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.22
    bsdf.inputs["Metallic"].default_value = 0.25
    for key in ("Coat Weight", "Clearcoat"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = 0.7
            break
    for key in ("Coat Roughness", "Clearcoat Roughness"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = 0.08
            break

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-900, 0)
    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-700, 0)
    mapping.inputs["Scale"].default_value = (22.0, 22.0, 22.0)
    mapping.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(45.0))

    wave_u = nodes.new("ShaderNodeTexWave")
    wave_u.location = (-480, 160)
    wave_u.wave_type = "BANDS"
    wave_u.bands_direction = "X"
    wave_u.inputs["Scale"].default_value = 5.0
    wave_u.inputs["Distortion"].default_value = 0.0
    wave_u.inputs["Detail"].default_value = 0.0

    wave_v = nodes.new("ShaderNodeTexWave")
    wave_v.location = (-480, -40)
    wave_v.wave_type = "BANDS"
    wave_v.bands_direction = "Y"
    wave_v.inputs["Scale"].default_value = 5.0
    wave_v.inputs["Distortion"].default_value = 0.0
    wave_v.inputs["Detail"].default_value = 0.0

    mix = nodes.new("ShaderNodeMix")
    mix.location = (-260, 60)
    mix.data_type = "FLOAT"
    mix.inputs["Factor"].default_value = 0.5

    # Tint base color slightly by the weave so the pattern reads even without
    # strong normals (EEVEE Next is soft on tiny bump at this scale).
    color_ramp = nodes.new("ShaderNodeValToRGB")
    color_ramp.location = (-40, 200)
    color_ramp.color_ramp.elements[0].position = 0.35
    color_ramp.color_ramp.elements[0].color = (0.025, 0.026, 0.028, 1.0)
    color_ramp.color_ramp.elements[1].position = 0.65
    color_ramp.color_ramp.elements[1].color = (0.07, 0.072, 0.075, 1.0)

    bump = nodes.new("ShaderNodeBump")
    bump.location = (120, -80)
    bump.inputs["Strength"].default_value = 0.7
    bump.inputs["Distance"].default_value = 0.006

    links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], wave_u.inputs["Vector"])
    links.new(mapping.outputs["Vector"], wave_v.inputs["Vector"])
    links.new(wave_u.outputs["Fac"], mix.inputs["A"])
    links.new(wave_v.outputs["Fac"], mix.inputs["B"])
    links.new(mix.outputs["Result"], color_ramp.inputs["Fac"])
    links.new(mix.outputs["Result"], bump.inputs["Height"])
    links.new(color_ramp.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


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


# ---------------------------------------------------------------------------
# Spline / loft
# ---------------------------------------------------------------------------


def _catmull_rom(p0: Vector, p1: Vector, p2: Vector, p3: Vector, t: float) -> Vector:
    t2 = t * t
    t3 = t2 * t
    return 0.5 * (
        (2.0 * p1)
        + (-p0 + p2) * t
        + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
        + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
    )


def resample_spline(controls: list[tuple[float, float, float]], n: int) -> list[Vector]:
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


def resample_scalar(values: list[float], n: int) -> list[float]:
    m = len(values)
    out = []
    for i in range(n):
        u = (i / (n - 1)) * (m - 1)
        lo = int(math.floor(u))
        hi = min(lo + 1, m - 1)
        frac = u - lo
        out.append(values[lo] * (1.0 - frac) + values[hi] * frac)
    return out


def loft_channel(
    name: str,
    spine_controls: list[tuple[float, float, float]],
    halfwidths: list[float],
    depths: list[float],
    rims: list[float],
    *,
    ref_axis: Vector,
    n_rings: int,
    profile_n: int,
    material: bpy.types.Material,
    collection: bpy.types.Collection,
    seed_out: Vector,
    center_offset: float = 0.0,
) -> bpy.types.Object:
    spine = resample_spline(spine_controls, n_rings)
    hw = resample_scalar(halfwidths, n_rings)
    dp = resample_scalar(depths, n_rings)
    rm = resample_scalar(rims, n_rings)

    tangents = []
    for i in range(n_rings):
        if i == 0:
            t = (spine[1] - spine[0]).normalized()
        elif i == n_rings - 1:
            t = (spine[-1] - spine[-2]).normalized()
        else:
            t = (spine[i + 1] - spine[i - 1]).normalized()
        tangents.append(t)

    rings: list[list[Vector]] = []
    prev_up = None
    for i in range(n_rings):
        t = tangents[i]
        right = ref_axis - t * ref_axis.dot(t)
        if right.length < 1e-6:
            alt = Vector((0, 0, 1)) if abs(ref_axis.z) < 0.9 else Vector((1, 0, 0))
            right = alt - t * alt.dot(t)
        right.normalize()
        up = t.cross(right).normalized()
        if prev_up is None:
            if up.dot(seed_out) < 0.0:
                up = -up
                right = -right
        else:
            if up.dot(prev_up) < 0.0:
                up = -up
                right = -right
        prev_up = up

        ring_center = spine[i] + up * center_offset
        ring = []
        for j in range(profile_n):
            v = -1.0 + 2.0 * j / (profile_n - 1)
            x_off = v * hw[i]
            z_off = -dp[i] * (1.0 - v * v) + rm[i] * (v * v)
            ring.append(ring_center + right * x_off + up * z_off)
        rings.append(ring)

    bm = bmesh.new()
    bm_rings = [[bm.verts.new(p) for p in ring] for ring in rings]
    faces = []
    for i in range(n_rings - 1):
        for j in range(profile_n - 1):
            a = bm_rings[i][j]
            b = bm_rings[i][j + 1]
            c = bm_rings[i + 1][j + 1]
            d = bm_rings[i + 1][j]
            try:
                f = bm.faces.new((a, b, c, d))
                faces.append(f)
            except ValueError:
                continue

    bm.normal_update()
    avg_normal = Vector((0.0, 0.0, 0.0))
    for f in faces:
        avg_normal += f.normal
    if avg_normal.dot(seed_out) < 0.0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)

    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges)

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    ob = bpy.data.objects.new(name, mesh)
    collection.objects.link(ob)
    assign(ob, material)
    return ob


# ---------------------------------------------------------------------------
# Primitive builders
# ---------------------------------------------------------------------------


def make_cylinder(
    name: str,
    *,
    radius: float,
    depth: float,
    loc: tuple[float, float, float],
    material: bpy.types.Material,
    collection: bpy.types.Collection,
    axis: str = "Z",
    vertices: int = 32,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius, depth=depth, location=loc, vertices=vertices
    )
    ob = bpy.context.active_object
    ob.name = name
    if axis == "X":
        ob.rotation_euler = (0.0, math.pi / 2.0, 0.0)
    elif axis == "Y":
        ob.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    assign(ob, material)
    link_only(ob, collection)
    add_bevel(ob, width=min(0.002, radius * 0.15), segments=2)
    shade_auto_smooth(ob)
    return ob


def make_box(
    name: str,
    *,
    size: tuple[float, float, float],
    loc: tuple[float, float, float],
    material: bpy.types.Material,
    collection: bpy.types.Collection,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
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
    return ob


def make_torus_loop(
    name: str,
    *,
    major: float,
    minor: float,
    loc: tuple[float, float, float],
    material: bpy.types.Material,
    collection: bpy.types.Collection,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> bpy.types.Object:
    """Rounded rectangular footrest built from a scaled torus (D-loop look)."""
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major,
        minor_radius=minor,
        major_segments=48,
        minor_segments=16,
        location=loc,
    )
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.rotation_euler = rotation
    assign(ob, material)
    link_only(ob, collection)
    shade_auto_smooth(ob, 50.0)
    return ob


def make_rounded_rect_tube(
    name: str,
    *,
    width: float,
    height: float,
    tube_r: float,
    loc: tuple[float, float, float],
    material: bpy.types.Material,
    collection: bpy.types.Collection,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    corner_r: float = 0.06,
) -> bpy.types.Object:
    """Open rectangular loop with rounded corners — carbon footrest frame."""
    hw = width / 2.0
    hh = height / 2.0
    cr = min(corner_r, hw - tube_r * 1.1, hh - tube_r * 1.1)

    # Build a bezier curve rectangle with rounded corners, then bevel it.
    curve = bpy.data.curves.new(name + "_curve", type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 12
    curve.bevel_depth = tube_r
    curve.bevel_resolution = 6
    curve.fill_mode = "FULL"

    spline = curve.splines.new("BEZIER")
    # 8 control points: 2 per corner (approximating rounded rect)
    n = 8
    spline.bezier_points.add(n - 1)

    def set_pt(i: int, x: float, y: float, hx: float, hy: float) -> None:
        bp = spline.bezier_points[i]
        bp.co = (x, y, 0.0)
        bp.handle_left_type = "ALIGNED"
        bp.handle_right_type = "ALIGNED"
        bp.handle_left = (x - hx, y - hy, 0.0)
        bp.handle_right = (x + hx, y + hy, 0.0)

    # Clockwise from bottom-left, rounded corners via short handles.
    k = cr * 0.55  # bezier handle length for circular-ish corner
    pts = [
        # bottom edge, left → right
        (-hw + cr, -hh, k, 0.0),
        (hw - cr, -hh, k, 0.0),
        # right edge, bottom → top
        (hw, -hh + cr, 0.0, k),
        (hw, hh - cr, 0.0, k),
        # top edge, right → left
        (hw - cr, hh, -k, 0.0),
        (-hw + cr, hh, -k, 0.0),
        # left edge, top → bottom
        (-hw, hh - cr, 0.0, -k),
        (-hw, -hh + cr, 0.0, -k),
    ]
    for i, (x, y, hx, hy) in enumerate(pts):
        set_pt(i, x, y, hx, hy)
    spline.use_cyclic_u = True

    ob = bpy.data.objects.new(name, curve)
    collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = rotation
    assign(ob, material)

    # Convert to mesh for solid geometry in the .blend
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.ops.object.convert(target="MESH")
    ob = bpy.context.active_object
    ob.name = name
    shade_auto_smooth(ob, 50.0)
    return ob


# ---------------------------------------------------------------------------
# Seat subsystems
# ---------------------------------------------------------------------------


def build_shell_and_cushion(
    c_shell: bpy.types.Collection,
    c_cushion: bpy.types.Collection,
    c_hw: bpy.types.Collection,
    materials: dict,
) -> list[bpy.types.Object]:
    objs: list[bpy.types.Object] = []
    X = Vector((1, 0, 0))
    Y = Vector((0, 1, 0))
    m_shell = materials["shell"]
    m_cushion = materials["cushion"]
    m_trim = materials["trim"]
    m_hw = materials["metal"]

    # Local frame: Y forward (pan tip), Z up, X left/right.
    # Raised rims on the sides form the torso "arm" bolsters.
    main_spine = [
        (0.0, -0.055, 0.560),
        (0.0, -0.035, 0.470),
        (0.0, -0.010, 0.360),
        (0.0, 0.015, 0.240),
        (0.0, 0.038, 0.130),
        (0.0, 0.052, 0.055),
        (0.0, 0.062, 0.010),
        (0.0, 0.075, -0.010),
        (0.0, 0.150, -0.020),
        (0.0, 0.300, -0.010),
        (0.0, 0.420, 0.010),
        (0.0, 0.480, 0.025),
    ]
    # Wider mid-section + taller side rails = visible arm bolsters
    main_hw = [
        0.148, 0.195, 0.228, 0.252, 0.268,
        0.274, 0.276, 0.274, 0.255, 0.210,
        0.125, 0.030,
    ]
    main_dp = [
        0.018, 0.030, 0.048, 0.064, 0.078,
        0.072, 0.062, 0.054, 0.042, 0.028,
        0.016, 0.006,
    ]
    # Tall rims at torso = arm bolsters; lower at pan tip
    main_rim = [
        0.038, 0.055, 0.078, 0.095, 0.100,
        0.090, 0.072, 0.055, 0.036, 0.022,
        0.012, 0.004,
    ]

    shell_main = loft_channel(
        "Shell_Main",
        main_spine,
        main_hw,
        main_dp,
        main_rim,
        ref_axis=X,
        n_rings=76,
        profile_n=25,
        material=m_shell,
        collection=c_shell,
        seed_out=Vector((0.0, -1.0, 0.15)),
    )
    add_solidify(shell_main, 0.014)
    add_subsurf(shell_main, 1)
    shade_auto_smooth(shell_main)
    objs.append(shell_main)

    cushion_main = loft_channel(
        "Cushion_Main",
        main_spine,
        [max(w - 0.048, 0.0) for w in main_hw],
        [d * 0.55 + 0.010 for d in main_dp],
        [r * 0.22 for r in main_rim],
        ref_axis=X,
        n_rings=68,
        profile_n=21,
        material=m_cushion,
        collection=c_cushion,
        seed_out=Vector((0.0, -1.0, 0.15)),
        center_offset=-0.024,
    )
    add_solidify(cushion_main, 0.032)
    add_subsurf(cushion_main, 1)
    shade_auto_smooth(cushion_main, 50.0)
    objs.append(cushion_main)

    # Twin head wings — forward-curling paddles framing the helmet notch
    for side, sign in (("L", 1.0), ("R", -1.0)):
        wing_spine = [
            (sign * 0.155, -0.045, 0.520),
            (sign * 0.210, -0.005, 0.610),
            (sign * 0.260, 0.050, 0.690),
            (sign * 0.290, 0.120, 0.740),
        ]
        wing_hw = [0.130, 0.115, 0.078, 0.024]
        wing_dp = [0.022, 0.024, 0.018, 0.006]
        wing_rim = [0.026, 0.030, 0.020, 0.006]

        shell_wing = loft_channel(
            f"Shell_Wing_{side}",
            wing_spine,
            wing_hw,
            wing_dp,
            wing_rim,
            ref_axis=Y,
            n_rings=36,
            profile_n=17,
            material=m_shell,
            collection=c_shell,
            seed_out=Vector((sign * 0.55, -0.55, 0.35)),
        )
        add_solidify(shell_wing, 0.009)
        add_subsurf(shell_wing, 1)
        shade_auto_smooth(shell_wing)
        objs.append(shell_wing)

        cushion_wing = loft_channel(
            f"Cushion_Wing_{side}",
            wing_spine,
            [max(w - 0.032, 0.0) for w in wing_hw],
            [d * 0.5 + 0.004 for d in wing_dp],
            [r * 0.24 for r in wing_rim],
            ref_axis=Y,
            n_rings=30,
            profile_n=13,
            material=m_cushion,
            collection=c_cushion,
            seed_out=Vector((sign * 0.55, -0.55, 0.35)),
            center_offset=-0.014,
        )
        add_solidify(cushion_wing, 0.016)
        add_subsurf(cushion_wing, 1)
        shade_auto_smooth(cushion_wing, 50.0)
        objs.append(cushion_wing)

        # Arm pad — small padded shelf on the inner face of each side bolster
        # (Crew Dragon has no traditional armrests; these are the lateral
        # torso/arm bolsters visible in the photo as raised shell rails).
        arm_pad = make_box(
            f"Arm_Pad_{side}",
            size=(0.055, 0.110, 0.028),
            loc=(sign * 0.195, 0.16, 0.14),
            material=m_cushion,
            collection=c_cushion,
            rotation=(math.radians(-12.0), math.radians(sign * -8.0), 0.0),
        )
        objs.append(arm_pad)

        # Dark gasket/trim strip along the shell rim near the arm pad
        trim = make_box(
            f"Trim_Strip_{side}",
            size=(0.008, 0.160, 0.012),
            loc=(sign * 0.270, 0.14, 0.16),
            material=m_trim,
            collection=c_hw,
            rotation=(math.radians(15.0), 0.0, 0.0),
        )
        objs.append(trim)

        # Small silver latch/inset on the outer bolster (visible in photo)
        inset = make_box(
            f"Bolster_Inset_{side}",
            size=(0.018, 0.012, 0.006),
            loc=(sign * 0.285, 0.22, 0.08),
            material=m_hw,
            collection=c_hw,
            rotation=(math.radians(-8.0), 0.0, 0.0),
        )
        objs.append(inset)

    # Front-lip hardware plate
    plate = make_box(
        "Front_Lip_Plate",
        size=(0.048, 0.022, 0.006),
        loc=(0.0, 0.400, 0.016),
        material=m_hw,
        collection=c_hw,
        rotation=(math.radians(-6.0), 0.0, 0.0),
    )
    objs.append(plate)

    return objs


def build_footrest(
    c_foot: bpy.types.Collection,
    materials: dict,
) -> list[bpy.types.Object]:
    """Carbon-fiber rectangular footrest loop + twin attachment arms + pins.

    In the reference the loop is a large open rectangle roughly in a plane
    facing the occupant (tilted ~35° from vertical), extending forward and
    slightly down from under the seat pan — not hanging flat like a ladder.
    """
    objs: list[bpy.types.Object] = []
    m_carbon = materials["carbon"]
    m_metal = materials["metal_dark"]

    # Larger loop, tube section closer to photo scale, facing the sitter.
    # Local curve XY becomes the loop plane; we rotate ~55° about X so the
    # far edge drops and the near edge sits under the pan tip.
    loop = make_rounded_rect_tube(
        "Footrest_Loop",
        width=0.48,
        height=0.62,
        tube_r=0.020,
        loc=(0.0, 0.78, -0.18),
        material=m_carbon,
        collection=c_foot,
        rotation=(math.radians(55.0), 0.0, 0.0),
        corner_r=0.085,
    )
    objs.append(loop)

    # Twin thick carbon arms from seat-pan underside to the near crossbar
    for side, sign in (("L", 1.0), ("R", -1.0)):
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.022,
            depth=0.34,
            location=(sign * 0.155, 0.55, -0.05),
            vertices=28,
        )
        arm = bpy.context.active_object
        arm.name = f"Footrest_Arm_{side}"
        # Slightly flattened oval cross-section (carbon arm look)
        arm.scale = (1.15, 0.70, 1.0)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        arm.rotation_euler = (math.radians(48.0), 0.0, math.radians(sign * 6.0))
        assign(arm, m_carbon)
        link_only(arm, c_foot)
        add_bevel(arm, width=0.0025, segments=2)
        shade_auto_smooth(arm)
        objs.append(arm)

        # Hinge pin / clevis at seat attachment
        pin = make_cylinder(
            f"Footrest_Pin_{side}",
            radius=0.009,
            depth=0.048,
            loc=(sign * 0.175, 0.38, 0.005),
            material=m_metal,
            collection=c_foot,
            axis="X",
            vertices=20,
        )
        objs.append(pin)

        # Clevis ear (dark plate) where arm meets shell underside
        clevis = make_box(
            f"Footrest_Clevis_{side}",
            size=(0.034, 0.042, 0.018),
            loc=(sign * 0.168, 0.375, 0.000),
            material=m_carbon,
            collection=c_foot,
            rotation=(math.radians(8.0), 0.0, 0.0),
        )
        objs.append(clevis)

        # Bolt head detail on outer face of clevis
        bolt = make_cylinder(
            f"Footrest_Bolt_{side}",
            radius=0.007,
            depth=0.010,
            loc=(sign * 0.188, 0.375, 0.000),
            material=m_metal,
            collection=c_foot,
            axis="X",
            vertices=16,
        )
        objs.append(bolt)

        # Secondary fastener on the loop end of each arm
        bolt2 = make_cylinder(
            f"Footrest_ArmBolt_{side}",
            radius=0.006,
            depth=0.012,
            loc=(sign * 0.155, 0.70, -0.18),
            material=m_metal,
            collection=c_foot,
            axis="X",
            vertices=12,
        )
        objs.append(bolt2)

    return objs


def build_mount(
    c_mount: bpy.types.Collection,
    materials: dict,
) -> list[bpy.types.Object]:
    """White aluminum mounting bars, pivot collar, clevises, recessed light."""
    objs: list[bpy.types.Object] = []
    m_alum = materials["aluminum"]
    m_alum_dark = materials["aluminum_dark"]
    m_metal = materials["metal"]
    m_led = materials["led"]

    # Main lateral pivot tube under the seat pan (white aluminum)
    pivot = make_cylinder(
        "Mount_Pivot_Tube",
        radius=0.042,
        depth=0.38,
        loc=(0.0, 0.12, -0.10),
        material=m_alum,
        collection=c_mount,
        axis="X",
        vertices=40,
    )
    objs.append(pivot)

    # Central white structural housing / pillar body (photo: substantial
    # white mount casting under the seat, not just bare tubes)
    housing = make_box(
        "Mount_Housing",
        size=(0.22, 0.18, 0.10),
        loc=(0.0, 0.12, -0.18),
        material=m_alum,
        collection=c_mount,
        rotation=(math.radians(8.0), 0.0, 0.0),
    )
    objs.append(housing)
    housing_lower = make_box(
        "Mount_Housing_Lower",
        size=(0.16, 0.14, 0.12),
        loc=(0.0, 0.08, -0.32),
        material=m_alum,
        collection=c_mount,
        rotation=(math.radians(12.0), 0.0, 0.0),
    )
    objs.append(housing_lower)

    # End caps on the pivot tube
    for side, sign in (("L", 1.0), ("R", -1.0)):
        cap = make_cylinder(
            f"Mount_Pivot_Cap_{side}",
            radius=0.042,
            depth=0.016,
            loc=(sign * 0.185, 0.12, -0.10),
            material=m_alum,
            collection=c_mount,
            axis="X",
            vertices=32,
        )
        objs.append(cap)

        # Circular recessed detail / LED on the outer face of the right-ish
        # mount (photo shows a glowing circular recess on the side).
        recess = make_cylinder(
            f"Mount_Recess_{side}",
            radius=0.018,
            depth=0.006,
            loc=(sign * 0.196, 0.12, -0.10),
            material=m_alum_dark,
            collection=c_mount,
            axis="X",
            vertices=28,
        )
        objs.append(recess)

        led = make_cylinder(
            f"Mount_LED_{side}",
            radius=0.010,
            depth=0.003,
            loc=(sign * 0.200, 0.12, -0.10),
            material=m_led if side == "R" else m_alum_dark,
            collection=c_mount,
            axis="X",
            vertices=20,
        )
        objs.append(led)

    # Vertical / diagonal aluminum support bars (photo: cluster of white tubes)
    bar_specs = [
        # (name, loc, rot_xyz_deg, radius, length)
        ("Mount_Bar_Aft_L", (-0.10, -0.02, -0.32), (25, 0, 12), 0.018, 0.42),
        ("Mount_Bar_Aft_R", (0.10, -0.02, -0.32), (25, 0, -12), 0.018, 0.42),
        ("Mount_Bar_Fwd_L", (-0.12, 0.22, -0.30), (40, 0, 8), 0.016, 0.36),
        ("Mount_Bar_Fwd_R", (0.12, 0.22, -0.30), (40, 0, -8), 0.016, 0.36),
        ("Mount_Bar_Cross", (0.0, 0.12, -0.38), (0, 90, 0), 0.014, 0.28),
        ("Mount_Bar_Diag", (0.0, 0.05, -0.28), (55, 0, 0), 0.015, 0.30),
    ]
    for name, loc, rot_deg, radius, length in bar_specs:
        bpy.ops.mesh.primitive_cylinder_add(
            radius=radius, depth=length, location=loc, vertices=28
        )
        bar = bpy.context.active_object
        bar.name = name
        bar.rotation_euler = tuple(math.radians(a) for a in rot_deg)
        assign(bar, m_alum)
        link_only(bar, c_mount)
        add_bevel(bar, width=0.002, segments=2)
        shade_auto_smooth(bar)
        objs.append(bar)

    # Attachment clevises / plates where bars meet the pivot and floor
    clevis_specs = [
        ("Mount_Clevis_Pivot_L", (-0.14, 0.12, -0.10), (0.04, 0.05, 0.022)),
        ("Mount_Clevis_Pivot_R", (0.14, 0.12, -0.10), (0.04, 0.05, 0.022)),
        ("Mount_Clevis_Floor_L", (-0.10, -0.10, -0.52), (0.05, 0.06, 0.018)),
        ("Mount_Clevis_Floor_R", (0.10, -0.10, -0.52), (0.05, 0.06, 0.018)),
        ("Mount_Clevis_Floor_C", (0.0, 0.18, -0.50), (0.06, 0.05, 0.018)),
    ]
    for name, loc, size in clevis_specs:
        plate = make_box(
            name,
            size=size,
            loc=loc,
            material=m_alum,
            collection=c_mount,
        )
        objs.append(plate)

    # Fastener heads on clevises (attachment points)
    fastener_locs = [
        (-0.14, 0.12, -0.10),
        (0.14, 0.12, -0.10),
        (-0.10, -0.10, -0.52),
        (0.10, -0.10, -0.52),
        (0.0, 0.18, -0.50),
        (-0.08, 0.12, -0.10),
        (0.08, 0.12, -0.10),
    ]
    for i, loc in enumerate(fastener_locs):
        # Hex-ish bolt head (short cylinder)
        bolt = make_cylinder(
            f"Mount_Bolt_{i}",
            radius=0.007,
            depth=0.008,
            loc=loc,
            material=m_metal,
            collection=c_mount,
            axis="Z",
            vertices=8,
        )
        objs.append(bolt)
        # Washer under bolt
        washer = make_cylinder(
            f"Mount_Washer_{i}",
            radius=0.011,
            depth=0.002,
            loc=(loc[0], loc[1], loc[2] - 0.005),
            material=m_metal,
            collection=c_mount,
            axis="Z",
            vertices=20,
        )
        objs.append(washer)

    # Seat-to-pivot saddle plates (where shell underside bolts to the tube)
    for side, sign in (("L", 1.0), ("R", -1.0)):
        saddle = make_box(
            f"Mount_Saddle_{side}",
            size=(0.055, 0.070, 0.020),
            loc=(sign * 0.09, 0.12, -0.055),
            material=m_alum,
            collection=c_mount,
            rotation=(math.radians(8.0), 0.0, 0.0),
        )
        objs.append(saddle)
        # Pair of bolts on each saddle
        for j, dy in enumerate((-0.018, 0.018)):
            b = make_cylinder(
                f"Mount_SaddleBolt_{side}_{j}",
                radius=0.005,
                depth=0.012,
                loc=(sign * 0.09, 0.12 + dy, -0.042),
                material=m_metal,
                collection=c_mount,
                axis="Z",
                vertices=8,
            )
            objs.append(b)

    # Small spring/strut detail visible under the seat in the photo
    strut = make_cylinder(
        "Mount_Spring_Strut",
        radius=0.010,
        depth=0.14,
        loc=(0.05, 0.20, -0.22),
        material=m_alum_dark,
        collection=c_mount,
        axis="Z",
        vertices=20,
    )
    strut.rotation_euler = (math.radians(35.0), 0.0, math.radians(-20.0))
    objs.append(strut)

    # Coil suggestion: thin torus stack
    for i in range(5):
        t = i / 4.0
        coil = make_cylinder(
            f"Mount_Coil_{i}",
            radius=0.016,
            depth=0.006,
            loc=(0.05 + 0.02 * t, 0.20 + 0.04 * t, -0.28 + 0.055 * t),
            material=m_metal,
            collection=c_mount,
            axis="Z",
            vertices=16,
        )
        objs.append(coil)

    return objs


# ---------------------------------------------------------------------------
# Scene assembly / camera / render
# ---------------------------------------------------------------------------


def recline_seat(objects: list[bpy.types.Object], angle_deg: float = 8.0) -> bpy.types.Object:
    pivot = bpy.data.objects.new("Seat_Recline_Pivot", None)
    bpy.context.scene.collection.objects.link(pivot)
    for ob in objects:
        ob.parent = pivot
    pivot.rotation_euler = (math.radians(-angle_deg), 0.0, 0.0)
    return pivot


def compute_world_bbox(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    bpy.context.view_layer.update()
    corners = []
    for ob in objects:
        if ob.type not in {"MESH", "CURVE"}:
            continue
        for corner in ob.bound_box:
            corners.append(ob.matrix_world @ Vector(corner))
    lo = Vector((min(c[i] for c in corners) for i in range(3)))
    hi = Vector((max(c[i] for c in corners) for i in range(3)))
    return lo, hi


def setup_lights(lights_col: bpy.types.Collection, center: Vector, scale: float) -> None:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.05, 0.053, 0.06, 1.0)
    bg.inputs[1].default_value = 1.0

    specs = [
        ("Key", 55, 1.1 * scale, Vector((1.2, -1.4, 1.6)) * scale, (55, 0, 35)),
        ("Fill", 22, 1.4 * scale, Vector((-1.5, -0.4, 0.9)) * scale, (70, 0, -60)),
        ("Rim", 32, 0.9 * scale, Vector((0.2, 1.4, 1.1)) * scale, (-55, 0, 10)),
        ("Bounce", 18, 1.5 * scale, Vector((0.2, 1.5, -0.5)) * scale, (-100, 0, 0)),
    ]
    for lname, energy, size, offset, rot_deg in specs:
        light = bpy.data.objects.new(lname, bpy.data.lights.new(lname, "AREA"))
        light.data.energy = energy
        light.data.size = size
        light.location = center + offset
        light.rotation_euler = tuple(math.radians(d) for d in rot_deg)
        bpy.context.scene.collection.objects.link(light)
        lights_col.objects.link(light)
        bpy.context.scene.collection.objects.unlink(light)


def add_camera(
    name: str,
    direction: Vector,
    center: Vector,
    radius: float,
    *,
    lens: float = 40.0,
    width: int = 1600,
    height: int = 1200,
    margin: float = 1.30,
) -> bpy.types.Object:
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    sensor_w = cam_data.sensor_width
    hfov = 2.0 * math.atan(sensor_w / (2.0 * lens))
    vfov = 2.0 * math.atan(math.tan(hfov / 2.0) * (height / width))
    fov = min(hfov, vfov)
    distance = (radius / math.sin(fov / 2.0)) * margin

    cam = bpy.data.objects.new(name, cam_data)
    cam.location = center + direction.normalized() * distance
    look_dir = center - cam.location
    cam.rotation_euler = look_dir.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(cam)
    return cam


def set_engine(scene: bpy.types.Scene) -> None:
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "EEVEE", "CYCLES"):
        try:
            scene.render.engine = eng
            return
        except TypeError:
            continue


def render_to(cam: bpy.types.Object, path: Path, *, width: int, height: int) -> None:
    scene = bpy.context.scene
    scene.camera = cam
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.filepath = str(path.with_suffix(""))
    bpy.ops.render.render(write_still=True)
    print(f"wrote {path}")


def build_materials() -> dict:
    return {
        "shell": mat("shell_composite", (0.745, 0.752, 0.760), roughness=0.32, clearcoat=0.22),
        "cushion": mat("cushion_suede", (0.016, 0.016, 0.019), roughness=0.88, sheen=0.25),
        "trim": mat("trim_gasket", (0.12, 0.13, 0.14), roughness=0.75),
        "carbon": carbon_mat(),
        # Crew Dragon mount structure is white-painted aluminum, not bare metal
        "aluminum": mat(
            "aluminum_white",
            (0.82, 0.83, 0.85),
            roughness=0.38,
            metallic=0.18,
            clearcoat=0.12,
        ),
        "aluminum_dark": mat(
            "aluminum_dark",
            (0.42, 0.43, 0.45),
            roughness=0.42,
            metallic=0.35,
        ),
        "metal": mat("hardware_metal", (0.62, 0.63, 0.65), roughness=0.25, metallic=0.90),
        "metal_dark": mat("hardware_dark", (0.18, 0.18, 0.20), roughness=0.35, metallic=0.85),
        "led": mat("led_glow", (0.85, 0.90, 0.95), roughness=0.2, emission=(0.7, 0.85, 1.0)),
    }


def build_seat() -> dict:
    root = col("Seat")
    c_shell = col("01_Shell", root)
    c_cushion = col("02_Cushion", root)
    c_foot = col("03_Footrest", root)
    c_mount = col("04_Mount", root)
    c_hw = col("05_Hardware", root)
    c_lights = col("06_Lights", root)

    materials = build_materials()
    objs: list[bpy.types.Object] = []
    objs += build_shell_and_cushion(c_shell, c_cushion, c_hw, materials)
    objs += build_footrest(c_foot, materials)
    objs += build_mount(c_mount, materials)

    return {
        "root": root,
        "lights": c_lights,
        "objects": objs,
    }


def main() -> int:
    bpy.ops.wm.read_factory_settings(use_empty=True)

    print("==> building full Crew Dragon seat assembly")
    meta = build_seat()

    print("==> reclining assembly")
    recline_seat(meta["objects"], angle_deg=10.0)

    lo, hi = compute_world_bbox(meta["objects"])
    center = (lo + hi) / 2.0
    diag = (hi - lo).length
    radius = diag / 2.0
    print(f"bbox lo={tuple(round(x, 3) for x in lo)} hi={tuple(round(x, 3) for x in hi)} diag={diag:.3f}")

    print("==> lights")
    setup_lights(meta["lights"], center, diag)

    scene = bpy.context.scene
    set_engine(scene)
    if scene.render.engine.startswith("BLENDER_EEVEE") or scene.render.engine == "EEVEE":
        try:
            scene.eevee.use_raytracing = True
        except AttributeError:
            pass

    # Three-quarter from front-right — matches reference photo framing
    # (seat facing camera-right, footrest and mount visible in foreground)
    cam_front = add_camera(
        "Cam_Front",
        Vector((1.15, 1.20, 0.35)),
        center + Vector((0.0, 0.05, -0.05)),
        radius,
        lens=36.0,
        margin=1.22,
    )
    print("==> render front 3/4")
    render_to(cam_front, PNG_OUT, width=1600, height=1200)

    # Side profile — shell curve + footrest + mount bars
    cam_side = add_camera("Cam_Side", Vector((1.7, 0.25, 0.10)), center, radius, lens=40.0)
    print("==> render side")
    render_to(cam_side, PNG_OUT_SIDE, width=1600, height=1200)

    # Low mount-detail view — aluminum bars / clevises / footrest attachment
    cam_mount = add_camera(
        "Cam_Mount",
        Vector((1.2, 0.85, -0.25)),
        center + Vector((0.0, 0.20, -0.18)),
        radius * 0.70,
        lens=45.0,
        margin=1.12,
    )
    print("==> render mount detail")
    render_to(cam_mount, PNG_OUT_MOUNT, width=1600, height=1200)

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT))
    print(f"saved {BLEND_OUT}")
    print(f"objects: {len(meta['objects'])}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback

        traceback.print_exc()
        raise SystemExit(1)
