#!/usr/bin/env python3
"""Import FlightGear Space Shuttle .ac meshes into one navigable .blend.

Run::

    /snap/bin/blender -b -P assets/flightgear_space_shuttle/build_shuttle_blend.py

Output: ``space_shuttle_assembled.blend`` next to this script.

Outliner: each major system is a Collection. Click the eye (Hide) or
monitor (Disable in Viewports) to mute parts and climb the structure.
Object parenting preserves each .ac file's internal hierarchy under an
empty root named after the part.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Vector

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FG_MODELS = REPO / "CatskillsFusionSSTO" / "Models"
BLEND_OUT = HERE / "space_shuttle_assembled.blend"

# FG PropertyList offsets are metres in the aircraft frame used by this model.
# Parts with no offsets sit at the origin like SpaceShuttle.xml.

PARTS = [
    # (collection_path, ac_relpath, empty_name, loc_xyz_m, rot_xyz_deg, hide_viewport)
    ("01_Exterior", "shuttle_o2.ac", "Orbiter_Exterior", (0, 0, 0), (0, 0, 0), False),
    ("01_Exterior", "OMSPods.ac", "OMS_Pods", (0, 0, 0), (0, 0, 0), False),
    ("01_Exterior", "LandingGears.ac", "Landing_Gears", (0, 0, 0), (0, 0, 0), False),
    ("01_Exterior", "SSME.ac", "SSME_1_Center", (-0.1, 0, 0), (0, 0, 0), False),
    ("01_Exterior", "SSME.ac", "SSME_2_Left", (0.0, -1.5, -2.5), (0, 0, 0), False),
    ("01_Exterior", "SSME.ac", "SSME_3_Right", (0.0, 1.5, -2.5), (0, 0, 0), False),
    ("01_Exterior", "cockpit_glass_outer.ac", "Cockpit_Glass_Outer", (0.01, 0, 0), (0, 0, 0), False),
    ("01_Exterior", "cockpit_glass_broken.ac", "Cockpit_Glass_Broken", (0.02, 0, 0), (0, 0, 0), True),
    ("02_Interior", "cockpit.ac", "Cockpit_Flight_Deck", (0, 0, 0), (0, 0, 0), False),
    ("02_Interior", "cockpit-detailed.ac", "Cockpit_Detailed_Alt", (0, 0, 0), (0, 0, 0), True),
    ("02_Interior", "RHC-Commander.ac", "RHC_Commander", (0, 0, 0), (0, 0, 0), False),
    ("02_Interior", "coas.ac", "COAS", (0, 0, 0), (0, 0, 0), False),
    ("03_Payload_Bay", "PayloadBay/Airlock-Module/airlock_module.ac", "Airlock_Module", (0, 0, 0), (0, 0, 0), False),
    ("03_Payload_Bay", "PayloadBay/rmsArm.ac", "RMS_Arm", (0, 0, 0), (0, 0, 0), False),
    ("03_Payload_Bay", "PayloadBay/Pallet.ac", "Bay_Pallet", (-10.5, -2.1, 1.5), (0, 0, 0), True),
    ("03_Payload_Bay", "PayloadBay/OMS-KIT/oms-kit.ac", "OMS_KIT", (0, 0, 0), (0, 0, 0), True),
    ("03_Payload_Bay", "PayloadBay/KU-Antenna/Antenna-ku-Assembly.ac", "KU_Antenna", (0, 0, 0), (0, 0, 0), False),
    ("04_Payloads_Optional", "PayloadBay/HST/hst.ac", "HST", (-8.5, -2.1, -1.1), (0, 0, 0), True),
    ("04_Payloads_Optional", "PayloadBay/TDRS/TDRS_demo.ac", "TDRS", (-8.5, -2.1, -1.1), (0, 0, 0), True),
    ("04_Payloads_Optional", "PayloadBay/Spartan-201/SPARTAN-201.ac", "Spartan_201", (-8.5, -2.1, -1.1), (0, 0, 0), True),
    ("05_Stack_Optional", "et.ac", "External_Tank", (0, 0, 0), (0, 0, 0), True),
    ("05_Stack_Optional", "srb.ac", "SRB_Mesh", (0, 0, 0), (0, 0, 0), True),
    ("05_Stack_Optional", "air-data-boom.ac", "Air_Data_Boom_ALT", (0, 0, 0), (0, 0, 0), True),
    ("05_Stack_Optional", "TailCone.ac", "Tail_Cone_ALT", (0, 0, 0), (0, 0, 0), True),
    ("06_ISS_Optional", "ISS/ISS_simple_docked.ac", "ISS_Simple", (0, 0, 0), (0, 0, 0), True),
    ("06_ISS_Optional", "ISS/ISS_docked.ac", "ISS_Detailed", (0, 0, 0), (0, 0, 0), True),
    ("07_Damage_Optional", "shuttle_o2-damage.ac", "Orbiter_Damage", (0, 0, 0), (0, 0, 0), True),
    ("07_Damage_Optional", "cockpit-damage.ac", "Cockpit_Damage", (0, 0, 0), (0, 0, 0), True),
    ("07_Damage_Optional", "damage.ac", "Damage_Bits", (0, 0, 0), (0, 0, 0), True),
]


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.collections):
        for b in list(block):
            if b.users == 0:
                block.remove(b)
    # Remove non-master collections
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)


def ensure_addon() -> None:
    try:
        bpy.ops.preferences.addon_enable(module="io_scene_ac3d")
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: could not enable io_scene_ac3d: {exc}")


def collection_path(path: str) -> bpy.types.Collection:
    """Create nested collections under the scene root, e.g. '01_Exterior'."""
    scene_col = bpy.context.scene.collection
    parent = scene_col
    parts = path.split("/")
    current = None
    for name in parts:
        existing = parent.children.get(name) if hasattr(parent.children, "get") else None
        if existing is None:
            for c in parent.children:
                if c.name == name:
                    existing = c
                    break
        if existing is None:
            existing = bpy.data.collections.new(name)
            parent.children.link(existing)
        current = existing
        parent = existing
    assert current is not None
    return current


def set_layer_exclude(coll: bpy.types.Collection, exclude: bool) -> None:
    def walk(lc):
        if lc.collection == coll:
            lc.exclude = exclude
            return True
        for child in lc.children:
            if walk(child):
                return True
        return False

    walk(bpy.context.view_layer.layer_collection)


def import_ac(path: Path) -> list[bpy.types.Object]:
    before = set(bpy.data.objects)
    # Prefer the installed AC3D addon (materials + textures).
    try:
        bpy.ops.import_scene.import_ac3d(filepath=str(path))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR importing {path}: {exc}")
        # Fallback: paper-repo minimal importer
        sys.path.insert(0, str(HERE.parents[1] / "research" / "figures" / "cad"))
        from import_ac3d import import_ac3d as fallback_import  # type: ignore

        tmp = bpy.data.collections.new("_tmp_import")
        bpy.context.scene.collection.children.link(tmp)
        fallback_import(path, collection=tmp, name_prefix="")
        bpy.data.collections.remove(tmp)
    after = [o for o in bpy.data.objects if o not in before]
    return after


def rehome(objects: list[bpy.types.Object], coll: bpy.types.Collection, root_name: str,
           loc: tuple[float, float, float], rot_deg: tuple[float, float, float]) -> bpy.types.Object:
    root = bpy.data.objects.new(root_name, None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 1.5
    root.location = Vector(loc)
    root.rotation_euler = Euler(tuple(math.radians(a) for a in rot_deg), "XYZ")
    coll.objects.link(root)

    # Top-level imported objects (no parent among the new set)
    new_set = set(objects)
    tops = [o for o in objects if o.parent not in new_set]

    for ob in objects:
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        coll.objects.link(ob)

    for ob in tops:
        ob.parent = root
        # Keep world transform while parenting
        ob.matrix_parent_inverse = root.matrix_world.inverted()

    return root


def main() -> int:
    if not FG_MODELS.is_dir():
        print(f"ERROR: FG models missing at {FG_MODELS}")
        return 1

    print(f"==> FG models: {FG_MODELS}")
    print(f"==> Output:    {BLEND_OUT}")

    clear_scene()
    ensure_addon()

    master = collection_path("SpaceShuttle_FG")
    # Move master under scene (collection_path already did)

    for coll_name, ac_rel, empty_name, loc, rot, hide in PARTS:
        ac_path = FG_MODELS / ac_rel
        if not ac_path.is_file():
            print(f"SKIP missing: {ac_path}")
            continue
        print(f"==> Import {ac_rel} -> {coll_name}/{empty_name}")
        coll = collection_path(f"SpaceShuttle_FG/{coll_name}")
        new_objs = import_ac(ac_path)
        if not new_objs:
            print(f"WARN: no objects from {ac_rel}")
            continue
        rehome(new_objs, coll, empty_name, loc, rot)
        if hide:
            # Hide the part root in viewports; collection still browsable in Outliner
            root = bpy.data.objects.get(empty_name)
            if root:
                root.hide_set(True)
                root.hide_viewport = True
                for child in root.children_recursive:
                    child.hide_viewport = True

    # Hide entire optional collections via layer exclude for easy mute
    for optional in (
        "04_Payloads_Optional",
        "05_Stack_Optional",
        "06_ISS_Optional",
        "07_Damage_Optional",
    ):
        c = bpy.data.collections.get(optional)
        if c:
            set_layer_exclude(c, True)

    # Also exclude detailed cockpit alt by default (heavy duplicate)
    # Keep objects hidden via root; collection stays visible for toggling

    # Camera framing
    bpy.ops.object.camera_add(location=(40, -45, 20))
    cam = bpy.context.active_object
    cam.name = "View_Camera"
    cam.rotation_euler = Euler((math.radians(70), 0, math.radians(50)), "XYZ")
    bpy.context.scene.camera = cam
    master.objects.link(cam)
    # camera was linked to scene collection too
    for c in list(cam.users_collection):
        if c != master:
            c.objects.unlink(cam)

    light_data = bpy.data.lights.new("Key", "SUN")
    light_data.energy = 3.0
    light = bpy.data.objects.new("Key_Sun", light_data)
    light.rotation_euler = Euler((math.radians(45), math.radians(15), math.radians(30)), "XYZ")
    master.objects.link(light)

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT))
    print(f"wrote {BLEND_OUT}")
    print("Outliner tip: eye = hide, monitor icon = disable collection in viewports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
