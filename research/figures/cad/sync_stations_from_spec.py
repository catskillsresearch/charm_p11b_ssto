#!/usr/bin/env python3
"""Sync legacy stations.json from vehicle_spec.json (paper-derived CAD truth)."""

from __future__ import annotations

import json
from pathlib import Path

CAD = Path(__file__).resolve().parent
SPEC = CAD / "vehicle_spec.json"
STATIONS = CAD / "stations.json"


def main() -> None:
    spec = json.loads(SPEC.read_text())
    oml = spec["oml"]
    cargo = next(s for s in spec["stations_m"] if s["id"] == "cargo")
    out = {
        "name": spec["meta"]["name"],
        "length_m": oml["length_m"],
        "fuselage_width_m": oml["fuselage_width_m"],
        "fuselage_height_m": oml["fuselage_height_m"],
        "bay_width_m": cargo["bay_width_m"],
        "bay_height_m": cargo["bay_height_m"],
        "wingspan_m": oml["wingspan_m"],
        "stations": [
            {
                "id": s["id"],
                "x0": s["x0"],
                "x1": s["x1"],
                "label": s["label"],
                "color": s["color"],
            }
            for s in spec["stations_m"]
        ],
    }
    STATIONS.write_text(json.dumps(out, indent=2) + "\n")
    print(f"Wrote {STATIONS} from {SPEC}")


if __name__ == "__main__":
    main()
