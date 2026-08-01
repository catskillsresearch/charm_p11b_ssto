#!/usr/bin/env python3
"""Stretch Shuttle wing mesh to Plan A span/area (visual matches FDM).

Heritage OV: b≈23.79 m, S≈250 m².
Plan A high-AR loft: b≈60 m, S≈900 m² (AR≈4 — climb margin on paper σ1/σ2 T/W).
  k_span  = 60/23.79 ≈ 2.522
  k_chord = (900/249.9)/k_span ≈ 1.428

AC axes (shuttle_o2.ac): +X aft, +Y up, +Z right.

The span/chord warp only carries the body glove and gear doors to the Plan A
track. The wing itself comes from build_delta_wing.install_delta_wing(), which
deletes the OV glove/strake skins and lofts a clean cropped delta with the
trailing edge on a straight elevon hinge line.
"""

from __future__ import annotations

import math
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_delta_wing import install_delta_wing  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]  # Models/
SRC = ROOT / "shuttle_o2_heritage.ac"
DST = ROOT / "shuttle_o2_plan_a.ac"
FALLBACK = ROOT / "shuttle_o2.ac"

# Plan A loft / heritage
K_SPAN = 60.0 / 23.79
K_CHORD = (900.0 / 249.9) / K_SPAN
Z_BODY = 3.60  # fuselage half-width (upper body |z|max ≈ 3.62)
Z_TIP = 11.93  # outboard elevon tip (heritage mesh; delta wing sets real tip)
X_PIVOT = -1.50  # root LE-ish (heatshield wing min x ≈ -1.52)

# Objects whose vertices participate in the wing warp.
WING_OBJECTS = {
    "fuselage",
    "heatshield",
    "inboard-elevon-left",
    "inboard-elevon-right",
    "outboard-elevon-left",
    "outboard-elevon-right",
    "GearDoorL",
    "GearDoorR",
}

# Elevons / tips: always full wing weight (no body blend).
FULL_WING = {
    "inboard-elevon-left",
    "inboard-elevon-right",
    "outboard-elevon-left",
    "outboard-elevon-right",
}


def k_outboard() -> float:
    """Outboard stretch so tip maps to tip * K_SPAN with body wall fixed."""
    return (Z_TIP * K_SPAN - Z_BODY) / (Z_TIP - Z_BODY)


def map_span(az: float) -> float:
    if az <= Z_BODY:
        return az
    return Z_BODY + k_outboard() * (az - Z_BODY)


def wing_weight(x: float, y: float, z: float, obj: str) -> float:
    """0 = body (unchanged), 1 = full wing (span+chord)."""
    if obj in FULL_WING:
        return 1.0
    az = abs(z)
    # Soft ramp across the wing glove
    if az <= Z_BODY:
        return 0.0
    if az >= 5.5:
        w = 1.0
    else:
        w = (az - Z_BODY) / (5.5 - Z_BODY)
    # Keep tall fuselage sides / OMS shoulders from chord-stretching
    if y > -1.5 and az < 6.0:
        w *= max(0.0, (-y - 0.5) / 2.0)  # fade above belly/wing
    return max(0.0, min(1.0, w))


def transform(x: float, y: float, z: float, obj: str) -> tuple[float, float, float]:
    w = wing_weight(x, y, z, obj)
    az = abs(z)
    # Span: continuous map for outboard structure; blend near body via weight
    if az > Z_BODY:
        az2 = map_span(az)
        # Blend: at w=0 keep az, at w=1 use az2 (elevons always w=1)
        az_new = az + w * (az2 - az)
        z_new = math.copysign(az_new, z)
    else:
        z_new = z

    if w <= 0.0:
        return x, y, z_new

    x_stretched = X_PIVOT + (x - X_PIVOT) * K_CHORD
    x_new = x + w * (x_stretched - x)
    return x_new, y, z_new


def ensure_heritage() -> Path:
    """Keep an untouched heritage copy; seed from shuttle_o2.ac once."""
    if SRC.exists():
        return SRC
    if not FALLBACK.exists():
        raise SystemExit(f"missing {FALLBACK}")
    shutil.copy2(FALLBACK, SRC)
    print(f"seeded heritage copy → {SRC.name}")
    return SRC


