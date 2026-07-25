# SPDX-License-Identifier: Apache-2.0
"""Blender primitive builders + reusable drop-in "kits".

Primitives (box/cylinder/text_label/...) are the same low-level helpers
build_crew_capsule_blender.py used before this refactor. The kits below
(pressure_shell, ring_hatch, hinged_door_leaf, clamshell_bay_door, tank,
tie_down_grid) generalize patterns that repeat across the crew capsule,
airlock, and cargo skid so each figure script only has to place hardware,
not reinvent hatch/shell geometry.
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Euler, Vector

# ---------------------------------------------------------------------------
# Primitives
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
    align: str = "CENTER",
) -> bpy.types.Object:
    curve = bpy.data.curves.new(name=name, type="FONT")
    curve.body = body
    curve.size = size
    curve.align_x = align
    curve.align_y = "CENTER"
    ob = bpy.data.objects.new(name, curve)
    ob.location = loc
    ob.rotation_euler = (0.0, 0.0, 0.0)  # flat on XY for top view
    to_col(ob, collection)
    assign(ob, mat("label_ink", (0.05, 0.05, 0.08), roughness=0.9))
    return ob


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
# Reusable kits — shared across drop-in modules (crew capsule, airlock,
# cargo skid) so hatch/shell/tank geometry isn't reinvented per figure.
# ---------------------------------------------------------------------------


def pressure_shell(
    x0: float,
    x1: float,
    width: float,
    wall_h: float,
    *,
    material: bpy.types.Material,
    collection: bpy.types.Collection,
    floor_z: float = 0.0,
    wall_t: float = 0.08,
    name_prefix: str = "PV",
) -> dict:
    """Open-top pressure vessel shell: floor + two side walls + fwd/aft bulkheads.

    Used by the crew capsule's own pressure vessel and the airlock's — both
    are simple rectangular-plan shells at this level of detail.
    """
    length = x1 - x0
    cx = (x0 + x1) / 2.0
    y_half = width / 2.0

    floor = box(
        f"{name_prefix}_Floor",
        (length, width, 0.06),
        (cx, 0.0, floor_z + 0.03),
        material,
        collection,
    )

    wall_port = box(
        f"{name_prefix}_Wall_Port",
        (length, wall_t, wall_h),
        (cx, y_half - wall_t / 2.0, floor_z + wall_h / 2.0),
        material,
        collection,
    )
    wall_stbd = box(
        f"{name_prefix}_Wall_Stbd",
        (length, wall_t, wall_h),
        (cx, -(y_half - wall_t / 2.0), floor_z + wall_h / 2.0),
        material,
        collection,
    )

    bulkhead_fwd = box(
        f"{name_prefix}_Bulkhead_Fwd",
        (wall_t, width, wall_h),
        (x0 + wall_t / 2.0, 0.0, floor_z + wall_h / 2.0),
        material,
        collection,
    )
    bulkhead_aft = box(
        f"{name_prefix}_Bulkhead_Aft",
        (wall_t, width, wall_h),
        (x1 - wall_t / 2.0, 0.0, floor_z + wall_h / 2.0),
        material,
        collection,
    )

    return {
        "floor": floor,
        "wall_port": wall_port,
        "wall_stbd": wall_stbd,
        "bulkhead_fwd": bulkhead_fwd,
        "bulkhead_aft": bulkhead_aft,
        "length": length,
        "cx": cx,
        "y_half": y_half,
        "wall_t": wall_t,
    }


def hinged_door_leaf(
    name: str,
    *,
    hinge_xyz: tuple[float, float, float],
    width: float,
    height: float,
    open_deg: float,
    material: bpy.types.Material,
    collection: bpy.types.Collection,
    thickness: float = 0.06,
) -> bpy.types.Object:
    """A rectangular door leaf hinged about a vertical (Z) axis, swung ajar
    into the cabin — for wall-mounted doors (e.g. the crew capsule's Earth
    side hatch). The leaf is centered `width/2` from the hinge line along
    local +Y before rotating, so it reads as "ajar" from top-down.
    """
    hx, hy, hz = hinge_xyz
    door = box(
        name,
        (thickness, width, height),
        (hx, hy + width / 2.0, hz),
        material,
        collection,
    )
    door.rotation_euler = Euler((0.0, 0.0, math.radians(open_deg)), "XYZ")
    return door


def ring_hatch(
    name_prefix: str,
    *,
    x: float,
    z: float,
    radius: float,
    direction: float,
    y: float = 0.0,
    wall_t: float = 0.08,
    inset: float = 0.35,
    y_offset: float = 0.35,
    open_deg: float = 55.0,
    material: bpy.types.Material,
    collection: bpy.types.Collection,
) -> dict:
    """A circular pressure hatch through a bulkhead: a ring frame at the
    bulkhead station, plus a door leaf swung ajar into the cabin.

    `direction` is the sign of the *inward* offset for the open door leaf
    (the negative of the port's outward `normal` in assembly.json — e.g. an
    aft bulkhead with normal [1, 0, 0] passes direction=-1.0 here).
    """
    door_t = 0.06
    door = box(
        f"{name_prefix}_Door",
        (door_t, radius * 2.0, radius * 2.0),
        (x + direction * inset, y + y_offset, z),
        material,
        collection,
    )
    door.rotation_euler = Euler((0.0, 0.0, math.radians(open_deg)), "XYZ")

    frame = cylinder(
        f"{name_prefix}_Frame",
        radius + 0.08,
        wall_t + 0.06,
        (x, y, z),
        material,
        collection,
        axis="X",
    )
    return {"door": door, "frame": frame}


def clamshell_bay_door(
    name: str,
    *,
    hinge_x0: float,
    hinge_x1: float,
    hinge_y: float,
    panel_width: float,
    thickness: float,
    open_deg: float,
    material: bpy.types.Material,
    collection: bpy.types.Collection,
    z: float = 0.0,
) -> bpy.types.Object:
    """A cargo-bay-style door panel hinged along a fore-aft roof line and
    swung open outward/down — matches a `role: roof_hinge` port in
    assembly.json (left_cargo_door / right_cargo_door).

    The panel is built flat and closed, then re-origined to the hinge line
    (via the 3D cursor) before rotating about local X, so the hinge edge
    stays put and the outer edge swings open — like real Shuttle-bay doors.
    """
    length = hinge_x1 - hinge_x0
    cx = (hinge_x0 + hinge_x1) / 2.0
    sign = 1.0 if hinge_y >= 0.0 else -1.0

    panel = box(
        name,
        (length, panel_width, thickness),
        (cx, hinge_y + sign * panel_width / 2.0, z),
        material,
        collection,
    )

    saved_cursor = bpy.context.scene.cursor.location.copy()
    bpy.context.scene.cursor.location = (cx, hinge_y, z)
    bpy.context.view_layer.objects.active = panel
    bpy.ops.object.select_all(action="DESELECT")
    panel.select_set(True)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    bpy.context.scene.cursor.location = saved_cursor

    panel.rotation_euler = Euler((sign * math.radians(open_deg), 0.0, 0.0), "XYZ")
    return panel


def tank(
    name: str,
    radius: float,
    depth: float,
    loc: tuple[float, float, float],
    material: bpy.types.Material,
    collection: bpy.types.Collection,
    *,
    axis: str = "Z",
) -> bpy.types.Object:
    """Thin wrapper over `cylinder` for pressure/gas tanks (naming clarity)."""
    return cylinder(name, radius, depth, loc, material, collection, axis=axis)


def callout(
    name: str,
    *,
    anchor_xyz: tuple[float, float, float],
    label_xyz: tuple[float, float, float],
    text: str,
    collection: bpy.types.Collection,
    z: float | None = None,
    dot_radius: float = 0.035,
    line_t: float = 0.02,
    text_size: float = 0.12,
    material: bpy.types.Material | None = None,
) -> dict:
    """A leader-line callout: a small dot at the anchor point on a part, a
    thin line out to the label position, and centered text there.

    This is the "real engineering drawing" alternative to a bare floating
    `text_label` — the label stays visibly tied to the part it names even
    once several labels are packed into a small figure.
    """
    ink = material or mat("callout_ink", (0.05, 0.05, 0.08), roughness=0.9)
    ax, ay, az0 = anchor_xyz
    lx, ly, lz0 = label_xyz
    az = az0 if z is None else z
    lz = lz0 if z is None else z

    dot = cylinder(f"{name}_Anchor", dot_radius, 0.02, (ax, ay, az), ink, collection, axis="Z")

    dx, dy = lx - ax, ly - ay
    length = math.hypot(dx, dy)
    leader = None
    if length > 1e-6:
        mx, my = (ax + lx) / 2.0, (ay + ly) / 2.0
        leader = box(f"{name}_Leader", (length, line_t, 0.02), (mx, my, az), ink, collection)
        leader.rotation_euler = Euler((0.0, 0.0, math.atan2(dy, dx)), "XYZ")

    label = text_label(f"{name}_Text", text, (lx, ly, lz), collection, size=text_size)
    return {"dot": dot, "leader": leader, "label": label}


def dimension_line(
    name: str,
    *,
    p0: tuple[float, float],
    p1: tuple[float, float],
    offset: float,
    text: str,
    collection: bpy.types.Collection,
    z: float = 0.0,
    line_t: float = 0.02,
    text_size: float = 0.16,
    material: bpy.types.Material | None = None,
) -> dict:
    """A dimension annotation between two points: extension lines from each
    endpoint out to an offset dimension line, tick dots at both ends of that
    line, and the measurement text centered on it.

    `offset` is signed distance along the perpendicular to p0->p1; positive
    is a left turn from the p0->p1 direction.
    """
    ink = material or mat("dim_ink", (0.05, 0.05, 0.08), roughness=0.9)
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1e-6:
        raise ValueError("dimension_line: p0 and p1 must differ")
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux

    ox0, oy0 = x0 + nx * offset, y0 + ny * offset
    ox1, oy1 = x1 + nx * offset, y1 + ny * offset

    for i, (bx, by, ex, ey) in enumerate(((x0, y0, ox0, oy0), (x1, y1, ox1, oy1))):
        ext_len = math.hypot(ex - bx, ey - by)
        mx, my = (bx + ex) / 2.0, (by + ey) / 2.0
        ext = box(f"{name}_Ext{i}", (line_t, ext_len, 0.02), (mx, my, z), ink, collection)
        ext.rotation_euler = Euler((0.0, 0.0, math.atan2(ny, nx)), "XYZ")
        cylinder(f"{name}_Tick{i}", 0.035, 0.02, (ex, ey, z), ink, collection, axis="Z")

    mx, my = (ox0 + ox1) / 2.0, (oy0 + oy1) / 2.0
    dim_line = box(f"{name}_Line", (length, line_t, 0.02), (mx, my, z), ink, collection)
    dim_line.rotation_euler = Euler((0.0, 0.0, math.atan2(uy, ux)), "XYZ")

    label_off = text_size * 1.4
    label = text_label(
        f"{name}_Text",
        text,
        (mx + nx * label_off, my + ny * label_off, z),
        collection,
        size=text_size,
    )
    return {"line": dim_line, "label": label}


def legend(
    entries: list[tuple[bpy.types.Material, str]],
    origin_xyz: tuple[float, float, float],
    collection: bpy.types.Collection,
    *,
    title: str | None = None,
    swatch: float = 0.16,
    row_gap: float = 0.30,
    label_dx: float = 0.35,
    text_size: float = 0.13,
) -> None:
    """A small stacked legend: one color swatch + subsystem name per row,
    e.g. structure / hatches / systems / payload — the same subsystem colors
    used for the figure's own materials, named once in a corner.
    """
    ox, oy, oz = origin_xyz
    row = 0
    if title:
        text_label(
            "Legend_Title",
            title,
            (ox + label_dx, oy, oz),
            collection,
            size=text_size * 1.1,
            align="LEFT",
        )
        row += 1
    for i, (material, label) in enumerate(entries):
        ry = oy - (row + i) * row_gap
        box(f"Legend_Swatch_{i}", (swatch, swatch, 0.02), (ox, ry, oz), material, collection)
        text_label(
            f"Legend_Label_{i}",
            label,
            (ox + label_dx, ry, oz),
            collection,
            size=text_size,
            align="LEFT",
        )


def tie_down_grid(
    x0: float,
    x1: float,
    width: float,
    *,
    material: bpy.types.Material,
    collection: bpy.types.Collection,
    spacing: float = 1.0,
    floor_z: float = 0.0,
    margin: float = 0.4,
) -> list[bpy.types.Object]:
    """A grid of small tie-down point markers on a cargo floor.

    Rows/columns are spaced evenly (<= `spacing`) and kept symmetric about
    the centerline, rather than walking from one edge (which can leave a
    lopsided last row/column when the span isn't an exact multiple).
    """

    def symmetric_positions(lo: float, hi: float) -> list[float]:
        span = hi - lo
        if span <= 0.0:
            return [(lo + hi) / 2.0]
        n = max(1, round(span / spacing) + 1)
        if n == 1:
            return [(lo + hi) / 2.0]
        step = span / (n - 1)
        return [lo + i * step for i in range(n)]

    xs = symmetric_positions(x0 + margin, x1 - margin)
    y_half = width / 2.0 - margin
    ys = symmetric_positions(-y_half, y_half)

    points = []
    for i, xv in enumerate(xs):
        for j, yv in enumerate(ys):
            points.append(
                cylinder(
                    f"TieDown_{i}_{j}",
                    0.04,
                    0.03,
                    (xv, yv, floor_z + 0.02),
                    material,
                    collection,
                    axis="Z",
                )
            )
    return points
