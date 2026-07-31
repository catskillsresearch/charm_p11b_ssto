#!/usr/bin/env python3
"""Stamp bright-yellow panel ID/purpose text into the cockpit texture atlases.

Uses the same method as the original Shuttle lettering: pixels drawn into
fwd-cockpit-text-map-x.png and aft-cockpit-text-map-x.png with a regular
(not bold) DejaVu Sans face at the stock secondary-legend size (~9 px).
Color is bright yellow so the IDs stand out from white heritage engraving.

Placement rules (strict — skip rather than drape over controls):
  1. Extract crew-facing UV polygons for the panel mesh.
  2. Keep only large contiguous UV islands (real face plates). Tiny
     islands are usually switch/talkback UV patches and are ignored.
  3. Build a "safe blank" mask: mid-gray panel paint clear of legends.
  4. Stamp only when the entire text rectangle lies on safe rim pixels.

Tiny MDU doors (C4/C5) originally used ~26×25 atlas islands, which
upscaled into blurry cockpit smears. Those objects are UV-remapped onto
larger blank atlas patches before stamping so the lettering stays sharp.

Backups are made once as *.bak_pre_panel_ids and restored before every
build. Run after scripts/stamp_grenadier_apu_labels.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "Models"
COCKPIT_AC = MODELS / "cockpit.ac"
FWD = MODELS / "fwd-cockpit-text-map-x.png"
AFT = MODELS / "aft-cockpit-text-map-x.png"

# Bright yellow — same drawing path as stock white, different ink color.
YELLOW = (255, 220, 0)
# Stock secondary legends (ROLL / PITCH / AIR DATA) match ~9 px regular Sans.
STOCK_FONT_PX = 9

# Minimum UV island area (atlas pixels). Smaller patches are switch/gauge
# UV holes; stamping there drapes text over 3D hardware in the cockpit.
MIN_ISLAND_PX = 12_000

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

# Expand tiny door UVs onto blank atlas patches so stock-sized glyphs stay sharp.
# value: (texture path name, x0, y0, x1, y1) in atlas pixels.
UV_REMAPS: dict[str, tuple[str, int, int, int, int]] = {
    "C4-panel": (FWD.name, 1408, 16, 1568, 64),
    "C5-panel": (FWD.name, 1600, 16, 1760, 64),
}

# Measured blank-edge stamps for plates where automatic search still cannot
# find a continuous safe rectangle (tiny MDU faces, fragmented UVs).
# value: (texture, x, y, compact, rotate90)
MANUAL_STAMPS: dict[str, tuple[str, int, int, bool, bool]] = {
    "F5": (FWD.name, 562, 350, True, False),
    "L4": (FWD.name, 45, 1555, False, False),
    "R4": (FWD.name, 2700, 2530, False, False),
    "R7": (FWD.name, 40, 2045, False, False),
    # Centered in UV-remapped MDU door patches.
    "C4": (FWD.name, 1420, 28, False, False),
    "C5": (FWD.name, 1612, 28, False, False),
    "C6": (FWD.name, 2020, 1375, False, False),
    "C7": (FWD.name, 2030, 1557, False, False),
    # A1 AUDIO CENTER right rim — not switch UV holes / sibling S-BAND faces.
    "A1": (AFT.name, 3517, 989, True, True),
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
    # Regular weight — matches heritage Shuttle panel engraving (not Bold).
    for fp in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
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
        if all(0 <= x < width and 0 <= y < height for x, y in polygon):
            polygons.append(polygon)
    return polygons


def _mesh_for_panel(panel_id: str, meshes: dict[str, Mesh]) -> Mesh | None:
    name = MESH_NAME.get(panel_id, f"{panel_id}-panel")
    if name in meshes:
        return meshes[name]
    if f"{panel_id}-base" in meshes:
        return meshes[f"{panel_id}-base"]
    candidates = [mesh for name, mesh in meshes.items() if name.startswith(f"{panel_id}-")]
    return candidates[0] if candidates else None


def _backup(path: Path) -> Path:
    backup = path.with_name(path.name + ".bak_pre_panel_ids")
    if not backup.exists():
        Image.open(path).save(backup, format="PNG")
        print(f"wrote {backup.name}")
    return backup


def _label_bitmap(panel_id: str, purpose: str, *, compact: bool = False) -> Image.Image:
    """Transparent bitmap: bright-yellow letters at stock legend size/weight.

    Drawn the same way as heritage white engraving and the Grenadier plant
    stamps: 1:1 atlas pixels with a regular Sans face (no bold, no soft scale).
    """
    if compact:
        lines = (panel_id, purpose)
        font_px = STOCK_FONT_PX - 1
    else:
        lines = (f"{panel_id}  {purpose}",)
        font_px = STOCK_FONT_PX

    font = _font(font_px)
    boxes = [font.getbbox(line) for line in lines]
    widths = [box[2] - box[0] for box in boxes]
    heights = [box[3] - box[1] for box in boxes]
    gap = 1 if len(lines) > 1 else 0
    bitmap = Image.new("RGBA", (max(widths), sum(heights) + gap), (0, 0, 0, 0))
    draw = ImageDraw.Draw(bitmap)
    y = 0
    for line, box, width, height in zip(lines, boxes, widths, heights):
        draw.text(
            ((bitmap.width - width) // 2 - box[0], y - box[1]),
            line,
            fill=(*YELLOW, 255),
            font=font,
        )
        y += height + gap
    return bitmap


def _remap_object_uvs(
    ac_path: Path,
    object_name: str,
    atlas_size: tuple[int, int],
    dest: tuple[int, int, int, int],
) -> bool:
    """Map an object's current UV AABB onto dest atlas pixels. Returns True if written."""
    width, height = atlas_size
    x0, y0, x1, y1 = dest
    lines = ac_path.read_text(errors="replace").splitlines()
    i = 0
    changed = False
    while i < len(lines):
        if not lines[i].startswith("OBJECT poly"):
            i += 1
            continue
        start = i
        i += 1
        name: str | None = None
        while i < len(lines) and not lines[i].startswith("OBJECT "):
            if lines[i].startswith("name "):
                name = lines[i].split(" ", 1)[1].strip().strip('"')
            i += 1
        end = i
        if name != object_name:
            continue

        # Collect current UV AABB from all refs in this object.
        us: list[float] = []
        vs: list[float] = []
        j = start
        while j < end:
            if lines[j].startswith("refs "):
                count = int(lines[j].split()[1])
                j += 1
                for _ in range(count):
                    fields = lines[j].split()
                    us.append(float(fields[1]))
                    vs.append(float(fields[2]))
                    j += 1
                continue
            j += 1
        if not us:
            continue
        u_min, u_max = min(us), max(us)
        v_min, v_max = min(vs), max(vs)
        # Already on the destination patch?
        px0 = int(round(u_min * (width - 1)))
        px1 = int(round(u_max * (width - 1)))
        py0 = int(round((1.0 - v_max) * (height - 1)))
        py1 = int(round((1.0 - v_min) * (height - 1)))
        if abs(px0 - x0) <= 2 and abs(py0 - y0) <= 2 and abs(px1 - x1) <= 2 and abs(py1 - y1) <= 2:
            return False

        du = max(u_max - u_min, 1e-9)
        dv = max(v_max - v_min, 1e-9)
        # Dest in UV space (v increases upward in AC).
        u_a = x0 / (width - 1)
        u_b = (x1 - 1) / (width - 1)
        v_a = 1.0 - (y1 - 1) / (height - 1)
        v_b = 1.0 - y0 / (height - 1)

        j = start
        while j < end:
            if lines[j].startswith("refs "):
                count = int(lines[j].split()[1])
                j += 1
                for _ in range(count):
                    fields = lines[j].split()
                    idx = fields[0]
                    u = float(fields[1])
                    v = float(fields[2])
                    u_n = u_a + (u - u_min) / du * (u_b - u_a)
                    v_n = v_a + (v - v_min) / dv * (v_b - v_a)
                    rest = " ".join(fields[3:])
                    lines[j] = f"{idx} {u_n:.6f} {v_n:.6f}" + (f" {rest}" if rest else "")
                    changed = True
                    j += 1
                continue
            j += 1
        if changed:
            ac_path.write_text("\n".join(lines) + "\n")
            print(f"remapped UVs {object_name} -> atlas ({x0},{y0})-({x1},{y1})")
        return changed
    print(f"warning: object {object_name} not found in {ac_path.name}")
    return False


