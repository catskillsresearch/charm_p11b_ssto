# SU2 digital tunnel (scripted)

[SU2](https://su2code.github.io/) is open-source CFD. Unlike VSPAERO Viewer, it is
driven by config files + meshes — no GUI menus.

## Install (already done locally)

OpenMP Linux binary unpacks under `third_party/su2/bin/` (SU2 v8.5.0).

```bash
export PATH="$PWD/third_party/su2/bin:$PATH"
SU2_CFD --help
```

Needs (Poetry): `gmsh`, `trimesh`, `pyvista`, `tetgen`, `scikit-image`.

## First case (NACA 0012 — proof it works)

```bash
make su2-naca
# → research/figures/cad/su2/naca0012/{flow.vtu,surface_flow.csv,naca0012_cp.png}
```

Inviscid, M=0.8, α=1.25°. Open `flow.vtu` in ParaView for a field view, or look at
`naca0012_cp.png`.

## CHARM SSTO (coarse 3D Euler)

Gmsh’s STL→CAD path fails on the multi-body OpenVSP export. The scripted path is:

1. Voxel-remesh `catskills_ssto.stl` → single watertight manifold.
2. TetGen: far-field box with the body as a hole → coarse tets (~80k).
3. SU2 Euler at M=0.3, α=4°; pyvista ¾ view with surface Cp + mid-span slice.

```bash
make su2-ssto
# → research/figures/cad/su2/ssto/{ssto_farfield.su2,flow.vtu,ssto_euler_cp.png}
```

This is a **poster / digital-tunnel demo**, not BL-resolved RANS. The voxel body is a
blobby stand-in for the true VSP surfaces — good enough for “plane in airflow,” not
for coefficients you’ll trust against VSPAERO.

Optional: `SU2_THREADS=16 make su2-ssto`