def rewrite(src: Path, dst: Path) -> None:
    lines = src.read_text(errors="ignore").splitlines(keepends=True)
    out = []
    obj = None
    collecting = False
    left = 0
    n_vert = 0
    n_changed = 0
    tip_before = 0.0
    tip_after = 0.0

    for line in lines:
        if line.startswith("name "):
            # name "foo" or name foo
            if '"' in line:
                obj = line.split('"')[1]
            else:
                obj = line.split()[1]
            collecting = False
            out.append(line)
            continue

        if line.startswith("numvert") and obj in WING_OBJECTS:
            left = int(line.split()[1])
            collecting = True
            out.append(line)
            continue

        if collecting and left > 0:
            parts = line.split()
            if len(parts) >= 3:
                try:
                    x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
                    tip_before = max(tip_before, abs(z))
                    x2, y2, z2 = transform(x, y, z, obj)
                    tip_after = max(tip_after, abs(z2))
                    if (x2, y2, z2) != (x, y, z):
                        n_changed += 1
                    rest = " ".join(parts[3:])
                    line = f"{x2:.6f} {y2:.6f} {z2:.6f}" + (f" {rest}" if rest else "") + (
                        "\n" if line.endswith("\n") else ""
                    )
                    if not line.endswith("\n") and lines:  # preserve newline style
                        pass
                    n_vert += 1
                except ValueError:
                    pass
            left -= 1
            if left == 0:
                collecting = False
            out.append(line)
            continue

        out.append(line)

    dst.write_text("".join(out))
    print(
        f"wrote {dst.name}: verts_touched≈{n_vert}, changed={n_changed}, "
        f"|z| tip {tip_before:.2f} → {tip_after:.2f} m "
        f"(span≈{2*tip_after:.2f} m), k_span={K_SPAN:.3f}, k_chord={K_CHORD:.3f}"
    )


def hinge_report() -> None:
    """Print the elevon hinge line for SpaceShuttle.xml (FG y = AC z, FG z = AC y)."""
    import build_delta_wing as dw

    # Flat-bottomed sections: the hinge sits mid-height of the blunt trailing edge.
    root = dw.y_lower(dw.Z_ELEVON_ROOT) + 0.5 * dw.T_TE_ROOT
    tip = dw.y_lower(dw.Z_TIP) + 0.5 * dw.T_TE_TIP
    print(
        "elevon hinge axis (straight, both sides): "
        f"x={dw.X_TE:.2f}  z={0.5 * (root + tip):.2f}  y=0 → ±{dw.Z_TIP:.2f}"
    )



# Plan A chord loft parks elevon TE ≈19.6 m while the heritage boat-tail / fin /
# OMS still end ≈17.8 m. Stretch the aft body so the tail rides with the flaps;
# the Grenadier nozzle is rebuilt separately to exit just past that line.
AFT_PIVOT = 11.0
AFT_SCALE = (21.00 - 11.0) / (17.768 - 11.0)  # fuse tip → ≈21.0 m (slender elevon TE)
AFT_FULL_OBJECTS = {"BodyFlap", "SpeedBrakeL", "SpeedBrakeR"}
OMS_GREN = ROOT / "OMSPods_grenadier.ac"
OMS_HERITAGE = ROOT / "OMSPods.ac"


def map_aft_x(x: float) -> float:
    if x <= AFT_PIVOT:
        return x
    return AFT_PIVOT + (x - AFT_PIVOT) * AFT_SCALE


def aft_body_weight(x: float, y: float, z: float, obj: str) -> float:
    """1 = follow aft stretch (boat-tail / fin), 0 = leave (wing skin)."""
    if obj in AFT_FULL_OBJECTS:
        return 1.0 if x > AFT_PIVOT else 0.0
    if obj not in ("fuselage", "heatshield"):
        return 0.0
    if x <= AFT_PIVOT:
        return 0.0
    az = abs(z)
    if az < 0.85 and y > 1.2:  # vertical fin
        return 1.0
    if az < 3.85:  # boat-tail / OMS mount / aft belly
        return 1.0
    if az < 5.0:  # soft glove so wing root does not tear
        return max(0.0, 1.0 - (az - 3.85) / 1.15)
    return 0.0


