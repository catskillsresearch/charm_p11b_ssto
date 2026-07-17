"""Lab single-shot vs continuous plant operator modes."""

from __future__ import annotations

# Survey time-axis: pulsed / NBI-limited research stands → lab_shot.
# Claimed continuous / quasi-steady plant path → continuous_plant (APU/genset UI).
OPERATION_MODE: dict[str, str] = {
    # Lab single-shot / pulsed research
    "tae": "lab_shot",  # Norman/C-2W: ≤40 ms NB-limited
    "hb11": "lab_shot",
    "marvel": "lab_shot",
    "blue-laser": "lab_shot",
    "anubal": "lab_shot",
    "xjtu-cn-hedp": "lab_shot",
    "lppfusion": "lab_shot",
    "helion": "lab_shot",
    "jiht-nvd": "lab_shot",
    "fusion-project": "lab_shot",
    "probono": "lab_shot",
    "degenerate-catcher": "lab_shot",
    "lhd-nifs": "lab_shot",
    "pfs-pfrc": "lab_shot",
    # Continuous / continuous-ish plant narrative (even if Q≪1)
    "avalanche": "continuous_plant",
    "enn": "continuous_plant",
    "pale-blue-charm": "continuous_plant",
    "thea": "continuous_plant",
    "catania-avalanche": "continuous_plant",
    "radiation-trapping": "continuous_plant",
    "nanjing-mucf": "lab_shot",
}


def mode_for_slug(slug: str, family: str = "") -> str:
    if slug in OPERATION_MODE:
        return OPERATION_MODE[slug]
    if family in {"laser_hedp"}:
        return "lab_shot"
    if family == "mec_orbitron":
        return "continuous_plant"
    return "lab_shot"


def lab_shot_banner(slug: str) -> str:
    if slug == "tae":
        return (
            "SINGLE-SHOT LAB EXPERIMENT — not a continuous production design. "
            "Norman/C-2W: plasma sustained ≤ ~40 ms (NBI pulse limit). "
            "Facility grid power assumed; warmup steps logged only."
        )
    return (
        "SINGLE-SHOT LAB EXPERIMENT — not a continuous production design. "
        "Facility grid power assumed; focus is shot diagnostics, not islanded APU."
    )


def continuous_banner(slug: str) -> str:
    return (
        "CONTINUOUS / QUASI-STEADY OPERATOR VIEW — islanded starter-bus (APU) model. "
        "Surplus can trickle-charge the pack; Q≪1 drains it. "
        f"Architecture: {slug}."
    )
