#!/usr/bin/env python3
"""Build a flight-config STL for snappy: clean cruise OML only.

Paper profile figures keep gear, OMS pods, and the body flap. The exterior
aero mesh keeps the body flap (it now overlaps the aft belly, so snappy
reads it as a proper protruding surface) but still drops gear stubs, the
free-floating OMS/RCS pods, and hatch nubs — those OpenVSP placeholders
never touch the OML and snappyHexMesh turns the thin/soft ones into
corn-chip artifacts at the tail.
"""

from __future__ import annotations

import sys
from pathlib import Path

import trimesh

CAD = Path(__file__).resolve().parents[1]
SRC = CAD / "catskills_ssto.stl"
OUT = Path(__file__).resolve().parent / "ssto_snappy" / "constant" / "triSurface" / "catskills_ssto.stl"


def _is_gear_stub(p: trimesh.Trimesh) -> bool:
    b = p.bounds
    return len(p.faces) <= 400 and float(b[1, 2]) < -3.6


def _is_oms_pod(p: trimesh.Trimesh) -> bool:
    """Shuttle OMS/RCS fairing pods — look like Frito H-stabs under snappy."""
    b = p.bounds
    dx = float(b[1, 0] - b[0, 0])
    dy = float(b[1, 1] - b[0, 1])
    dz = float(b[1, 2] - b[0, 2])
    y_clear = abs(float(b[0, 1])) >= 1.0 or abs(float(b[1, 1])) >= 1.0
    return (
        40.0 <= float(b[0, 0]) <= 46.0
        and dx <= 8.0
        and 1.5 <= dy <= 4.0
        and dz <= 4.0
        and y_clear
        and len(p.faces) <= 400
    )


def _is_hatch_nub(p: trimesh.Trimesh) -> bool:
    """Tiny crew/airlock hatch markers — noise on the aero wall."""
    b = p.bounds
    dx = float(b[1, 0] - b[0, 0])
    dy = float(b[1, 1] - b[0, 1])
    dz = float(b[1, 2] - b[0, 2])
    return len(p.faces) <= 400 and dx <= 2.0 and dy <= 1.5 and dz <= 1.5 and float(b[1, 0]) < 20.0


def main() -> int:
    if not SRC.is_file():
        print(f"Missing {SRC}; run make cad-figures", file=sys.stderr)
        return 1
    m = trimesh.load(SRC, force="mesh")
    parts = m.split(only_watertight=False)
    keep = []
    counts = {"gear": 0, "oms": 0, "hatch": 0}
    for p in parts:
        if _is_gear_stub(p):
            counts["gear"] += 1
            continue
        if _is_oms_pod(p):
            counts["oms"] += 1
            continue
        if _is_hatch_nub(p):
            counts["hatch"] += 1
            continue
        keep.append(p)
    if not keep:
        print("Refused to drop everything", file=sys.stderr)
        return 1
    out_mesh = trimesh.util.concatenate(keep)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out_mesh.export(OUT)
    dropped = ", ".join(f"{v} {k}" for k, v in counts.items() if v)
    print(
        f"wrote {OUT.relative_to(CAD.parents[2])}  "
        f"bodies {len(parts)}→{len(keep)} (dropped {dropped or 'none'})  "
        f"faces={len(out_mesh.faces)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