def _prepare_uv_remaps(images: dict[str, Image.Image]) -> None:
    """Expand tiny door UVs and paint their new atlas patches panel-gray."""
    for object_name, (tex_name, x0, y0, x1, y1) in UV_REMAPS.items():
        if tex_name not in images:
            continue
        _remap_object_uvs(COCKPIT_AC, object_name, images[tex_name].size, (x0, y0, x1, y1))
        img = images[tex_name]
        arr = np.asarray(img)
        # Sample nearby panel gray for a seamless door face.
        sample = arr[max(0, y0) : min(arr.shape[0], y1), max(0, x0 - 8) : x0]
        if sample.size == 0:
            gray = (156, 156, 149)
        else:
            mid = sample.reshape(-1, 3)
            mid = mid[mid.max(axis=1) < 180]
            gray = tuple(int(v) for v in (mid.mean(axis=0) if len(mid) else (156, 156, 149)))
        ImageDraw.Draw(img).rectangle([x0, y0, x1 - 1, y1 - 1], fill=gray)


def _large_panel_mask(
    polygons: list[list[tuple[int, int]]],
    size: tuple[int, int],
) -> np.ndarray:
    width, height = size
    mask_img = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask_img)
    for polygon in polygons:
        draw.polygon(polygon, fill=255)
    raw = ndimage.binary_closing(np.asarray(mask_img) > 0, structure=np.ones((3, 3)))
    labels, count = ndimage.label(raw)
    keep = np.zeros_like(raw)
    for i in range(1, count + 1):
        if int((labels == i).sum()) >= MIN_ISLAND_PX:
            keep |= labels == i
    return keep


