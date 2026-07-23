#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Minimal AC3D (.ac) importer for Blender (FlightGear Shuttle meshes)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import bpy
from mathutils import Vector


@dataclass
class _ACObj:
    name: str = "Object"
    loc: tuple[float, float, float] = (0.0, 0.0, 0.0)
    verts: list[tuple[float, float, float]] = field(default_factory=list)
    faces: list[list[int]] = field(default_factory=list)
    kids: int = 0
    is_poly: bool = False
    parent_idx: int | None = None
    idx: int = -1


def _parse_ac(path: Path) -> list[_ACObj]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    objs: list[_ACObj] = []
    # stack of (parent_idx, remaining_kids)
    stack: list[tuple[int, int]] = []

    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith("OBJECT"):
            i += 1
            continue
        kind = line.split(None, 1)[1] if " " in line else "poly"
        o = _ACObj(is_poly=(kind == "poly"))
        i += 1
        while i < len(lines):
            s = lines[i].strip()
            if s.startswith("OBJECT"):
                break
            if s.startswith("name "):
                o.name = s[5:].strip().strip('"')
                i += 1
            elif s.startswith("loc "):
                p = s.split()
                o.loc = (float(p[1]), float(p[2]), float(p[3]))
                i += 1
            elif s.startswith("numvert "):
                n = int(s.split()[1])
                i += 1
                for _ in range(n):
                    x, y, z = map(float, lines[i].split()[:3])
                    o.verts.append((x, y, z))
                    i += 1
            elif s.startswith("numsurf "):
                nsurf = int(s.split()[1])
                i += 1
                for _ in range(nsurf):
                    while i < len(lines) and not lines[i].strip().startswith("refs "):
                        i += 1
                    if i >= len(lines):
                        break
                    nref = int(lines[i].split()[1])
                    i += 1
                    face: list[int] = []
                    for _ in range(nref):
                        face.append(int(lines[i].split()[0]))
                        i += 1
                    if len(face) >= 3:
                        o.faces.append(face)
            elif s.startswith("kids "):
                o.kids = int(s.split()[1])
                o.idx = len(objs)
                if stack:
                    parent_idx, left = stack[-1]
                    o.parent_idx = parent_idx
                    left -= 1
                    if left <= 0:
                        stack.pop()
                    else:
                        stack[-1] = (parent_idx, left)
                objs.append(o)
                if o.kids > 0:
                    stack.append((o.idx, o.kids))
                i += 1
                break
            else:
                i += 1
        else:
            break
    return objs


def import_ac3d(
    path: Path,
    *,
    collection: bpy.types.Collection,
    name_prefix: str = "",
    scale: float = 1.0,
) -> bpy.types.Object:
    path = Path(path)
    parsed = _parse_ac(path)

    root = bpy.data.objects.new(f"{name_prefix}AC_ROOT_{path.stem}", None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 2.0
    collection.objects.link(root)

    created: dict[int, bpy.types.Object] = {}
    for ac in parsed:
        name = f"{name_prefix}{ac.name}" if ac.name else f"{name_prefix}mesh_{ac.idx}"
        if ac.is_poly and ac.verts:
            mesh = bpy.data.meshes.new(name)
            verts = [(v[0] * scale, v[1] * scale, v[2] * scale) for v in ac.verts]
            faces: list[list[int]] = []
            for f in ac.faces:
                if len(f) in (3, 4):
                    faces.append(f)
                elif len(f) > 4:
                    for k in range(1, len(f) - 1):
                        faces.append([f[0], f[k], f[k + 1]])
            mesh.from_pydata(verts, [], faces)
            mesh.update()
            ob = bpy.data.objects.new(name, mesh)
        else:
            ob = bpy.data.objects.new(name, None)
            ob.empty_display_type = "PLAIN_AXES"
            ob.empty_display_size = 0.4
        ob.location = Vector((ac.loc[0] * scale, ac.loc[1] * scale, ac.loc[2] * scale))
        collection.objects.link(ob)
        created[ac.idx] = ob

    for ac in parsed:
        ob = created[ac.idx]
        if ac.parent_idx is not None and ac.parent_idx in created:
            ob.parent = created[ac.parent_idx]
        else:
            ob.parent = root
    return root