def _rewrite_verts(
    path: Path,
    want: set[str] | None,
    weight_fn,
) -> tuple[int, float]:
    """Apply map_aft_x blended by weight_fn. want=None means all objects."""
    lines = path.read_text(errors="ignore").splitlines(keepends=True)
    out: list[str] = []
    obj = None
    collecting = False
    left = 0
    n_move = 0
    max_dx = 0.0
    for line in lines:
        if line.startswith("name "):
            obj = line.split('"')[1] if '"' in line else line.split()[1]
            collecting = False
            out.append(line)
            continue
        if line.startswith("numvert") and (want is None or obj in want):
            left = int(line.split()[1])
            collecting = True
            out.append(line)
            continue
        if collecting and left > 0:
            parts = line.split()
            if len(parts) >= 3:
                try:
                    x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
                    w = weight_fn(x, y, z, obj or "")
                    if w > 1e-6:
                        x2 = x + w * (map_aft_x(x) - x)
                        dx = x2 - x
                        if abs(dx) > 0.01:
                            x = x2
                            n_move += 1
                            max_dx = max(max_dx, dx)
                    rest = " ".join(parts[3:])
                    nl = "\n" if line.endswith("\n") else ""
                    line = f"{x:.6f} {y:.6f} {z:.6f}" + (f" {rest}" if rest else "") + nl
                except ValueError:
                    pass
            left -= 1
            if left == 0:
                collecting = False
            out.append(line)
            continue
        out.append(line)
    path.write_text("".join(out))
    return n_move, max_dx


def stretch_aft_tail(path: Path) -> None:
    """Pull boat-tail, fin, body flap and speedbrake aft toward elevon TE."""
    names = {"fuselage", "heatshield"} | AFT_FULL_OBJECTS
    n_move, max_dx = _rewrite_verts(path, names, aft_body_weight)
    print(
        f"aft tail stretch: moved {n_move} verts (max +x {max_dx:.2f} m), "
        f"scale={AFT_SCALE:.3f} from x={AFT_PIVOT:.1f}"
    )


def stretch_oms_pods() -> None:
    """Re-strip heritage OMS pods then apply the same aft stretch."""
    strip = Path(__file__).resolve().parent / "strip_oms_engines.py"
    if OMS_HERITAGE.exists() and strip.exists():
        import runpy

        runpy.run_path(str(strip), run_name="__main__")
    if not OMS_GREN.exists():
        print("stretch_oms_pods: OMSPods_grenadier.ac missing — skipped")
        return

    def w(x, y, z, obj):
        return 1.0 if x > AFT_PIVOT else 0.0

    n_move, max_dx = _rewrite_verts(OMS_GREN, None, w)
    print(f"OMS pods aft stretch: moved {n_move} verts (max +x {max_dx:.2f} m)")


def stretch_grenadier_aft_meshes() -> None:
    """Rebuild scoop/internals from unscaled source, then apply aft stretch once."""
    prop = Path(__file__).resolve().parent / "build_grenadier_propulsion_ac.py"
    if prop.exists():
        import runpy
        import sys

        gdir = str(Path(__file__).resolve().parent)
        if gdir not in sys.path:
            sys.path.insert(0, gdir)
        ns = runpy.run_path(str(prop))
        # Nozzle is authored already in Plan A length — do not aft-stretch it.
        ns["build_scoop"]()
        ns["build_internals"]()

    for rel in (
        "grenadier_scoop.ac",
        "grenadier_internals.ac",
    ):
        p = Path(__file__).resolve().parent / rel
        if not p.exists():
            continue

        def w(x, y, z, obj, _x0=AFT_PIVOT):
            return 1.0 if x > _x0 else 0.0

        n_move, max_dx = _rewrite_verts(p, None, w)
        print(f"{rel}: aft stretch moved {n_move} verts (max +x {max_dx:.2f} m)")



def rebuild_long_nozzle() -> None:
    """Regenerate petal bell with Plan A exit (past elevon TE); no aft stretch."""
    prop = Path(__file__).resolve().parent / "build_grenadier_propulsion_ac.py"
    if not prop.exists():
        return
    import runpy
    import sys

    gdir = str(Path(__file__).resolve().parent)
    if gdir not in sys.path:
        sys.path.insert(0, gdir)
    ns = runpy.run_path(str(prop))
    ns["build_nozzle"]()


def main() -> None:
    src = ensure_heritage()
    rewrite(src, DST)
    install_delta_wing(DST)
    stretch_aft_tail(DST)
    stretch_oms_pods()
    stretch_grenadier_aft_meshes()
    rebuild_long_nozzle()
    hinge_report()
    print(f"heritage={SRC.name}  plan_a={DST.name}")


if __name__ == "__main__":
    main()
