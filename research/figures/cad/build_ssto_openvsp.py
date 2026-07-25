#!/usr/bin/env python3
"""Build CATSKILLS-SSTO in OpenVSP from vehicle_spec.json (paper-derived).

Rule: each enabled entry in vehicle_spec.parts[] becomes OpenVSP geometry.
Finer paper requirements → denser parts / loft → finer model.

    make install-openvsp   # once
    make cad-figures

Outputs:
  research/figures/cad/catskills_ssto.vsp3
  research/figures/charm_ssto_interior_floorplan.png
  research/figures/charm_ssto_exterior_profile.png
"""

from __future__ import annotations

import json
import math
import os
import struct
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon, Rectangle

CAD_DIR = Path(__file__).resolve().parent
FIGURES_DIR = CAD_DIR.parent
SPEC_PATH = CAD_DIR / "vehicle_spec.json"
STATIONS_PATH = CAD_DIR / "stations.json"
VSP3_OUT = CAD_DIR / "catskills_ssto.vsp3"
STL_OUT = CAD_DIR / "catskills_ssto.stl"
FLOORPLAN_OUT = FIGURES_DIR / "charm_ssto_interior_floorplan.png"
PROFILE_OUT = FIGURES_DIR / "charm_ssto_exterior_profile.png"


def _ensure_openvsp_libs() -> None:
    root = CAD_DIR.parents[2]
    lib = root / "third_party/openvsp/sysdeps/usr/lib/x86_64-linux-gnu"
    if lib.is_dir():
        cur = os.environ.get("LD_LIBRARY_PATH", "")
        prefix = str(lib)
        if prefix not in cur.split(":"):
            os.environ["LD_LIBRARY_PATH"] = f"{prefix}:{cur}" if cur else prefix


def load_spec(path: Path = SPEC_PATH) -> dict[str, Any]:
    return json.loads(path.read_text())


