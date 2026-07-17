"""Plant configuration keyed by catalog architecture + mixins + knobs."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PlantConfig:
    slug: str
    name: str
    family: str  # magnetic_compact | laser_hedp | mec_orbitron | generic
    path_type: str = ""
    time_mode: str = ""
    confinement: str = ""
    fuel: str = ""
    kinetics: str = ""
    pos_star: float | None = None
    plant_odds_rank: int | None = None
    hedp_degenerate_host: bool = False
    mixins: dict[str, bool] = field(default_factory=dict)
    # Operator knobs
    driver_power_MW: float = 5.0
    fueling_H: float = 1.0
    fueling_B11: float = 1.0
    rep_rate_Hz: float = 1.0
    B_T: float = 1.0
    HV_kV: float = 100.0
    nonthermal: float = 0.4
    Z_eff: float = 1.5
    fuel_mode: str = "p11b"  # p11b | dt_learning
    novel_tag: str | None = None

    def capability(self, name: str) -> bool:
        caps = {
            "rep_rate": self.family in {"laser_hedp", "mec_orbitron"},
            "HV": self.family == "mec_orbitron",
            "B_field": self.family == "magnetic_compact",
            "mixin_degenerate": self.hedp_degenerate_host,
            "fuel_mode": self.family == "mec_orbitron",
            "shot_clock": self.family in {"laser_hedp", "mec_orbitron"},
        }
        return caps.get(name, False)
