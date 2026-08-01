#!/usr/bin/env python3
"""Replace the heritage OV wing skin with a clean cropped-delta wing.

The OV planform is a cranked glove: warping it to Plan A span/chord produced
SR-71-like chines that suddenly widen, plus see-through notches at the elevons.
JSBSim Plan A assumes an equivalent slender cropped delta (S≈900 m², b≈60 m),
so build that shape directly instead of stretching heritage topology:

  * delete every fuselage/heatshield surface outboard of the body wall at wing
    level (the old glove + strake skins),
  * generate a closed cropped-delta shell per side, root rib buried inside the
    fuselage, trailing edge on a straight hinge line,
  * regenerate the four elevon objects as clean panels flush to that hinge line
    so no ground shows between wing and flap.

The OV is a monowing: one flat black-tiled boat runs from the centreline to the
tips with the fuselage sitting on top, and the main gear doors are cut into that
boat. So the generated wing is flat-bottomed and level with the boat rather than
a symmetric airfoil, the root rib sits inboard of the hull chine (|z| ≈ 2.66 at
wing level) so nothing protrudes, the underside samples the same black HRSI tile
field as the heatshield, and a recessed bay is boxed out under the gear doors.

AC axes (shuttle_o2*.ac): +X aft, +Y up, +Z right (left wing = +Z).
Object names for the elevons are preserved so existing FG animations still bind.
"""

from __future__ import annotations

from pathlib import Path

# --- planform (metres, AC frame) -------------------------------------------
# The OV is a monowing: one flat tiled boat runs from the centreline out to the
# tips with the fuselage sitting on top of it. The hull side wall at wing level
# is only |z| ≈ 2.66, so the root rib must sit inboard of that to stay hidden,
# and the underside must be flat and level with the boat rather than an airfoil
# belly curving up away from it.
Z_ROOT = 2.10  # root rib, well inboard of the hull chine and of the bay opening
# High-AR slow-path loft: same S≈900 m², span 60 m → AR≈4 (was 45 m / AR≈2.25).
# Chord scaled ~0.762 about the elevon hinge so area holds while induced drag falls.
Z_TIP = 30.00  # tip → span ≈ 60.0 m
X_LE_ROOT = 1.05
X_LE_TIP = 10.49
X_TE = 17.20  # straight elevon hinge line (unchanged)

Y_LOWER_ROOT = -5.230  # flat underside, just under the OV boat plane (-5.20)
Y_LOWER_TIP = -5.020
T_MAX_ROOT = 0.900  # thinner section with shorter chord
T_MAX_TIP = 0.400
T_TE_ROOT = 0.620  # full thickness at the blunt TE (sets the elevon LE)
T_TE_TIP = 0.280

# Elevons: hinge on X_TE, trailing edge tapering aft of the fin/boat-tail.
X_ELEVON_LE = 17.17  # slight overlap so the hinge never opens a slit
X_ELEVON_TE_ROOT = 21.01
X_ELEVON_TE_TIP = 19.79
T_ELEVON_TE = 0.14  # blunt trailing edge thickness
Z_ELEVON_ROOT = 3.05  # clear of the body flap, which reaches |z| = 3.02
Z_ELEVON_SPLIT = 18.80  # inboard/outboard seam (scaled with span)
ELEVON_SEAM = 0.015  # half the inboard/outboard slit; small enough not to show ground

# Chord fractions of the airfoil loop, LE → TE, and thickness multipliers.
# Indices 2 and 4 are pulled onto the gear-well edges near the root (see
# _chord_fracs) so the bay is a true rectangle under the tiled door.
CHORD_FRACS = (0.00, 0.035, 0.112, 0.18, 0.420, 0.68, 1.00)
THICK_MULT = (0.10, 0.45, 0.72, 0.88, 1.00, 0.86, None)  # None → blunt TE
WELL_IDX_FWD, WELL_IDX_MID, WELL_IDX_AFT = 2, 3, 4

