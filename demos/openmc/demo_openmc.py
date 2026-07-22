#!/usr/bin/env python3
"""Comprehensive OpenMC demo — Monte Carlo neutron transport tour.

Tours https://github.com/openmc-dev/openmc capabilities:
  1. Nuclear data / cross-section library setup
  2. Materials (UO₂, Zircaloy, borated water + S(α,β))
  3. CSG pin-cell geometry + universe hierarchy
  4. Geometry / material plots
  5. Eigenvalue calculation with Shannon entropy
  6. Tallies (flux, fission, absorption, nuclide-specific rates)
  7. Built-in PWR assembly example
  8. Post-processing StatePoint results

Requires the micromamba env at demos/.envs/openmc and nuclear data under
demos/openmc/nuclear_data/ (see demos/README.md).

By default opens interactive plot windows (close each to continue).
Use ``--headless`` to only write PNGs.

Run::

    demos/openmc/run.sh
    demos/openmc/run.sh --headless
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "demos" / "scripts"))
from demo_display import add_display_args, configure_matplotlib, present  # noqa: E402

OUT = ROOT / "demos" / "output" / "openmc"
XS_XML = ROOT / "demos" / "openmc" / "nuclear_data" / "cross_sections.xml"
WORKDIR = OUT / "run"


def banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def setup_env() -> None:
    if not XS_XML.is_file():
        raise FileNotFoundError(
            f"Missing {XS_XML}. Run demos/scripts/fetch_openmc_data.py first."
        )
    os.environ["OPENMC_CROSS_SECTIONS"] = str(XS_XML)
    OUT.mkdir(parents=True, exist_ok=True)
    if WORKDIR.exists():
        shutil.rmtree(WORKDIR)
    WORKDIR.mkdir(parents=True)


def section_materials_geometry():
    banner("1) Materials + CSG pin-cell geometry (from scratch)")
    import openmc

    fuel = openmc.Material(name="UO2 (2.4%)")
    fuel.set_density("g/cm3", 10.29769)
    fuel.add_nuclide("U234", 4.4843e-6)
    fuel.add_nuclide("U235", 5.5815e-4)
    fuel.add_nuclide("U238", 2.2408e-2)
    fuel.add_nuclide("O16", 4.5829e-2)

    clad = openmc.Material(name="Zircaloy")
    clad.set_density("g/cm3", 6.55)
    clad.add_nuclide("Zr90", 2.1827e-2)
    clad.add_nuclide("Zr91", 4.7600e-3)
    clad.add_nuclide("Zr92", 7.2758e-3)
    clad.add_nuclide("Zr94", 7.3734e-3)
    clad.add_nuclide("Zr96", 1.1879e-3)

    water = openmc.Material(name="Hot borated water")
    water.set_density("g/cm3", 0.740582)
    water.add_nuclide("H1", 4.9457e-2)
    water.add_nuclide("O16", 2.4672e-2)
    water.add_nuclide("B10", 8.0042e-6)
    water.add_nuclide("B11", 3.2218e-5)
    water.add_s_alpha_beta("c_H_in_H2O")

    mats = openmc.Materials([fuel, clad, water])
    print("  materials:", [m.name for m in mats])
    print("  nuclides:", sorted({n.name for m in mats for n in m.nuclides}))

    pitch = 1.26
    fuel_or = openmc.ZCylinder(r=0.39218, name="Fuel OR")
    clad_or = openmc.ZCylinder(r=0.45720, name="Clad OR")
    left = openmc.XPlane(x0=-pitch / 2, boundary_type="reflective")
    right = openmc.XPlane(x0=+pitch / 2, boundary_type="reflective")
    bottom = openmc.YPlane(y0=-pitch / 2, boundary_type="reflective")
    top = openmc.YPlane(y0=+pitch / 2, boundary_type="reflective")

    fuel_cell = openmc.Cell(name="Fuel", fill=fuel, region=-fuel_or)
    clad_cell = openmc.Cell(name="Clad", fill=clad, region=+fuel_or & -clad_or)
    water_cell = openmc.Cell(
        name="Water",
        fill=water,
        region=+clad_or & +left & -right & +bottom & -top,
    )
    root = openmc.Universe(name="root", cells=[fuel_cell, clad_cell, water_cell])
    geom = openmc.Geometry(root)
    print("  cells:", [c.name for c in root.cells.values()])
    return mats, geom, fuel_cell, clad_cell, water_cell


def show_png(plt, path: Path, *, headless: bool, title: str) -> None:
    """Display a saved PNG in an interactive matplotlib window."""
    if headless or not path.is_file():
        return
    img = plt.imread(path)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(img)
    ax.set_axis_off()
    ax.set_title(title)
    fig.tight_layout()
    print(f"  → showing: {title} (close the window to continue)")
    try:
        plt.show(block=True)
    except Exception as exc:
        print(f"  (interactive display failed: {exc})")
    plt.close("all")


def section_plots(plt, geom, mats, *, headless: bool) -> None:
    banner("2) Geometry / material color plots")
    import openmc

    plot = openmc.Plot()
    plot.filename = "pin_xy"
    plot.width = (1.26, 1.26)
    plot.pixels = (400, 400)
    plot.color_by = "material"
    plot.colors = {
        mats[0]: "red",
        mats[1]: "silver",
        mats[2]: "skyblue",
    }
    plots = openmc.Plots([plot])
    model = openmc.Model(geometry=geom, materials=mats)
    model.plots = plots
    cwd = WORKDIR / "plots"
    cwd.mkdir(parents=True)
    model.export_to_xml(cwd)
    openmc.plot_geometry(cwd=cwd, openmc_exec="openmc")
    for src in cwd.glob("*.png"):
        dest = OUT / src.name
        shutil.copy(src, dest)
        print(f"  wrote {dest}")
        show_png(plt, dest, headless=headless, title="Pin-cell materials")


def section_tallies(fuel_cell, water_cell):
    banner("3) Tallies — flux, fission, absorption, U-235 rates")
    import openmc

    cell_filter = openmc.CellFilter([fuel_cell, water_cell])
    energy_filter = openmc.EnergyFilter([0.0, 0.625, 20.0e6])

    t_flux = openmc.Tally(name="flux")
    t_flux.filters = [cell_filter, energy_filter]
    t_flux.scores = ["flux", "fission", "absorption", "nu-fission"]

    t_u235 = openmc.Tally(name="u235_rates")
    t_u235.filters = [openmc.CellFilter(fuel_cell)]
    t_u235.nuclides = ["U235"]
    t_u235.scores = ["total", "fission", "absorption", "(n,gamma)"]

    mesh = openmc.RegularMesh()
    mesh.dimension = [20, 20, 1]
    mesh.lower_left = [-0.63, -0.63, -1.0]
    mesh.upper_right = [0.63, 0.63, 1.0]
    mesh_filter = openmc.MeshFilter(mesh)
    t_mesh = openmc.Tally(name="mesh_flux")
    t_mesh.filters = [mesh_filter]
    t_mesh.scores = ["flux"]

    return openmc.Tallies([t_flux, t_u235, t_mesh]), mesh


def section_eigenvalue(plt, mats, geom, tallies, *, headless: bool) -> dict:
    banner("4) Eigenvalue pin-cell run (keff + Shannon entropy)")
    import openmc

    settings = openmc.Settings()
    settings.batches = 40
    settings.inactive = 10
    settings.particles = 2000
    settings.entropy_mesh = openmc.RegularMesh()
    settings.entropy_mesh.dimension = [8, 8, 1]
    settings.entropy_mesh.lower_left = [-0.63, -0.63, -100.0]
    settings.entropy_mesh.upper_right = [0.63, 0.63, 100.0]

    model = openmc.Model(geometry=geom, materials=mats, settings=settings, tallies=tallies)
    pin_dir = WORKDIR / "pincell"
    pin_dir.mkdir(parents=True)
    sp_path = model.run(cwd=pin_dir, output=True)
    print(f"  statepoint → {sp_path}")

    with openmc.StatePoint(sp_path) as sp:
        keff = sp.keff
        print(f"  keff = {keff}")
        entropy = list(sp.entropy) if sp.entropy is not None else []
        t_flux = sp.get_tally(name="flux")
        t_u235 = sp.get_tally(name="u235_rates")
        t_mesh = sp.get_tally(name="mesh_flux")
        print("  flux tally mean (first bins):", t_flux.mean.ravel()[:4])
        print("  U-235 rates:", dict(zip(t_u235.scores, t_u235.mean.ravel())))

        mean = t_mesh.mean.reshape(20, 20)
        fig, ax = plt.subplots(figsize=(5, 4.5))
        im = ax.imshow(mean, origin="lower", extent=[-0.63, 0.63, -0.63, 0.63])
        ax.set_xlabel("x [cm]")
        ax.set_ylabel("y [cm]")
        ax.set_title("Pin-cell mesh flux")
        fig.colorbar(im, ax=ax, label="flux")
        fig.tight_layout()
        present(
            plt,
            fig,
            OUT / "pincell_mesh_flux.png",
            headless=headless,
            title="Pin-cell mesh flux",
        )

        if entropy:
            fig, ax = plt.subplots(figsize=(6, 3.5))
            ax.plot(entropy, lw=2)
            ax.set_xlabel("batch")
            ax.set_ylabel("Shannon entropy")
            ax.set_title("Source convergence")
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            present(
                plt,
                fig,
                OUT / "pincell_entropy.png",
                headless=headless,
                title="Shannon entropy",
            )

        result = {
            "keff_nominal": float(keff.n),
            "keff_std": float(keff.s),
            "batches": settings.batches,
            "particles": settings.particles,
            "entropy_last": float(entropy[-1]) if entropy else None,
        }
    return result


def section_builtin_examples(plt, *, headless: bool) -> dict:
    banner("5) Built-in openmc.examples — PWR pin + assembly")
    import openmc
    import openmc.examples as ex

    results = {}
    pin = ex.pwr_pin_cell()
    pin.settings.batches = 30
    pin.settings.inactive = 8
    pin.settings.particles = 1500
    pin_dir = WORKDIR / "examples_pin"
    pin_dir.mkdir(parents=True)
    sp = pin.run(cwd=pin_dir, output=True)
    with openmc.StatePoint(sp) as state:
        results["examples_pwr_pin_keff"] = float(state.keff.n)
        print(f"  examples.pwr_pin_cell keff = {state.keff}")

    asm = ex.pwr_assembly()
    asm.settings.batches = 25
    asm.settings.inactive = 8
    asm.settings.particles = 2000
    plot = openmc.Plot()
    plot.filename = "assembly_xy"
    plot.width = (21.42, 21.42)
    plot.pixels = (500, 500)
    plot.color_by = "material"
    asm.plots = openmc.Plots([plot])
    asm_dir = WORKDIR / "examples_assembly"
    asm_dir.mkdir(parents=True)
    asm.export_to_xml(asm_dir)
    openmc.plot_geometry(cwd=asm_dir, openmc_exec="openmc")
    for src in asm_dir.glob("*.png"):
        dest = OUT / src.name
        shutil.copy(src, dest)
        print(f"  wrote {dest}")
        show_png(plt, dest, headless=headless, title="PWR assembly materials")
    sp = asm.run(cwd=asm_dir, output=True)
    with openmc.StatePoint(sp) as state:
        results["examples_pwr_assembly_keff"] = float(state.keff.n)
        print(f"  examples.pwr_assembly keff = {state.keff}")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_display_args(parser)
    args = parser.parse_args(argv)
    plt = configure_matplotlib(args.headless)

    banner("OpenMC comprehensive demo")
    try:
        import openmc
    except ImportError:
        print("OpenMC not importable. Use demos/openmc/run.sh")
        return 1

    print(f"  openmc {openmc.__version__}")
    print(
        f"  mode: {'headless' if args.headless else 'interactive (close each window to continue)'}"
    )
    setup_env()
    print(f"  OPENMC_CROSS_SECTIONS={os.environ['OPENMC_CROSS_SECTIONS']}")

    mats, geom, fuel_cell, clad_cell, water_cell = section_materials_geometry()
    section_plots(plt, geom, mats, headless=args.headless)
    tallies, _mesh = section_tallies(fuel_cell, water_cell)
    pin_result = section_eigenvalue(plt, mats, geom, tallies, headless=args.headless)
    ex_result = section_builtin_examples(plt, headless=args.headless)

    report = {"pincell": pin_result, "examples": ex_result, "openmc": openmc.__version__}
    path = OUT / "summary.json"
    path.write_text(json.dumps(report, indent=2))
    banner("Done")
    print(f"  summary → {path}")
    print("  Key capabilities exercised:")
    print("    • Materials / nuclides / S(α,β) thermal scattering")
    print("    • CSG surfaces, cells, universes, reflective BC")
    print("    • Geometry color plots (interactive)")
    print("    • Eigenvalue mode + Shannon entropy mesh")
    print("    • Cell / energy / mesh / nuclide tallies")
    print("    • StatePoint post-processing")
    print("    • openmc.examples.pwr_pin_cell + pwr_assembly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