def sync_stations(spec: dict[str, Any]) -> dict[str, Any]:
    """Write slim stations.json and return the figure-facing station view."""
    oml = spec["oml"]
    cargo = next(s for s in spec["stations_m"] if s["id"] == "cargo")
    slim = {
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
    STATIONS_PATH.write_text(json.dumps(slim, indent=2) + "\n")
    return slim


def _station(spec: dict[str, Any], sid: str) -> dict[str, Any]:
    return next(s for s in spec["stations_m"] if s["id"] == sid)


def _part(spec: dict[str, Any], pid: str) -> dict[str, Any] | None:
    for p in spec["parts"]:
        if p["id"] == pid:
            return p
    return None


def _clear_errors(vsp) -> None:
    err = vsp.ErrorMgrSingleton.getInstance()
    while err.GetNumTotalErrors():
        err.PopLastError()


def _set_xsec_loc(xsec_id: str, frac: float, vsp) -> None:
    vsp.SetParmVal(vsp.GetXSecParm(xsec_id, "XLocPercent"), float(frac))


def _set_general_fuse(
    xsec_id: str,
    width: float,
    height: float,
    vsp,
    *,
    max_width_loc: float = -0.35,
    corner_rad: float = 0.35,
) -> None:
    vsp.SetParmVal(vsp.GetXSecParm(xsec_id, "Width"), width)
    vsp.SetParmVal(vsp.GetXSecParm(xsec_id, "Height"), height)
    vsp.SetParmVal(vsp.GetXSecParm(xsec_id, "MaxWidthLoc"), max_width_loc)
    vsp.SetParmVal(vsp.GetXSecParm(xsec_id, "CornerRad"), corner_rad)


def _set_circle(xsec_id: str, diameter: float, vsp) -> None:
    vsp.SetParmVal(vsp.GetXSecParm(xsec_id, "Circle_Diameter"), diameter)


def _add_pod(
    vsp,
    parent: str,
    name: str,
    *,
    length: float,
    fine_ratio: float,
    x: float,
    y: float = 0.0,
    z: float = 0.0,
    rx: float = 0.0,
    ry: float = 0.0,
    rz: float = 0.0,
    sym: int | None = None,
) -> str:
    gid = vsp.AddGeom("POD", parent)
    vsp.SetGeomName(gid, name)
    vsp.SetParmVal(gid, "Length", "Design", length)
    vsp.SetParmVal(gid, "FineRatio", "Design", fine_ratio)
    vsp.SetParmVal(gid, "X_Rel_Location", "XForm", x)
    vsp.SetParmVal(gid, "Y_Rel_Location", "XForm", y)
    vsp.SetParmVal(gid, "Z_Rel_Location", "XForm", z)
    vsp.SetParmVal(gid, "X_Rel_Rotation", "XForm", rx)
    vsp.SetParmVal(gid, "Y_Rel_Rotation", "XForm", ry)
    vsp.SetParmVal(gid, "Z_Rel_Rotation", "XForm", rz)
    if sym is not None:
        vsp.SetParmVal(gid, "Sym_Planar_Flag", "Sym", sym)
    return gid


def _ss_group(vsp, geom_id: str) -> str:
    """Return the SS_Control parm group name for the first control surface."""
    n = vsp.GetNumSubSurf(geom_id)
    # Newest is last; find SS_Control_* groups by probing
    for i in range(1, n + 3):
        g = f"SS_Control_{i}"
        try:
            vsp.GetParmVal(geom_id, "EtaStart", g)
            return g
        except Exception:
            continue
    return "SS_Control_1"


def _add_control_surface(vsp, geom_id: str, cfg: dict[str, Any], name: str) -> None:
    vsp.AddSubSurf(geom_id, vsp.SS_CONTROL)
    grp = _ss_group(vsp, geom_id)
    vsp.SetParmVal(geom_id, "EtaStart", grp, float(cfg["eta_start"]))
    vsp.SetParmVal(geom_id, "EtaEnd", grp, float(cfg["eta_end"]))
    vsp.SetParmVal(geom_id, "Length_C_Start", grp, float(cfg["chord_frac"]))
    vsp.SetParmVal(geom_id, "Length_C_End", grp, float(cfg["chord_frac"]))
    vsp.SetParmVal(geom_id, "LE_Flag", grp, float(cfg.get("le_flag", 0)))
    # Name via subsurface id if possible
    try:
        ssid = vsp.GetSubSurf(geom_id, vsp.GetNumSubSurf(geom_id) - 1)
        vsp.SetSubSurfName(ssid, name)
    except Exception:
        pass


# ----- part builders ---------------------------------------------------------


def build_fuse_oml(vsp, spec: dict[str, Any], ctx: dict[str, str]) -> None:
    oml = spec["oml"]
    part = _part(spec, "fuse_oml")
    assert part is not None
    ov = part["openvsp"]
    length = float(oml["length_m"])
    fuse_w = float(oml["fuselage_width_m"])
    fuse_h = float(oml["fuselage_height_m"])
    cargo = _station(spec, "cargo")
    bay_w = float(cargo["bay_width_m"])
    mw = float(ov.get("flat_belly_max_width_loc", -0.38))

    # Loft densifies with stations: nose shaping + each station boundary + engine face.
    loft: list[tuple[float, str, float, float, dict]] = [
        (0.00, "point", 0.0, 0.0, {}),
        (0.04, "general", fuse_w * 0.42, fuse_h * 0.55, {"mw": -0.15, "cr": 0.55}),
        (0.12, "general", fuse_w * 0.88, fuse_h * 0.92, {"mw": -0.30, "cr": 0.40}),
    ]
    for s in spec["stations_m"]:
        frac = s["x0"] / length
        if s["id"] == "cargo":
            loft.append(
                (
                    frac,
                    "general",
                    max(bay_w + 0.55, fuse_w),
                    fuse_h * 1.02,
                    {"mw": mw, "cr": 0.22},
                )
            )
        elif s["id"] == "engine":
            loft.append((frac, "general", fuse_w * 0.75, fuse_h * 0.85, {"mw": -0.20, "cr": 0.45}))
        else:
            taper = 1.0 if s["x0"] < 40 else 0.90
            loft.append((frac, "general", fuse_w * taper, fuse_h * taper, {"mw": mw, "cr": 0.32}))
    loft.append((cargo["x1"] / length, "general", fuse_w * 0.98, fuse_h, {"mw": mw, "cr": 0.28}))
    loft.append((0.97, "circle", fuse_w * 0.55, fuse_w * 0.55, {}))
    loft.append((1.00, "point", 0.0, 0.0, {}))
    # Deduplicate fracs (keep first)
    seen: set[float] = set()
    uniq: list[tuple[float, str, float, float, dict]] = []
    for row in loft:
        key = round(row[0], 4)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(row)
    loft = sorted(uniq, key=lambda r: r[0])

    fuse = vsp.AddGeom("FUSELAGE")
    vsp.SetGeomName(fuse, ov.get("name", "FUSE_OML"))
    vsp.SetParmVal(fuse, "Length", "Design", length)
    vsp.SetParmVal(fuse, "Tess_U", "Shape", int(oml.get("tess_u", 33)))
    vsp.SetParmVal(fuse, "Tess_W", "Shape", int(oml.get("tess_w", 25)))

    xs = vsp.GetXSecSurf(fuse, 0)
    while vsp.GetNumXSec(xs) < len(loft):
        vsp.InsertXSec(fuse, 1, vsp.XS_GENERAL_FUSE)
        xs = vsp.GetXSecSurf(fuse, 0)
    while vsp.GetNumXSec(xs) > len(loft):
        vsp.CutXSec(fuse, 1)
        xs = vsp.GetXSecSurf(fuse, 0)

    n = vsp.GetNumXSec(xs)
    for i, (frac, kind, width, height, extra) in enumerate(loft[:n]):
        if kind == "point":
            vsp.ChangeXSecShape(xs, i, vsp.XS_POINT)
            _set_xsec_loc(vsp.GetXSec(xs, i), frac, vsp)
        elif kind == "circle":
            vsp.ChangeXSecShape(xs, i, vsp.XS_CIRCLE)
            xsec = vsp.GetXSec(xs, i)
            _set_xsec_loc(xsec, frac, vsp)
            _set_circle(xsec, width, vsp)
        else:
            vsp.ChangeXSecShape(xs, i, vsp.XS_GENERAL_FUSE)
            xsec = vsp.GetXSec(xs, i)
            _set_xsec_loc(xsec, frac, vsp)
            _set_general_fuse(
                xsec,
                width,
                height,
                vsp,
                max_width_loc=float(extra.get("mw", mw)),
                corner_rad=float(extra.get("cr", 0.3)),
            )

    vsp.SetXSecTanAngles(vsp.GetXSec(xs, 0), vsp.XSEC_BOTH_SIDES, 75, 75, 75, 75)
    vsp.SetXSecTanAngles(vsp.GetXSec(xs, n - 1), vsp.XSEC_BOTH_SIDES, -40, -40, -40, -40)
    ctx["fuse"] = fuse
    print(f"  + fuse_oml  ({n} xsecs from stations)")


def build_main_wing(vsp, spec: dict[str, Any], ctx: dict[str, str]) -> None:
    part = _part(spec, "main_wing")
    assert part is not None
    ov = part["openvsp"]
    oml = spec["oml"]
    cargo = _station(spec, "cargo")
    fuse = ctx["fuse"]
    fuse_h = float(oml["fuselage_height_m"])
    span = float(ov.get("span_m", oml["wingspan_m"]))
    half = span / 2.0
    inner_b = half * float(ov["inner_span_frac"])
    outer_b = half - inner_b

    wing = vsp.AddGeom("WING", fuse)
    vsp.SetGeomName(wing, ov.get("name", "MAIN_WING"))
    vsp.InsertXSec(wing, 1, vsp.XS_FOUR_SERIES)
    vsp.SetParmVal(wing, "X_Rel_Location", "XForm", cargo["x0"] + float(ov["x_le_offset_from_cargo_m"]))
    vsp.SetParmVal(wing, "Z_Rel_Location", "XForm", fuse_h * float(ov["z_frac_of_fuse_h"]))
    vsp.SetParmVal(wing, "Span", "XSec_1", inner_b)
    vsp.SetParmVal(wing, "Root_Chord", "XSec_1", float(ov["root_chord_m"]))
    vsp.SetParmVal(wing, "Tip_Chord", "XSec_1", float(ov["kink_chord_m"]))
    vsp.SetParmVal(wing, "Sweep", "XSec_1", float(ov["inner_sweep_deg"]))
    vsp.SetParmVal(wing, "Dihedral", "XSec_1", float(ov["dihedral_inner_deg"]))
    vsp.SetParmVal(wing, "SectTess_U", "XSec_1", 12)
    vsp.SetParmVal(wing, "ThickChord", "XSecCurve_0", float(ov["thick_root"]))
    vsp.SetParmVal(wing, "ThickChord", "XSecCurve_1", float(ov["thick_kink"]))
    vsp.SetParmVal(wing, "Span", "XSec_2", outer_b)
    vsp.SetParmVal(wing, "Root_Chord", "XSec_2", float(ov["kink_chord_m"]))
    vsp.SetParmVal(wing, "Tip_Chord", "XSec_2", float(ov["tip_chord_m"]))
    vsp.SetParmVal(wing, "Sweep", "XSec_2", float(ov["outer_sweep_deg"]))
    vsp.SetParmVal(wing, "Dihedral", "XSec_2", float(ov["dihedral_outer_deg"]))
    vsp.SetParmVal(wing, "SectTess_U", "XSec_2", 10)
    vsp.SetParmVal(wing, "ThickChord", "XSecCurve_2", float(ov["thick_tip"]))
    ctx["MAIN_WING"] = wing
    print(f"  + main_wing  span={span} m double-delta")


def build_elevons(vsp, spec: dict[str, Any], ctx: dict[str, str]) -> None:
    part = _part(spec, "elevons")
    assert part is not None
    wing = ctx.get("MAIN_WING")
    if not wing:
        print("  ! elevons skipped (no MAIN_WING)")
        return
    _add_control_surface(vsp, wing, part["openvsp"], "ELEVON")
    print("  + elevons  SS_CONTROL on MAIN_WING")


def build_vertical_fin(vsp, spec: dict[str, Any], ctx: dict[str, str]) -> None:
    part = _part(spec, "vertical_fin")
    assert part is not None
    ov = part["openvsp"]
    fuse = ctx["fuse"]
    fuse_h = float(spec["oml"]["fuselage_height_m"])
    fin = vsp.AddGeom("WING", fuse)
    vsp.SetGeomName(fin, ov.get("name", "VERTICAL_FIN"))
    vsp.SetParmVal(fin, "Sym_Planar_Flag", "Sym", 0)
    vsp.SetParmVal(fin, "X_Rel_Location", "XForm", float(ov["x_m"]))
    vsp.SetParmVal(fin, "Z_Rel_Location", "XForm", fuse_h * float(ov["z_frac_of_fuse_h"]))
    vsp.SetParmVal(fin, "X_Rel_Rotation", "XForm", 90.0)
    vsp.SetParmVal(fin, "Span", "XSec_1", float(ov["span_m"]))
    vsp.SetParmVal(fin, "Root_Chord", "XSec_1", float(ov["root_chord_m"]))
    vsp.SetParmVal(fin, "Tip_Chord", "XSec_1", float(ov["tip_chord_m"]))
    vsp.SetParmVal(fin, "Sweep", "XSec_1", float(ov["sweep_deg"]))
    vsp.SetParmVal(fin, "SectTess_U", "XSec_1", 10)
    vsp.SetParmVal(fin, "ThickChord", "XSecCurve_0", float(ov["thick_root"]))
    vsp.SetParmVal(fin, "ThickChord", "XSecCurve_1", float(ov["thick_tip"]))
    ctx["VERTICAL_FIN"] = fin
    print("  + vertical_fin")


def build_rudder_speedbrake(vsp, spec: dict[str, Any], ctx: dict[str, str]) -> None:
    part = _part(spec, "rudder_speedbrake")
    assert part is not None
    fin = ctx.get("VERTICAL_FIN")
    if not fin:
        print("  ! rudder_speedbrake skipped (no VERTICAL_FIN)")
        return
    _add_control_surface(vsp, fin, part["openvsp"], "RUDDER_SB")
    print("  + rudder_speedbrake  SS_CONTROL on VERTICAL_FIN")


def build_body_flap(vsp, spec: dict[str, Any], ctx: dict[str, str]) -> None:
    part = _part(spec, "body_flap")
    assert part is not None
    ov = part["openvsp"]
    fuse = ctx["fuse"]
    fuse_h = float(spec["oml"]["fuselage_height_m"])
    flap = vsp.AddGeom("WING", fuse)
    vsp.SetGeomName(flap, ov.get("name", "BODY_FLAP"))
    vsp.SetParmVal(flap, "Sym_Planar_Flag", "Sym", 0)
    vsp.SetParmVal(flap, "X_Rel_Location", "XForm", float(ov["x_m"]))
    vsp.SetParmVal(flap, "Z_Rel_Location", "XForm", fuse_h * float(ov["z_frac_of_fuse_h"]))
    half = float(ov["span_m"]) / 2.0
    vsp.SetParmVal(flap, "Span", "XSec_1", half)
    vsp.SetParmVal(flap, "Root_Chord", "XSec_1", float(ov["root_chord_m"]))
    vsp.SetParmVal(flap, "Tip_Chord", "XSec_1", float(ov["tip_chord_m"]))
    vsp.SetParmVal(flap, "Sweep", "XSec_1", float(ov["sweep_deg"]))
    vsp.SetParmVal(flap, "ThickChord", "XSecCurve_0", 0.08)
    vsp.SetParmVal(flap, "ThickChord", "XSecCurve_1", 0.08)
    # Mirror manually: OpenVSP sym on a centered wing — use XY sym instead
    vsp.SetParmVal(flap, "Sym_Planar_Flag", "Sym", 2)
    print("  + body_flap")


def build_plbd(vsp, spec: dict[str, Any], ctx: dict[str, str]) -> None:
    part = _part(spec, "plbd")
    assert part is not None
    ov = part["openvsp"]
    cargo = _station(spec, "cargo")
    fuse = ctx["fuse"]
    fuse_h = float(spec["oml"]["fuselage_height_m"])
    # Closed top clamshell: two low-profile wings lying on bay roof (port/starboard).
    for side, ysign in (("L", -1.0), ("R", 1.0)):
        door = vsp.AddGeom("WING", fuse)
        vsp.SetGeomName(door, f"{ov['name_prefix']}_{side}")
        vsp.SetParmVal(door, "Sym_Planar_Flag", "Sym", 0)
        vsp.SetParmVal(door, "X_Rel_Location", "XForm", cargo["x0"] + 0.5)
        vsp.SetParmVal(door, "Y_Rel_Location", "XForm", ysign * 0.15)
        vsp.SetParmVal(door, "Z_Rel_Location", "XForm", fuse_h * 0.48)
        vsp.SetParmVal(door, "Z_Rel_Rotation", "XForm", ysign * 8.0)  # slight roof angle
        vsp.SetParmVal(door, "Span", "XSec_1", float(ov["span_each_m"]))
        vsp.SetParmVal(door, "Root_Chord", "XSec_1", float(cargo["bay_length_m"]) - 1.0)
        vsp.SetParmVal(door, "Tip_Chord", "XSec_1", float(cargo["bay_length_m"]) - 1.0)
        vsp.SetParmVal(door, "Sweep", "XSec_1", 0.0)
        vsp.SetParmVal(door, "ThickChord", "XSecCurve_0", float(ov["thickness_chord"]))
        vsp.SetParmVal(door, "ThickChord", "XSecCurve_1", float(ov["thickness_chord"]))
    print("  + plbd  closed clamshell L/R")


def build_oms_pods(vsp, spec: dict[str, Any], ctx: dict[str, str]) -> None:
    part = _part(spec, "oms_pods")
    assert part is not None
    ov = part["openvsp"]
    fuse = ctx["fuse"]
    fuse_h = float(spec["oml"]["fuselage_height_m"])
    z = fuse_h * float(ov["z_frac_of_fuse_h"])
    for side, ysign in (("L", -1.0), ("R", 1.0)):
        _add_pod(
            vsp,
            fuse,
            f"{ov['name_prefix']}_{side}",
            length=float(ov["length_m"]),
            fine_ratio=float(ov["fine_ratio"]),
            x=float(ov["x_m"]),
            y=ysign * float(ov["y_m"]),
            z=z,
            sym=0,
        )
    print("  + oms_pods  L/R fairings")


def build_nose_gear(vsp, spec: dict[str, Any], ctx: dict[str, str]) -> None:
    part = _part(spec, "nose_gear")
    assert part is not None
    ov = part["openvsp"]
    _add_pod(
        vsp,
        ctx["fuse"],
        ov["name"],
        length=float(ov["length_m"]),
        fine_ratio=float(ov["fine_ratio"]),
        x=float(ov["x_m"]),
        z=float(ov["z_m"]),
        rx=float(ov.get("rotate_x_deg", 90)),
        sym=0,
    )
    print("  + nose_gear  placeholder strut")


def build_main_gear(vsp, spec: dict[str, Any], ctx: dict[str, str]) -> None:
    part = _part(spec, "main_gear")
    assert part is not None
    ov = part["openvsp"]
    for side, ysign in (("L", -1.0), ("R", 1.0)):
        _add_pod(
            vsp,
            ctx["fuse"],
            f"{ov['name_prefix']}_{side}",
            length=float(ov["length_m"]),
            fine_ratio=float(ov["fine_ratio"]),
            x=float(ov["x_m"]),
            y=ysign * float(ov["y_m"]),
            z=float(ov["z_m"]),
            rx=float(ov.get("rotate_x_deg", 90)),
            sym=0,
        )
    print("  + main_gear  L/R placeholder struts")


def build_crew_hatch(vsp, spec: dict[str, Any], ctx: dict[str, str]) -> None:
    part = _part(spec, "crew_hatch")
    assert part is not None
    ov = part["openvsp"]
    _add_pod(
        vsp,
        ctx["fuse"],
        ov["name"],
        length=float(ov["length_m"]),
        fine_ratio=float(ov["fine_ratio"]),
        x=float(ov["x_m"]),
        y=float(ov["y_m"]),
        z=float(ov["z_m"]),
        sym=0,
    )
    print("  + crew_hatch  port ground-only")


def build_airlock_hatches(vsp, spec: dict[str, Any], ctx: dict[str, str]) -> None:
    part = _part(spec, "airlock_hatches")
    assert part is not None
    ov = part["openvsp"]
    al = _station(spec, "airlock")
    fuse = ctx["fuse"]
    for name, x in (("FWD", al["x0"]), ("AFT", al["x1"])):
        _add_pod(
            vsp,
            fuse,
            f"{ov['name_prefix']}_{name}",
            length=float(ov["length_m"]),
            fine_ratio=float(ov["fine_ratio"]),
            x=float(x),
            z=0.0,
            ry=90.0,
            sym=0,
        )
    print("  + airlock_hatches  FWD/AFT bulkhead markers")


def build_engine_nacelle(vsp, spec: dict[str, Any], ctx: dict[str, str]) -> None:
    part = _part(spec, "engine_nacelle")
    assert part is not None
    ov = part["openvsp"]
    eng = _station(spec, ov.get("station", "engine"))
    x = 0.5 * (eng["x0"] + eng["x1"]) - 0.5 * float(ov["length_m"])
    _add_pod(
        vsp,
        ctx["fuse"],
        ov["name"],
        length=float(ov["length_m"]),
        fine_ratio=float(ov["fine_ratio"]),
        x=x,
        z=float(ov.get("z_m", 0.0)),
        sym=0,
    )
    print("  + engine_nacelle  combined-cycle")


def build_inlets(vsp, spec: dict[str, Any], ctx: dict[str, str]) -> None:
    part = _part(spec, "inlets")
    assert part is not None
    ov = part["openvsp"]
    fuse = ctx["fuse"]
    for side, ysign in (("L", -1.0), ("R", 1.0)):
        _add_pod(
            vsp,
            fuse,
            f"{ov['name_prefix']}_{side}",
            length=float(ov["length_m"]),
            fine_ratio=float(ov["fine_ratio"]),
            x=float(ov["x_m"]),
            y=ysign * float(ov["y_m"]),
            z=float(ov["z_m"]),
            sym=0,
        )
    print("  + inlets  L/R variable inlets")


BUILDERS = {
    "fuse_oml": build_fuse_oml,
    "main_wing": build_main_wing,
    "elevons": build_elevons,
    "vertical_fin": build_vertical_fin,
    "rudder_speedbrake": build_rudder_speedbrake,
    "body_flap": build_body_flap,
    "plbd": build_plbd,
    "oms_pods": build_oms_pods,
    "nose_gear": build_nose_gear,
    "main_gear": build_main_gear,
    "crew_hatch": build_crew_hatch,
    "airlock_hatches": build_airlock_hatches,
    "engine_nacelle": build_engine_nacelle,
    "inlets": build_inlets,
}


def build_vsp_model(spec: dict[str, Any]) -> dict[str, str]:
    import openvsp as vsp

    _clear_errors(vsp)
    vsp.ClearVSPModel()
    ctx: dict[str, str] = {}

    # Fuse first (parent), then remaining parts in JSON order.
    ordered = sorted(
        [p for p in spec["parts"] if p.get("enabled", True)],
        key=lambda p: 0 if p["builder"] == "fuse_oml" else 1,
    )
    print(f"Building {len(ordered)} enabled parts from {SPEC_PATH.name} ...")
    for part in ordered:
        builder = BUILDERS.get(part["builder"])
        if builder is None:
            print(f"  ! no builder for {part['id']} ({part['builder']})")
            continue
        builder(vsp, spec, ctx)
        _clear_errors(vsp)

    vsp.Update()
    vsp.WriteVSPFile(str(VSP3_OUT))
    vsp.ExportFile(str(STL_OUT), vsp.SET_ALL, vsp.EXPORT_STL)

    from validate_vehicle_constraints import validate

    failures = validate(spec, VSP3_OUT)
    if failures:
        print(f"CONSTRAINT FAIL ({len(failures)}):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        raise SystemExit(1)
    print(f"  constraints OK ({len(spec.get('constraints', []))})")
    return ctx


# ----- figures ---------------------------------------------------------------


def _read_stl_triangles(path: Path) -> np.ndarray:
    data = path.read_bytes()
    if data[:5].lower() == b"solid" and b"\x00" not in data[:80]:
        verts = []
        tri: list[list[float]] = []
        for line in data.decode("ascii", errors="ignore").splitlines():
            parts = line.strip().split()
            if len(parts) >= 4 and parts[0] == "vertex":
                tri.append([float(parts[1]), float(parts[2]), float(parts[3])])
                if len(tri) == 3:
                    verts.append(tri)
                    tri = []
        return np.asarray(verts, dtype=np.float64)
    n = struct.unpack_from("<I", data, 80)[0]
    tris = np.empty((n, 3, 3), dtype=np.float64)
    off = 84
    for i in range(n):
        vals = struct.unpack_from("<12fH", data, off)
        tris[i] = np.array(vals[3:12], dtype=np.float64).reshape(3, 3)
        off += 50
    return tris


def _silhouette_segments(tris: np.ndarray, axes: tuple[int, int]):
    a, b = axes
    step = max(1, len(tris) // 8000)
    for tri in tris[::step]:
        for i in range(3):
            p0, p1 = tri[i], tri[(i + 1) % 3]
            yield np.array([p0[a], p0[b]]), np.array([p1[a], p1[b]])


def _station_color(rgb: list[float], alpha: float = 0.55) -> tuple:
    return (rgb[0], rgb[1], rgb[2], alpha)


def render_floorplan(slim: dict, wing_ov: dict, tris: np.ndarray, out: Path) -> None:
    length = float(slim["length_m"])
    fuse_w = float(slim["fuselage_width_m"])
    span = float(slim["wingspan_m"])
    stations = slim["stations"]
    half = span / 2.0
    cargo_x0 = next(s["x0"] for s in stations if s["id"] == "cargo")
    root_x0 = cargo_x0 + float(wing_ov.get("x_le_offset_from_cargo_m", -1.5))
    root_c = float(wing_ov.get("root_chord_m", 18.5))
    kink_c = float(wing_ov.get("kink_chord_m", 7.2))
    tip_c = float(wing_ov.get("tip_chord_m", 2.4))
    inner_b = half * float(wing_ov.get("inner_span_frac", 0.42))
    sw1 = math.radians(float(wing_ov.get("inner_sweep_deg", 52)))
    sw2 = math.radians(float(wing_ov.get("outer_sweep_deg", 28)))
    le_kink = root_x0 + math.tan(sw1) * inner_b
    te_kink = le_kink + kink_c
    le_tip = le_kink + math.tan(sw2) * (half - inner_b)
    te_tip = le_tip + tip_c
    wing_poly = np.array(
        [
            [root_x0, fuse_w / 2],
            [le_kink, fuse_w / 2 + inner_b],
            [le_tip, half],
            [te_tip, half],
            [te_kink, fuse_w / 2 + inner_b],
            [root_x0 + root_c, fuse_w / 2],
        ]
    )

    fig, ax = plt.subplots(figsize=(14.0, 6.2), dpi=160)
    fig.patch.set_facecolor("#6e6e6e")
    ax.set_facecolor("#6e6e6e")
    for sign in (1.0, -1.0):
        pts = wing_poly.copy()
        pts[:, 1] *= sign
        ax.add_patch(Polygon(pts, closed=True, facecolor="#9a9a9a", edgecolor="#2a2a2a", lw=0.8, zorder=1))
    ax.add_patch(Rectangle((0.0, -fuse_w / 2), length, fuse_w, facecolor="#b0b0b0", edgecolor="#222", lw=1.0, zorder=2))
    for s in stations:
        ax.add_patch(
            Rectangle(
                (s["x0"], -fuse_w / 2 + 0.15),
                s["x1"] - s["x0"],
                fuse_w - 0.3,
                facecolor=_station_color(s["color"]),
                edgecolor="#333",
                lw=0.4,
                zorder=3,
            )
        )
        ax.text(
            0.5 * (s["x0"] + s["x1"]),
            0.0,
            s["label"],
            ha="center",
            va="center",
            fontsize=7.5,
            color="#1a1a1a",
            rotation=90 if (s["x1"] - s["x0"]) < 3.5 else 0,
            zorder=4,
        )
    for p0, p1 in _silhouette_segments(tris, (0, 1)):
        ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color="#1f1f1f", lw=0.12, alpha=0.22, zorder=5)
    ax.set_aspect("equal")
    ax.set_xlim(-2, length + 2)
    ax.set_ylim(-half - 1.5, half + 1.5)
    ax.axis("off")
    ax.text(length / 2, -half - 0.8, "CATSKILLS-SSTO FLOORPLAN  ·  vehicle_spec → OpenVSP", ha="center", va="top", fontsize=11, color="#f0f0f0", fontweight="bold")
    fig.tight_layout(pad=0.4)
    fig.savefig(out, dpi=160)
    plt.close(fig)


def render_profile(slim: dict, fin_ov: dict, tris: np.ndarray, out: Path, *, show_gear: bool) -> None:
    length = float(slim["length_m"])
    fuse_h = float(slim["fuselage_height_m"])
    stations = slim["stations"]
    fig, ax = plt.subplots(figsize=(14.0, 4.8), dpi=160)
    fig.patch.set_facecolor("#6e6e6e")
    ax.set_facecolor("#6e6e6e")
    ax.add_patch(Polygon(np.array([[0.0, 0.0], [8.0, fuse_h / 2], [8.0, -fuse_h / 2]]), closed=True, facecolor="#a8a8a8", edgecolor="#222", lw=0.8, zorder=2))
    ax.add_patch(Rectangle((8.0, -fuse_h / 2), length - 8.0, fuse_h, facecolor="#b0b0b0", edgecolor="#222", lw=1.0, zorder=2))
    # TPS belly band
    ax.add_patch(Rectangle((0.0, -fuse_h / 2), length, fuse_h * 0.12, facecolor="#3a3a3a", edgecolor="none", zorder=2.5, alpha=0.55))
    for s in stations:
        ax.add_patch(
            Rectangle(
                (s["x0"], -fuse_h / 2 + 0.1),
                s["x1"] - s["x0"],
                fuse_h - 0.2,
                facecolor=_station_color(s["color"], 0.45),
                edgecolor="#333",
                lw=0.4,
                zorder=3,
            )
        )
        ax.text(
            0.5 * (s["x0"] + s["x1"]),
            0.0,
            s["label"],
            ha="center",
            va="center",
            fontsize=7,
            color="#111",
            rotation=90 if (s["x1"] - s["x0"]) < 3.5 else 0,
            zorder=4,
        )
    fx = float(fin_ov.get("x_m", 44.5))
    fh = float(fin_ov.get("span_m", 7.2))
    ax.add_patch(
        Polygon(
            np.array([[fx, fuse_h / 2], [fx + 3.5, fuse_h / 2 + fh], [fx + 5.5, fuse_h / 2 + fh * 0.85], [fx + 5.5, fuse_h / 2]]),
            closed=True,
            facecolor="#8e8e8e",
            edgecolor="#222",
            lw=0.8,
            zorder=3,
        )
    )
    if show_gear:
        for x in (8.5, 30.0):
            ax.plot([x, x], [-fuse_h / 2, -fuse_h / 2 - 3.5], color="#222", lw=1.2, zorder=6)
            ax.add_patch(plt.Circle((x, -fuse_h / 2 - 3.7), 0.55, facecolor="#444", edgecolor="#111", zorder=6))
    for p0, p1 in _silhouette_segments(tris, (0, 2)):
        ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color="#1f1f1f", lw=0.12, alpha=0.22, zorder=5)
    ax.set_aspect("equal")
    ax.set_xlim(-2, length + 2)
    ax.set_ylim(-fuse_h / 2 - 5.0, fuse_h / 2 + 8.0)
    ax.axis("off")
    ax.text(length / 2, -fuse_h / 2 - 4.2, "CATSKILLS-SSTO PROFILE  ·  vehicle_spec → OpenVSP", ha="center", va="top", fontsize=11, color="#f0f0f0", fontweight="bold")
    fig.tight_layout(pad=0.4)
    fig.savefig(out, dpi=160)
    plt.close(fig)


def main() -> int:
    if os.environ.get("_OPENVSP_REEXEC") != "1":
        _ensure_openvsp_libs()
        os.environ["_OPENVSP_REEXEC"] = "1"
        os.execv(sys.executable, [sys.executable, *sys.argv])

    spec = load_spec()
    slim = sync_stations(spec)
    print(f"Synced {STATIONS_PATH.name} from {SPEC_PATH.name}")
    build_vsp_model(spec)
    print(f"  wrote {VSP3_OUT}")
    print(f"  wrote {STL_OUT}")

    tris = _read_stl_triangles(STL_OUT)
    print(f"  mesh triangles: {len(tris)}")
    wing_ov = (_part(spec, "main_wing") or {}).get("openvsp", {})
    fin_ov = (_part(spec, "vertical_fin") or {}).get("openvsp", {})
    show_gear = any(p["id"] in {"nose_gear", "main_gear"} and p.get("enabled", True) for p in spec["parts"])
    render_floorplan(slim, wing_ov, tris, FLOORPLAN_OUT)
    render_profile(slim, fin_ov, tris, PROFILE_OUT, show_gear=show_gear)
    print(f"  wrote {FLOORPLAN_OUT}")
    print(f"  wrote {PROFILE_OUT}")
    n_on = sum(1 for p in spec["parts"] if p.get("enabled", True))
    print(f"Done: {n_on}/{len(spec['parts'])} parts enabled from paper spec.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
