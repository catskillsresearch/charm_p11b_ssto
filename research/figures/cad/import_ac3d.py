#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""AC3D (.ac) importer for Blender — geometry + materials + textures (FG meshes)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import bpy
from mathutils import Vector


@dataclass
class _ACMat:
    name: str
    rgb: tuple[float, float, float] = (0.8, 0.8, 0.8)
    amb: float = 0.2
    emis: float = 0.0
    spec: float = 0.2
    shi: float = 32.0
    trans: float = 0.0


@dataclass
class _ACFace:
    verts: list[int] = field(default_factory=list)
    uvs: list[tuple[float, float]] = field(default_factory=list)
    mat: int = 0


@dataclass
class _ACObj:
    name: str = "Object"
    loc: tuple[float, float, float] = (0.0, 0.0, 0.0)
    verts: list[tuple[float, float, float]] = field(default_factory=list)
    faces: list[_ACFace] = field(default_factory=list)
    texture: str | None = None
    kids: int = 0
    is_poly: bool = False
    parent_idx: int | None = None
    idx: int = -1


def _parse_material(line: str) -> _ACMat:
    # MATERIAL "name" rgb r g b  amb …  emis …  spec …  shi N trans T
    name = "mat"
    if '"' in line:
        name = line.split('"')[1]
    parts = line.replace('"', " ").split()
    def after(key, n=3):
        if key not in parts:
            return None
        i = parts.index(key)
        return tuple(float(parts[i + 1 + k]) for k in range(n))

    rgb = after("rgb") or (0.8, 0.8, 0.8)
    amb = after("amb")
    emis = after("emis")
    spec = after("spec")
    shi = 32.0
    if "shi" in parts:
        shi = float(parts[parts.index("shi") + 1])
    trans = 0.0
    if "trans" in parts:
        trans = float(parts[parts.index("trans") + 1])
    return _ACMat(
        name=name,
        rgb=(rgb[0], rgb[1], rgb[2]),
        amb=(amb[0] if amb else 0.2),
        emis=(emis[0] if emis else 0.0),
        spec=(spec[0] if spec else 0.2),
        shi=shi,
        trans=trans,
    )


