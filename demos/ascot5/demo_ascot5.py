#!/usr/bin/env python3
"""Comprehensive ASCOT5 demo — orbit-following for fusion fast ions.

Tours https://github.com/ascot4fusion/ascot5 (based on official tutorials):
  1. Create an ASCOT5 HDF5 workspace and template inputs
  2. Analytical ITER-like circular B-field, wall, plasma, E-field
  3. Generate guiding-center α markers
  4. Run ``ascot5_main`` (orbit following)
  5. Post-process endstates (confined vs wall losses)
  6. Orbit collection + RZ orbit plots
  7. Input field visualization (B, wall)

Requires demos/.envs/ascot5 with compiled libascot / ascot5_main
(see demos/README.md).

By default opens interactive plot windows (close each to continue).
Use ``--headless`` to only write PNGs.

Run::

    demos/ascot5/run.sh
    demos/ascot5/run.sh --headless
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "demos" / "scripts"))
from demo_display import add_display_args, configure_matplotlib, present  # noqa: E402
VENDOR = ROOT / "demos" / "vendor" / "ascot5"
ENV = ROOT / "demos" / ".envs" / "ascot5"
OUT = ROOT / "demos" / "output" / "ascot5"
WORKDIR = OUT / "run"
ASCOT_BIN = VENDOR / "build" / "ascot5_main"
LIBDIR = VENDOR / "build"


def banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def prepare_env() -> None:
    if not ASCOT_BIN.is_file():
        raise FileNotFoundError(
            f"Missing {ASCOT_BIN}. Build with demos/scripts/build_ascot5.sh"
        )
    OUT.mkdir(parents=True, exist_ok=True)
    if WORKDIR.exists():
        shutil.rmtree(WORKDIR)
    WORKDIR.mkdir(parents=True)
    # Prefer compiled shared library
    ld = os.environ.get("LD_LIBRARY_PATH", "")
    parts = [str(LIBDIR), str(ENV / "lib")]
    os.environ["LD_LIBRARY_PATH"] = ":".join(parts + ([ld] if ld else []))
    os.chdir(WORKDIR)


def section_create_inputs():
    banner("1) Create ASCOT5 HDF5 inputs (tutorial templates)")
    from a5py import Ascot
    from a5py.ascot5io.marker import Marker

    h5 = WORKDIR / "ascot.h5"
    if h5.exists():
        h5.unlink()
    a5 = Ascot(str(h5), create=True)

    a5.data.create_input("options tutorial")
    a5.data.create_input("bfield analytical iter circular")
    a5.data.create_input("wall rectangular")
    a5.data.create_input("plasma flat")
    a5.data.create_input("E_TC", exyz=np.array([0.0, 0.0, 0.0]))
    a5.data.create_input("N0_3D")
    a5.data.create_input("Boozer")
    a5.data.create_input("MHD_STAT")
    a5.data.create_input("asigma_loc")

    n = 40
    mrk = Marker.generate("gc", n=n, species="alpha")
    mrk["energy"][:] = 3.5e6
    rng = np.random.default_rng(42)
    mrk["pitch"][:] = 0.99 - 1.98 * rng.random(n)
    mrk["r"][:] = np.linspace(6.2, 8.2, n)
    a5.data.create_input("gc", **mrk)

    # Short orbit-following run; keep orbit write on, heavy dists off (tutorial
    # defaults enable multi-D distributions that balloon the HDF5 to hundreds of MB).
    name = a5.data.options.active.new(
        ENDCOND_MAX_MILEAGE=1.0e-2,
        ENABLE_ORBITWRITE=1,
        ORBITWRITE_MODE=1,
        ORBITWRITE_INTERVAL=1.0e-7,
        ORBITWRITE_NPOINT=1500,
        ENABLE_DIST_5D=0,
        ENABLE_DIST_6D=0,
        ENABLE_DIST_RHO5D=0,
        ENABLE_DIST_RHO6D=0,
        ENABLE_DIST_COM=0,
        desc="DemoFastOrbits",
    )
    a5.data.options[name].activate()
    print(f"  workspace → {h5}")
    print(f"  markers: {n} GC alphas @ 3.5 MeV")
    print(f"  options: {name}")
    return a5, h5


def section_plot_inputs(plt, a5, *, headless: bool) -> None:
    banner("2) Visualize magnetic field + wall inputs")
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), constrained_layout=True)
    try:
        a5.input_plotrz(axes[0], "bnorm")
        axes[0].set_title("|B| (analytical ITER circular)")
    except Exception as exc:
        axes[0].text(0.5, 0.5, f"B plot failed:\n{exc}", ha="center", va="center")
    try:
        a5.input_plotwallcontour(axes[1])
        axes[1].set_title("Wall contour")
    except Exception as exc:
        axes[1].text(0.5, 0.5, f"Wall plot failed:\n{exc}", ha="center", va="center")
    present(
        plt,
        fig,
        OUT / "inputs_bfield_wall.png",
        headless=headless,
        title="ASCOT5 B-field + wall",
    )


def section_run_binary(h5: Path) -> None:
    banner("3) Run ascot5_main (orbit-following)")
    cmd = [str(ASCOT_BIN), '--d="p11b ASCOT5 demo"']
    print("  $", " ".join(cmd))
    env = os.environ.copy()
    proc = subprocess.run(
        cmd,
        cwd=str(WORKDIR),
        env=env,
        capture_output=True,
        text=True,
    )
    log = OUT / "ascot5_main.log"
    log.write_text(proc.stdout + "\n" + proc.stderr)
    print(proc.stdout[-1500:] if len(proc.stdout) > 1500 else proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr)
        raise RuntimeError(f"ascot5_main failed with code {proc.returncode}")
    print(f"  log → {log}")


def section_endstates(plt, a5, *, headless: bool) -> dict:
    banner("4) Post-process endstates")
    run = a5.data.active
    r, z, ekin, endcond, weight = run.getstate(
        "r", "z", "ekin", "endcond", "weight", state="end"
    )
    unique, counts = np.unique(np.asarray(endcond), return_counts=True)
    print("  endcond value counts:")
    for u, c in zip(unique, counts):
        print(f"    {u}: {c}")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    axes[0].scatter(np.asarray(r), np.asarray(z), c=np.asarray(ekin) / 1e6, s=40, cmap="plasma")
    axes[0].set_xlabel("R [m]")
    axes[0].set_ylabel("Z [m]")
    axes[0].set_title("Endstate (R,Z) colored by E [MeV]")
    axes[0].set_aspect("equal", adjustable="datalim")
    axes[0].grid(True, alpha=0.3)

    axes[1].hist(np.asarray(ekin) / 1e6, bins=12, color="steelblue", edgecolor="k")
    axes[1].set_xlabel("Ekin [MeV]")
    axes[1].set_ylabel("markers")
    axes[1].set_title("Endstate energy spectrum")
    present(plt, fig, OUT / "endstates.png", headless=headless, title="Marker endstates")

    r0 = run.getstate("r", state="ini")
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    ax.scatter(np.asarray(r0), np.asarray(r), s=35, alpha=0.8)
    lims = [
        min(np.min(r0), np.min(r)),
        max(np.max(r0), np.max(r)),
    ]
    ax.plot(lims, lims, "k--", lw=1, alpha=0.5)
    ax.set_xlabel("R_ini [m]")
    ax.set_ylabel("R_end [m]")
    ax.set_title("Radial confinement proxy")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    present(
        plt,
        fig,
        OUT / "r_ini_vs_end.png",
        headless=headless,
        title="R_ini vs R_end",
    )

    return {
        "n_markers": int(len(r)),
        "endcond_values": {str(int(u)): int(c) for u, c in zip(unique, counts)},
        "ekin_mean_MeV": float(np.mean(ekin) / 1e6),
        "r_end_mean_m": float(np.mean(r)),
    }


def section_orbits(plt, a5, *, headless: bool) -> None:
    banner("5) Collected orbits (RZ trajectories)")
    run = a5.data.active
    try:
        orbit_q = run.getorbit_list()
        keys = list(orbit_q.keys()) if isinstance(orbit_q, dict) else list(orbit_q)
        print(f"  orbit quantities ({len(keys)}): {keys[:12]}...")
    except Exception as exc:
        print(f"  no orbit list: {exc}")

    fig, ax = plt.subplots(figsize=(6, 6))
    plotted = 0
    for mid in range(1, 9):
        try:
            r, z = run.getorbit("r", "z", ids=mid)
            ax.plot(np.asarray(r), np.asarray(z), lw=1.2, alpha=0.85, label=f"id={mid}")
            plotted += 1
        except Exception:
            continue
    if plotted:
        try:
            a5.input_plotwallcontour(ax)
        except Exception:
            pass
        ax.set_xlabel("R [m]")
        ax.set_ylabel("Z [m]")
        ax.set_title("Guiding-center α orbits")
        ax.set_aspect("equal", adjustable="datalim")
        ax.legend(fontsize=8, loc="best")
        ax.grid(True, alpha=0.3)
        present(
            plt,
            fig,
            OUT / "orbits_rz.png",
            headless=headless,
            title=f"α orbits ({plotted} markers)",
        )
    else:
        print("  no orbit data available")
        plt.close(fig)


def section_distributions(a5) -> None:
    banner("6) Distribution diagnostics (disabled in this demo for disk size)")
    run = a5.data.active
    dist_names, moments = run.getdist_list()
    print(f"  distributions present: {dist_names}")
    print(f"  moment types available when dists enabled: {[m[0] for m in moments]}")
    print("  Tip: set ENABLE_DIST_RHO5D=1 in options to collect ρ-space distributions.")


def section_live_api(a5) -> None:
    banner("7) Optional in-process simulation API probe")
    for name in (
        "simulation_initinputs",
        "simulation_initmarkers",
        "simulation_initoptions",
        "simulation_run",
        "simulation_free",
    ):
        print(f"  hasattr Ascot.{name}: {hasattr(a5, name)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_display_args(parser)
    args = parser.parse_args(argv)
    plt = configure_matplotlib(args.headless)

    banner("ASCOT5 comprehensive demo")
    print(
        f"  mode: {'headless' if args.headless else 'interactive (close each window to continue)'}"
    )
    prepare_env()
    try:
        from a5py import Ascot  # noqa: F401
    except ImportError:
        print("a5py not importable. Use demos/ascot5/run.sh")
        return 1

    a5, h5 = section_create_inputs()
    section_plot_inputs(plt, a5, headless=args.headless)
    section_run_binary(h5)
    from a5py import Ascot

    a5 = Ascot(str(h5))
    summary = section_endstates(plt, a5, headless=args.headless)
    section_orbits(plt, a5, headless=args.headless)
    section_distributions(a5)
    section_live_api(a5)

    report = {"summary": summary, "h5": str(h5)}
    (OUT / "summary.json").write_text(json.dumps(report, indent=2))

    banner("Done")
    print(f"  summary → {OUT / 'summary.json'}")
    print("  Key capabilities exercised:")
    print("    • Ascot HDF5 workspace + create_input templates")
    print("    • Analytical B-field, wall, plasma, markers")
    print("    • Options (mileage endcond + orbit write)")
    print("    • ascot5_main orbit-following")
    print("    • Endstate / orbit post-processing (interactive)")
    print("    • Input field visualization")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        traceback = __import__("traceback")
        traceback.print_exc()
        print("ERROR:", exc)
        sys.exit(1)