# Main gear well: the OV boat carries the tiled gear doors, so the wing needs a
# matching opening or the door panels sit flush in the skin and vanish from
# below. Door footprint is x 0.49..5.30, |z| 2.65..4.41; the bay is cut a little
# larger all round so the door hangs in it with a visible tile gap and never
# z-fights the skin.
WELL_X_FWD, WELL_X_AFT = 0.38, 5.42
WELL_Z_INNER, WELL_Z_OUTER = 2.55, 4.52
WELL_BLEND_Z = 7.00  # chord fractions relax back to nominal by here
WELL_CEIL_Y = -4.80  # roof of the bay, clear of the retracted gear door

# Span stations: root, both gear-well edges, then evenly out to the tip.
SPAN_OUTER_STATIONS = 10

# --- texture atlas patches (spstob_1.png) ----------------------------------
# The underside has to sample the same black HRSI tile field as the boat or the
# wing/hull join shows up as a paint seam; the upper surface takes white LRSI.
DARK_U0, DARK_U1 = 0.332, 0.396  # black tile field (mean RGB ≈ 55)
DARK_V0, DARK_V1 = 0.352, 0.478
LIGHT_U0, LIGHT_U1 = 0.170, 0.326  # white tile field (mean RGB ≈ 234)
LIGHT_V0, LIGHT_V1 = 0.726, 0.808

WING_SKIN_OBJECTS = ("fuselage", "heatshield")
ELEVON_OBJECTS = (
    "inboard-elevon-left",
    "inboard-elevon-right",
    "outboard-elevon-left",
    "outboard-elevon-right",
)
WING_OBJECT_NAMES = ("plan-a-wing-left", "plan-a-wing-right")
TEXTURE = "spstob_1.png"


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _span_t(az: float) -> float:
    return max(0.0, min(1.0, (az - Z_ROOT) / (Z_TIP - Z_ROOT)))


def x_le(az: float) -> float:
    return _lerp(X_LE_ROOT, X_LE_TIP, _span_t(az))


def _chord_fracs(az: float) -> list[float]:
    """Chord fractions at |z| = az, with the gear-well pair snapped to absolute x."""
    fr = list(CHORD_FRACS)
    if az <= WELL_Z_OUTER:
        t = 1.0
    elif az < WELL_BLEND_Z:
        t = (WELL_BLEND_Z - az) / (WELL_BLEND_Z - WELL_Z_OUTER)
    else:
        return fr
    le = x_le(az)
    chord = X_TE - le
    fr[WELL_IDX_FWD] = _lerp(fr[WELL_IDX_FWD], (WELL_X_FWD - le) / chord, t)
    fr[WELL_IDX_AFT] = _lerp(fr[WELL_IDX_AFT], (WELL_X_AFT - le) / chord, t)
    # Keep the loop monotonic in chord.
    fr[WELL_IDX_FWD] = min(max(fr[WELL_IDX_FWD], CHORD_FRACS[1] + 0.008), CHORD_FRACS[3] - 0.01)
    fr[WELL_IDX_AFT] = min(max(fr[WELL_IDX_AFT], CHORD_FRACS[3] + 0.01), CHORD_FRACS[5] - 0.01)
    return fr


def y_lower(az: float) -> float:
    """Flat boat underside at |z| = az."""
    return _lerp(Y_LOWER_ROOT, Y_LOWER_TIP, _span_t(az))


def _section(az: float) -> list[tuple[float, float, float]]:
    """Closed loop at |z| = az: (x, y, chord_frac), upper LE→TE then lower TE→LE.

    Flat-bottomed: all camber lives in the upper surface so the underside stays
    coplanar with the tiled boat.
    """
    t = _span_t(az)
    y_lo = y_lower(az)
    t_max = _lerp(T_MAX_ROOT, T_MAX_TIP, t)
    t_te = _lerp(T_TE_ROOT, T_TE_TIP, t)
    le = x_le(az)
    chord = X_TE - le
    fracs = _chord_fracs(az)

    def thickness(i: int) -> float:
        mult = THICK_MULT[i]
        return t_te if mult is None else t_max * mult

    loop: list[tuple[float, float, float]] = []
    for i, f in enumerate(fracs):
        loop.append((le + chord * f, y_lo + thickness(i), f))
    for i in range(len(fracs) - 1, -1, -1):
        loop.append((le + chord * fracs[i], y_lo, fracs[i]))
    return loop


