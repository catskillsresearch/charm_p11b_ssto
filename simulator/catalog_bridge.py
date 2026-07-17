"""Load PlantConfig rows from the survey SQLite catalog."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from simulator.plant.config import PlantConfig

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "p11b_catalog.sqlite"

# slug → physics family for operator theater
FAMILY_MAP: dict[str, str] = {
    "tae": "magnetic_compact",
    "enn": "magnetic_compact",
    "pale-blue-charm": "magnetic_compact",
    "lhd-nifs": "magnetic_compact",
    "helion": "magnetic_compact",
    "pfs-pfrc": "magnetic_compact",
    "thea": "magnetic_compact",
    "hb11": "laser_hedp",
    "marvel": "laser_hedp",
    "blue-laser": "laser_hedp",
    "anubal": "laser_hedp",
    "xjtu-cn-hedp": "laser_hedp",
    "probono": "laser_hedp",
    "fusion-project": "laser_hedp",
    "degenerate-catcher": "laser_hedp",
    "lppfusion": "laser_hedp",  # pinch theater uses pulsed schematic
    "avalanche": "mec_orbitron",
    "jiht-nvd": "mec_orbitron",
}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def list_architectures() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                a.slug, a.name,
                tm.name AS time_mode,
                cf.name AS confinement,
                fe.name AS fuel,
                kr.name AS kinetics,
                pt.name AS path_type,
                po.rank AS plant_odds_rank,
                po.pos_star AS pos_star,
                EXISTS(
                    SELECT 1 FROM hedp_degenerate_host h
                    WHERE h.architecture_id = a.id
                ) AS hedp_host
            FROM architecture a
            LEFT JOIN time_mode tm ON tm.id = a.time_mode_id
            LEFT JOIN confinement_family cf ON cf.id = a.confinement_family_id
            LEFT JOIN fuel_end_state fe ON fe.id = a.fuel_end_state_id
            LEFT JOIN kinetics_regime kr ON kr.id = a.kinetics_regime_id
            LEFT JOIN path_type pt ON pt.id = a.path_type_id
            LEFT JOIN plant_odds po ON po.architecture_id = a.id
            ORDER BY COALESCE(po.rank, 999), a.name
            """
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["family"] = FAMILY_MAP.get(d["slug"], "generic")
        d["hedp_host"] = bool(d["hedp_host"])
        out.append(d)
    return out


def hedp_host_slugs() -> set[str]:
    return {a["slug"] for a in list_architectures() if a["hedp_host"]}


def config_from_slug(slug: str, **knob_overrides: object) -> PlantConfig:
    arches = {a["slug"]: a for a in list_architectures()}
    if slug not in arches:
        raise KeyError(f"Unknown architecture slug: {slug}")
    a = arches[slug]
    family = a["family"]
    defaults = _default_knobs(family, slug)
    defaults.update({k: v for k, v in knob_overrides.items() if v is not None})
    return PlantConfig(
        slug=slug,
        name=a["name"],
        family=family,
        path_type=a["path_type"] or "",
        time_mode=a["time_mode"] or "",
        confinement=a["confinement"] or "",
        fuel=a["fuel"] or "",
        kinetics=a["kinetics"] or "",
        pos_star=a["pos_star"],
        plant_odds_rank=a["plant_odds_rank"],
        hedp_degenerate_host=a["hedp_host"],
        mixins={"degenerate_boron": False},
        driver_power_MW=float(defaults["driver_power_MW"]),
        fueling_H=float(defaults["fueling_H"]),
        fueling_B11=float(defaults["fueling_B11"]),
        rep_rate_Hz=float(defaults["rep_rate_Hz"]),
        B_T=float(defaults["B_T"]),
        HV_kV=float(defaults["HV_kV"]),
        nonthermal=float(defaults["nonthermal"]),
        Z_eff=float(defaults["Z_eff"]),
        fuel_mode=str(defaults["fuel_mode"]),
        novel_tag=defaults.get("novel_tag"),  # type: ignore[arg-type]
    )


def _default_knobs(family: str, slug: str) -> dict:
    base = {
        "driver_power_MW": 5.0,
        "fueling_H": 1.0,
        "fueling_B11": 1.0,
        "rep_rate_Hz": 1.0,
        "B_T": 1.0,
        "HV_kV": 100.0,
        "nonthermal": 0.4,
        "Z_eff": 1.5,
        "fuel_mode": "p11b",
        "novel_tag": None,
    }
    if family == "magnetic_compact":
        base.update(
            {
                "driver_power_MW": 8.0 if slug == "tae" else 6.0,
                "B_T": 1.2 if slug == "tae" else 2.5,
                "nonthermal": 0.55 if slug == "tae" else 0.35,
                "rep_rate_Hz": 0.0,
            }
        )
    elif family == "laser_hedp":
        base.update(
            {
                "driver_power_MW": 30.0,
                "rep_rate_Hz": 10.0,
                "nonthermal": 0.75,
                "B_T": 0.0,
            }
        )
    elif family == "mec_orbitron":
        base.update(
            {
                "driver_power_MW": 0.15,
                "HV_kV": 300.0,
                "rep_rate_Hz": 50.0,
                "nonthermal": 0.85,
                "fuel_mode": "dt_learning" if slug == "avalanche" else "p11b",
            }
        )
    return base


def nearest_family_for_qualifiers(
    time: str | None,
    confinement: str | None,
    fuel: str | None,
    kinetics: str | None,
) -> str:
    """Map free qualifiers to a plugin family for novel presets."""
    conf = (confinement or "").lower()
    tm = (time or "").lower()
    if "orbitron" in conf or "nvd" in conf or "mec" in tm or "compact mec" in tm:
        return "mec_orbitron"
    if "laser" in conf or "icf" in conf or "hedp" in conf or "beam-target" in conf or "dpf" in conf:
        return "laser_hedp"
    if "pulsed" in tm and ("laser" in conf or "nano" in conf):
        return "laser_hedp"
    return "magnetic_compact"
