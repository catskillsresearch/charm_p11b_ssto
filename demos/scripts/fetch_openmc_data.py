#!/usr/bin/env python3
"""Download a minimal ENDF/B-VII.1 HDF5 library for the OpenMC demos."""

from __future__ import annotations

from pathlib import Path

import openmc
from openmc_data_downloader import download_cross_section_data

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "demos" / "openmc" / "nuclear_data"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fuel = openmc.Material(name="fuel")
    fuel.add_nuclide("U234", 1e-6)
    fuel.add_nuclide("U235", 1e-3)
    fuel.add_nuclide("U238", 1e-2)
    fuel.add_nuclide("O16", 2e-2)
    clad = openmc.Material(name="clad")
    for z, a in [
        ("Zr90", 0.5),
        ("Zr91", 0.1),
        ("Zr92", 0.2),
        ("Zr94", 0.15),
        ("Zr96", 0.05),
    ]:
        clad.add_nuclide(z, a)
    water = openmc.Material(name="water")
    water.add_nuclide("H1", 2)
    water.add_nuclide("O16", 1)
    water.add_nuclide("B10", 1e-5)
    water.add_nuclide("B11", 4e-5)
    water.add_s_alpha_beta("c_H_in_H2O")
    steel = openmc.Material(name="steel")
    for n, f in [
        ("Fe54", 0.05),
        ("Fe56", 0.9),
        ("Fe57", 0.02),
        ("Fe58", 0.01),
        ("C0", 0.01),
        ("Ni58", 0.005),
        ("Ni60", 0.002),
        ("Cr52", 0.01),
        ("Mn55", 0.01),
    ]:
        steel.add_nuclide(n, f)
    mats = openmc.Materials([fuel, clad, water, steel])
    xs = download_cross_section_data(
        mats,
        libraries=["ENDFB-7.1-NNDC"],
        destination=str(OUT),
        particles=["neutron"],
        set_OPENMC_CROSS_SECTIONS=False,
        overwrite=False,
    )
    print(f"Wrote {xs}")


if __name__ == "__main__":
    main()