def _elevon_section(az: float) -> list[tuple[float, float, float]]:
    """4-point loop: LE-upper, TE-upper, TE-lower, LE-lower (flat underside)."""
    t = _span_t(az)
    y_lo = y_lower(az)
    t_le = _lerp(T_TE_ROOT, T_TE_TIP, t)
    x_te = _lerp(X_ELEVON_TE_ROOT, X_ELEVON_TE_TIP, t)
    return [
        (X_ELEVON_LE, y_lo + t_le, 0.0),
        (x_te, y_lo + T_ELEVON_TE, 1.0),
        (x_te, y_lo, 1.0),
        (X_ELEVON_LE, y_lo, 0.0),
    ]


def _uv(chord_frac: float, span_frac: float, light: bool) -> tuple[float, float]:
    if light:
        return (
            _lerp(LIGHT_U0, LIGHT_U1, chord_frac),
            _lerp(LIGHT_V0, LIGHT_V1, span_frac),
        )
    return (
        _lerp(DARK_U0, DARK_U1, chord_frac),
        _lerp(DARK_V0, DARK_V1, span_frac),
    )


class Shell:
    """Accumulates verts/faces for one generated object."""

    def __init__(self) -> None:
        self.verts: list[tuple[float, float, float]] = []
        self.faces: list[tuple[list[int], list[tuple[float, float]]]] = []

    def add_vert(self, x: float, y: float, z: float) -> int:
        self.verts.append((x, y, z))
        return len(self.verts) - 1

    def add_face(self, idx: list[int], uvs: list[tuple[float, float]], pivot) -> None:
        """Append a face, orienting its winding away from `pivot`."""
        p0, p1, p2 = (self.verts[i] for i in idx[:3])
        ux, uy, uz = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
        vx, vy, vz = (p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2])
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        cx = sum(self.verts[i][0] for i in idx) / len(idx)
        cy = sum(self.verts[i][1] for i in idx) / len(idx)
        cz = sum(self.verts[i][2] for i in idx) / len(idx)
        if (cx - pivot[0]) * nx + (cy - pivot[1]) * ny + (cz - pivot[2]) * nz < 0.0:
            idx = list(reversed(idx))
            uvs = list(reversed(uvs))
        self.faces.append((list(idx), list(uvs)))

    def to_ac(self, name: str) -> list[str]:
        out = ["OBJECT poly\n", f'name "{name}"\n', f'texture "{TEXTURE}"\n', "texrep 1 1\n"]
        out.append(f"numvert {len(self.verts)}\n")
        for x, y, z in self.verts:
            out.append(f"{x:.6f} {y:.6f} {z:.6f}\n")
        out.append(f"numsurf {len(self.faces)}\n")
        for idx, uvs in self.faces:
            out.append("SURF 0X30\n")  # shaded, two-sided
            out.append("mat 0\n")
            out.append(f"refs {len(idx)}\n")
            for i, (u, v) in zip(idx, uvs):
                out.append(f"{i} {u:.6f} {v:.6f}\n")
        out.append("kids 0\n")
        return out


