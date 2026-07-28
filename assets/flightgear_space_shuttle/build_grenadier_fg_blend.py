#!/usr/bin/env python3
"""Import the *current* CatskillsFusionSSTO (Grenadier Plan A) FG meshes into Blender.

Reads live aircraft Models/ (not the stale assets/flightgear copy).

Run::

    /snap/bin/blender -b -P assets/flightgear_space_shuttle/build_grenadier_fg_blend.py
    /snap/bin/blender assets/flightgear_space_shuttle/grenadier_fg_now.blend
"""

from __future__ import annotations

import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CAD = REPO / "research" / "figures" / "cad"
FG = Path("/home/catskills/Desktop/Aircraft/CatskillsFusionSSTO/Models")
BLEND_OUT = HERE / "grenadier_fg_now.blend"

sys.path.insert(0, str(CAD))
from import_ac3d import import_ac3d  # noqa: E402

# What FlightGear loads for Grenadier TA right now (SpaceShuttle.xml + Grenadier/*).
PARTS = [
    # collection, path under FG Models, empty name
    ("01_Exterior", "shuttle_o2_plan_a.ac", "Orbiter_PlanA_Wings"),
    ("01_Exterior", "OMSPods_grenadier.ac", "OMS_Pods_RCS_only"),
    ("01_Exterior", "LandingGears.ac", "Landing_Gears"),
    ("01_Exterior", "cockpit_glass_outer.ac", "Cockpit_Glass"),
    ("02_Grenadier", "Grenadier/grenadier_nozzle.ac", "Grenadier_Nozzle"),
    ("02_Grenadier", "Grenadier/grenadier_internals.ac", "Grenadier_Internals"),
    ("02_Grenadier", "Grenadier/grenadier_scoop.ac", "Grenadier_Scoops"),
    ("03_Bay_Plant", "Grenadier/grenadier_bay_plant.ac", "Bay_Plant_Water_CHARM"),
    ("04_RCS_Green", "Grenadier/grenadier_rcs.ac", "RCS_LMP103S"),
]


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.collections):
        for b in list(block):
            if b.users == 0:
                block.remove(b)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)


def ensure_collection(name: str) -> bpy.types.Collection:
    scene = bpy.context.scene.collection
    for c in scene.children:
        if c.name == name:
            return c
    col = bpy.data.collections.new(name)
    scene.children.link(col)
    return col


def main() -> None:
    if not FG.is_dir():
        raise SystemExit(f"FlightGear Models not found: {FG}")
    clear_scene()
    for col_name, rel, empty_name in PARTS:
        path = FG / rel
        if not path.exists():
            print(f"SKIP missing {path}")
            continue
        col = ensure_collection(col_name)
        print(f"import {path.name} → {col_name}/{empty_name}")
        root = import_ac3d(
            path,
            collection=col,
            name_prefix=f"{empty_name}_",
            texture_dirs=[FG, FG / "Liveries", FG / "Grenadier", FG / "Grenadier" / "textures"],
        )
        root.name = empty_name

    # Prefer Material Preview so AC colors/textures show immediately
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.shading.type = "MATERIAL"

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT))
    print(f"wrote {BLEND_OUT}")
    print(f"Open: /snap/bin/blender {BLEND_OUT}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)
