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
    # lab_shot = single-shot experiment UI; continuous_plant = APU/operator UI
    operation_mode: str = "lab_shot"
    # Plant envelope (from plant_spec / defaults)
    footprint_m2: float = 100.0
    vessel_length_m: float = 5.0
    vessel_diameter_m: float = 2.0
    rated_gross_MW: float = 1.0
    rated_net_MW: float = 0.5
    rated_driver_MW: float = 1.0
    starter_battery_kWh: float = 50.0
    starter_battery_V: float = 400.0
    batt_max_charge_C: float = 1.0  # battery recharge limit (1C = 1 h to full)
    design_fuel_H_mg_s: float = 0.5
    design_fuel_B11_mg_s: float = 0.5
    neutron_energy_fraction: float = 0.02
    # Black-start / first production (plant_spec); 0 ⇒ instantaneous books
    time_to_production_s: float = 0.0
    startup_aux_MW: float = 0.0
    startup_energy_kWh: float = 0.0
    startup_notes: str = ""
    spec_notes: str = ""
    spec_data_quality: str = "editorial"

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