def _safe_blank_mask(rgb: np.ndarray, panel_mask: np.ndarray) -> np.ndarray:
    gray = rgb.mean(axis=2)
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    gx = ndimage.sobel(gray, axis=1, mode="nearest")
    gy = ndimage.sobel(gray, axis=0, mode="nearest")
    detail = np.hypot(gx, gy)
    mean = ndimage.uniform_filter(gray, size=5, mode="nearest")
    mean2 = ndimage.uniform_filter(gray * gray, size=5, mode="nearest")
    local_std = np.sqrt(np.maximum(mean2 - mean * mean, 0.0))

    paint = panel_mask & (gray >= 105) & (gray <= 168) & (chroma < 28)
    occupied = panel_mask & (
        (gray > 170)
        | (gray < 90)
        | (chroma > 30)
        | (detail > 22)
        | (local_std > 8)
    )
    occupied = ndimage.binary_dilation(occupied, iterations=5)
    safe = paint & ~occupied
    safe = ndimage.binary_erosion(safe, iterations=1)
    edge_distance = ndimage.distance_transform_edt(panel_mask)
    rim = (edge_distance >= 2) & (edge_distance <= 14)
    return safe & rim


def _find_on_island(
    rgb_full: np.ndarray,
    island: np.ndarray,
    text_width: int,
    text_height: int,
) -> tuple[int, int, float] | None:
    ys, xs = np.where(island)
    if len(xs) == 0:
        return None
    x0, y0 = int(xs.min()), int(ys.min())
    x1, y1 = int(xs.max()) + 1, int(ys.max()) + 1
    if x1 - x0 < text_width or y1 - y0 < text_height:
        return None
    local = island[y0:y1, x0:x1]
    safe = _safe_blank_mask(rgb_full[y0:y1, x0:x1], local)
    if not np.any(safe):
        return None
    coverage = ndimage.uniform_filter(
        safe.astype(np.float32), size=(text_height, text_width), mode="constant"
    )
    valid = coverage >= 0.995
    if not np.any(valid):
        valid = coverage >= 0.98
    if not np.any(valid):
        return None
    edge_distance = ndimage.distance_transform_edt(local)
    yy = np.arange(local.shape[0], dtype=np.float32)[:, None]
    y_norm = yy / max(1.0, float(local.shape[0] - 1))
    score = edge_distance.astype(np.float32) + 20.0 * y_norm
    score[~valid] = np.inf
    cy, cx = np.unravel_index(np.argmin(score), score.shape)
    if not np.isfinite(score[cy, cx]):
        return None
    return (
        x0 + int(cx) - text_width // 2,
        y0 + int(cy) - text_height // 2,
        float(score[cy, cx]) - 0.0001 * float(island.sum()),
    )


def _find_blank_edge(
    image: Image.Image,
    polygons: list[list[tuple[int, int]]],
    text_width: int,
    text_height: int,
) -> tuple[int, int, float] | None:
    if not polygons:
        return None
    panel_mask = _large_panel_mask(polygons, image.size)
    if not np.any(panel_mask):
        return None
    rgb_full = np.asarray(image.convert("RGB"), dtype=np.float32)
    labels, count = ndimage.label(panel_mask)
    best: tuple[int, int, float] | None = None
    for i in range(1, count + 1):
        island = labels == i
        if int(island.sum()) < MIN_ISLAND_PX:
            continue
        hit = _find_on_island(rgb_full, island, text_width, text_height)
        if hit is None:
            continue
        if best is None or hit[2] < best[2]:
            best = hit
    return best


