"""Unhide Cockpit_Detailed_Alt (seats) and hide the seatless Cockpit_Flight_Deck.

In an open Blender: Scripting workspace → Open this file → Run Script (Alt+P).

Or headless::

    /snap/bin/blender -b assets/flightgear_space_shuttle/space_shuttle_assembled.blend \\
      -P assets/flightgear_space_shuttle/unhide_detailed_cockpit.py
"""

from __future__ import annotations

from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
OUT = HERE / "space_shuttle_seats_visible.blend"


def unhide(ob: bpy.types.Object) -> None:
    ob.hide_viewport = False
    ob.hide_set(False)
    ob.hide_render = False


def main() -> None:
    root = bpy.data.objects.get("Cockpit_Detailed_Alt")
    if not root:
        raise SystemExit("Cockpit_Detailed_Alt not found")

    unhide(root)
    n = 0
    for ob in root.children_recursive:
        unhide(ob)
        n += 1

    other = bpy.data.objects.get("Cockpit_Flight_Deck")
    if other:
        other.hide_viewport = True
        other.hide_set(True)
        for ob in other.children_recursive:
            ob.hide_viewport = True
            ob.hide_set(True)

    bpy.context.view_layer.update()
    print(f"Unhid Cockpit_Detailed_Alt + {n} children; hid Cockpit_Flight_Deck")

    # When run with blender -b -P, also save a convenience copy.
    if bpy.app.background:
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
        print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