def _build_lofted_shell(
    stations: list[float],
    section_fn,
    side: int,
    light_segments: set[int],
    skip=None,
) -> Shell:
    """Loft a closed shell through `stations` (|z| values) mirrored by `side` (+1/-1).

    `skip(seg, az0, az1)` may veto individual quads, e.g. to open a gear well.
    """
    shell = Shell()
    rings: list[list[int]] = []
    ring_data: list[list[tuple[float, float, float]]] = []
    for az in stations:
        loop = section_fn(az)
        ring_data.append(loop)
        rings.append([shell.add_vert(x, y, side * az) for x, y, _f in loop])

    n_loop = len(rings[0])
    for s in range(len(stations) - 1):
        az0, az1 = stations[s], stations[s + 1]
        sf0, sf1 = _span_t(az0), _span_t(az1)
        pivot0 = _section_centroid(ring_data[s], side * az0)
        pivot1 = _section_centroid(ring_data[s + 1], side * az1)
        pivot = tuple((a + b) / 2.0 for a, b in zip(pivot0, pivot1))
        for k in range(n_loop):
            k2 = (k + 1) % n_loop
            if skip is not None and skip(k, az0, az1):
                continue
            light = k in light_segments
            idx = [rings[s][k], rings[s][k2], rings[s + 1][k2], rings[s + 1][k]]
            uvs = [
                _uv(ring_data[s][k][2], sf0, light),
                _uv(ring_data[s][k2][2], sf0, light),
                _uv(ring_data[s + 1][k2][2], sf1, light),
                _uv(ring_data[s + 1][k][2], sf1, light),
            ]
            shell.add_face(idx, uvs, pivot)

    # End caps: root rib is buried in the body, tip rib closes the shell.
    for s, az in ((0, stations[0]), (len(stations) - 1, stations[-1])):
        centre = _section_centroid(ring_data[s], side * az)
        inboard = (centre[0], centre[1], side * (az - 1.0 if s else az + 1.0))
        sf = _span_t(az)
        idx = list(rings[s])
        uvs = [_uv(p[2], sf, False) for p in ring_data[s]]
        shell.add_face(idx, uvs, inboard)
    return shell


def _section_centroid(loop, z: float) -> tuple[float, float, float]:
    cx = sum(p[0] for p in loop) / len(loop)
    cy = sum(p[1] for p in loop) / len(loop)
    return (cx, cy, z)


def _lower_point(az: float, idx: int) -> tuple[float, float]:
    """(x, y) on the wing lower surface at span |z| = az and loop station `idx`."""
    loop = _section(az)
    n = len(CHORD_FRACS)
    lower = loop[n + (n - 1 - idx)]
    return lower[0], lower[1]


def _add_gear_well(shell: Shell, side: int) -> None:
    """Box out the main gear bay so the tiled door reads as a panel in a recess."""
    z0, z1 = WELL_Z_INNER, WELL_Z_OUTER
    # Lower-surface opening boundary runs through the intermediate loop station.
    idxs = (WELL_IDX_FWD, WELL_IDX_MID, WELL_IDX_AFT)
    pivot = (
        0.5 * (WELL_X_FWD + WELL_X_AFT),
        WELL_CEIL_Y + 1.0,  # above the bay, so walls wind facing inwards
        side * 0.5 * (z0 + z1),
    )

    def wall(pa, pb, za, zb) -> None:
        a = shell.add_vert(pa[0], pa[1], side * za)
        b = shell.add_vert(pb[0], pb[1], side * zb)
        c = shell.add_vert(pb[0], WELL_CEIL_Y, side * zb)
        d = shell.add_vert(pa[0], WELL_CEIL_Y, side * za)
        uvs = [_uv(f, s, False) for f, s in ((0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8))]
        shell.add_face([a, b, c, d], uvs, pivot)

    # Inboard / outboard ribs follow the opening outline (two panels each).
    for az in (z0, z1):
        for ia, ib in zip(idxs, idxs[1:]):
            wall(_lower_point(az, ia), _lower_point(az, ib), az, az)
    # Fore / aft walls run spanwise along the well edges.
    for idx in (WELL_IDX_FWD, WELL_IDX_AFT):
        wall(_lower_point(z0, idx), _lower_point(z1, idx), z0, z1)

    # Bay roof.
    roof = []
    for az, idx in ((z0, WELL_IDX_FWD), (z0, WELL_IDX_AFT), (z1, WELL_IDX_AFT), (z1, WELL_IDX_FWD)):
        x, _y = _lower_point(az, idx)
        roof.append(shell.add_vert(x, WELL_CEIL_Y, side * az))
    uvs = [_uv(f, s, False) for f, s in ((0.3, 0.3), (0.7, 0.3), (0.7, 0.7), (0.3, 0.7))]
    shell.add_face(roof, uvs, (pivot[0], WELL_CEIL_Y - 2.0, pivot[2]))


