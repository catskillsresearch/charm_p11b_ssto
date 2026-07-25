#!/usr/bin/env python3
"""Set Φ = U∞·x on far-field patches (no coded BC / WM_OPTIONS needed)."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

CASE = Path(__file__).resolve().parent / "ssto_snappy"
UINF = np.array([101.8, 0.0, 7.1])
PATCHES = ("inlet", "outlet", "ground", "sky", "side1", "side2")


def _read_points(mesh: Path) -> np.ndarray:
    text = (mesh / "points").read_text()
    m = re.search(r"(\d+)\s*\n\(", text)
    if not m:
        raise SystemExit("bad points file")
    n = int(m.group(1))
    body = text.split("\n(", 1)[1]
    pts = []
    for line in body.splitlines():
        line = line.strip().rstrip(",")
        if not line.startswith("("):
            continue
        x, y, z = map(float, line.strip("(),").split())
        pts.append((x, y, z))
        if len(pts) >= n:
            break
    return np.asarray(pts, dtype=float)


def _face_centres(mesh: Path, pts: np.ndarray, patch: str) -> np.ndarray:
    # boundary file lists patches with nFaces / startFace into faces
    boundary = (mesh / "boundary").read_text()
    pat = rf"{patch}\s*\{{[^}}]*?nFaces\s+(\d+);\s*startFace\s+(\d+);"
    m = re.search(pat, boundary, re.S)
    if not m:
        raise SystemExit(f"patch {patch} not found in boundary")
    n_faces, start = int(m.group(1)), int(m.group(2))
    faces_text = (mesh / "faces").read_text()
    # faces are "N(i j k ...)" lines after count
    fm = re.search(r"(\d+)\s*\n\(", faces_text)
    body = faces_text.split("\n(", 1)[1]
    all_faces = []
    for line in body.splitlines():
        line = line.strip().rstrip(",")
        if not line or not line[0].isdigit():
            # format: 4(0 1 2 3)
            if "(" in line and line.split("(")[0].strip().isdigit():
                pass
            else:
                continue
        if "(" not in line:
            continue
        n_s, rest = line.split("(", 1)
        ids = list(map(int, rest.strip("),").split()))
        all_faces.append(ids)
        if len(all_faces) >= start + n_faces and len(all_faces) > start:
            # keep reading until we have enough
            pass
        if len(all_faces) >= start + n_faces:
            break
    # More reliable line scan
    all_faces = []
    for line in body.splitlines():
        line = line.strip().rstrip(",")
        if "(" not in line:
            continue
        try:
            prefix, rest = line.split("(", 1)
            if not prefix.strip().isdigit():
                continue
            ids = list(map(int, rest.strip("),").split()))
        except ValueError:
            continue
        all_faces.append(ids)
        if len(all_faces) >= start + n_faces:
            break
    sel = all_faces[start : start + n_faces]
    cents = np.array([pts[f].mean(axis=0) for f in sel], dtype=float)
    return cents


def _write_phi(patch_values: dict[str, np.ndarray]) -> None:
    lines = [
        "FoamFile",
        "{",
        "    version     2.0;",
        "    format      ascii;",
        "    class       volScalarField;",
        "    object      Phi;",
        "}",
        "",
        "dimensions      [0 2 -1 0 0 0 0];",
        "",
        "internalField   uniform 0;",
        "",
        "boundaryField",
        "{",
        "    WALL",
        "    {",
        "        type            zeroGradient;",
        "    }",
    ]
    for patch in PATCHES:
        vals = patch_values[patch]
        lines += [
            f"    {patch}",
            "    {",
            "        type            fixedValue;",
            "        value           nonuniform List<scalar>",
            f"        {len(vals)}",
            "        (",
        ]
        lines += [f"        {v:.8g}" for v in vals]
        lines += [
            "        );",
            "    }",
        ]
    lines += ["}", ""]
    out = CASE / "0" / "Phi"
    out.write_text("\n".join(lines) + "\n")
    print(f"wrote {out} with Φ=U∞·x on {', '.join(PATCHES)}")


def main() -> int:
    mesh = CASE / "constant" / "polyMesh"
    pts = _read_points(mesh)
    patch_values = {}
    for patch in PATCHES:
        c = _face_centres(mesh, pts, patch)
        patch_values[patch] = c @ UINF
        print(f"  {patch}: {len(c)} faces  Φ∈[{patch_values[patch].min():.1f},{patch_values[patch].max():.1f}]")
    (CASE / "0").mkdir(exist_ok=True)
    _write_phi(patch_values)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
