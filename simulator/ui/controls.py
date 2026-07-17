"""Operator control column: architecture, mixins, knobs, run buttons."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from simulator.catalog_bridge import list_architectures
from simulator.plant.config import PlantConfig


class ControlPanel(QWidget):
    config_changed = Signal(object)  # PlantConfig
    run_clicked = Signal()
    pause_clicked = Signal()
    abort_clicked = Signal()
    reset_clicked = Signal()
    report_clicked = Signal()
    novel_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._arches = list_architectures()
        self._by_slug = {a["slug"]: a for a in self._arches}
        self._novel_configs: dict[str, PlantConfig] = {}
        self._building = False

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        arch_box = QGroupBox("Architecture")
        arch_form = QFormLayout(arch_box)
        self.arch_combo = QComboBox()
        for a in self._arches:
            label = a["slug"]
            if a["pos_star"] is not None:
                label += f"  (POS★ {a['pos_star']:.0f})"
            self.arch_combo.addItem(label, a["slug"])
        arch_form.addRow("Machine", self.arch_combo)
        self.meta_label = QLabel("")
        self.meta_label.setWordWrap(True)
        self.meta_label.setStyleSheet("color:#9bb0a8; font-size:11px;")
        arch_form.addRow(self.meta_label)
        root.addWidget(arch_box)

        mix_box = QGroupBox("Mixins")
        mix_l = QVBoxLayout(mix_box)
        self.mixin_degen = QCheckBox("Compressed-degenerate boron")
        self.mixin_degen.setToolTip(
            "Laser/HEDP hosts only — survey §3.2 / ref 91. Blocked on magnetic/MEC."
        )
        mix_l.addWidget(self.mixin_degen)
        self.mixin_hint = QLabel("")
        self.mixin_hint.setWordWrap(True)
        self.mixin_hint.setStyleSheet("color:#c4a574; font-size:11px;")
        mix_l.addWidget(self.mixin_hint)
        root.addWidget(mix_box)

        knob_box = QGroupBox("Setpoints")
        form = QFormLayout(knob_box)
        self.driver = self._spin(0.01, 200.0, 0.1, "MW")
        self.fuel_h = self._spin(0.0, 5.0, 0.05, "")
        self.fuel_b = self._spin(0.0, 5.0, 0.05, "")
        self.rep = self._spin(0.0, 200.0, 0.5, "Hz")
        self.b_field = self._spin(0.0, 10.0, 0.1, "T")
        self.hv = self._spin(0.0, 500.0, 5.0, "kV")
        self.nonthermal = self._spin(0.0, 1.0, 0.05, "")
        self.zeff = self._spin(1.0, 5.0, 0.1, "")
        self.fuel_mode = QComboBox()
        self.fuel_mode.addItem("p–¹¹B end-state", "p11b")
        self.fuel_mode.addItem("D–T learning", "dt_learning")
        form.addRow("Driver", self.driver)
        form.addRow("Fuel H", self.fuel_h)
        form.addRow("Fuel ¹¹B", self.fuel_b)
        form.addRow("Rep-rate", self.rep)
        form.addRow("B field", self.b_field)
        form.addRow("HV", self.hv)
        form.addRow("Nonthermal", self.nonthermal)
        form.addRow("Z_eff", self.zeff)
        form.addRow("Fuel mode", self.fuel_mode)
        root.addWidget(knob_box)

        btn_row = QHBoxLayout()
        self.btn_run = QPushButton("RUN")
        self.btn_pause = QPushButton("PAUSE")
        self.btn_abort = QPushButton("ABORT")
        self.btn_reset = QPushButton("RESET")
        self.btn_run.setStyleSheet("background:#0b6e4f; color:white; font-weight:600;")
        self.btn_pause.setStyleSheet("background:#3d4f48; color:white;")
        self.btn_pause.setToolTip("Freeze the plant clock (toggle to resume)")
        self.btn_abort.setStyleSheet("background:#8b2e2e; color:white;")
        btn_row.addWidget(self.btn_run)
        btn_row.addWidget(self.btn_pause)
        btn_row.addWidget(self.btn_abort)
        btn_row.addWidget(self.btn_reset)
        root.addLayout(btn_row)

        extra = QHBoxLayout()
        self.btn_report = QPushButton("Report")
        self.btn_novel = QPushButton("Novel preset…")
        extra.addWidget(self.btn_report)
        extra.addWidget(self.btn_novel)
        root.addLayout(extra)
        root.addStretch(1)

        self.arch_combo.currentIndexChanged.connect(self._on_arch)
        self.mixin_degen.toggled.connect(self._emit_config)
        for w in (
            self.driver,
            self.fuel_h,
            self.fuel_b,
            self.rep,
            self.b_field,
            self.hv,
            self.nonthermal,
            self.zeff,
        ):
            w.valueChanged.connect(self._emit_config)
        self.fuel_mode.currentIndexChanged.connect(self._emit_config)
        self.btn_run.clicked.connect(self.run_clicked.emit)
        self.btn_pause.clicked.connect(self.pause_clicked.emit)
        self.btn_abort.clicked.connect(self.abort_clicked.emit)
        self.btn_reset.clicked.connect(self.reset_clicked.emit)
        self.btn_report.clicked.connect(self.report_clicked.emit)
        self.btn_novel.clicked.connect(self.novel_clicked.emit)

        # Select TAE by default if present
        idx = self.arch_combo.findData("tae")
        if idx >= 0:
            self.arch_combo.setCurrentIndex(idx)
        self._on_arch()

    def _spin(self, lo: float, hi: float, step: float, suffix: str) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setSingleStep(step)
        s.setDecimals(3)
        if suffix:
            s.setSuffix(f" {suffix}")
        return s

    def current_slug(self) -> str:
        return str(self.arch_combo.currentData())

    def _on_arch(self) -> None:
        slug = self.current_slug()
        a = self._by_slug.get(slug, {})
        self.meta_label.setText(
            f"{a.get('name', slug)}\n{a.get('time_mode', '')} · {a.get('confinement', '')}\n"
            f"{a.get('fuel', '')} · {a.get('kinetics', '')}\nfamily={a.get('family', '')}"
        )
        # Load default knobs without fighting user mid-edit too hard
        self._building = True
        from simulator.catalog_bridge import config_from_slug

        if slug in self._novel_configs:
            cfg = self._novel_configs[slug]
        else:
            cfg = config_from_slug(slug)
        self.driver.setValue(cfg.driver_power_MW)
        self.fuel_h.setValue(cfg.fueling_H)
        self.fuel_b.setValue(cfg.fueling_B11)
        self.rep.setValue(cfg.rep_rate_Hz)
        self.b_field.setValue(cfg.B_T)
        self.hv.setValue(cfg.HV_kV)
        self.nonthermal.setValue(cfg.nonthermal)
        self.zeff.setValue(cfg.Z_eff)
        fm = self.fuel_mode.findData(cfg.fuel_mode)
        if fm >= 0:
            self.fuel_mode.setCurrentIndex(fm)
        self.mixin_degen.setChecked(bool(cfg.mixins.get("degenerate_boron")))
        self._building = False
        self._update_enabled(cfg)
        self._emit_config()

    def _update_enabled(self, cfg: PlantConfig) -> None:
        self.rep.setEnabled(cfg.capability("rep_rate"))
        self.hv.setEnabled(cfg.capability("HV"))
        self.b_field.setEnabled(cfg.capability("B_field"))
        self.fuel_mode.setEnabled(cfg.capability("fuel_mode"))
        allowed = cfg.capability("mixin_degenerate")
        self.mixin_degen.setEnabled(allowed)
        if not allowed:
            self.mixin_degen.setChecked(False)
            self.mixin_hint.setText(
                "Mixin disabled: not a catalog laser/HEDP degenerate-boron host."
            )
        else:
            self.mixin_hint.setText("Allowed on this host (HB11/Marvel/… catalog table).")

    def build_config(self) -> PlantConfig:
        from simulator.catalog_bridge import config_from_slug

        slug = self.current_slug()
        if slug in self._novel_configs:
            cfg = PlantConfig(**{**self._novel_configs[slug].__dict__})
        else:
            cfg = config_from_slug(slug)
        cfg.driver_power_MW = self.driver.value()
        cfg.fueling_H = self.fuel_h.value()
        cfg.fueling_B11 = self.fuel_b.value()
        cfg.rep_rate_Hz = self.rep.value()
        cfg.B_T = self.b_field.value()
        cfg.HV_kV = self.hv.value()
        cfg.nonthermal = self.nonthermal.value()
        cfg.Z_eff = self.zeff.value()
        cfg.fuel_mode = str(self.fuel_mode.currentData())
        want_mixin = self.mixin_degen.isChecked()
        if want_mixin and not cfg.hedp_degenerate_host:
            self.mixin_degen.blockSignals(True)
            self.mixin_degen.setChecked(False)
            self.mixin_degen.blockSignals(False)
            self.mixin_hint.setText(
                "Blocked: degenerate-boron mixin is laser/HEDP-only (survey §3.2)."
            )
            want_mixin = False
        cfg.mixins = dict(cfg.mixins)
        cfg.mixins["degenerate_boron"] = want_mixin
        if slug in self._novel_configs:
            self._novel_configs[slug] = cfg
        return cfg

    def _emit_config(self) -> None:
        if self._building:
            return
        cfg = self.build_config()
        self._update_enabled(cfg)
        self.config_changed.emit(cfg)

    def apply_external_config(self, cfg: PlantConfig) -> None:
        """Load a novel/preset config into the widgets."""
        self._building = True
        self._novel_configs[cfg.slug] = cfg
        idx = self.arch_combo.findData(cfg.slug)
        if idx < 0:
            # Add temporary novel entry
            self.arch_combo.addItem(f"{cfg.slug} (novel)", cfg.slug)
            self._by_slug[cfg.slug] = {
                "slug": cfg.slug,
                "name": cfg.name,
                "time_mode": cfg.time_mode,
                "confinement": cfg.confinement,
                "fuel": cfg.fuel,
                "kinetics": cfg.kinetics,
                "family": cfg.family,
                "pos_star": cfg.pos_star,
                "hedp_host": cfg.hedp_degenerate_host,
            }
            idx = self.arch_combo.findData(cfg.slug)
        self.arch_combo.setCurrentIndex(idx)
        self.driver.setValue(cfg.driver_power_MW)
        self.fuel_h.setValue(cfg.fueling_H)
        self.fuel_b.setValue(cfg.fueling_B11)
        self.rep.setValue(cfg.rep_rate_Hz)
        self.b_field.setValue(cfg.B_T)
        self.hv.setValue(cfg.HV_kV)
        self.nonthermal.setValue(cfg.nonthermal)
        self.zeff.setValue(cfg.Z_eff)
        fm = self.fuel_mode.findData(cfg.fuel_mode)
        if fm >= 0:
            self.fuel_mode.setCurrentIndex(fm)
        self.mixin_degen.setChecked(bool(cfg.mixins.get("degenerate_boron")))
        self.meta_label.setText(
            f"{cfg.name}\n{cfg.time_mode} · {cfg.confinement}\n"
            f"{cfg.fuel} · family={cfg.family}"
            + (f"\n{cfg.novel_tag}" if cfg.novel_tag else "")
        )
        self._building = False
        self._update_enabled(cfg)
        self.config_changed.emit(cfg)
