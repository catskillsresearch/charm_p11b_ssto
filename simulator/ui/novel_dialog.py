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
            driver_power_MW=10.0 if family == "laser_hedp" else 5.0,
            rep_rate_Hz=10.0 if family != "magnetic_compact" else 0.0,
            HV_kV=250.0 if family == "mec_orbitron" else 0.0,
            B_T=1.5 if family == "magnetic_compact" else 0.0,
            nonthermal=0.6,
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
