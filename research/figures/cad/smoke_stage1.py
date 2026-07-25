#!/usr/bin/env python3
"""Stage 1 smoke test — VSPAERO outline go/no-go (§10.2.1).

Reads ``vspaero/summary.json`` (from ``make cad-vspaero``) and checks the
Stage 1 pass criteria. Does not re-run the tunnel unless ``--rerun``.

Exit 0 = Stage 1 outline PASS (or soft-pass only on CD floor).
Exit 1 = FAIL / missing artifacts.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

CAD_DIR = Path(__file__).resolve().parent
ROOT = CAD_DIR.parents[2]
SUMMARY = CAD_DIR / "vspaero" / "summary.json"
PAPER_S_M2 = 229.0
TRANS_MACH = 0.8
TRANS_CD_LO, TRANS_CD_HI = 0.05, 0.20  # order-of-magnitude vs frozen ~0.09
SUB_MACH = 0.3
SUB_CD_MAX = 0.06  # soft: VLM under-counts parasite vs frozen 0.045


def _cd_at(summary: dict, mach: float, alpha: float = 0.0) -> float | None:
    for r in summary.get("rows", []):
        if math.isclose(r["Mach"], mach, abs_tol=1e-6) and math.isclose(
            r["Alpha_deg"], alpha, abs_tol=1e-6
        ):
            return float(r["CD"])
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--rerun",
        action="store_true",
        help="run make cad-vspaero before checking",
    )
    args = ap.parse_args()

    if args.rerun:
        print("==> re-running make cad-vspaero")
        rc = subprocess.call(["make", "cad-vspaero"], cwd=ROOT)
        if rc != 0:
            print("FAIL: cad-vspaero exited", rc)
            return 1

    if not SUMMARY.is_file():
        print(f"FAIL: missing {SUMMARY.relative_to(ROOT)}")
        print("  run: make cad-vspaero")
        return 1

    summary = json.loads(SUMMARY.read_text())
    rows = summary.get("rows") or []
    checks: list[tuple[str, bool, str]] = []

    ok_n = len(rows) >= 8
    checks.append(("polar written", ok_n, f"{len(rows)} cases"))

    # Sref from best_L_D / cd rows is not stored; cross-check wing area helper.
    sys.path.insert(0, str(CAD_DIR))
    from constants_model import wing_reference_area_m2

    sref = wing_reference_area_m2()
    ok_s = abs(sref - PAPER_S_M2) / PAPER_S_M2 < 0.02
    checks.append(("S_ref ~ 229 m^2", ok_s, f"{sref:.1f} m^2"))

    cd_trans = _cd_at(summary, TRANS_MACH, 0.0)
    ok_trans = cd_trans is not None and TRANS_CD_LO <= cd_trans <= TRANS_CD_HI
    checks.append(
        (
            "transonic CD peak (M=0.8, α=0)",
            ok_trans,
            f"CD={cd_trans:.3f}" if cd_trans is not None else "missing",
        )
    )

    cd_sub = _cd_at(summary, SUB_MACH, 0.0)
    ok_sub = cd_sub is not None and 0.0 < cd_sub <= SUB_CD_MAX
    checks.append(
        (
            "subsonic CD floor soft (M=0.3, α=0)",
            ok_sub,
            f"CD={cd_sub:.3f}" if cd_sub is not None else "missing",
        )
    )

    best = summary.get("best_L_D") or {}
    ok_ld = float(best.get("L_D", 0.0)) > 5.0
    checks.append(
        (
            "best L/D > 5",
            ok_ld,
            f"L/D={best.get('L_D', 0):.1f} at M={best.get('Mach')}, α={best.get('Alpha_deg')}°",
        )
    )

    print("Stage 1 smoke (VSPAERO outline / §10.2.1)")
    hard_fail = False
    for name, ok, note in checks:
        mark = "PASS" if ok else "FAIL"
        # subsonic floor is soft in the paper — warn but don't fail the smoke
        if name.startswith("subsonic") and not ok:
            mark = "SOFT-FAIL"
        elif name.startswith("subsonic"):
            mark = "SOFT-PASS"
        print(f"  [{mark}] {name}: {note}")
        if not ok and not name.startswith("subsonic"):
            hard_fail = True

    if hard_fail:
        print("VERDICT: Stage 1 FAIL")
        return 1
    print("VERDICT: Stage 1 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