def _parse_ac(path: Path) -> tuple[list[_ACMat], list[_ACObj]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    mats: list[_ACMat] = []
    objs: list[_ACObj] = []
    stack: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        if line.startswith("MATERIAL"):
            mats.append(_parse_material(line))
            i += 1
            continue
        if not line.startswith("OBJECT"):
            i += 1
            continue
        kind = line.split(None, 1)[1] if " " in line else "poly"
        o = _ACObj(is_poly=(kind == "poly"))
        i += 1
        cur_mat = 0
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
            elif s.startswith("texture "):
                o.texture = s.split(None, 1)[1].strip().strip('"')
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
                    cur_mat = 0
                    while i < len(lines):
                        t = lines[i].strip()
                        if t.startswith("mat "):
                            cur_mat = int(t.split()[1])
                            i += 1
                        elif t.startswith("refs "):
                            break
                        elif t.startswith("SURF") or t.startswith("MATERIAL"):
                            i += 1
                        else:
                            i += 1
                            if t.startswith("OBJECT") or t.startswith("kids"):
                                break
                    if i >= len(lines) or not lines[i].strip().startswith("refs "):
                        break
                    nref = int(lines[i].split()[1])
                    i += 1
                    face = _ACFace(mat=cur_mat)
                    for _ in range(nref):
                        bits = lines[i].split()
                        face.verts.append(int(bits[0]))
                        if len(bits) >= 3:
                            face.uvs.append((float(bits[1]), float(bits[2])))
                        else:
                            face.uvs.append((0.0, 0.0))
                        i += 1
                    if len(face.verts) >= 3:
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
    return mats, objs


def _ensure_image(tex_name: str, search_dirs: list[Path]) -> bpy.types.Image | None:
    for d in search_dirs:
        for cand in (d / tex_name, d / Path(tex_name).name):
            if cand.is_file():
                try:
                    return bpy.data.images.load(str(cand), check_existing=True)
                except Exception:  # noqa: BLE001
                    return None
    return None


def _blender_material(
    ac_mat: _ACMat,
    *,
    prefix: str,
    image: bpy.types.Image | None = None,
) -> bpy.types.Material:
    key = f"{prefix}{ac_mat.name}" + (f"::{image.name}" if image else "")
    existing = bpy.data.materials.get(key)
    if existing:
        return existing
    mat = bpy.data.materials.new(name=key)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    out.location = (300, 0)
    bsdf.location = (0, 0)
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    col = (*ac_mat.rgb, 1.0 - ac_mat.trans)
    bsdf.inputs["Base Color"].default_value = col
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (*ac_mat.rgb, 1.0)
        bsdf.inputs["Emission Strength"].default_value = ac_mat.emis * 2.0
    elif "Emission" in bsdf.inputs:
        bsdf.inputs["Emission"].default_value = (*ac_mat.rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = max(0.05, 1.0 - min(1.0, ac_mat.shi / 100.0))
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = min(1.0, ac_mat.spec)
    elif "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = min(1.0, ac_mat.spec)
    if ac_mat.trans > 0.05:
        mat.blend_method = "BLEND"
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = 1.0 - ac_mat.trans
    if image is not None:
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = image
        tex.location = (-300, 0)
        links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        if ac_mat.trans > 0.05 and "Alpha" in bsdf.inputs:
            links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    return mat


def import_ac3d(
    path: Path,
    *,
    collection: bpy.types.Collection,
    name_prefix: str = "",
    scale: float = 1.0,
    texture_dirs: list[Path] | None = None,
) -> bpy.types.Object:
    path = Path(path)
    mats, parsed = _parse_ac(path)
    if not mats:
        mats = [_ACMat(name="default", rgb=(0.75, 0.75, 0.78))]

    search = list(texture_dirs or [])
    search.append(path.parent)
    # FlightGear Models/ next to Grenadier/
    if (path.parent.parent / "spstob_1.png").exists():
        search.append(path.parent.parent)
    if (path.parent / "spstob_1.png").exists():
        search.append(path.parent)

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
            # Expand ngons; keep parallel lists of mat index + uvs per output face
            bl_faces: list[list[int]] = []
            bl_mats: list[int] = []
            bl_uvs: list[list[tuple[float, float]]] = []
            for f in ac.faces:
                idx = f.verts
                uvs = f.uvs
                mi = f.mat if f.mat < len(mats) else 0
                if len(idx) in (3, 4):
                    bl_faces.append(list(idx))
                    bl_mats.append(mi)
                    bl_uvs.append(list(uvs))
                elif len(idx) > 4:
                    for k in range(1, len(idx) - 1):
                        bl_faces.append([idx[0], idx[k], idx[k + 1]])
                        bl_mats.append(mi)
                        bl_uvs.append([uvs[0], uvs[k], uvs[k + 1]])
            mesh.from_pydata(verts, [], bl_faces)
            mesh.update()

            image = _ensure_image(ac.texture, search) if ac.texture else None
            # Slot per unique mat index used
            used = sorted(set(bl_mats)) or [0]
            slot_for: dict[int, int] = {}
            for mi in used:
                ac_mat = mats[mi] if mi < len(mats) else mats[0]
                bmat = _blender_material(ac_mat, prefix=name_prefix, image=image)
                slot_for[mi] = len(mesh.materials)
                mesh.materials.append(bmat)

            for poly, mi in zip(mesh.polygons, bl_mats):
                poly.material_index = slot_for.get(mi, 0)

            if any(any(abs(u) + abs(v) > 1e-8 for u, v in uvs) for uvs in bl_uvs):
                uv_layer = mesh.uv_layers.new(name="UVMap")
                for poly, uvs in zip(mesh.polygons, bl_uvs):
                    for li, (u, v) in zip(poly.loop_indices, uvs):
                        uv_layer.data[li].uv = (u, v)

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
