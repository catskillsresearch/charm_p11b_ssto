#!/usr/bin/env python3
"""Digital wind-tunnel: VSPAERO Mach×α sweep on catskills_ssto.vsp3.

Uses the OpenVSP Python API + the VSPAERO solver that ships with the vendored
OpenVSP .deb (NOSA 1.3). Geometry is the living ``catskills_ssto.vsp3`` from
``make cad-figures``. Landing gear pods are excluded from the aero set.

    make install-openvsp   # once
    make cad-figures       # ensure .vsp3 exists
    make cad-vspaero

Outputs (under research/figures/cad/vspaero/):
  summary.json   — machine-readable polar + run metadata
  polar.csv      — Mach, Alpha, CL, CD, L/D, …
  polar.png      — CL/CD and L/D overview plot
  run/           — raw VSPAERO working files (gitignored)
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Unbuffered status lines when make/poetry pipes stdout.
try:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
except Exception:
    pass

import matplotlib.pyplot as plt
import numpy as np

CAD_DIR = Path(__file__).resolve().parent
ROOT = CAD_DIR.parents[2]
VSP3_SRC = CAD_DIR / "catskills_ssto.vsp3"
OPENVSP_ROOT = ROOT / "third_party/openvsp/opt/OpenVSP"
OPENVSP_LIB = ROOT / "third_party/openvsp/sysdeps/usr/lib/x86_64-linux-gnu"
OUT_DIR = CAD_DIR / "vspaero"
RUN_DIR = OUT_DIR / "run"

# Steady VLM polar matrix. VSPAERO is potential-flow / vortex-lattice — useful
# for subsonic–transonic planform sanity, not a hypersonic CFD substitute.
# Mach ≥ ~1.2 on this full airframe stalled for >15 min/case in practice, so
# the default tunnel stays in the regime where the solver converges quickly.
MACH_LIST = [0.3, 0.6, 0.8, 0.95]
ALPHA_LIST = [0.0, 4.0, 8.0]

EXCLUDE_FROM_AERO = {
    "NOSE_GEAR",
    "MAIN_GEAR_L",
    "MAIN_GEAR_R",
}


def _ensure_openvsp_libs() -> None:
    if OPENVSP_LIB.is_dir():
        cur = os.environ.get("LD_LIBRARY_PATH", "")
        prefix = str(OPENVSP_LIB)
        if prefix not in cur.split(":"):
            os.environ["LD_LIBRARY_PATH"] = f"{prefix}:{cur}" if cur else prefix


def _parse_polar(path: Path) -> list[dict[str, float]]:
    """Parse VSPAERO ``.polar`` into one row per (Mach, AoA)."""
    text = path.read_text(errors="replace")
    rows: list[dict[str, float]] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 14:
            continue
        try:
            beta = float(parts[0])
            mach = float(parts[1])
            aoa = float(parts[2])
        except ValueError:
            continue
        # Header / banner lines won't parse as three floats in that pattern
        # with a plausible Mach/AoA; also skip wake-iter junk if any.
        if not (0.0 <= mach <= 30.0 and -90.0 <= aoa <= 90.0 and abs(beta) <= 90.0):
            continue
        rows.append(
            {
                "Beta": beta,
                "Mach": mach,
                "Alpha_deg": aoa,
                "Re_1e6": float(parts[3]),
                "CL": float(parts[6]),  # CLtot
                "CD": float(parts[9]),  # CDtot
                "CDo": float(parts[7]),
                "CDi": float(parts[8]),
                "L_D": float(parts[13]),
                "E": float(parts[14]),
                "CMy": float(parts[21]),  # CMytot
            }
        )
    # Deduplicate identical (M,α) keeping last (solver final).
    uniq: dict[tuple[float, float], dict[str, float]] = {}
    for r in rows:
        uniq[(round(r["Mach"], 6), round(r["Alpha_deg"], 6))] = r
    return [uniq[k] for k in sorted(uniq)]


def _write_plot(rows: list[dict[str, float]], out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2), dpi=140)
    fig.patch.set_facecolor("#f7f7f7")
    machs = sorted({r["Mach"] for r in rows})
    cmap = plt.cm.viridis(np.linspace(0.1, 0.9, len(machs)))
    for ax in axes:
        ax.set_facecolor("#ffffff")
        ax.grid(True, alpha=0.35, lw=0.6)

    for color, mach in zip(cmap, machs):
        pts = [r for r in rows if r["Mach"] == mach]
        pts.sort(key=lambda r: r["Alpha_deg"])
        a = [r["Alpha_deg"] for r in pts]
        axes[0].plot(a, [r["CL"] for r in pts], "o-", color=color, label=f"M={mach:g}", lw=1.4, ms=5)
        axes[0].plot(a, [r["CD"] for r in pts], "s--", color=color, alpha=0.75, lw=1.1, ms=4)
        axes[1].plot(a, [r["L_D"] for r in pts], "o-", color=color, label=f"M={mach:g}", lw=1.4, ms=5)

    axes[0].set_xlabel("α (deg)")
    axes[0].set_ylabel("CL (solid) / CD (dashed)")
    axes[0].set_title("VSPAERO forces vs α")
    axes[0].legend(fontsize=8, loc="best")
    axes[1].set_xlabel("α (deg)")
    axes[1].set_ylabel("L/D")
    axes[1].set_title("Lift-to-drag vs α")
    axes[1].legend(fontsize=8, loc="best")
    fig.suptitle("CATSKILLS-SSTO · OpenVSP/VSPAERO digital tunnel (gear retracted)", fontsize=11)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def _delete_gear(vsp) -> list[str]:
    """Remove landing-gear pods from the working copy (cleaner wake / drag)."""
    removed: list[str] = []
    for name in sorted(EXCLUDE_FROM_AERO):
        for gid in list(vsp.FindGeomsWithName(name)):
            vsp.DeleteGeom(gid)
            removed.append(name)
    vsp.Update()
    return removed


def run() -> int:
    if os.environ.get("_OPENVSP_REEXEC") != "1":
        _ensure_openvsp_libs()
        os.environ["_OPENVSP_REEXEC"] = "1"
        os.execv(sys.executable, [sys.executable, *sys.argv])

    if not VSP3_SRC.is_file():
        print(f"Missing {VSP3_SRC}; run: make cad-figures", file=sys.stderr)
        return 1
    if not OPENVSP_ROOT.is_dir():
        print(f"Missing {OPENVSP_ROOT}; run: make install-openvsp", file=sys.stderr)
        return 1

    import openvsp as vsp

    if RUN_DIR.exists():
        shutil.rmtree(RUN_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    work_vsp3 = RUN_DIR / "catskills_ssto.vsp3"
    shutil.copy2(VSP3_SRC, work_vsp3)

    # VSPAERO writes next to the .vsp3 / cwd — keep the repo root clean.
    os.chdir(RUN_DIR)

    vsp.ClearVSPModel()
    if not vsp.SetVSPAEROPath(str(OPENVSP_ROOT)):
        print("SetVSPAEROPath failed", file=sys.stderr)
        return 1
    if not vsp.CheckForVSPAERO(str(OPENVSP_ROOT)):
        print(f"VSPAERO binaries not found under {OPENVSP_ROOT}", file=sys.stderr)
        return 1

    vsp.ReadVSPFile(str(work_vsp3))
    vsp.Update()
    removed = _delete_gear(vsp)
    vsp.WriteVSPFile(str(work_vsp3), vsp.SET_ALL)
    vsp.ClearVSPModel()
    vsp.ReadVSPFile(str(work_vsp3))
    vsp.Update()

    n_cpu = max(1, min(8, os.cpu_count() or 4))
    print(f"VSPAERO digital tunnel: Mach={MACH_LIST}, Alpha={ALPHA_LIST}, NCPU={n_cpu}")
    print(f"  model: {VSP3_SRC}")
    print(f"  deleted gear pods: {removed}")

    # Default VSPAEROComputeGeometry builds a thin-surface (VLM) DegenGeom —
    # same path as OpenVSP's TestAnalysisVSPAERO.vspscript. Custom GeomSets
    # previously flipped this model into a broken PANEL mesh; keep defaults.
    comp = "VSPAEROComputeGeometry"
    vsp.SetAnalysisInputDefaults(comp)
    print("  ExecAnalysis VSPAEROComputeGeometry …")
    vsp.ExecAnalysis(comp)

    # Discrete Mach list: one Alpha sweep per Mach (MachStart/End/Npts only
    # does linear spacing, which is not what we want for the paper table).
    all_rows: list[dict[str, float]] = []
    for mach in MACH_LIST:
        analysis = "VSPAEROSweep"
        vsp.SetAnalysisInputDefaults(analysis)
        vsp.SetIntAnalysisInput(analysis, "NCPU", [n_cpu])
        vsp.SetIntAnalysisInput(analysis, "RefFlag", [1])  # component = MAIN_WING
        wid = vsp.FindGeomsWithName("MAIN_WING")
        if not wid:
            print("MAIN_WING not found in model", file=sys.stderr)
            return 1
        vsp.SetStringAnalysisInput(analysis, "WingID", wid)
        vsp.SetDoubleAnalysisInput(analysis, "AlphaStart", [float(ALPHA_LIST[0])])
        vsp.SetDoubleAnalysisInput(analysis, "AlphaEnd", [float(ALPHA_LIST[-1])])
        vsp.SetIntAnalysisInput(analysis, "AlphaNpts", [len(ALPHA_LIST)])
        vsp.SetDoubleAnalysisInput(analysis, "MachStart", [float(mach)])
        vsp.SetIntAnalysisInput(analysis, "MachNpts", [1])
        vsp.Update()
        print(f"  ExecAnalysis VSPAEROSweep  Mach={mach:g} …")
        vsp.ExecAnalysis(analysis)
        polar_path = RUN_DIR / "catskills_ssto.polar"
        if not polar_path.is_file():
            cands = sorted(RUN_DIR.glob("*.polar"))
            if not cands:
                print(f"No .polar written for Mach={mach:g}", file=sys.stderr)
                return 1
            polar_path = cands[-1]
        chunk = _parse_polar(polar_path)
        if not chunk:
            print(f"Failed to parse {polar_path}", file=sys.stderr)
            return 1
        all_rows.extend(chunk)

    # Stable unique (M,α) order.
    uniq: dict[tuple[float, float], dict[str, float]] = {}
    for r in all_rows:
        uniq[(round(r["Mach"], 6), round(r["Alpha_deg"], 6))] = r
    rows = [uniq[k] for k in sorted(uniq)]
    polar_path = RUN_DIR / "catskills_ssto.polar"

    csv_path = OUT_DIR / "polar.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["Mach", "Alpha_deg", "CL", "CD", "CDo", "CDi", "L_D", "E", "CMy", "Re_1e6"],
        )
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in w.fieldnames})

    plot_path = OUT_DIR / "polar.png"
    _write_plot(rows, plot_path)

    # Paper-facing highlights: CD at α≈0 vs Mach (parasite-ish), and best L/D.
    cd_alpha0 = [
        {"Mach": r["Mach"], "CD": r["CD"], "CL": r["CL"]}
        for r in rows
        if abs(r["Alpha_deg"]) < 1e-6
    ]
    best = max(rows, key=lambda r: r["L_D"])
    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "model": str(VSP3_SRC.relative_to(ROOT)),
        "solver": "VSPAERO (OpenVSP bundled)",
        "method": "vortex lattice / thin surface (VSPAEROComputeGeometry + VSPAEROSweep)",
        "exclusions": removed,
        "Sref_note": "Reference area from MAIN_WING (OpenVSP RefFlag=component); ~229 m²",
        "limits": (
            "Potential-flow VLM — good for subsonic/transonic planform trends; "
            "not a substitute for hypersonic CFD or stage-2/3 propulsion aero."
        ),
        "mach_list": MACH_LIST,
        "alpha_list_deg": ALPHA_LIST,
        "n_cases": len(rows),
        "cd_at_alpha_0": cd_alpha0,
        "best_L_D": {
            "Mach": best["Mach"],
            "Alpha_deg": best["Alpha_deg"],
            "L_D": best["L_D"],
            "CL": best["CL"],
            "CD": best["CD"],
        },
        "rows": rows,
        "artifacts": {
            "polar_csv": str(csv_path.relative_to(ROOT)),
            "polar_png": str(plot_path.relative_to(ROOT)),
            "raw_polar": str(polar_path.relative_to(ROOT)),
        },
    }
    summary_path = OUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")

    print(f"Wrote {summary_path.relative_to(ROOT)} ({len(rows)} cases)")
    print(f"Wrote {csv_path.relative_to(ROOT)}")
    print(f"Wrote {plot_path.relative_to(ROOT)}")
    print("CD(α=0) vs Mach:")
    for r in cd_alpha0:
        print(f"  M={r['Mach']:g}  CD={r['CD']:.4f}  CL={r['CL']:.4f}")
    print(
        f"Best L/D={best['L_D']:.2f} at M={best['Mach']:g}, α={best['Alpha_deg']:g}° "
        f"(CL={best['CL']:.3f}, CD={best['CD']:.4f})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
