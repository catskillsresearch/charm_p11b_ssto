#!/usr/bin/env python3
"""Build OMSPods_grenadier.ac from heritage OMSPods.ac.

Grenadier keeps pod shells, RCS, aft mount bases, and the *forward cowling*
of each OMS engine mesh. Only the protruding OMS bell is removed.

Earlier mistakes:
  - DROP included oms*Base → open pockets behind RCS (fixed: keep bases).
  - DROP of whole oms*.001 → lost the mount cowling that seals the pod
    aperture beside the RCS packs; box plugs in the scoop mesh were a poor
    substitute. This script keeps .001 and truncates the bell.
  - set_kids(len(flat_descendants)) parented omsRight under omsLeft whenever
    .001 was kept; kids must be the *direct* child count.
"""

from __future__ import annotations

from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "OMSPods.ac"
DST = Path(__file__).resolve().parents[1] / "OMSPods_grenadier.ac"

# Heritage omsLeft.001 / omsRight.001 are one mesh: short mount cowling
# (x ≲ 14.55) plus the flaring OMS bell aft of that. Keep cowling only.
BELL_TRIM = {"omsLeft.001", "omsRight.001"}
# Faces with any vertex at or beyond this local X are bell — drop them.
BELL_X_MIN = 14.55


def obj_name(block: list[str]) -> str | None:
    for line in block:
        if line.startswith("name "):
            if '"' in line:
                return line.split('"')[1]
            return line.split()[1]
    return None


def obj_kids(block: list[str]) -> int:
    for line in block:
        if line.startswith("kids "):
            return int(line.split()[1])
    return 0


def set_kids(block: list[str], n: int) -> list[str]:
    return [f"kids {n}" if line.startswith("kids ") else line for line in block]


def split_file(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    i = 0
    while i < len(lines) and not lines[i].startswith("OBJECT"):
        i += 1
    if i >= len(lines):
        raise SystemExit("no OBJECT in OMSPods.ac")
    header = lines[:i]
    objs: list[list[str]] = []
    k = i
    while k < len(lines):
        if not lines[k].startswith("OBJECT"):
            k += 1
            continue
        start = k
        k += 1
        while k < len(lines) and not lines[k].startswith("OBJECT"):
            k += 1
        objs.append(lines[start:k])
    return header, objs


def _parse_mesh(block: list[str]) -> tuple[list[str], list[tuple[float, float, float]], list[dict], list[str]]:
    """Return (pre_vert_lines, verts, surfs, post_surf_lines)."""
    i = 0
    while i < len(block) and not block[i].startswith("numvert "):
        i += 1
    if i >= len(block):
        raise SystemExit(f"no numvert in {obj_name(block)}")
    pre = block[:i]
    nv = int(block[i].split()[1])
    i += 1
    verts: list[tuple[float, float, float]] = []
    for _ in range(nv):
        parts = block[i].split()
        verts.append((float(parts[0]), float(parts[1]), float(parts[2])))
        i += 1
    while i < len(block) and not block[i].startswith("numsurf "):
        i += 1
    if i >= len(block):
        raise SystemExit(f"no numsurf in {obj_name(block)}")
    ns = int(block[i].split()[1])
    i += 1
    surfs: list[dict] = []
    for _ in range(ns):
        head: list[str] = []
        while i < len(block) and not block[i].startswith("refs "):
            head.append(block[i])
            i += 1
        if i >= len(block):
            raise SystemExit(f"truncated surf in {obj_name(block)}")
        nrefs = int(block[i].split()[1])
        i += 1
        refs: list[str] = []
        for _ in range(nrefs):
            refs.append(block[i])
            i += 1
        surfs.append({"head": head, "refs": refs})
    post = block[i:]
    return pre, verts, surfs, post


def trim_bell(block: list[str], x_min: float) -> list[str]:
    """Keep only faces whose vertices are entirely forward of x_min; reindex."""
    pre, verts, surfs, post = _parse_mesh(block)
    kept_surfs: list[dict] = []
    used: set[int] = set()
    for s in surfs:
        idxs = [int(r.split()[0]) for r in s["refs"]]
        if any(verts[j][0] >= x_min for j in idxs):
            continue
        kept_surfs.append(s)
        used.update(idxs)
    if not kept_surfs:
        raise SystemExit(f"{obj_name(block)}: bell trim removed every face")

    old_to_new = {old: new for new, old in enumerate(sorted(used))}
    new_verts = [verts[old] for old in sorted(used)]

    out = list(pre)
    out.append(f"numvert {len(new_verts)}")
    for x, y, z in new_verts:
        out.append(f"{x:.7f} {y:.7f} {z:.7f}")
    out.append(f"numsurf {len(kept_surfs)}")
    for s in kept_surfs:
        out.extend(s["head"])
        out.append(f"refs {len(s['refs'])}")
        for r in s["refs"]:
            parts = r.split()
            old = int(parts[0])
            rest = " ".join(parts[1:])
            out.append(f"{old_to_new[old]} {rest}" if rest else f"{old_to_new[old]}")
    out.extend(post)

    nm = obj_name(block)
    print(
        f"  trim {nm}: verts {len(verts)}→{len(new_verts)}, "
        f"faces {len(surfs)}→{len(kept_surfs)} (drop x>={x_min})"
    )
    return out


def prune_forest(
    objs: list[list[str]], start: int, count: int
) -> tuple[list[list[str]], int, int]:
    """Keep `count` siblings from `start`.

    Returns (flat_blocks, next_index, n_direct_kept).
    """
    kept: list[list[str]] = []
    i = start
    n_direct = 0
    for _ in range(count):
        if i >= len(objs):
            break
        block = objs[i]
        name = obj_name(block)
        n_kids = obj_kids(block)
        i += 1
        child_flat, i, n_child_direct = prune_forest(objs, i, n_kids)
        if name in BELL_TRIM:
            block = trim_bell(block, BELL_X_MIN)
        n_direct += 1
        kept.append(set_kids(block, n_child_direct))
        kept.extend(child_flat)
    return kept, i, n_direct


def main() -> None:
    lines = SRC.read_text(errors="ignore").splitlines()
    header, objs = split_file(lines)
    if not objs:
        raise SystemExit("empty OMSPods.ac")

    world = objs[0]
    forest, _, roots = prune_forest(objs, 1, obj_kids(world))

    out = header + set_kids(world, roots)
    for block in forest:
        out.extend(block)
    DST.write_text("\n".join(out) + "\n")

    print(f"wrote {DST.name}: {len(forest)} objs, world kids={roots}")
    i = 0
    while i < len(forest):
        nm = obj_name(forest[i])
        nk = obj_kids(forest[i])
        print(f"  root {nm} kids={nk}")
        i += 1
        stack = [nk]
        while stack:
            left = stack.pop()
            for _ in range(left):
                if i >= len(forest):
                    break
                stack.append(obj_kids(forest[i]))
                i += 1


if __name__ == "__main__":
    main()
