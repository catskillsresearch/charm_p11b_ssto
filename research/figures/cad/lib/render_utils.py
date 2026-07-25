# SPDX-License-Identifier: Apache-2.0
"""Scene setup, orthographic top-down camera, and render helpers."""

from __future__ import annotations

from pathlib import Path

import bpy

from .procedural_geometry import to_col


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def set_engine(scene: bpy.types.Scene) -> None:
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "EEVEE"):
        try:
            scene.render.engine = eng
            return
        except TypeError:
            continue


def enable_technical_outline(scene: bpy.types.Scene, *, thickness: float = 1.6) -> None:
    """Crisp black silhouette/crease/border outlines on every mesh — turns flat-
    shaded primitives into an engineering-drawing look with no geometry changes.

    Freestyle renders straight into the combined pass (no compositor needed)
    as long as "as_render_pass" is off, and is supported under EEVEE Next.
    """
    scene.render.use_freestyle = True
    view_layer = bpy.context.view_layer
    view_layer.use_freestyle = True
    fs = view_layer.freestyle_settings
    for existing in list(fs.linesets):
        fs.linesets.remove(existing)
    lineset = fs.linesets.new("TechnicalLines")
    lineset.select_silhouette = True
    lineset.select_crease = True
    lineset.select_border = True
    lineset.select_material_boundary = True
    lineset.select_edge_mark = False
    lineset.select_suggestive_contour = False
    lineset.select_ridge_valley = False
    style = lineset.linestyle
    style.color = (0.05, 0.05, 0.07)
    style.thickness = thickness
    style.use_chaining = True


def render_to(
    cam: bpy.types.Object,
    path: Path,
    *,
    width: int,
    height: int,
    outline: bool = True,
) -> None:
    scene = bpy.context.scene
    scene.camera = cam
    set_engine(scene)
    if outline:
        enable_technical_outline(scene)
    else:
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


def setup_topdown_camera(
    root_col: bpy.types.Collection,
    lights_col: bpy.types.Collection,
    *,
    cx: float,
    length: float,
    width: float,
    cam_y: float = 0.0,
    ortho_pad: float = 1.35,
    ortho_scale: float | None = None,
    cam_z: float = 40.0,
) -> bpy.types.Object:
    """Orthographic top-down camera + sun/fill lights centered at (cx, cam_y).

    `length`/`width` set the default `ortho_scale` (max(length * ortho_pad,
    width * 3.2)) unless the caller passes an explicit `ortho_scale`. Callers
    with an off-center composition (e.g. a parked roof cover, or a title
    label sitting below the footprint) should compute `cam_y`/`ortho_scale`
    to fit their actual content bounds rather than relying on the default.

    Frame: +X aft (station), +Y port, +Z up. Camera looks straight down -Z
    with zero roll, so +X stays "right" and +Y stays "up" in every render —
    the same convention build_crew_capsule_blender.py established.
    """
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.88, 0.89, 0.91, 1.0)
    bg.inputs[1].default_value = 1.0

    # Shadows off: a technical top-down diagram wants flat vector-style color
    # fills under the Freestyle outlines, not soft drop-shadows from primitives.
    bpy.ops.object.light_add(type="SUN", location=(cx, cam_y - 4.0, cam_z))
    sun = bpy.context.active_object
    sun.name = "Sun"
    sun.data.energy = 3.5
    sun.data.use_shadow = False
    sun.rotation_euler = (0.3, 0.2, 0.1)
    to_col(sun, lights_col)

    bpy.ops.object.light_add(type="AREA", location=(cx, cam_y, cam_z * 0.625))
    area = bpy.context.active_object
    area.name = "Fill"
    area.data.energy = 800
    area.data.size = 40
    area.data.use_shadow = False
    to_col(area, lights_col)

    data = bpy.data.cameras.new("Cam_Top")
    data.type = "ORTHO"
    data.ortho_scale = ortho_scale if ortho_scale is not None else max(length * ortho_pad, width * 3.2)
    cam = bpy.data.objects.new("Cam_Top", data)
    cam.location = (cx, cam_y, cam_z)
    cam.rotation_euler = (0.0, 0.0, 0.0)  # camera default looks down local -Z
    to_col(cam, root_col)
    return cam
