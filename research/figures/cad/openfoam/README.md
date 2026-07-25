# OpenFOAM / snappyHexMesh (host install — not Poetry)

OpenFOAM is a **system CFD toolbox** (like Blender / OpenVSP): it cannot be
installed via Poetry. The case under `ssto_snappy/` is meant to be run on the
host after OpenFOAM is on `PATH`.

## Install (Ubuntu 24.04)

```bash
sudo apt-get install -y openfoam
which snappyHexMesh   # Ubuntu package puts apps on PATH (/usr/bin)
# Do NOT source /usr/share/openfoam/etc/bashrc on Ubuntu — foamEtcFile links are broken.
```

## Run

```bash
make cad-snappy          # mesh + layers → openfoam/ssto_snappy/
# optional later: convert / SU2 / simpleFoam (see Allrun)
```

Uses `research/figures/cad/catskills_ssto.stl` (true OpenVSP shell — **not** the
voxel plushy). `snappyHexMesh` adds a few prism layers on `WALL` for a first
BL-aware exterior mesh.

## Honesty

This is still a **coarse demo mesh** (poster / digital-tunnel), not a
certification RANS grid. Hypersonic Stage‑2 \(C_D(M)\) remains on the generic
table until a real high-Mach solver+mesh closes.
