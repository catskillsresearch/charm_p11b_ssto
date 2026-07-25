#!/usr/bin/env python3
"""Build a coarse exterior volume mesh around catskills_ssto.stl for SU2.

Gmsh's STL→CAD path fails on the multi-body OpenVSP export (overlapping /
non-parametrizable facets). Instead:

  1. Voxel-remesh → single watertight manifold (world coordinates).
  2. TetGen: far-field box with body as a hole → coarse tets.
  3. Write .su2 with WALL + FARFIELD markers (by face proximity).

Intentionally coarse (Euler / poster demo), not BL-resolved RANS.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pyvista as pv
import trimesh
from tetgen import TetGen

CAD = Path(__file__).resolve().parents[1]
STL_SRC = CAD / "catskills_ssto.stl"
OUT_DIR = Path(__file__).resolve().parent / "ssto"
STL_BODY = OUT_DIR / "body_voxel.stl"
OUT_VTU = OUT_DIR / "ssto_farfield.vtu"
OUT_SU2 = OUT_DIR / "ssto_farfield.su2"

VOXEL_PITCH_M = 0.55
# VTK element type tags used by SU2 mesh files.
VTK_TRIANGLE = 5
VTK_TETRA = 10


def _prepare_body_stl(src: Path, dst: Path, pitch: float) -> trimesh.Trimesh:
    """Fuse OpenVSP multi-body STL into one manifold via voxel → marching cubes."""
    m = trimesh.load(src, force="mesh")
    vox = m.voxelized(pitch)
    shell = vox.marching_cubes
    # marching_cubes is often in index space; always map with the voxel transform
    # when extents disagree with the source mesh.
    if not np.allclose(shell.extents, m.extents, rtol=0.25, atol=1.0):
        shell.apply_transform(vox.transform)
    trimesh.repair.fix_normals(shell)
    parts = shell.split(only_watertight=False)
    shell = max(parts, key=lambda p: len(p.faces))
    dst.parent.mkdir(parents=True, exist_ok=True)
    shell.export(dst)
    return shell


def _farfield_box(bounds: np.ndarray, L: float) -> tuple[pv.PolyData, np.ndarray]:
    xmin, xmax = bounds[0]
    ymin, ymax = bounds[1]
    zmin, zmax = bounds[2]
    box_bounds = (
        xmin - 1.0 * L,
        xmax + 2.0 * L,
        ymin - 1.2 * L,
        ymax + 1.2 * L,
        zmin - 0.8 * L,
        zmax + 1.2 * L,
    )
    cube = pv.Box(bounds=box_bounds).extract_surface(algorithm="dataset_surface")
    cube = cube.triangulate().subdivide(3)
    cube.compute_normals(auto_orient_normals=True, inplace=True)
    return cube, np.asarray(box_bounds, dtype=float)


def _write_su2(
    nodes: np.ndarray,
    tets: np.ndarray,
    wall_faces: np.ndarray,
    far_faces: np.ndarray,
    path: Path,
) -> None:
    """Write a 3D SU2 mesh with WALL / FARFIELD triangle markers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("NDIME= 3\n")
        f.write(f"NELEM= {len(tets)}\n")
        for i, tet in enumerate(tets):
            f.write(
                f"{VTK_TETRA}\t{tet[0]}\t{tet[1]}\t{tet[2]}\t{tet[3]}\t{i}\n"
            )
        f.write(f"NPOIN= {len(nodes)}\n")
        for i, (x, y, z) in enumerate(nodes):
            f.write(f"{x:.10g}\t{y:.10g}\t{z:.10g}\t{i}\n")
        f.write("NMARK= 2\n")
        f.write("MARKER_TAG= WALL\n")
        f.write(f"MARKER_ELEMS= {len(wall_faces)}\n")
        for i, face in enumerate(wall_faces):
            f.write(f"{VTK_TRIANGLE}\t{face[0]}\t{face[1]}\t{face[2]}\t{i}\n")
        f.write("MARKER_TAG= FARFIELD\n")
        f.write(f"MARKER_ELEMS= {len(far_faces)}\n")
        for i, face in enumerate(far_faces):
            f.write(f"{VTK_TRIANGLE}\t{face[0]}\t{face[1]}\t{face[2]}\t{i}\n")


