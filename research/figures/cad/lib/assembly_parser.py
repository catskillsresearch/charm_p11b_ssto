# SPDX-License-Identifier: Apache-2.0
"""assembly.json loading and node lookup — the SSOT for every CAD figure build."""

from __future__ import annotations

import json
from pathlib import Path


def load_assembly(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def find_node(root: dict, node_id: str) -> dict | None:
    """Depth-first search for a node by id under `root` (a single node dict)."""
    if root.get("id") == node_id:
        return root
    for child in root.get("children") or []:
        hit = find_node(child, node_id)
        if hit:
            return hit
    return None


def find_node_in_doc(doc: dict, node_id: str) -> dict | None:
    """Convenience: pass the full parsed assembly.json (with its top-level "root")."""
    root = doc["root"] if "root" in doc else doc
    return find_node(root, node_id)


def envelope_of(node: dict) -> tuple[float, float, float]:
    """Return (x0, x1, width_m) from a node's envelope."""
    env = node["envelope"]
    return float(env["x0"]), float(env["x1"]), float(env["width_m"])


def port_xyz(node: dict, port_id: str) -> tuple[float, float, float] | None:
    """Look up a port's xyz on a node by port id, if present."""
    for p in node.get("ports") or []:
        if p.get("id") == port_id and "xyz" in p:
            xyz = p["xyz"]
            return float(xyz[0]), float(xyz[1]), float(xyz[2])
    return None


def port_normal(node: dict, port_id: str) -> tuple[float, float, float] | None:
    """Look up a port's outward normal by port id, if present."""
    for p in node.get("ports") or []:
        if p.get("id") == port_id and "normal" in p:
            n = p["normal"]
            return float(n[0]), float(n[1]), float(n[2])
    return None
