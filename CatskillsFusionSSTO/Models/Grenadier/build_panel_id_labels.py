#!/usr/bin/env python3
"""Build magenta installer ID + purpose labels for live Grenadier cockpit panels.

Reads panel plate bounds from cockpit.ac / cockpit-detailed.ac, writes
grenadier_panel_id_labels.ac (+ textures) sized as a header strip on each
panel face so switchgear is not covered.
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "Models"
OUT = Path(__file__).resolve().parent
TEX = OUT / "textures" / "panel_id"

# Live Grenadier plates only (blanked A12/A14/O2 omitted).
PANELS: dict[str, str] = {
    "F1": "CDR caution & warning",
    "F2": "CDR flight instruments",
    "F3": "Center instruments / SPI",
    "F4": "PLT flight instruments",
    "F5": "PLT caution & warning",
    "F6": "CDR HUD",
    "F7": "Center glareshield annunciators",
    "F8": "PLT HUD",
    "F9": "Center air-data gauges",
    "L1": "CDR inboard MDU",
    "L2": "CDR outboard MDU",
    "L4": "Left circuit breakers",
    "L9": "Aft-left cabin lighting",
    "L10": "Left connector / utility",
    "L11": "Left mid-aft switches",
    "L12": "Left talkbacks / status",
    "R1": "PLT inboard MDU",
    "R2": "PLT MDU + CHARM plant row",
    "R4": "Brake isolation valves",
    "R7": "Right circuit breakers",
    "R10": "Aft-right cabin lighting",
    "R11": "Aft MDU + keypad",
    "R12": "Right aft systems / comm",
    "R13": "Right aft systems",
    "R14": "Right aft breakers",
    "C2": "CRT/IDP keyboards",
    "C3": "STAGE ± / SCRAM",
    "C4": "Center MDU",
    "C5": "Center MDU",
    "C6": "Gear / NWS / brakes",
    "C7": "Speedbrake / body flap",
    "O1": "GPC status / COAS",
    "O3": "Electrical / event timer",
    "O4": "Overhead panel lighting",
    "O5": "Communications (left ovhd)",
    "O6": "GPC power + left lighting",
    "O7": "ECLSS / cabin atmosphere",
    "O8": "Right lighting + ECLSS",
    "O9": "Communications / antennas",
    "O10": "Overhead flood lighting",
    "O13": "Overhead circuit breakers",
    "O14": "Overhead systems / breakers",
    "O15": "Overhead systems / breakers",
    "O16": "Overhead systems / breakers",
    "O17": "Overhead ATCS / water",
    "O19": "Aft COAS mount",
    "A1": "Audio / communications",
    "A2": "Aft THC",
    "A3": "CCTV monitors",
    "A4": "Mission / event timers",
    "A6": "Aft MDU + lighting + THC",
    "A7": "Aft RHC station",
    "A8": "Aft flight-control RHC",
    "A11": "Payload bay / door switches",
    "A13": "Propellant / heater controls",
    "A15": "Aft circuit breakers",
}

# Mesh object name overrides (default "{ID}-panel").
MESH_NAME = {
    "O19": "O19-coas-panel",
}


def parse_ac_objects(path: Path) -> dict[str, list[tuple[float, float, float]]]:
    text = path.read_text(errors="replace").splitlines()
    objs: dict[str, list[tuple[float, float, float]]] = {}
    i = 0
    while i < len(text):
        if not text[i].startswith("OBJECT poly"):
            i += 1
            continue
        name = None
        verts: list[tuple[float, float, float]] = []
        loc = (0.0, 0.0, 0.0)
        i += 1
        while i < len(text) and not text[i].startswith("OBJECT "):
            if text[i].startswith("name "):
                name = text[i].split(" ", 1)[1].strip().strip('"')
            elif text[i].startswith("loc "):
                loc = tuple(map(float, text[i].split()[1:4]))  # type: ignore[assignment]
            elif text[i].startswith("numvert "):
                n = int(text[i].split()[1])
                i += 1
                for _ in range(n):
                    x, y, z = map(float, text[i].split()[:3])
                    verts.append((x + loc[0], y + loc[1], z + loc[2]))
                    i += 1
                continue
            i += 1
        if name and verts:
            objs[name] = verts
    return objs


def load_panels() -> dict[str, list[tuple[float, float, float]]]:
    merged: dict[str, list[tuple[float, float, float]]] = {}
    for ac in (MODELS / "cockpit.ac", MODELS / "cockpit-detailed.ac"):
        if not ac.is_file():
            continue
        for name, verts in parse_ac_objects(ac).items():
            merged[name] = verts
    return merged


def write_magenta_label(path: Path, panel_id: str, purpose: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    w, h = 768, 192
    # Magenta plate, white text — high contrast in dim cockpit
    bg = (220, 0, 180)
    fg = (255, 255, 255)
    im = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(im)
    try:
        font_id = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64
        )
        font_p = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36
        )
    except OSError:
        font_id = font_p = ImageFont.load_default()

    line1 = panel_id
    line2 = purpose
    # Shrink purpose until it fits
    for size in (36, 30, 26, 22, 18):
        try:
            font_p = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size
            )
        except OSError:
            break
        bbox = draw.textbbox((0, 0), line2, font=font_p)
        if bbox[2] - bbox[0] <= w - 40:
            break

    b1 = draw.textbbox((0, 0), line1, font=font_id)
    b2 = draw.textbbox((0, 0), line2, font=font_p)
    tw1, th1 = b1[2] - b1[0], b1[3] - b1[1]
    tw2, th2 = b2[2] - b2[0], b2[3] - b2[1]
    gap = 10
    total_h = th1 + gap + th2
    y0 = (h - total_h) / 2 - 4
    draw.text(((w - tw1) / 2, y0), line1, fill=fg, font=font_id)
    draw.text(((w - tw2) / 2, y0 + th1 + gap), line2, fill=fg, font=font_p)
    # Thin white border so plate reads against panel paint
    draw.rectangle((2, 2, w - 3, h - 3), outline=(255, 255, 255), width=4)
    im.save(path)


def face_label_quad(
    panel_id: str,
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
    zmin: float,
    zmax: float,
    *,
    margin: float = 0.04,
    strip_frac: float = 0.14,
    lift: float = 0.012,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]], list[list[tuple[float, float]]]]:
    """Header-strip quad on the crew-facing side of the panel AABB."""
    dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin
    # Keep strip thin so switches below stay clear
    strip = max(0.035, min(0.11, max(dy, dz, dx) * strip_frac))
    pad = margin

    letter = panel_id[0]
    # Outward / crew-facing placement by station
    if letter == "F":
        # Glare / forward: face crew (+X aft of panel)
        x = xmax + lift
        z0, z1 = zmin + pad * dz, zmax - pad * dz
        y1 = ymax - pad * dy
        y0 = y1 - strip
        verts = [(x, y0, z0), (x, y0, z1), (x, y1, z1), (x, y1, z0)]
    elif letter == "A":
        # Aft station: face crew (−X)
        x = xmin - lift
        z0, z1 = zmin + pad * dz, zmax - pad * dz
        y1 = ymax - pad * dy
        y0 = y1 - strip
        verts = [(x, y0, z1), (x, y0, z0), (x, y1, z0), (x, y1, z1)]
    elif letter == "L":
        # Left wall (+Z port): face cabin (−Z)
        z = zmin - lift
        x0, x1 = xmin + pad * dx, xmax - pad * dx
        y1 = ymax - pad * dy
        y0 = y1 - strip
        # If panel is nearly horizontal (thin Y), put strip on top face instead
        if dy < 0.20 and dx > dy and dz > dy:
            y = ymax + lift
            z0, z1 = zmin + pad * dz, zmax - pad * dz
            # strip along forward edge of top face
            x1s = xmin + pad * dx + max(0.04, dx * 0.18)
            x0s = xmin + pad * dx
            verts = [(x0s, y, z0), (x1s, y, z0), (x1s, y, z1), (x0s, y, z1)]
        else:
            verts = [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]
    elif letter == "R":
        # Right wall (−Z): face cabin (+Z)
        z = zmax + lift
        x0, x1 = xmin + pad * dx, xmax - pad * dx
        y1 = ymax - pad * dy
        y0 = y1 - strip
        if dy < 0.20 and dx > dy and dz > dy:
            y = ymax + lift
            z0, z1 = zmin + pad * dz, zmax - pad * dz
            x1s = xmin + pad * dx + max(0.04, dx * 0.18)
            x0s = xmin + pad * dx
            verts = [(x0s, y, z0), (x1s, y, z0), (x1s, y, z1), (x0s, y, z1)]
        else:
            verts = [(x1, y0, z), (x0, y0, z), (x0, y1, z), (x1, y1, z)]
    elif letter == "O":
        # Overhead: face down (−Y), strip along forward (−X) edge
        y = ymin - lift
        x0 = xmin + pad * dx
        x1 = x0 + max(0.05, min(dx * 0.22, 0.16))
        z0, z1 = zmin + pad * dz, zmax - pad * dz
        verts = [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]
    else:
        # Center console C*: face up (+Y), strip along aft or forward edge
        y = ymax + lift
        # Prefer forward edge of console (more negative X)
        x0 = xmin + pad * dx
        x1 = x0 + max(0.05, min(dx * 0.20, 0.14))
        z0, z1 = zmin + pad * dz, zmax - pad * dz
        verts = [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]

    # Width along the longer in-plane span — shrink if strip would dominate
    faces = [(0, 1, 2, 3)]
    uvs = [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]]
    return verts, faces, uvs


def write_ac(
    path: Path,
    objects: list[dict],
) -> None:
    # Emissive magenta so labels stay readable under cabin lighting
    lines = [
        "AC3Db",
        'MATERIAL "panel-id-magenta" rgb 0.90 0.00 0.75  '
        "amb 0.40 0.40 0.40  emis 0.55 0.05 0.45  "
        "spec 0.20 0.20 0.20  shi 20  trans 0.00",
        "OBJECT world",
        'name "grenadier_panel_id_labels"',
        f"kids {len(objects)}",
    ]
    for obj in objects:
        lines.append("OBJECT poly")
        lines.append(f'name "{obj["name"]}"')
        lines.append("loc 0 0 0")
        lines.append(f'texture "{obj["texture"]}"')
        lines.append("texrep 1 1")
        lines.append("crease 40.0")
        lines.append(f"numvert {len(obj['verts'])}")
        for x, y, z in obj["verts"]:
            lines.append(f"{x:.6f} {y:.6f} {z:.6f}")
        lines.append("numsurf 1")
        lines.append("SURF 0x30")
        lines.append("mat 0")
        lines.append("refs 4")
        for idx, (u, vv) in zip(obj["faces"][0], obj["uvs"][0]):
            lines.append(f"{idx} {u:.6f} {vv:.6f}")
        lines.append("kids 0")
    path.write_text("\n".join(lines) + "\n")


def write_xml(path: Path, object_names: list[str]) -> None:
    lines = [
        '<?xml version="1.0"?>',
        "<!-- Magenta installer ID labels for Grenadier live panels. -->",
        "<PropertyList>",
        "  <path>Aircraft/CatskillsFusionSSTO/Models/Grenadier/grenadier_panel_id_labels.ac</path>",
        "  <effect>",
        "    <inherits-from>Aircraft/CatskillsFusionSSTO/Models/Effects/shuttle-main</inherits-from>",
    ]
    for n in object_names:
        lines.append(f"    <object-name>{n}</object-name>")
    lines += [
        "  </effect>",
        "</PropertyList>",
        "",
    ]
    path.write_text("\n".join(lines))


def main() -> None:
    meshes = load_panels()
    objects = []
    names = []
    missing = []
    for pid, purpose in PANELS.items():
        mesh = MESH_NAME.get(pid, f"{pid}-panel")
        verts = meshes.get(mesh)
        if not verts:
            # A2 has no -panel; use A2-base if present
            alt = f"{pid}-base"
            verts = meshes.get(alt)
            mesh = alt if verts else mesh
        if not verts:
            # A3 is CTVM units — union any "{ID}-*" mesh verts
            pref = f"{pid}-"
            bundle = []
            for n, vv in meshes.items():
                if n.startswith(pref):
                    bundle.extend(vv)
            verts = bundle
        if not verts:
            missing.append(pid)
            continue
        xs = [p[0] for p in verts]
        ys = [p[1] for p in verts]
        zs = [p[2] for p in verts]
        tex_name = f"panel_id_{pid}.png"
        write_magenta_label(TEX / tex_name, pid, purpose)
        qv, qf, quv = face_label_quad(
            pid, min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)
        )
        obj_name = f"panel-id-{pid}"
        objects.append(
            dict(
                name=obj_name,
                verts=qv,
                faces=qf,
                uvs=quv,
                texture=f"textures/panel_id/{tex_name}",
            )
        )
        names.append(obj_name)

    ac_path = OUT / "grenadier_panel_id_labels.ac"
    xml_path = OUT / "grenadier_panel_id_labels.xml"
    write_ac(ac_path, objects)
    write_xml(xml_path, names)
    print(f"wrote {ac_path} ({len(objects)} labels)")
    print(f"wrote {xml_path}")
    if missing:
        print("MISSING mesh for:", ", ".join(missing))


if __name__ == "__main__":
    main()
