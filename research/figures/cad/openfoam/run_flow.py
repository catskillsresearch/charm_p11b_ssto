#!/usr/bin/env python3
"""Mesh (if needed) + simpleFoam + wing-streamline render."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE / "ssto_snappy"
ROOT = HERE.parents[3]


def main() -> int:
    if not (CASE / "constant" / "polyMesh" / "points").is_file() or "--remesh" in sys.argv:
        rc = subprocess.call([sys.executable, str(HERE / "run_snappy.py")], cwd=ROOT)
        if rc != 0:
            return rc

    env = os.environ.copy()
    env.setdefault("WM_PROJECT_DIR", "/usr/share/openfoam")
    env.setdefault("FOAM_ETC", "/usr/share/openfoam/etc")
    print("==> Allrun.flow")
    rc = subprocess.call(["bash", str(CASE / "Allrun.flow")], cwd=CASE, env=env)
    if rc != 0:
        return rc
    return subprocess.call([sys.executable, str(HERE / "render_wing_flow.py")], cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
