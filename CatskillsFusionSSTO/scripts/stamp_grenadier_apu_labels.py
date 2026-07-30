#!/usr/bin/env python3
"""Stamp / blank Grenadier panel paint on Shuttle text maps.

Only switches that are wired into Grenadier ops (or live brake isol)
keep labels. Mesh hardware stays; unwired groups lose their paint.

Wired keep (see Nasal/grenadier/grenadier_ops.nas):
  APU OPERATE     →  CART / BATT / CRYO
  APU CNTLR PWR   →  MAGNET / FUEL / RF
  ENGINE POWER    →  REACTOR POWER + CHARM / DEC / VACUUM
  Panel R4        →  BRAKE ISOL VLV only

Also relabels aft AFT LEFT/RIGHT RCS biprop OXID/FUEL → green monoprop
(LMP-103S): He A/B + PROP/PROP on aft-cockpit-text-map-x.png.

Restores from *.bak_pre_grenadier when present, then blanks + stamps.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
TEX = ROOT / "Models" / "fwd-cockpit-text-map-x.png"
BAK = ROOT / "Models" / "fwd-cockpit-text-map-x.png.bak_pre_grenadier"
AFT_TEX = ROOT / "Models" / "aft-cockpit-text-map-x.png"
AFT_BAK = ROOT / "Models" / "aft-cockpit-text-map-x.png.bak_pre_grenadier"

# --- R2: blank whole plate (remapped labels stamped fresh below) ---
# Include MPS PRPLT DUMP header row above ENGINE/REACTOR POWER (~y 900–990).
R2_BLANK = (250, 900, 1020, 2140)
R2_KEEP: tuple[tuple[int, int, int, int], ...] = ()

# --- R4: blank whole plate; brake-isol labels stamped fresh below ---
R4_BLANK = (2300, 2520, 2835, 2898)
R4_KEEP: tuple[tuple[int, int, int, int], ...] = ()

# --- Center console (C3): blank unused Shuttle stack / 3-SSME / fuel-cell paint ---
# Measured on bak_pre_grenadier (4096², y down). Keep MAIN ENGINE header, CTR,
# LIMIT SHUT ENABLE (SCRAM). OMS ENG ARM switches stay live as Stage ± — stamped below.
C3_BLANKS: tuple[tuple[int, int, int, int], ...] = (
    (1445, 905, 1495, 935),  # MAIN ENGINE SHUT DOWN · LEFT
    (1555, 905, 1615, 935),  # MAIN ENGINE SHUT DOWN · RIGHT (keep CTR ~1500–1550)
    (1485, 1005, 1558, 1110),  # former left SEP selector MAN/AUTO paint
    (1555, 975, 1925, 1165),  # SRB SEPARATION + ET SEPARATION (+ MAN/AUTO)
    (1335, 1285, 1675, 1415),  # FUEL CELL REAC VLV 1/2/3 CLOSE
)

PANEL_GRAY = (156, 156, 149)


def _font(size: int) -> ImageFont.ImageFont:
    for fp in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ):
        try:
            return ImageFont.truetype(fp, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _panel_gray(arr: np.ndarray, x: int, y: int, r: int = 6) -> tuple[int, int, int]:
    patch = arr[y - r : y + r + 1, x - r : x + r + 1].reshape(-1, 3)
    mid = patch[patch.max(axis=1) < 180]
    if len(mid):
        return tuple(int(v) for v in mid.mean(axis=0))
    return (110, 110, 112)


def _blank_with_keeps(
    arr: np.ndarray,
    blank: tuple[int, int, int, int],
    keeps: tuple[tuple[int, int, int, int], ...],
    gray: tuple[int, int, int] = PANEL_GRAY,
) -> None:
    x0, y0, x1, y1 = blank
    g = np.array(gray, dtype=np.uint8)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    mask = np.ones(xx.shape, dtype=bool)
    for kx0, ky0, kx1, ky1 in keeps:
        mask &= ~((xx >= kx0) & (xx < kx1) & (yy >= ky0) & (yy < ky1))
    region = arr[y0:y1, x0:x1]
    region[mask] = g
    arr[y0:y1, x0:x1] = region


def _stamp_row(
    img: Image.Image,
    arr: np.ndarray,
    centers_x: list[int],
    labels: list[str],
    y: int,
    *,
    cover_w: int,
    cover_h: int,
    font_size: int,
) -> None:
    d = ImageDraw.Draw(img)
    font = _font(font_size)
    gray = _panel_gray(arr, centers_x[1], y)
    for cx, lab in zip(centers_x, labels):
        d.rectangle(
            [cx - cover_w // 2, y - cover_h // 2, cx + cover_w // 2, y + cover_h // 2],
            fill=gray,
        )
        bbox = d.textbbox((0, 0), lab, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text((int(cx - tw / 2), int(y - th / 2 - 1)), lab, fill=(245, 245, 245), font=font)


def _stamp_centered(
    img: Image.Image,
    arr: np.ndarray,
    label: str,
    cx: int,
    y: int,
    *,
    cover_w: int,
    cover_h: int,
    font_size: int,
) -> None:
    d = ImageDraw.Draw(img)
    font = _font(font_size)
    gray = _panel_gray(arr, cx, y)
    d.rectangle(
        [cx - cover_w // 2, y - cover_h // 2, cx + cover_w // 2, y + cover_h // 2],
        fill=gray,
    )
    bbox = d.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text((int(cx - tw / 2), int(y - th / 2 - 1)), label, fill=(245, 245, 245), font=font)


def _stamp_multiline(
    img: Image.Image,
    arr: np.ndarray,
    lines: list[str],
    cx: int,
    y: int,
    *,
    cover_w: int,
    cover_h: int,
    font_size: int,
) -> None:
    d = ImageDraw.Draw(img)
    font = _font(font_size)
    gray = _panel_gray(arr, cx, y)
    d.rectangle(
        [cx - cover_w // 2, y - cover_h // 2, cx + cover_w // 2, y + cover_h // 2],
        fill=gray,
    )
    line_h = font_size + 1
    total_h = line_h * len(lines)
    y0 = int(y - total_h / 2)
    for i, lab in enumerate(lines):
        bbox = d.textbbox((0, 0), lab, font=font)
        tw = bbox[2] - bbox[0]
        d.text((int(cx - tw / 2), y0 + i * line_h), lab, fill=(245, 245, 245), font=font)


def stamp_aft_rcs_monoprop() -> None:
    """AFT LEFT/RIGHT RCS: biprop OXID/FUEL → He A/B + PROP (LMP-103S)."""
    if not AFT_TEX.is_file():
        print(f"skip aft RCS stamp: missing {AFT_TEX}")
        return
    if not AFT_BAK.is_file():
        Image.open(AFT_TEX).save(AFT_BAK, format="PNG")
        print(f"wrote bak {AFT_BAK.name}")
    src = AFT_BAK
    img = Image.open(src).convert("RGB")
    arr = np.array(img)
    img = Image.fromarray(arr)

    # Measured on aft bak (4096²). Oval centers for L/R He + tanks.
    # He (OXID)/(FUEL) → He (A)/(B); tank OXID/FUEL → PROP/PROP.
    for cx, cy in ((3507, 2877), (3842, 2877)):  # He A (was OXID)
        _stamp_multiline(
            img, arr, ["He", "(A)"], cx, cy, cover_w=72, cover_h=42, font_size=9
        )
    for cx, cy in ((3600, 2877), (3935, 2877)):  # He B (was FUEL)
        _stamp_multiline(
            img, arr, ["He", "(B)"], cx, cy, cover_w=72, cover_h=42, font_size=9
        )
    for cx, cy in (
        (3537, 3040),
        (3617, 3040),
        (3845, 3040),
        (3942, 3040),
    ):  # PROP tanks (were OXID/FUEL)
        _stamp_centered(img, arr, "PROP", cx, cy, cover_w=58, cover_h=24, font_size=10)

    Image.fromarray(np.asarray(img)).save(AFT_TEX)
    print(f"wrote {AFT_TEX} (source={src.name}) — RCS monoprop labels")


def main() -> None:
    src = BAK if BAK.is_file() else TEX
    img = Image.open(src).convert("RGB")
    arr = np.array(img)  # writable copy (np.asarray is read-only)

    _blank_with_keeps(arr, R2_BLANK, R2_KEEP)
    _blank_with_keeps(arr, R4_BLANK, R4_KEEP)
    for box in C3_BLANKS:
        _blank_with_keeps(arr, box, ())

    img = Image.fromarray(arr)

    # Pixel centers measured on fwd-cockpit-text-map-x.png (4096²).
    _stamp_centered(
        img,
        arr,
        "REACTOR POWER",
        551,
        1061,
        cover_w=168,
        cover_h=12,
        font_size=9,
    )
    _stamp_row(
        img,
        arr,
        [443, 524, 606],
        ["CHARM", "DEC", "VACUUM"],
        1076,
        cover_w=44,
        cover_h=14,
        font_size=8,
    )
    _stamp_centered(
        img,
        arr,
        "ON",
        524,
        1095,
        cover_w=28,
        cover_h=10,
        font_size=7,
    )
    _stamp_centered(
        img,
        arr,
        "APU OPERATE",
        761,
        1385,
        cover_w=110,
        cover_h=11,
        font_size=8,
    )
    _stamp_row(
        img,
        arr,
        [701, 761, 820],
        ["CART", "BATT", "CRYO"],
        1404,
        cover_w=28,
        cover_h=11,
        font_size=8,
    )
    _stamp_centered(
        img,
        arr,
        "APU CNTLR PWR",
        884,
        1712,
        cover_w=120,
        cover_h=11,
        font_size=8,
    )
    _stamp_row(
        img,
        arr,
        [825, 884, 948],
        ["MAGNET", "FUEL", "RF"],
        1732,
        cover_w=32,
        cover_h=11,
        font_size=8,
    )

    # C3 — repurpose the two prominent black SEP pushbuttons as Stage -/+.
    # These coordinates are the actual SRB/ET panel legends, not the nearby
    # OMS ARM texture island used by the first attempt.
    _stamp_centered(
        img,
        arr,
        "STAGE −",
        1575,
        1050,
        cover_w=94,
        cover_h=12,
        font_size=9,
    )
    _stamp_centered(
        img,
        arr,
        "STAGE +",
        1715,
        1050,
        cover_w=94,
        cover_h=12,
        font_size=9,
    )

    # Both button-label meshes share this UV patch. Replace SEP with STG on
    # the black button face; the adjacent panel legends identify - versus +.
    d = ImageDraw.Draw(img)
    d.rectangle((1048, 312, 1087, 336), fill=(4, 4, 4))
    font = _font(14)
    label = "STG"
    bbox = d.textbbox((0, 0), label, font=font)
    d.text(
        (int(1067.5 - (bbox[2] - bbox[0]) / 2), int(324 - (bbox[3] - bbox[1]) / 2 - 2)),
        label,
        fill=(245, 245, 245),
        font=font,
    )

    # R4 — only live brake isol (failures.xml reads brake-isolation-valve-*-status)
    _stamp_centered(
        img,
        arr,
        "BRAKE ISOL VLV",
        2375,
        2660,
        cover_w=100,
        cover_h=11,
        font_size=8,
    )
    _stamp_row(
        img,
        arr,
        [2335, 2375, 2415],
        ["1", "2", "3"],
        2695,
        cover_w=14,
        cover_h=10,
        font_size=8,
    )
    _stamp_centered(
        img,
        arr,
        "OPEN",
        2375,
        2682,
        cover_w=40,
        cover_h=10,
        font_size=7,
    )
    _stamp_centered(
        img,
        arr,
        "CLOSE",
        2375,
        2720,
        cover_w=44,
        cover_h=10,
        font_size=7,
    )

    Image.fromarray(np.asarray(img)).save(TEX)
    print(f"wrote {TEX} (source={src.name})")
    stamp_aft_rcs_monoprop()


if __name__ == "__main__":
    main()