def build_wing_objects() -> dict[str, list[str]]:
    outer = [
        WELL_Z_OUTER + (Z_TIP - WELL_Z_OUTER) * (i + 1) / SPAN_OUTER_STATIONS
        for i in range(SPAN_OUTER_STATIONS)
    ]
    stations = [Z_ROOT, WELL_Z_INNER, WELL_Z_OUTER] + outer
    # Upper surface aft of the RCC leading-edge wrap is white LRSI; the wrap,
    # the trailing edge and the whole underside stay black HRSI like the boat.
    light = set(range(1, len(CHORD_FRACS) - 1))
    # Lower-surface quads spanning the gear well are omitted (see CHORD_FRACS).
    well_segments = {
        len(CHORD_FRACS) + 2,  # 0.420 → 0.18
        len(CHORD_FRACS) + 3,  # 0.18  → 0.112
    }

    def skip(seg: int, az0: float, az1: float) -> bool:
        return seg in well_segments and az0 >= WELL_Z_INNER - 0.01 and az1 <= WELL_Z_OUTER + 0.01

    out: dict[str, list[str]] = {}
    for name, side in zip(WING_OBJECT_NAMES, (1, -1)):
        shell = _build_lofted_shell(stations, _section, side, light, skip=skip)
        _add_gear_well(shell, side)
        out[name] = shell.to_ac(name)
    return out


def build_elevon_objects() -> dict[str, list[str]]:
    spans = {
        "inboard": (Z_ELEVON_ROOT, Z_ELEVON_SPLIT - ELEVON_SEAM),
        "outboard": (Z_ELEVON_SPLIT + ELEVON_SEAM, Z_TIP),
    }
    out: dict[str, list[str]] = {}
    for kind, (z0, z1) in spans.items():
        for hand, side in (("left", 1), ("right", -1)):
            name = f"{kind}-elevon-{hand}"
            # Loop order is upper, TE, lower, LE — only the upper face is white.
            shell = _build_lofted_shell([z0, z1], _elevon_section, side, {0})
            out[name] = shell.to_ac(name)
    return out


def planform_area() -> float:
    """Reference area (both sides incl. elevons + body carry-through), m²."""

    def trapezoid(x_fwd, x_aft, z0, z1) -> float:
        c0 = x_aft(z0) - x_fwd(z0)
        c1 = x_aft(z1) - x_fwd(z1)
        return 0.5 * (c0 + c1) * (z1 - z0)

    def elevon_te(az: float) -> float:
        return _lerp(X_ELEVON_TE_ROOT, X_ELEVON_TE_TIP, _span_t(az))

    exposed = trapezoid(x_le, lambda z: X_TE, Z_ROOT, Z_TIP)
    flap = trapezoid(lambda z: X_TE, elevon_te, Z_ROOT, Z_TIP)
    carry = 2.0 * Z_ROOT * (elevon_te(Z_ROOT) - x_le(Z_ROOT))
    return 2.0 * (exposed + flap) + carry


# --- AC file surgery --------------------------------------------------------


