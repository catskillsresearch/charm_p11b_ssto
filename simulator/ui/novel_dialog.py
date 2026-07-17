"""Dialog to mint a novel-N preset from qualifiers."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from simulator.catalog_bridge import (
    connect,
    nearest_family_for_qualifiers,
)
from simulator.plant.config import PlantConfig
from simulator.plant.operation_mode import mode_for_slug

ROOT = Path(__file__).resolve().parents[2]
NOVEL_PATH = ROOT / "data" / "novel_twins.json"
PRESET_DIR = ROOT / "data" / "presets"


def _axis_names(table: str) -> list[str]:
    with connect() as conn:
        rows = conn.execute(f"SELECT name FROM {table} ORDER BY name").fetchall()
    return [r[0] for r in rows]


class NovelDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Novel 0-order configuration")
        self._result: PlantConfig | None = None
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Pick survey qualifiers. If no catalog machine matches exactly, "
                "mint novel-N and run on the nearest family plugin."
            )
        )
        form = QFormLayout()
        self.time = QComboBox()
        self.conf = QComboBox()
        self.fuel = QComboBox()
        self.kin = QComboBox()
        for box, table in (
            (self.time, "time_mode"),
            (self.conf, "confinement_family"),
            (self.fuel, "fuel_end_state"),
            (self.kin, "kinetics_regime"),
        ):
            box.addItem("—", "")
            for name in _axis_names(table):
                box.addItem(name, name)
            form.addRow(table.replace("_", " "), box)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def result_config(self) -> PlantConfig | None:
        return self._result

    def _accept(self) -> None:
        time = str(self.time.currentData() or "")
        conf = str(self.conf.currentData() or "")
        fuel = str(self.fuel.currentData() or "")
        kin = str(self.kin.currentData() or "")
        if not all([time, conf, fuel, kin]):
            return
        family = nearest_family_for_qualifiers(time, conf, fuel, kin)
        tag = self._mint_novel(time, conf, fuel, kin)
        hedp = family == "laser_hedp"
        # Envelope defaults by family (genset-scale editorial)
        if family == "mec_orbitron":
            env = dict(
                footprint_m2=20,
                vessel_length_m=1.5,
                vessel_diameter_m=1.0,
                rated_gross_MW=0.05,
                rated_net_MW=0.01,
                rated_driver_MW=0.2,
                starter_battery_kWh=30,
                starter_battery_V=400,
                design_fuel_H_mg_s=0.05,
                design_fuel_B11_mg_s=0.02,
                neutron_energy_fraction=0.5,
                time_to_production_s=3.0,
                startup_aux_MW=0.02,
                startup_energy_kWh=0.05,
                startup_notes="Novel MEC: HV/orbit enable editorial.",
                driver_power_MW=0.2,
                rep_rate_Hz=40.0,
                HV_kV=250.0,
                B_T=0.0,
            )
        elif family == "laser_hedp":
            env = dict(
                footprint_m2=800,
                vessel_length_m=8,
                vessel_diameter_m=6,
                rated_gross_MW=40,
                rated_net_MW=10,
                rated_driver_MW=40,
                starter_battery_kWh=60,
                starter_battery_V=800,
                design_fuel_H_mg_s=0.5,
                design_fuel_B11_mg_s=0.8,
                neutron_energy_fraction=0.001,
                time_to_production_s=8.0,
                startup_aux_MW=3.0,
                startup_energy_kWh=10.0,
                startup_notes="Novel laser: bank fill to first shot; not full average wall-plug on batt.",
                driver_power_MW=40.0,
                rep_rate_Hz=10.0,
                HV_kV=0.0,
                B_T=0.0,
            )
        else:
            env = dict(
                footprint_m2=1000,
                vessel_length_m=15,
                vessel_diameter_m=4,
                rated_gross_MW=50,
                rated_net_MW=25,
                rated_driver_MW=20,
                starter_battery_kWh=150,
                starter_battery_V=800,
                design_fuel_H_mg_s=1.0,
                design_fuel_B11_mg_s=1.0,
                neutron_energy_fraction=0.02,
                time_to_production_s=90.0,
                startup_aux_MW=1.2,
                startup_energy_kWh=35.0,
                startup_notes="Novel magnetic: house/aux + coil energy; NBI wall-plug not on batt in prep.",
                driver_power_MW=20.0,
                rep_rate_Hz=0.0,
                HV_kV=0.0,
                B_T=1.5,
            )
        cfg = PlantConfig(
            slug=tag,
            name=f"Novel twin ({tag})",
            family=family,
            time_mode=time,
            confinement=conf,
            fuel=fuel,
            kinetics=kin,
            hedp_degenerate_host=hedp,
            mixins={"degenerate_boron": False},
            novel_tag=tag,
            operation_mode=mode_for_slug(tag, family),
            nonthermal=0.6,
            spec_notes="Novel qualifier combo — envelope is family-default editorial.",
            spec_data_quality="aspirational",
            **env,
        )
        self._save_preset(cfg)
        self._result = cfg
        self.accept()

    def _mint_novel(self, time: str, conf: str, fuel: str, kin: str) -> str:
        fp = f"time={time}|confinement={conf}|fuel={fuel}|kinetics={kin}"
        PRESET_DIR.mkdir(parents=True, exist_ok=True)
        if NOVEL_PATH.exists():
            data = json.loads(NOVEL_PATH.read_text(encoding="utf-8"))
        else:
            data = {"next_id": 1, "by_fingerprint": {}}
        if fp in data.get("by_fingerprint", {}):
            return data["by_fingerprint"][fp]["tag"]
        n = int(data.get("next_id", 1))
        tag = f"novel-{n}"
        data.setdefault("by_fingerprint", {})[fp] = {
            "tag": tag,
            "id": n,
            "selection": {
                "time": time,
                "confinement": conf,
                "fuel": fuel,
                "kinetics": kin,
            },
        }
        data["next_id"] = n + 1
        NOVEL_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return tag

    def _save_preset(self, cfg: PlantConfig) -> None:
        PRESET_DIR.mkdir(parents=True, exist_ok=True)
        path = PRESET_DIR / f"{cfg.slug}.json"
        path.write_text(
            json.dumps(
                {
                    "slug": cfg.slug,
                    "name": cfg.name,
                    "family": cfg.family,
                    "time_mode": cfg.time_mode,
                    "confinement": cfg.confinement,
                    "fuel": cfg.fuel,
                    "kinetics": cfg.kinetics,
                    "hedp_degenerate_host": cfg.hedp_degenerate_host,
                    "mixins": cfg.mixins,
                    "novel_tag": cfg.novel_tag,
                    "driver_power_MW": cfg.driver_power_MW,
                    "rep_rate_Hz": cfg.rep_rate_Hz,
                    "HV_kV": cfg.HV_kV,
                    "B_T": cfg.B_T,
                    "nonthermal": cfg.nonthermal,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
