#!/usr/bin/env python3
"""Stamp magenta panel ID/purpose text into the cockpit texture atlases.

This uses the same method as the original Shuttle lettering: pixels in
fwd-cockpit-text-map-x.png and aft-cockpit-text-map-x.png.  It creates no
extra geometry, background plaque, or white lettering.

For each live panel, the script:
  1. extracts the crew-facing UV polygons from the AC mesh;
  2. finds a low-detail blank patch near a polygon edge;
  3. stamps one small line of magenta text at the original engraving scale.

Backups are made once as *.bak_pre_panel_ids and restored before every build.
Run after scripts/stamp_grenadier_apu_labels.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "Models"
FWD = MODELS / "fwd-cockpit-text-map-x.png"
AFT = MODELS / "aft-cockpit-text-map-x.png"
MAGENTA = (255, 0, 210)

# Short enough to read like existing panel-edge engraving.
PANELS: dict[str, str] = {
    "F1": "CDR C&W",
    "F2": "CDR FLIGHT INST",
    "F3": "CENTER SPI",
    "F4": "PLT FLIGHT INST",
    "F5": "C&W",
    "F6": "CDR HUD",
    "F7": "GLARESHIELD",
    "F8": "PLT HUD",
    "F9": "AIR DATA",
    "L1": "THERMAL / CABIN FANS",
    "L2": "CABIN AIR / O2 / N2",
    "L4": "BRK",
    "L9": "AFT-L LIGHTS",
    "L10": "UTIL",
    "L11": "SW",
    "L12": "L TALKBACKS",
    "R2": "CHARM PLANT / PROP",
    "R4": "BRK ISOL",
    "R7": "BRK",
    "R10": "LIGHT",
    "R11": "AFT MDU",
    "R12": "R AFT / COMM",
    "R13": "R AFT SYS",
    "R14": "R AFT BREAKERS",
    "C2": "CRT KEYBOARDS",
    "C3": "STAGE / SCRAM",
    "C4": "MDU",
    "C5": "MDU",
    "C6": "GEAR/NWS",
    "C7": "SPDBK/BF",
    "O1": "CABIN AIR GAUGES",
    "O2": "CRYO TANK GAUGES",
    "O3": "ELEC / TIMER",
    "O4": "LIGHT",
    "O5": "COMM L",
    "O6": "GPC PWR / L LIT",
    "O7": "ECLSS",
    "O8": "R LIT / ECLSS",
    "O9": "COMM / ANT",
    "O10": "OVHD FLOOD",
    "O13": "OVHD BREAKERS",
    "O14": "OVHD SYSTEMS",
    "O15": "OVHD SYSTEMS",
    "O16": "OVHD SYSTEMS",
    "O17": "ATCS / WATER",
    "O19": "AFT COAS",
    "A1": "AUDIO / COMM",
    "A2": "AFT THC",
    "A3": "CCTV",
    "A4": "TIMERS",
    "A6": "AFT MDU / THC",
    "A7": "AFT RHC",
    "A8": "AFT RHC",
    "A11": "BAY DOORS",
    "A13": "PROP HEATERS",
    "A15": "AFT BREAKERS",
}

MESH_NAME = {"O19": "O19-coas-panel"}

# Tiny or heavily split UV islands where automatic edge search cannot fit a
# continuous rectangle. These coordinates were measured on the pristine
# 4096² atlas and are blank panel-edge pixels (not existing legends).
# value: (texture, x, y, compact)
MANUAL_STAMPS: dict[str, tuple[str, int, int, bool]] = {
    "F5": (FWD.name, 562, 350, True),
    "L4": (FWD.name, 45, 1555, False),
    "R4": (FWD.name, 2700, 2530, False),
    "R7": (FWD.name, 40, 2045, False),
    "C4": (FWD.name, 221, 444, True),
    "C5": (FWD.name, 221, 473, True),
    "C6": (FWD.name, 2020, 1375, False),
    "C7": (FWD.name, 2030, 1557, False),
}


@dataclass
class Face:
    refs: list[tuple[int, float, float]]


@dataclass
class Mesh:
    texture: str | None
    verts: list[tuple[float, float, float]]
    faces: list[Face]


def _font(size: int) -> ImageFont.ImageFont:
    for fp in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ):
        try:
            return ImageFont.truetype(fp, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _parse_ac(path: Path) -> dict[str, Mesh]:
    lines = path.read_text(errors="replace").splitlines()
    out: dict[str, Mesh] = {}
    i = 0
    while i < len(lines):
        if not lines[i].startswith("OBJECT poly"):
            i += 1
            continue
        name: str | None = None
        texture: str | None = None
        verts: list[tuple[float, float, float]] = []
        faces: list[Face] = []
        loc = (0.0, 0.0, 0.0)
        i += 1
        while i < len(lines) and not lines[i].startswith("OBJECT "):
            line = lines[i]
            if line.startswith("name "):
                name = line.split(" ", 1)[1].strip().strip('"')
            elif line.startswith("texture "):
                texture = line.split(" ", 1)[1].strip().strip('"')
            elif line.startswith("loc "):
                loc = tuple(map(float, line.split()[1:4]))  # type: ignore[assignment]
            elif line.startswith("numvert "):
                count = int(line.split()[1])
                i += 1
                for _ in range(count):
                    x, y, z = map(float, lines[i].split()[:3])
                    verts.append((x + loc[0], y + loc[1], z + loc[2]))
                    i += 1
                continue
            elif line.startswith("refs "):
                count = int(line.split()[1])
                i += 1
                refs: list[tuple[int, float, float]] = []
                for _ in range(count):
                    fields = lines[i].split()
                    refs.append((int(fields[0]), float(fields[1]), float(fields[2])))
                    i += 1
                faces.append(Face(refs))
                continue
            i += 1
        if name and verts and faces:
            out[name] = Mesh(texture, verts, faces)
    return out


def _load_meshes() -> dict[str, Mesh]:
    result: dict[str, Mesh] = {}
    for path in (MODELS / "cockpit.ac", MODELS / "cockpit-detailed.ac"):
        result.update(_parse_ac(path))
    return result


def _cross(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.cross(a, b)


def _crew_uv_polygons(panel_id: str, mesh: Mesh, size: tuple[int, int]) -> list[list[tuple[int, int]]]:
    width, height = size
    # Approximate eye point in the flight-deck cabin. This works for sloped
    # overhead/forward plates too: retain faces whose normals point inward
    # toward the crew, rather than assuming every O panel is horizontal.
    cabin = np.array((-11.7, -0.7, 0.0))
    polygons: list[list[tuple[int, int]]] = []
    for face in mesh.faces:
        if len(face.refs) < 3:
            continue
        points = np.asarray([mesh.verts[ref[0]] for ref in face.refs])
        normal = _cross(points[1] - points[0], points[2] - points[0])
        norm = float(np.linalg.norm(normal))
        to_cabin = cabin - points.mean(axis=0)
        cabin_distance = float(np.linalg.norm(to_cabin))
        if (
            norm == 0
            or cabin_distance == 0
            or float(np.dot(normal / norm, to_cabin / cabin_distance)) < 0.25
        ):
            continue
        polygon = [
            (
                int(round(u * (width - 1))),
                int(round((1.0 - v) * (height - 1))),
            )
            for _, u, v in face.refs
        ]
        # Ignore wrapped/repeated UV islands outside this atlas.
        if all(0 <= x < width and 0 <= y < height for x, y in polygon):
            polygons.append(polygon)
    return polygons


def _mesh_for_panel(panel_id: str, meshes: dict[str, Mesh]) -> Mesh | None:
    name = MESH_NAME.get(panel_id, f"{panel_id}-panel")
    if name in meshes:
        return meshes[name]
    if f"{panel_id}-base" in meshes:
        return meshes[f"{panel_id}-base"]
    # A3 is two CTVM units rather than one named plate; use the first face set.
    candidates = [mesh for name, mesh in meshes.items() if name.startswith(f"{panel_id}-")]
    return candidates[0] if candidates else None


def _backup(path: Path) -> Path:
    backup = path.with_name(path.name + ".bak_pre_panel_ids")
    if not backup.exists():
        Image.open(path).save(backup, format="PNG")
        print(f"wrote {backup.name}")
    return backup


def _text_size(text: str) -> tuple[ImageFont.ImageFont, int, int]:
    # Existing secondary cockpit legends are about 7–8 px on this 4096 atlas.
    # Keep these identifiers subordinate to the original control lettering.
    for size in (8, 7, 6):
        font = _font(size)
        box = font.getbbox(text)
        width, height = box[2] - box[0], box[3] - box[1]
        if width <= 115:
            return font, width, height
    return font, width, height


def _label_bitmap(panel_id: str, purpose: str, *, compact: bool = False) -> Image.Image:
    """Transparent bitmap containing magenta letters only."""
    if compact:
        font = _font(6)
        lines = (panel_id, purpose)
    else:
        font, _, _ = _text_size(f"{panel_id}  {purpose}")
        lines = (f"{panel_id}  {purpose}",)
    boxes = [font.getbbox(line) for line in lines]
    widths = [box[2] - box[0] for box in boxes]
    heights = [box[3] - box[1] for box in boxes]
    gap = 1 if len(lines) > 1 else 0
    bitmap = Image.new("RGBA", (max(widths), sum(heights) + gap), (0, 0, 0, 0))
    draw = ImageDraw.Draw(bitmap)
    y = 0
    for line, width, height in zip(lines, widths, heights):
        draw.text(((bitmap.width - width) // 2, y), line, fill=(*MAGENTA, 255), font=font)
        y += height + gap
    return bitmap


def _find_blank_edge(
    image: Image.Image,
    polygons: list[list[tuple[int, int]]],
    text_width: int,
    text_height: int,
) -> tuple[int, int] | None:
    if not polygons:
        return None
    all_x = [x for polygon in polygons for x, _ in polygon]
    all_y = [y for polygon in polygons for _, y in polygon]
    # Letters have no plaque/background, so only a one-pixel safety margin is
    # needed. This lets tiny MDU and breaker edge islands carry compact IDs.
    pad_x, pad_y = 1, 1
    box_w, box_h = text_width + 2 * pad_x, text_height + 2 * pad_y
    x0 = max(0, min(all_x) - 2)
    y0 = max(0, min(all_y) - 2)
    x1 = min(image.width, max(all_x) + 3)
    y1 = min(image.height, max(all_y) + 3)
    if x1 - x0 < box_w or y1 - y0 < box_h:
        return None

    mask_img = Image.new("L", (x1 - x0, y1 - y0), 0)
    draw = ImageDraw.Draw(mask_img)
    for polygon in polygons:
        draw.polygon([(x - x0, y - y0) for x, y in polygon], fill=255)
    # Rasterized AC triangles can leave one-pixel seams even though the panel
    # is continuous. Close only those seams; do not expand beyond the panel.
    mask = ndimage.binary_closing(np.asarray(mask_img) > 0, structure=np.ones((3, 3)))

    # Candidate center must contain the whole text rectangle within the panel.
    inside_fraction = ndimage.uniform_filter(
        mask.astype(np.float32), size=(box_h, box_w), mode="constant"
    )
    # AC panel faces are often split into tightly packed UV islands. Permit
    # narrow seams between those islands; the text has no background, and
    # unmapped seam pixels simply do not render.
    valid = inside_fraction > 0.70
    if not np.any(valid):
        return None

    rgb = np.asarray(image.crop((x0, y0, x1, y1)).convert("RGB"), dtype=np.float32)
    gray = rgb.mean(axis=2)
    gx = ndimage.sobel(gray, axis=1, mode="nearest")
    gy = ndimage.sobel(gray, axis=0, mode="nearest")
    detail = np.hypot(gx, gy)
    local_detail = ndimage.uniform_filter(detail, size=(box_h, box_w), mode="nearest")

    # Prefer a quiet patch near a panel edge. Distance is measured inside the
    # exact UV polygon, so this selects edge margins without drawing off-panel.
    edge_distance = ndimage.distance_transform_edt(mask)
    score = local_detail + 0.12 * edge_distance
    score[~valid] = np.inf
    cy, cx = np.unravel_index(np.argmin(score), score.shape)
    if not np.isfinite(score[cy, cx]):
        return None
    return x0 + int(cx) - text_width // 2, y0 + int(cy) - text_height // 2


def main() -> None:
    meshes = _load_meshes()
    images: dict[str, Image.Image] = {}
    sources: dict[str, Path] = {}
    for path in (FWD, AFT):
        backup = _backup(path)
        images[path.name] = Image.open(backup).convert("RGB")
        sources[path.name] = path

    placed: list[str] = []
    skipped: list[str] = []
    positions: list[tuple[str, str, int, int]] = []
    for panel_id, purpose in PANELS.items():
        mesh = _mesh_for_panel(panel_id, meshes)
        if mesh is None or mesh.texture not in images:
            skipped.append(panel_id)
            continue
        image = images[mesh.texture]
        polygons = _crew_uv_polygons(panel_id, mesh, image.size)
        label = _label_bitmap(panel_id, purpose)
        position = _find_blank_edge(image, polygons, label.width, label.height)
        if position is None:
            label = _label_bitmap(panel_id, purpose, compact=True)
            position = _find_blank_edge(image, polygons, label.width, label.height)
        if position is None:
            # Narrow UV strips (notably breaker side plates) need the atlas
            # lettering rotated; the mesh UV rotates it back on the panel.
            label = _label_bitmap(panel_id, purpose, compact=True).rotate(90, expand=True)
            position = _find_blank_edge(image, polygons, label.width, label.height)
        if position is None:
            skipped.append(panel_id)
            continue
        x, y = position
        image.paste(label, (x, y), label)
        placed.append(panel_id)
        positions.append((panel_id, mesh.texture, x, y))

    # Explicit blank-edge locations for UV islands too small/fragmented for
    # the conservative automatic rectangle search.
    for panel_id in list(skipped):
        manual = MANUAL_STAMPS.get(panel_id)
        if manual is None:
            continue
        texture_name, x, y, compact = manual
        label = _label_bitmap(panel_id, PANELS[panel_id], compact=compact)
        images[texture_name].paste(label, (x, y), label)
        skipped.remove(panel_id)
        placed.append(panel_id)
        positions.append((panel_id, texture_name, x, y))

    for texture_name, image in images.items():
        image.save(sources[texture_name])
        print(f"wrote {sources[texture_name]}")
    print(f"placed {len(placed)} panel labels")
    for panel_id, texture, x, y in positions:
        print(f"  {panel_id:>3} {texture:<30} ({x:4d}, {y:4d})")
    if skipped:
        print("skipped (no safe blank edge):", ", ".join(skipped))


if __name__ == "__main__":
    main()
