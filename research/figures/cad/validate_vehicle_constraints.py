#!/usr/bin/env python3
"""Validate OpenVSP model against vehicle_spec.json spatial constraints.

Run after build (also invoked from build_ssto_openvsp.py):

    poetry run python research/figures/cad/validate_vehicle_constraints.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

CAD_DIR = Path(__file__).resolve().parent
SPEC_PATH = CAD_DIR / "vehicle_spec.json"
VSP3_PATH = CAD_DIR / "catskills_ssto.vsp3"


def _ensure_openvsp_libs() -> None:
    root = CAD_DIR.parents[2]
    lib = root / "third_party/openvsp/sysdeps/usr/lib/x86_64-linux-gnu"
    if lib.is_dir():
        cur = os.environ.get("LD_LIBRARY_PATH", "")
        prefix = str(lib)
        if prefix not in cur.split(":"):
            os.environ["LD_LIBRARY_PATH"] = f"{prefix}:{cur}" if cur else prefix


def _find_geom(vsp, name: str) -> str | None:
    for gid in vsp.FindGeoms():
        if vsp.GetGeomName(gid) == name:
            return gid
    return None


def _parent_name(vsp, gid: str) -> str | None:
    pid = vsp.GetGeomParent(gid)
    if not pid:
        return None
    return vsp.GetGeomName(pid)


def _xform(vsp, gid: str, parm: str) -> float:
    return float(vsp.GetParmVal(gid, parm, "XForm"))


def _check_bounds(val: float, spec: dict[str, float], label: str) -> str | None:
    if "min" in spec and val < float(spec["min"]) - 1e-9:
        return f"{label}={val:.4g} < min {spec['min']}"
    if "max" in spec and val > float(spec["max"]) + 1e-9:
        return f"{label}={val:.4g} > max {spec['max']}"
    return None


def validate(spec: dict[str, Any], vsp3: Path = VSP3_PATH) -> list[str]:
    import openvsp as vsp

    err_mgr = vsp.ErrorMgrSingleton.getInstance()
    while err_mgr.GetNumTotalErrors():
        err_mgr.PopLastError()

    vsp.ClearVSPModel()
    vsp.ReadVSPFile(str(vsp3))
    vsp.Update()

    failures: list[str] = []
    for c in spec.get("constraints", []):
        cid = c.get("id", "?")
        ctype = c["type"]
        try:
            if ctype == "geom_exists":
                if _find_geom(vsp, c["geom"]) is None:
                    failures.append(f"{cid}: missing geom {c['geom']}")

            elif ctype == "parent":
                child = _find_geom(vsp, c["child"])
                if child is None:
                    failures.append(f"{cid}: missing child {c['child']}")
                    continue
                got = _parent_name(vsp, child)
                if got != c["parent"]:
                    failures.append(f"{cid}: parent of {c['child']} is {got!r}, want {c['parent']!r}")

            elif ctype == "xform_bounds":
                gid = _find_geom(vsp, c["geom"])
                if gid is None:
                    failures.append(f"{cid}: missing geom {c['geom']}")
                    continue
                mapping = {
                    "X_Rel_Location_m": "X_Rel_Location",
                    "Y_Rel_Location_m": "Y_Rel_Location",
                    "Z_Rel_Location_m": "Z_Rel_Location",
                    "X_Rel_Rotation_deg": "X_Rel_Rotation",
                    "Y_Rel_Rotation_deg": "Y_Rel_Rotation",
                    "Z_Rel_Rotation_deg": "Z_Rel_Rotation",
                }
                for key, parm in mapping.items():
                    if key not in c:
                        continue
                    msg = _check_bounds(_xform(vsp, gid, parm), c[key], f"{c['geom']}.{parm}")
                    if msg:
                        failures.append(f"{cid}: {msg}")

            elif ctype == "parm_bounds":
                gid = _find_geom(vsp, c["geom"])
                if gid is None:
                    failures.append(f"{cid}: missing geom {c['geom']}")
                    continue
                for p in c.get("parms", []):
                    val = float(vsp.GetParmVal(gid, p["name"], p["group"]))
                    msg = _check_bounds(val, p, f"{c['geom']}.{p['group']}.{p['name']}")
                    if msg:
                        failures.append(f"{cid}: {msg}")

            elif ctype == "forbid_xform":
                gid = _find_geom(vsp, c["geom"])
                if gid is None:
                    failures.append(f"{cid}: missing geom {c['geom']}")
                    continue
                if "X_Rel_Rotation_deg_near" in c:
                    near = c["X_Rel_Rotation_deg_near"]
                    val = _xform(vsp, gid, "X_Rel_Rotation")
                    if abs(val - float(near["value"])) <= float(near["tol"]):
                        failures.append(
                            f"{cid}: {c['geom']} X_Rel_Rotation={val:.3g}≈{near['value']} (forbidden)"
                        )

            else:
                failures.append(f"{cid}: unknown constraint type {ctype!r}")
        except Exception as exc:  # noqa: BLE001 — surface as constraint failure
            failures.append(f"{cid}: exception {exc}")

        while err_mgr.GetNumTotalErrors():
            err_mgr.PopLastError()

    return failures


def main() -> int:
    if os.environ.get("_OPENVSP_REEXEC") != "1":
        _ensure_openvsp_libs()
        os.environ["_OPENVSP_REEXEC"] = "1"
        os.execv(sys.executable, [sys.executable, *sys.argv])

    if not VSP3_PATH.is_file():
        print(f"Missing {VSP3_PATH}; run make cad-figures first", file=sys.stderr)
        return 2

    spec = json.loads(SPEC_PATH.read_text())
    failures = validate(spec)
    if failures:
        print(f"FAIL: {len(failures)} constraint(s) violated")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"OK: {len(spec.get('constraints', []))} constraints satisfied ({VSP3_PATH.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
