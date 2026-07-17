"""Compact facility-energy footnote for lab-shot mode (grid-powered)."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from simulator.plant.config import PlantConfig


class FacilityNotePanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self.label = QLabel("")
        self.label.setWordWrap(True)
        self.label.setStyleSheet("color:#9bb0a8; font-size:11px;")
        lay.addWidget(self.label)

    def set_config(self, cfg: PlantConfig) -> None:
        self.label.setText(
            f"<b>Facility energy (grid)</b> — islanded APU not modeled in lab-shot mode.<br>"
            f"Warmup kWh and timings appear on the alarm rail (TIMEWARP / FACILITY). "
            f"Shot focus: diagnostics over the NBI window. "
            f"Envelope ({cfg.spec_data_quality}): driver class {cfg.rated_driver_MW:g} MW · "
            f"{cfg.spec_notes}"
        )
