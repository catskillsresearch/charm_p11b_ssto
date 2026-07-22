# Fusion physics package demos
#
# Three GitHub codes installed for hands-on tours:
#   - ASCOT5  (orbit following)     https://github.com/ascot4fusion/ascot5
#   - OpenMC  (Monte Carlo transport) https://github.com/openmc-dev/openmc
#   - DipolEq (dipole Grad–Shafranov) https://github.com/dgarnier/dipoleq

## Quick start

```bash
# Interactive by default — close each plot window to continue
demos/dipoleq/run.sh
demos/openmc/run.sh
demos/ascot5/run.sh

# Save PNGs only (no GUI):
demos/dipoleq/run.sh --headless

# Or everything (use --headless for batch):
demos/run_all.sh --headless
```

Plots and `summary.json` land in `demos/output/{dipoleq,openmc,ascot5}/`.
In interactive mode the demos pause on each figure until you close the window.

## What each demo covers

### DipolEq (`demos/dipoleq/demo_dipoleq.py`)
Levitated-dipole Grad–Shafranov equilibria (LDX-style).
- Load YAML + legacy `.in` inputs
- Solve, `plot_eq`, pressure / J / β / q profiles
- Export HDF5 + EFIT GEQDSK (`to_hdf5`, `to_geqdsk`, `h5togeqdsk`)
- Gallery of bundled `Testing/*.in` cases (β, diverted vs limited)

### OpenMC (`demos/openmc/demo_openmc.py`)
Continuous-energy Monte Carlo neutron transport.
- Materials, nuclides, S(α,β) thermal scattering
- CSG pin-cell (reflective infinite lattice)
- Geometry color plots
- Eigenvalue + Shannon entropy
- Cell / energy / mesh / nuclide tallies + StatePoint plots
- Built-in `openmc.examples.pwr_pin_cell` and `pwr_assembly`

Nuclear data: minimal ENDF/B-VII.1 HDF5 under `demos/openmc/nuclear_data/`
(fetched by `demos/scripts/fetch_openmc_data.py`).

### ASCOT5 (`demos/ascot5/demo_ascot5.py`)
Fast-ion / marker orbit following (official tutorial workflow).
- `Ascot` HDF5 workspace + template inputs (B, wall, plasma, E, markers)
- 3.5 MeV α guiding-center markers on analytical ITER-circular field
- `ascot5_main` run with orbit diagnostics enabled
- Endstate scatter / spectra, RZ orbits, input field plots

**Note:** ASCOT5’s options I/O expects NumPy 1.x (`numpy<2` in the env).
Build with `CC=gcc` (conda `h5cc` passes `-shlib`, which GCC rejects).

## Environments

| Package | Location | Notes |
|--------|----------|-------|
| DipolEq | repo `.venv` | `pip install dipoleq` |
| OpenMC | `demos/.envs/openmc` | `micromamba create … openmc` |
| ASCOT5 | `demos/.envs/ascot5` | `demos/scripts/build_ascot5.sh` |

Vendor checkouts (shallow clones) live in `demos/vendor/{ascot5,dipoleq}/`.
Large envs / nuclear `.h5` files are gitignored.

## Re-create installs

```bash
# OpenMC
micromamba create -y -p demos/.envs/openmc -c conda-forge openmc matplotlib h5py pandas
micromamba run -p demos/.envs/openmc pip install openmc_data_downloader
micromamba run -p demos/.envs/openmc python demos/scripts/fetch_openmc_data.py

# ASCOT5
demos/scripts/build_ascot5.sh

# DipolEq
.venv/bin/pip install dipoleq
```

## Upstream docs

- [ASCOT5 tutorials](https://ascot4fusion.github.io/ascot5/)
- [OpenMC user’s guide / pin-cell example](https://docs.openmc.org/)
- [DipolEq docs](https://dipoleq.readthedocs.io/)
