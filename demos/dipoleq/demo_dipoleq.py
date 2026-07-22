#!/usr/bin/env python3
"""Comprehensive DipolEq demo — Grad–Shafranov equilibria for levitated dipoles.

Tours the Python API of https://github.com/dgarnier/dipoleq.

By default opens interactive plot windows (close each to continue).
Use ``--headless`` to only write PNGs under demos/output/dipoleq/.

Run::

    demos/dipoleq/run.sh
    demos/dipoleq/run.sh --headless
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "demos" / "scripts"))
from demo_display import add_display_args, configure_matplotlib, present  # noqa: E402

VENDOR = ROOT / "demos" / "vendor" / "dipoleq"
DATA = VENDOR / "python" / "tests" / "data"
TESTING = VENDOR / "Testing"
OUT = ROOT / "demos" / "output" / "dipoleq"


def banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def summarize(m, label: str) -> dict:
    pl = m.Plasma
    beta = np.asarray(pl.Beta_pr, dtype=float)
    beta_peak = float(np.nanmax(beta)) if beta.size and np.any(np.isfinite(beta)) else float("nan")
    summary = {
        "label": label,
        "Ip_A": float(pl.Ip),
        "diverted": bool(m.is_diverted()),
        "PsiLCFS": float(pl.PsiLCFS),
        "PsiFCFS": float(pl.PsiFCFS),
        "beta_peak": beta_peak,
        "n_coils": int(m.NumCoils),
    }
    try:
        m.get_plasma_parameters()
    except Exception:
        pass
    for key in ("RMagX", "ZMagX", "HalfWidth", "Elongation", "B0", "R0"):
        if hasattr(pl, key):
            try:
                summary[key] = float(getattr(pl, key))
            except Exception:
                pass
    return summary


def plot_profiles(plt, m, out_path: Path, title: str, *, headless: bool) -> None:
    pl = m.Plasma
    psi_norm = np.linspace(0.0, 1.0, len(pl.P_pr))
    fig, axes = plt.subplots(2, 2, figsize=(10, 8), constrained_layout=True)
    fig.suptitle(title)
    series = [
        (axes[0, 0], pl.P_pr, "Pressure P(ψ)", "Pa"),
        (axes[0, 1], pl.J_pr, "Toroidal current density J(ψ)", "A/m²"),
        (axes[1, 0], pl.Beta_pr, "β(ψ)", ""),
        (axes[1, 1], pl.q_pr, "Safety factor q(ψ)", ""),
    ]
    for ax, y, label, ylab in series:
        ax.plot(psi_norm, np.asarray(y), lw=2)
        ax.set_xlabel("ψ_norm (approx.)")
        ax.set_ylabel(ylab)
        ax.set_title(label)
        ax.grid(True, alpha=0.3)
    present(plt, fig, out_path, headless=headless, title=title)


def section_yaml_and_dotin() -> object:
    banner("1) Load beta1 from YAML and legacy .in — verify agreement")
    from dipoleq import Machine

    m_yaml = Machine.from_file(DATA / "beta1.yaml")
    m_in = Machine.from_file(DATA / "beta1.in")
    m_yaml.solve()
    m_in.solve()
    print(f"  YAML Ip = {m_yaml.Plasma.Ip:.4f} A")
    print(f"  .in  Ip = {m_in.Plasma.Ip:.4f} A")
    print(f"  |ΔIp| / Ip = {abs(m_yaml.Plasma.Ip - m_in.Plasma.Ip) / m_yaml.Plasma.Ip:.3e}")
    print(f"  diverted (yaml) = {m_yaml.is_diverted()}")
    return m_yaml


def section_plot_and_export(plt, m, *, headless: bool) -> dict:
    banner("2) Equilibrium plot, profiles, HDF5 + GEQDSK export")
    from dipoleq.h5togeqdsk import h5togeqdsk

    fig, ax = plt.subplots(figsize=(7, 7))
    m.plot_eq(ax=ax)
    ax.set_title("LDX β≈1 equilibrium (DipolEq)")
    present(
        plt,
        fig,
        OUT / "beta1_equilibrium.png",
        headless=headless,
        title="LDX β≈1 equilibrium",
    )

    plot_profiles(
        plt,
        m,
        OUT / "beta1_profiles.png",
        "LDX β≈1 flux-surface profiles",
        headless=headless,
    )

    h5_path = OUT / "beta1.h5"
    gfile = OUT / "beta1.geqdsk"
    m.to_hdf5(h5_path)
    m.to_geqdsk(gfile)
    gdata = h5togeqdsk(h5_path)
    print(f"  HDF5 → {h5_path}")
    print(f"  GEQDSK → {gfile}")
    print(f"  h5togeqdsk cpasma = {gdata['cpasma']:.4f} A")
    return summarize(m, "beta1")


def section_case_tour(plt, *, headless: bool) -> list[dict]:
    banner("3) Solve a gallery of LDX / dipole input decks")
    from dipoleq import Machine

    cases = [
        ("beta1", DATA / "beta1.yaml"),
        ("beta1_psinpeak", DATA / "beta1_psinpeak.in"),
        ("ldx4b", TESTING / "ldx4b.in"),
        ("beta1m", TESTING / "beta1m.in"),
    ]
    rows: list[dict] = []
    fig, axes = plt.subplots(2, 2, figsize=(10, 9), constrained_layout=True)
    axes = axes.ravel()
    for ax, (name, path) in zip(axes, cases):
        if not path.exists():
            ax.set_title(f"{name}: missing")
            ax.axis("off")
            continue
        try:
            m = Machine.from_file(path)
            m.solve()
            m.plot_eq(ax=ax)
            ax.set_title(f"{name}\nIp={m.Plasma.Ip/1e3:.1f} kA  div={m.is_diverted()}")
            row = summarize(m, name)
            rows.append(row)
            bp = row["beta_peak"]
            bp_s = f"{bp:.4f}" if np.isfinite(bp) else "n/a"
            print(
                f"  {name:16s}  Ip={row['Ip_A']:10.1f} A  "
                f"β_peak={bp_s}  diverted={row['diverted']}"
            )
        except Exception as exc:
            ax.set_title(f"{name}: FAILED")
            ax.text(0.5, 0.5, str(exc)[:80], ha="center", va="center", wrap=True)
            print(f"  {name}: FAILED — {exc}")
            traceback.print_exc()
    present(
        plt,
        fig,
        OUT / "equilibrium_gallery.png",
        headless=headless,
        title="LDX / dipole equilibrium gallery",
    )
    return rows


def section_psi_grid(m) -> None:
    banner("4) Inspect Ψ grid / limiter contact points")
    try:
        inner = m.get_inner_limiter_contact_point()
        outer = m.get_outer_limiter_contact_point()
        print(f"  inner limiter contact: {inner}")
        print(f"  outer limiter contact: {outer}")
    except Exception as exc:
        print(f"  limiter contacts unavailable: {exc}")
    try:
        xpts = m.get_x_points()
        print(f"  X-points: {xpts}")
    except Exception as exc:
        print(f"  X-points unavailable: {exc}")
    if hasattr(m, "PsiGrid"):
        pg = m.PsiGrid
        print(f"  PsiGrid attrs: {[a for a in dir(pg) if not a.startswith('_')][:25]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_display_args(parser)
    args = parser.parse_args(argv)
    plt = configure_matplotlib(args.headless)

    OUT.mkdir(parents=True, exist_ok=True)
    banner("DipolEq comprehensive demo")
    print(f"  vendor: {VENDOR}")
    print(f"  output: {OUT}")
    print(f"  mode: {'headless' if args.headless else 'interactive (close each window to continue)'}")

    try:
        from dipoleq import Machine  # noqa: F401
    except ImportError:
        print("dipoleq is not installed. From repo root:")
        print("  poetry run pip install dipoleq")
        return 1

    m = section_yaml_and_dotin()
    summary = section_plot_and_export(plt, m, headless=args.headless)
    rows = section_case_tour(plt, headless=args.headless)
    section_psi_grid(m)

    report = {"primary": summary, "gallery": rows}
    report_path = OUT / "summary.json"
    report_path.write_text(json.dumps(report, indent=2))
    banner("Done")
    print(f"  summary → {report_path}")
    print("  Key capabilities exercised:")
    print("    • Machine.from_file (YAML + .in)")
    print("    • Grad–Shafranov solve (Machine.solve)")
    print("    • plot_eq / plasma profiles (interactive)")
    print("    • to_hdf5 / to_geqdsk / h5togeqdsk")
    print("    • diverted vs limited topology flags")
    print("    • multi-case LDX gallery")
    return 0


if __name__ == "__main__":
    sys.exit(main())
