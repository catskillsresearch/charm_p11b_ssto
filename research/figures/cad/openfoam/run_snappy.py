#!/usr/bin/env python3
"""Run OpenFOAM snappyHexMesh on catskills_ssto.stl (host OpenFOAM, not Poetry).

Stops with a clear message if OpenFOAM is not installed / not sourced.
"""

from __future__ import annotations

import glob
import os
import subprocess
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parent / "ssto_snappy"
ROOT = Path(__file__).resolve().parents[4]


def main() -> int:
    if not (CASE / "Allrun").is_file():
        print(f"Missing case Allrun under {CASE}", file=sys.stderr)
        return 1

    stl = ROOT / "research/figures/cad/catskills_ssto.stl"
    if not stl.is_file():
        print(f"Missing {stl}; run make cad-figures", file=sys.stderr)
        return 1

    # Ubuntu's openfoam package puts apps on PATH via /usr/bin. Prefer that
    # over sourcing /usr/share/openfoam/etc/bashrc (broken foamEtcFile links).
    if subprocess.call(["bash", "-lc", "command -v snappyHexMesh >/dev/null"]) != 0:
        print("OpenFOAM / snappyHexMesh is not installed on this host.", file=sys.stderr)
        print("", file=sys.stderr)
        print("This is a host CFD toolbox (like Blender/OpenVSP), not a Poetry package.", file=sys.stderr)
        print("Need sudo to install — please run:", file=sys.stderr)
        print("  sudo apt-get install -y openfoam", file=sys.stderr)
        print("then re-run: make cad-snappy", file=sys.stderr)
        print("Docs: research/figures/cad/openfoam/README.md", file=sys.stderr)
        return 2

    # Wipe a previous failed/partial mesh so -overwrite is clean.
    clean = CASE / "Allclean"
    if clean.is_file():
        subprocess.call(["bash", str(clean)], cwd=CASE)

    env = os.environ.copy()
    # Help #includeEtc if any dict uses it (Ubuntu layout).
    env.setdefault("WM_PROJECT_DIR", "/usr/share/openfoam")
    env.setdefault("FOAM_ETC", "/usr/share/openfoam/etc")
    print(f"==> {CASE}/Allrun")
    return subprocess.call(["bash", str(CASE / "Allrun")], cwd=CASE, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
