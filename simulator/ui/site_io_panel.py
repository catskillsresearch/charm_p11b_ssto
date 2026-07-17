"""Diesel-genset-style site I/O readout (battery, fuels, ash, byproducts)."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from simulator.plant.config import PlantConfig
from simulator.plant.streams import StreamBus


def _fmt_power(kW: float) -> str:
    """Site powers are tracked in kW; show MW for plant-scale values."""
    if abs(kW) >= 1000.0:
        return f"{kW / 1000.0:.2f} MW"
    return f"{kW:.2f} kW"


class SiteIOPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        self.spec_label = QLabel("")
        self.spec_label.setWordWrap(True)
        self.spec_label.setStyleSheet("color:#9bb0a8; font-size:11px;")
        root.addWidget(self.spec_label)

        batt = QGroupBox("Starter battery / bus")
        bf = QFormLayout(batt)
        self.l_soc = self._val()
        self.l_vi = self._val()
        self.l_draw = self._val()
        self.l_used = self._val()
        self.l_grid = self._val()
        self.l_apu = self._val()
        bf.addRow("Pre-production", self.l_apu)
        bf.addRow("SOC", self.l_soc)
        bf.addRow("V / A", self.l_vi)
        bf.addRow("Draw / charge", self.l_draw)
        bf.addRow("Batt used", self.l_used)
        bf.addRow("Grid export", self.l_grid)
        root.addWidget(batt)

        mat = QGroupBox("Fuels & products (cumulative)")
        mf = QFormLayout(mat)
        self.l_h = self._val()
        self.l_b = self._val()
        self.l_he = self._val()
        self.l_rad = self._val()
        self.l_rates = self._val()
        mf.addRow("Protons (H) in", self.l_h)
        mf.addRow("Boron-11 in", self.l_b)
        mf.addRow("Helium ash out", self.l_he)
        mf.addRow("Other rad. proxy", self.l_rad)
        mf.addRow("Feed rates", self.l_rates)
        root.addWidget(mat)

        qbox = QGroupBox("Gain")
        qf = QFormLayout(qbox)
        self.l_q = self._val()
        qf.addRow("Q vs 1", self.l_q)
        root.addWidget(qbox)
        root.addStretch(1)

    def _val(self) -> QLabel:
        lab = QLabel("—")
        lab.setFont(QFont("IBM Plex Mono", 10))
        lab.setStyleSheet("color:#e8f0ec;")
        return lab

    def set_config(self, cfg: PlantConfig) -> None:
        if cfg.time_to_production_s <= 0:
            start = "Startup: instantaneous production model (t_prod=0)"
        else:
            start = (
                f"Startup ({cfg.spec_data_quality} estimate — not measured plant data): "
                f"{cfg.time_to_production_s:g}s to production · "
                f"{cfg.startup_aux_MW:g} MW aux · {cfg.startup_energy_kWh:g} kWh one-shot\n"
                f"{cfg.startup_notes}"
            )
        self.spec_label.setText(
            f"Envelope ({cfg.spec_data_quality}): "
            f"{cfg.footprint_m2:.0f} m² pad · vessel ~{cfg.vessel_length_m:.1f}×⌀{cfg.vessel_diameter_m:.1f} m\n"
            f"Rated gross/net/driver: {cfg.rated_gross_MW:g} / {cfg.rated_net_MW:g} / {cfg.rated_driver_MW:g} MW\n"
            f"Starter batt: {cfg.starter_battery_kWh:g} kWh @ {cfg.starter_battery_V:g} V "
            f"({cfg.starter_battery_kWh * 1000 / max(cfg.starter_battery_V, 1):.0f} Ah) · "
            f"max charge {cfg.batt_max_charge_C:g}C "
            f"({cfg.starter_battery_kWh * cfg.batt_max_charge_C:g} kW)\n"
            f"{start}\n"
            f"{cfg.spec_notes}"
        )

    def update_from_bus(self, bus: StreamBus) -> None:
        ramp = bus.get("apu_ramp")
        boot = bus.get("apu_bootstrap_s")
        rem = bus.get("preprod_remaining_s")
        if rem > 0.05 and boot > 0:
            if boot <= 1.0:
                self.l_apu.setText(f"{rem*1000:.0f} ms left in stage ({boot*1000:.0f} ms window)")
            else:
                self.l_apu.setText(
                    f"{rem:.1f}s left in stage / {boot:g}s ({100 * ramp:.0f}%) — see alarm rail for TIMEWARP/STAGE"
                )
        elif ramp >= 0.999 and boot > 0:
            self.l_apu.setText("stage complete / production or shot end")
        else:
            self.l_apu.setText("idle — RUN starts commission sequence (warps logged on right)")
        soc = bus.get("batt_SOC")
        self.l_soc.setText(f"{100 * soc:.1f}%  ({bus.get('batt_kWh'):.2f} / {bus.get('batt_kWh_cap'):.2f} kWh)")
        self.l_vi.setText(f"{bus.get('batt_V'):.0f} V · {bus.get('batt_A'):.1f} A")
        c_rate = bus.get("batt_charge_C") or 1.0
        self.l_draw.setText(
            f"draw {_fmt_power(bus.get('batt_draw_kW'))} · "
            f"charge {_fmt_power(bus.get('batt_charge_kW'))} (≤{c_rate:g}C)"
        )
        self.l_used.setText(f"{bus.get('batt_used_kWh'):.3f} kWh from battery")
        self.l_grid.setText(
            f"{_fmt_power(bus.get('grid_export_kW'))} · {bus.get('grid_export_kWh'):.3f} kWh cumulative"
        )
        self.l_h.setText(f"{bus.get('H_in_g'):.4f} g")
        self.l_b.setText(f"{bus.get('B11_in_g'):.4f} g")
        self.l_he.setText(f"{bus.get('He_out_g'):.4f} g")
        self.l_rad.setText(f"{bus.get('rad_out_g'):.4f} g (activation/n proxy)")
        self.l_rates.setText(
            f"H {bus.get('fuel_H'):.3f} mg/s · B {bus.get('fuel_B11'):.3f} mg/s"
        )
        qp, qe, qpl = bus.get("Q_plasma"), bus.get("Q_eng"), bus.get("Q_plant")

        def tag(q: float) -> str:
            if q >= 1.0:
                return "Q≥1"
            if q >= 0.1:
                return "Q≪1"
            return "Q≈0"

        self.l_q.setText(
            f"plasma {qp:.3g} ({tag(qp)}) · eng {qe:.3g} · plant {qpl:.3g}"
        )