def _split_objects(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    """Return (header lines through world 'kids', list of top-level object blocks)."""
    head_end = None
    for i, line in enumerate(lines):
        if line.startswith("kids "):
            head_end = i
            break
    if head_end is None:
        raise SystemExit("no world kids line found")
    header = lines[: head_end + 1]
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in lines[head_end + 1 :]:
        if line.startswith("OBJECT "):
            if current is not None:
                blocks.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        blocks.append(current)
    return header, blocks


def _block_name(block: list[str]) -> str:
    for line in block:
        if line.startswith("name "):
            return line.split('"')[1] if '"' in line else line.split()[1].strip()
    return ""


def _in_gear_bay(pts) -> bool:
    """True if a face sits inside the main gear bay opening (either side)."""
    cx = sum(p[0] for p in pts) / len(pts)
    cz = abs(sum(p[2] for p in pts) / len(pts))
    return (
        WELL_X_FWD - 0.15 <= cx <= WELL_X_AFT + 0.15
        and WELL_Z_INNER - 0.15 <= cz <= WELL_Z_OUTER + 0.15
    )


def _strip_wing_surfaces(block: list[str]) -> tuple[list[str], int]:
    """Drop surfaces that lie outboard of the body wall at wing level."""
    verts: list[tuple[float, float, float]] = []
    i = 0
    pre: list[str] = []
    while i < len(block):
        line = block[i]
        pre.append(line)
        if line.startswith("numvert"):
            nv = int(line.split()[1])
            i += 1
            for _ in range(nv):
                p = block[i].split()
                verts.append((float(p[0]), float(p[1]), float(p[2])))
                pre.append(block[i])
                i += 1
            continue
        if line.startswith("numsurf"):
            pre.pop()
            break
        i += 1
    else:
        return block, 0

    n_surf = int(block[i].split()[1])
    i += 1
    surfaces: list[tuple[list[str], list[int]]] = []
    for _ in range(n_surf):
        surf_lines = [block[i]]  # SURF
        i += 1
        while i < len(block) and not block[i].startswith("refs"):
            surf_lines.append(block[i])
            i += 1
        n_refs = int(block[i].split()[1])
        surf_lines.append(block[i])
        i += 1
        refs = []
        for _ in range(n_refs):
            refs.append(int(block[i].split()[0]))
            surf_lines.append(block[i])
            i += 1
        surfaces.append((surf_lines, refs))
    tail = block[i:]

    kept: list[tuple[list[str], list[int]]] = []
    dropped = 0
    for surf_lines, refs in surfaces:
        pts = [verts[r] for r in refs if r < len(verts)]
        if not pts:
            kept.append((surf_lines, refs))
            continue
        if max(abs(p[2]) for p in pts) >= 3.55 and max(p[1] for p in pts) <= -3.40:
            dropped += 1  # old glove / strake skin
            continue
        if max(p[1] for p in pts) <= -4.90 and _in_gear_bay(pts):
            dropped += 1  # boat panel across the gear bay opening
            continue
        kept.append((surf_lines, refs))

    out = list(pre)
    out.append(f"numsurf {len(kept)}\n")
    for surf_lines, _refs in kept:
        out.extend(surf_lines)
    out.extend(tail)
    return out, dropped


def install_delta_wing(path: Path) -> None:
    lines = path.read_text(errors="ignore").splitlines(keepends=True)
    header, blocks = _split_objects(lines)

    wing_blocks = build_wing_objects()
    elevon_blocks = build_elevon_objects()

    new_blocks: list[list[str]] = []
    dropped_total = 0
    for block in blocks:
        name = _block_name(block)
        if name in WING_SKIN_OBJECTS:
            block, dropped = _strip_wing_surfaces(block)
            dropped_total += dropped
            new_blocks.append(block)
        elif name in ELEVON_OBJECTS:
            new_blocks.append(elevon_blocks[name])
        else:
            new_blocks.append(block)

    for name in WING_OBJECT_NAMES:
        new_blocks.append(wing_blocks[name])

    for i, line in enumerate(header):
        if line.startswith("kids "):
            header[i] = f"kids {len(new_blocks)}\n"
            break

    out = list(header)
    for block in new_blocks:
        out.extend(block)
    path.write_text("".join(out))

    print(
        f"delta wing installed: dropped {dropped_total} OV wing-skin surfaces, "
        f"added {len(WING_OBJECT_NAMES)} wing shells + rebuilt {len(ELEVON_OBJECTS)} elevons; "
        f"span {2 * Z_TIP:.1f} m, S≈{planform_area():.0f} m², "
        f"root chord {X_TE - X_LE_ROOT:.1f} m, tip chord {X_TE - X_LE_TIP:.1f} m"
    )


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "shuttle_o2_plan_a.ac"
    install_delta_wing(target)