def _classify_boundary_faces(
    nodes: np.ndarray,
    faces: np.ndarray,
    body_bounds: np.ndarray,
    box_bounds: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Split boundary triangles into WALL (near body) vs FARFIELD (near box)."""
    cents = nodes[faces].mean(axis=1)
    # Inflated body AABB — wall faces sit on the body surface.
    pad = 0.05 * np.max(body_bounds[:, 1] - body_bounds[:, 0])
    bb0 = body_bounds[:, 0] - pad
    bb1 = body_bounds[:, 1] + pad
    on_body = np.all((cents >= bb0) & (cents <= bb1), axis=1)

    # Farfield: centroid near any outer box face.
    x0, x1, y0, y1, z0, z1 = box_bounds
    tol = 0.02 * max(x1 - x0, y1 - y0, z1 - z0)
    on_far = (
        (np.abs(cents[:, 0] - x0) < tol)
        | (np.abs(cents[:, 0] - x1) < tol)
        | (np.abs(cents[:, 1] - y0) < tol)
        | (np.abs(cents[:, 1] - y1) < tol)
        | (np.abs(cents[:, 2] - z0) < tol)
        | (np.abs(cents[:, 2] - z1) < tol)
    )
    # Prefer explicit far hits; remainder inside body pad → wall.
    wall = faces[on_body & ~on_far]
    far = faces[on_far]
    leftover = faces[~on_body & ~on_far]
    if len(leftover):
        # Assign leftovers by distance to body center vs box shell.
        bc = 0.5 * (body_bounds[:, 0] + body_bounds[:, 1])
        lc = nodes[leftover].mean(axis=1)
        d_body = np.linalg.norm(lc - bc, axis=1)
        # Heuristic: closer to body center than ~0.55 of box half-diag → wall.
        box_c = np.array([0.5 * (x0 + x1), 0.5 * (y0 + y1), 0.5 * (z0 + z1)])
        half = 0.5 * np.array([x1 - x0, y1 - y0, z1 - z0])
        d_far = np.abs(np.abs(lc - box_c) / np.maximum(half, 1e-9)).max(axis=1)
        take_wall = d_body < 0.55 * np.linalg.norm(half)
        # faces with d_far ~ 1 are on the box
        take_far = d_far > 0.92
        wall = np.vstack([wall, leftover[take_wall & ~take_far]]) if wall.size else leftover[take_wall & ~take_far]
        far = np.vstack([far, leftover[take_far]]) if far.size else leftover[take_far]
        still = leftover[~(take_wall | take_far)]
        if len(still):
            # Dump ambiguous to farfield so the fluid domain stays closed for SU2.
            far = np.vstack([far, still]) if far.size else still
    return wall.astype(np.int64), far.astype(np.int64)


def main() -> int:
    if not STL_SRC.is_file():
        print(f"Missing {STL_SRC}; run make cad-figures", file=sys.stderr)
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"==> voxel-remesh {STL_SRC.name} → {STL_BODY.name} (pitch={VOXEL_PITCH_M} m)")
    shell = _prepare_body_stl(STL_SRC, STL_BODY, VOXEL_PITCH_M)
    print(
        f"  body faces={len(shell.faces)} watertight={shell.is_watertight} "
        f"bbox={shell.bounds.tolist()}"
    )

    body = pv.read(str(STL_BODY)).triangulate()
    body.compute_normals(auto_orient_normals=True, inplace=True)
    bounds = np.array(body.bounds, dtype=float).reshape(3, 2)
    L = float(np.max(bounds[:, 1] - bounds[:, 0]))
    cube, box_bounds = _farfield_box(bounds, L)
    print(
        f"  farfield box: x[{box_bounds[0]:.1f},{box_bounds[1]:.1f}] "
        f"y[{box_bounds[2]:.1f},{box_bounds[3]:.1f}] "
        f"z[{box_bounds[4]:.1f},{box_bounds[5]:.1f}]"
    )

    mesh = pv.merge([body, cube])
    hole = (0.5 * (bounds[:, 0] + bounds[:, 1])).tolist()
    print(f"==> TetGen exterior mesh (hole at {hole})")
    tgen = TetGen(mesh)
    tgen.add_hole(hole)
    # Coarse quality mesh: ~0.12 L edge scale → manageable SU2 demo.
    maxvol = (0.12 * L) ** 3
    nodes, tets, *_ = tgen.tetrahedralize(
        switches=f"pq1.8a{maxvol:.8f}",
        steinerleft=80000,
        quiet=False,
    )
    nodes = np.asarray(nodes, dtype=float)
    tets = np.asarray(tets, dtype=np.int64)
    faces = np.asarray(tgen.trifaces, dtype=np.int64)
    print(f"  nodes={len(nodes)} tets={len(tets)} boundary_faces={len(faces)}")

    wall, far = _classify_boundary_faces(nodes, faces, bounds, box_bounds)
    print(f"  markers: WALL={len(wall)} FARFIELD={len(far)}")
    if len(wall) < 100 or len(far) < 12:
        print("Marker classification looks wrong; aborting.", file=sys.stderr)
        return 1

    tgen.grid.save(str(OUT_VTU))
    _write_su2(nodes, tets, wall, far, OUT_SU2)
    print(f"wrote {OUT_VTU.name} / {OUT_SU2.name}")
    print(f"  su2 size={OUT_SU2.stat().st_size / 1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
