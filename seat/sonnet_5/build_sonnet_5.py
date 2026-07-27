#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Procedural high-fidelity reproduction of the SpaceX Crew Dragon seat shown
in `spacex_crew_dragon_seat.png`, built as hand-lofted shell geometry (no
boxes/primitives standing in for the organic shell — every surface is a
ring-lofted channel matching the seat's actual silhouette).

Shape read from the reference photo:
  * A single continuous hard-shell "cradle" (open U/scoop channel, constant
    topology, varying width/depth/rail-height) running from the seat-pan
    front tip, back through the pan, around the lumbar/mid-back bolster,
    up to the shoulders.
  * Two separate blade-like "wings" that attach at the top-outboard edge of
    the backrest (shoulder height) and sweep up, outward, and slightly
    forward, tapering to a blunt point — these frame the head/neck opening
    that reads as a gap in the photo (the porthole is visible *between* the
    wings, since there is genuinely no shell material spanning that gap).
  * A recessed black suede cushion insert nested inside the shell (pan,
    backrest, and inboard wing faces), inset from the shell rim.
  * A small pale hardware plate on the seat-pan front lip (as in the photo).

Run::

    /snap/bin/blender -b -P seat/sonnet_5/build_sonnet_5.py

Outputs ``seat/sonnet_5/sonnet_5.blend`` and verification renders
``seat/sonnet_5/sonnet_5_render*.png``.
"""

from __future__ import annotations

import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

SEAT_DIR = Path(__file__).resolve().parent
BLEND_OUT = SEAT_DIR / "sonnet_5.blend"
PNG_OUT = SEAT_DIR / "sonnet_5_render.png"
PNG_OUT_SIDE = SEAT_DIR / "sonnet_5_render_side.png"

# ---------------------------------------------------------------------------
# Small generic helpers (collections / materials)
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


def mat(
    name: str,
    color,
    *,
    roughness=0.45,
    metallic=0.0,
    clearcoat=0.0,
    sheen=0.0,
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
    return m


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


# ---------------------------------------------------------------------------
# Spline / scalar resampling
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


# ---------------------------------------------------------------------------
# Ring-loft: builds an open U/scoop channel surface along a 3D spine.
# ---------------------------------------------------------------------------


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
    """Loft an open U-shaped channel: at each ring the profile runs from
    (-halfwidth, rim height) through (0, -depth) to (+halfwidth, rim height)
    — i.e. a shallow bowl whose side rails can be raised (rim) to form a
    wing/wall silhouette. `ref_axis` picks which world axis defines the
    channel's span direction (X for the main shell, Y for the wings) via
    Gram-Schmidt against the local spine tangent.

    Ring-to-ring orientation is kept continuous by comparing each new
    frame to the *previous* ring's frame (not a single fixed reference
    vector) — a fixed reference can be >90 deg from the true local outward
    normal once the spine bends through a right angle (backrest -> pan),
    which otherwise flips the frame mid-surface and creates a visible seam.
    `seed_out` only seeds the sign choice for the very first ring.
    `center_offset` shifts every ring inward/outward along its own local
    "up" (outward normal) by a fixed distance — used to nest the cushion
    just inside the shell surface without hand-authoring a second spine.
    """
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
    prev_right = None
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
        prev_up, prev_right = up, right

        ring_center = spine[i] + up * center_offset
        ring = []
        for j in range(profile_n):
            v = -1.0 + 2.0 * j / (profile_n - 1)
            x_off = v * hw[i]
            z_off = -dp[i] * (1.0 - v * v) + rm[i] * (v * v)
            p = ring_center + right * x_off + up * z_off
            ring.append(p)
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
    if mesh.materials:
        mesh.materials[0] = material
    else:
        mesh.materials.append(material)

    return ob


def add_solidify(ob: bpy.types.Object, thickness: float, *, offset: float = -1.0) -> None:
    mod = ob.modifiers.new("Shell", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = offset
    mod.use_rim = True
    mod.use_rim_only = False
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=mod.name)


# ---------------------------------------------------------------------------
# Seat build
# ---------------------------------------------------------------------------


def build_seat() -> dict:
    root = col("Seat")
    c_shell = col("01_Shell", root)
    c_cushion = col("02_Cushion", root)
    c_hw = col("03_Hardware", root)
    c_lights = col("04_Lights", root)

    m_shell = mat("shell_composite", (0.745, 0.752, 0.760), roughness=0.34, clearcoat=0.15)
    m_cushion = mat("cushion_suede", (0.016, 0.016, 0.019), roughness=0.85, sheen=0.2)
    m_hw = mat("hardware_aluminum", (0.65, 0.66, 0.68), roughness=0.28, metallic=0.85)

    X = Vector((1, 0, 0))
    Y = Vector((0, 1, 0))

    all_objects: list[bpy.types.Object] = []

    # --- Main shell: backrest-top -> lumbar -> seat crease -> pan -> tip ---
    # Local seat frame (unreclined): Y = fore/aft (0 at backrest, + forward),
    # Z = up (0 at seat-pan surface). X = left/right, symmetric about 0.
    # Extra closely-spaced stations around the crease (S4a/S4b) sharpen that
    # bend a little so the pan reads as a distinct flare, not a smooth cone.
    main_spine = [
        (0.0, -0.055, 0.560),   # S0 top of backrest (wings attach nearby)
        (0.0, -0.035, 0.470),   # S1 shoulder
        (0.0, -0.010, 0.360),   # S2 upper-mid back
        (0.0, 0.015, 0.240),    # S3 mid back
        (0.0, 0.038, 0.130),    # S4 lumbar bolster (deepest, widest)
        (0.0, 0.052, 0.055),    # S4a easing into the crease
        (0.0, 0.062, 0.010),    # S4b crease
        (0.0, 0.075, -0.010),   # S5 seat crease / pan start
        (0.0, 0.150, -0.020),   # S6 pan under thighs (wide, nearly flat)
        (0.0, 0.300, -0.010),   # S7 pan mid-front
        (0.0, 0.420, 0.010),    # S8 pan near front, slight lip-up
        (0.0, 0.480, 0.025),    # S9 pan front tip (rounded, not a needle)
    ]
    main_hw = [
        0.148, 0.192, 0.222, 0.242, 0.252,
        0.256, 0.258, 0.258, 0.248, 0.205,
        0.120, 0.028,
    ]
    main_dp = [
        0.016, 0.028, 0.042, 0.056, 0.066,
        0.062, 0.056, 0.050, 0.038, 0.026,
        0.016, 0.006,
    ]
    main_rim = [
        0.030, 0.042, 0.054, 0.058, 0.056,
        0.050, 0.044, 0.036, 0.024, 0.016,
        0.010, 0.004,
    ]

    shell_main = loft_channel(
        "Shell_Main",
        main_spine,
        main_hw,
        main_dp,
        main_rim,
        ref_axis=X,
        n_rings=72,
        profile_n=23,
        material=m_shell,
        collection=c_shell,
        seed_out=Vector((0.0, -1.0, 0.15)),
    )
    add_solidify(shell_main, 0.013)
    add_subsurf(shell_main, 1)
    shade_auto_smooth(shell_main)
    all_objects.append(shell_main)

    cushion_main = loft_channel(
        "Cushion_Main",
        main_spine,
        [max(w - 0.044, 0.0) for w in main_hw],
        [d * 0.55 + 0.008 for d in main_dp],
        [r * 0.24 for r in main_rim],
        ref_axis=X,
        n_rings=64,
        profile_n=19,
        material=m_cushion,
        collection=c_cushion,
        seed_out=Vector((0.0, -1.0, 0.15)),
        center_offset=-0.022,
    )
    add_solidify(cushion_main, 0.030)
    add_subsurf(cushion_main, 1)
    shade_auto_smooth(cushion_main, 50.0)
    all_objects.append(cushion_main)

    # --- Wings: attach near S0/S1 outer rim, sweep up/out to a blunt point.
    # Short + wide-based (paddle-like), not a long thin blade — matched to
    # the photo's proportions (wing height above the attach point is roughly
    # comparable to its own base width).
    for side, sign in (("L", 1.0), ("R", -1.0)):
        wing_spine = [
            (sign * 0.150, -0.045, 0.520),   # base, tucked against main shell
            (sign * 0.205, -0.010, 0.610),
            (sign * 0.255, 0.045, 0.685),
            (sign * 0.285, 0.110, 0.735),    # tip curls forward (blunt point)
        ]
        wing_hw = [0.125, 0.110, 0.075, 0.022]
        wing_dp = [0.020, 0.022, 0.017, 0.006]
        wing_rim = [0.022, 0.026, 0.018, 0.006]

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
        add_solidify(shell_wing, 0.008)
        add_subsurf(shell_wing, 1)
        shade_auto_smooth(shell_wing)
        all_objects.append(shell_wing)

        cushion_wing = loft_channel(
            f"Cushion_Wing_{side}",
            wing_spine,
            [max(w - 0.030, 0.0) for w in wing_hw],
            [d * 0.5 + 0.004 for d in wing_dp],
            [r * 0.24 for r in wing_rim],
            ref_axis=Y,
            n_rings=30,
            profile_n=13,
            material=m_cushion,
            collection=c_cushion,
            seed_out=Vector((sign * 0.55, -0.55, 0.35)),
            center_offset=-0.012,
        )
        add_solidify(cushion_wing, 0.014)
        add_subsurf(cushion_wing, 1)
        shade_auto_smooth(cushion_wing, 50.0)
        all_objects.append(cushion_wing)

    # --- Hardware: small pale plate on the seat-pan front lip (as in photo) ---
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.400, 0.014))
    plate = bpy.context.active_object
    plate.name = "Front_Lip_Plate"
    plate.scale = (0.045, 0.020, 0.005)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    plate.rotation_euler = (math.radians(-6.0), 0.0, 0.0)
    if plate.data.materials:
        plate.data.materials[0] = m_hw
    else:
        plate.data.materials.append(m_hw)
    for c in list(plate.users_collection):
        c.objects.unlink(plate)
    c_hw.objects.link(plate)
    all_objects.append(plate)

    return {
        "root": root,
        "shell": c_shell,
        "cushion": c_cushion,
        "hardware": c_hw,
        "lights": c_lights,
        "objects": all_objects,
    }


# ---------------------------------------------------------------------------
# Recline + camera/lighting + render
# ---------------------------------------------------------------------------


def recline_seat(objects: list[bpy.types.Object], angle_deg: float = 15.0) -> bpy.types.Object:
    """Tip the whole assembly back, matching the reclined pose in the
    reference photo (seats are canted back noticeably, not upright).
    """
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
        if ob.type != "MESH":
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

    # Energy tuned for Blender's photometric Watts on an AREA light of this
    # size at roughly this distance — the previous pass used values copied
    # from a much larger reference scene and blew every material to clipped
    # white regardless of its actual albedo (the near-black cushion looked
    # identical to the pale shell). These are ~10x lower.
    specs = [
        ("Key", 46, 1.0 * scale, Vector((1.1, -1.3, 1.5)) * scale, (55, 0, 35)),
        ("Fill", 20, 1.3 * scale, Vector((-1.4, -0.5, 0.8)) * scale, (70, 0, -60)),
        ("Rim", 30, 0.8 * scale, Vector((0.1, 1.2, 1.0)) * scale, (-60, 0, 10)),
        ("Bounce", 16, 1.4 * scale, Vector((0.3, 1.6, -0.3)) * scale, (-100, 0, 0)),
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
    margin: float = 1.25,
) -> bpy.types.Object:
    """Place a camera along `direction` from `center`, far enough back that
    a sphere of `radius` fits within frame (computed from the camera's
    actual FOV/aspect instead of a guessed distance multiplier).
    """
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


def main() -> int:
    bpy.ops.wm.read_factory_settings(use_empty=True)

    print("==> building seat shell/cushion/hardware")
    meta = build_seat()

    print("==> reclining assembly")
    recline_seat(meta["objects"], angle_deg=4.0)

    lo, hi = compute_world_bbox(meta["objects"])
    center = (lo + hi) / 2.0
    diag = (hi - lo).length
    print(f"bbox lo={tuple(lo)} hi={tuple(hi)} diag={diag:.3f}")

    print("==> lights")
    setup_lights(meta["lights"], center, diag)

    scene = bpy.context.scene
    set_engine(scene)
    if scene.render.engine.startswith("BLENDER_EEVEE") or scene.render.engine == "EEVEE":
        try:
            scene.eevee.use_raytracing = True
        except AttributeError:
            pass

    radius = diag / 2.0

    # Front/above 3-quarter view — pan tip points toward +Y (local "front"),
    # matching how a person would be photographed sitting in it.
    cam_front = add_camera("Cam_Front", Vector((0.7, 1.3, 0.75)), center, radius)
    print("==> render front 3/4")
    render_to(cam_front, PNG_OUT, width=1600, height=1200)

    # Side profile — shows the backrest -> pan curve and wing silhouette.
    cam_side = add_camera("Cam_Side", Vector((1.6, 0.05, 0.25)), center, radius)
    print("==> render side")
    render_to(cam_side, PNG_OUT_SIDE, width=1600, height=1200)

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT))
    print(f"saved {BLEND_OUT}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback

        traceback.print_exc()
        raise SystemExit(1)