def _manual_spot_is_safe(image: Image.Image, x: int, y: int, w: int, h: int) -> bool:
    pad = 4
    crop = np.asarray(
        image.crop((x - pad, y - pad, x + w + pad, y + h + pad)).convert("RGB"),
        dtype=np.float32,
    )
    if crop.size == 0:
        return False
    gray = crop.mean(axis=2)
    # Allow yellow already present from a prior rebuild; block white legends / dark.
    bright_white = (gray > 200) & (
        (crop.max(axis=2) - crop.min(axis=2)) < 40
    )
    dark = gray < 90
    core = gray[pad : pad + h, pad : pad + w]
    if core.size == 0:
        return False
    core_ok = ((core >= 100) & (core <= 175)).mean()
    return core_ok >= 0.90 and float(bright_white.mean()) <= 0.02 and float(dark.mean()) <= 0.05


def main() -> None:
    meshes = _load_meshes()
    images: dict[str, Image.Image] = {}
    sources: dict[str, Path] = {}
    for path in (FWD, AFT):
        backup = _backup(path)
        images[path.name] = Image.open(backup).convert("RGB")
        sources[path.name] = path

    _prepare_uv_remaps(images)
    # Reload meshes after possible AC UV rewrite.
    meshes = _load_meshes()

    placed: list[str] = []
    skipped: list[str] = []
    positions: list[tuple[str, str, int, int, str]] = []

    for panel_id, purpose in PANELS.items():
        manual = MANUAL_STAMPS.get(panel_id)
        if manual is not None:
            texture_name, x, y, compact, rotate90 = manual
            label = _label_bitmap(panel_id, purpose, compact=compact)
            if rotate90:
                label = label.rotate(90, expand=True)
            if texture_name in images and _manual_spot_is_safe(
                images[texture_name], x, y, label.width, label.height
            ):
                images[texture_name].paste(label, (x, y), label)
                placed.append(panel_id)
                positions.append((panel_id, texture_name, x, y, "manual"))
                continue

        mesh = _mesh_for_panel(panel_id, meshes)
        if mesh is None or mesh.texture not in images:
            skipped.append(panel_id)
            continue
        image = images[mesh.texture]
        polygons = _crew_uv_polygons(panel_id, mesh, image.size)

        variants: list[tuple[float, str, Image.Image]] = [
            (0.0, "auto", _label_bitmap(panel_id, purpose)),
            (30.0, "auto-compact", _label_bitmap(panel_id, purpose, compact=True)),
            (
                80.0,
                "auto-rotated",
                _label_bitmap(panel_id, purpose, compact=True).rotate(90, expand=True),
            ),
        ]
        best_choice: tuple[float, str, Image.Image, int, int] | None = None
        for style_penalty, how, label in variants:
            hit = _find_blank_edge(image, polygons, label.width, label.height)
            if hit is None:
                continue
            x, y, place_score = hit
            total = place_score + style_penalty
            if best_choice is None or total < best_choice[0]:
                best_choice = (total, how, label, x, y)
        if best_choice is None:
            skipped.append(panel_id)
            continue
        _, how, label, x, y = best_choice
        image.paste(label, (x, y), label)
        placed.append(panel_id)
        positions.append((panel_id, mesh.texture, x, y, how))

    for panel_id in list(skipped):
        manual = MANUAL_STAMPS.get(panel_id)
        if manual is None:
            continue
        texture_name, x, y, compact, rotate90 = manual
        label = _label_bitmap(panel_id, PANELS[panel_id], compact=compact)
        if rotate90:
            label = label.rotate(90, expand=True)
        if texture_name not in images:
            continue
        if not _manual_spot_is_safe(images[texture_name], x, y, label.width, label.height):
            print(f"  reject unsafe manual stamp {panel_id} @ ({x},{y})")
            continue
        images[texture_name].paste(label, (x, y), label)
        skipped.remove(panel_id)
        placed.append(panel_id)
        positions.append((panel_id, texture_name, x, y, "manual-fallback"))

    for texture_name, image in images.items():
        image.save(sources[texture_name])
        print(f"wrote {sources[texture_name]}")
    print(f"placed {len(placed)} panel labels (bright yellow, stock-size regular Sans)")
    for panel_id, texture, x, y, how in positions:
        print(f"  {panel_id:>3} {texture:<30} ({x:4d}, {y:4d})  {how}")
    if skipped:
        print("skipped (no safe blank edge):", ", ".join(skipped))


if __name__ == "__main__":
    main()
