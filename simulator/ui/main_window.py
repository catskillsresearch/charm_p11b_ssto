"""Main operator console window."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from simulator.catalog_bridge import config_from_slug
from simulator.plant.clock import PlantClock, RunState
from simulator.plant.config import PlantConfig
from simulator.plant.report import build_report
from simulator.ui.alarms import AlarmRail
from simulator.ui.controls import ControlPanel
from simulator.ui.novel_dialog import NovelDialog
from simulator.ui.schematic_view import SchematicView
from simulator.ui.site_io_panel import SiteIOPanel
from simulator.ui.stripcharts import StripChartPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("p11b operator twin — survey theater")
        self.resize(1400, 860)
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #0e1214; color: #d7e0dc; }
            QGroupBox { border: 1px solid #2a3632; margin-top: 10px; padding-top: 8px; }
            QGroupBox::title { color: #8fa89e; subcontrol-origin: margin; left: 8px; }
            QComboBox, QDoubleSpinBox, QPushButton {
                background: #1a2220; border: 1px solid #33423c; padding: 4px;
            }
            """
        )

        cfg = config_from_slug("tae")
        self.clock = PlantClock(cfg)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)

        # Header
        self.header = QLabel()
        self.header.setFont(QFont("IBM Plex Sans", 13, QFont.Weight.DemiBold))
        self.header.setStyleSheet(
            "background:#15201c; border-bottom:1px solid #2a3632; padding:10px 12px;"
        )
        outer.addWidget(self.header)

        split = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(split, 1)

        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 0, 0)
        self.controls = ControlPanel()
        left_l.addWidget(self.controls, 3)
        self.site_io = SiteIOPanel()
        left_l.addWidget(self.site_io, 2)
        split.addWidget(left)

        mid = QWidget()
        mid_l = QVBoxLayout(mid)
        mid_l.setContentsMargins(4, 4, 4, 4)
        self.schematic = SchematicView()
        mid_l.addWidget(self.schematic, 2)
        self.charts = StripChartPanel()
        mid_l.addWidget(self.charts, 3)
        split.addWidget(mid)

        right = QWidget()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(4, 4, 4, 4)
        self.alarms = AlarmRail()
        right_l.addWidget(self.alarms, 2)
        self.report_view = QTextEdit()
        self.report_view.setReadOnly(True)
        self.report_view.setPlaceholderText("Run report appears here…")
        self.report_view.setStyleSheet(
            "background:#101416; color:#c5d0ca; border:1px solid #2a3632; font-family: monospace;"
        )
        right_l.addWidget(self.report_view, 1)
        split.addWidget(right)
        split.setSizes([340, 720, 300])

        self.controls.config_changed.connect(self._on_config)
        self.controls.run_clicked.connect(self._run)
        self.controls.abort_clicked.connect(self._abort)
        self.controls.reset_clicked.connect(self._reset)
        self.controls.report_clicked.connect(self._report)
        self.controls.novel_clicked.connect(self._novel)

        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

        self._on_config(cfg)
        self._refresh_header()

    def _on_config(self, cfg: PlantConfig) -> None:
        self.clock.reconfigure(cfg)
        self.alarms.reset()
        self.schematic.set_context(
            self.clock.plugin.schematic_kind(),
            cfg.slug,
            bool(cfg.mixins.get("degenerate_boron")),
        )
        self.site_io.set_config(cfg)
        self._refresh_header()

    def _run(self) -> None:
        cfg = self.controls.build_config()
        self.clock.reconfigure(cfg)
        self.schematic.set_context(
            self.clock.plugin.schematic_kind(),
            cfg.slug,
            bool(cfg.mixins.get("degenerate_boron")),
        )
        self.site_io.set_config(cfg)
        self.clock.start()
        self._refresh_header()

    def _abort(self) -> None:
        self.clock.abort()
        self._refresh_header()

    def _reset(self) -> None:
        self.clock.reset()
        self.alarms.reset()
        self.report_view.clear()
        self._refresh_header()

    def _report(self) -> None:
        rep = build_report(self.clock)
        self.report_view.setPlainText(rep.as_text())

    def _novel(self) -> None:
        dlg = NovelDialog(self)
        if dlg.exec():
            cfg = dlg.result_config()
            if cfg:
                self.controls.apply_external_config(cfg)
                QMessageBox.information(
                    self,
                    "Novel preset",
                    f"Loaded {cfg.novel_tag} on family plugin '{cfg.family}'.",
                )

    def _tick(self) -> None:
        self.clock.tick()
        self.schematic.set_bus(self.clock.bus)
        self.charts.update_from_bus(self.clock.bus)
        self.alarms.update_from_bus(self.clock.bus)
        self.site_io.update_from_bus(self.clock.bus)
        self._refresh_header()

    def _refresh_header(self) -> None:
        cfg = self.clock.config
        st: RunState = self.clock.run_state
        pos = f"POS★ {cfg.pos_star:.0f}" if cfg.pos_star is not None else "POS★ —"
        rank = f"#{cfg.plant_odds_rank}" if cfg.plant_odds_rank else ""
        novel = f"  |  {cfg.novel_tag}" if cfg.novel_tag else ""
        health = self.clock.bus.get("twin_health", 1.0)
        batt = self.clock.bus.get("batt_SOC", 1.0)
        qpl = self.clock.bus.get("Q_plant", 0.0)
        self.header.setText(
            f"{cfg.name}  [{cfg.slug}]  ·  {st.value}  ·  t={self.clock.t:6.1f}s  ·  "
            f"{pos} {rank}  ·  Q_plant={qpl:.3g}  ·  batt {100*batt:.0f}%  ·  "
            f"health {health:.2f}  ·  {cfg.family}{novel}"
        )
