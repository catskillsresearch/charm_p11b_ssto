"""Main operator console window — lab-shot or continuous-plant layouts."""

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
from simulator.plant.operation_mode import continuous_banner, lab_shot_banner
from simulator.plant.report import build_report
from simulator.ui.alarms import AlarmRail
from simulator.ui.controls import ControlPanel
from simulator.ui.facility_note import FacilityNotePanel
from simulator.ui.novel_dialog import NovelDialog
from simulator.ui.schematic_view import SchematicView
from simulator.ui.shot_charts import ShotChartPanel
from simulator.ui.site_io_panel import SiteIOPanel
from simulator.ui.stripcharts import StripChartPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("p11b operator twin — survey theater")
        self.resize(1480, 900)
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

        self.mode_banner = QLabel()
        self.mode_banner.setWordWrap(True)
        self.mode_banner.setFont(QFont("IBM Plex Sans", 11, QFont.Weight.DemiBold))
        outer.addWidget(self.mode_banner)

        self.header = QLabel()
        self.header.setFont(QFont("IBM Plex Sans", 12, QFont.Weight.DemiBold))
        self.header.setStyleSheet(
            "background:#15201c; border-bottom:1px solid #2a3632; padding:8px 12px;"
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
        self.facility_note = FacilityNotePanel()
        left_l.addWidget(self.facility_note, 1)
        split.addWidget(left)

        mid = QWidget()
        mid_l = QVBoxLayout(mid)
        mid_l.setContentsMargins(4, 4, 4, 4)
        self.schematic = SchematicView()
        mid_l.addWidget(self.schematic, 2)
        self.charts = StripChartPanel()
        mid_l.addWidget(self.charts, 3)
        self.shot_charts = ShotChartPanel()
        mid_l.addWidget(self.shot_charts, 3)
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
        split.setSizes([320, 780, 300])

        self.controls.config_changed.connect(self._on_config)
        self.controls.run_clicked.connect(self._run)
        self.controls.pause_clicked.connect(self._pause)
        self.controls.abort_clicked.connect(self._abort)
        self.controls.reset_clicked.connect(self._reset)
        self.controls.report_clicked.connect(self._report)
        self.controls.novel_clicked.connect(self._novel)

        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

        self._apply_mode_layout(cfg)
        self._on_config(cfg)
        self._refresh_header()

    def _is_lab(self, cfg: PlantConfig | None = None) -> bool:
        c = cfg or self.clock.config
        return c.operation_mode == "lab_shot"

    def _apply_mode_layout(self, cfg: PlantConfig) -> None:
        lab = self._is_lab(cfg)
        if lab:
            self.mode_banner.setStyleSheet(
                "background:#3a2a12; color:#f0d9a8; border:1px solid #6a5020; padding:10px 12px;"
            )
            self.mode_banner.setText(lab_shot_banner(cfg.slug))
            self.site_io.hide()
            self.facility_note.show()
            self.facility_note.set_config(cfg)
            self.charts.hide()
            self.shot_charts.show()
        else:
            self.mode_banner.setStyleSheet(
                "background:#1a2a32; color:#a8d4e8; border:1px solid #2a5060; padding:10px 12px;"
            )
            self.mode_banner.setText(continuous_banner(cfg.slug))
            self.site_io.show()
            self.facility_note.hide()
            self.charts.show()
            self.shot_charts.hide()

    def _on_config(self, cfg: PlantConfig) -> None:
        self.clock.reconfigure(cfg)
        self.alarms.reset()
        self.shot_charts.reset()
        self.schematic.set_context(
            self.clock.plugin.schematic_kind(),
            cfg.slug,
            bool(cfg.mixins.get("degenerate_boron")),
        )
        self.site_io.set_config(cfg)
        self._apply_mode_layout(cfg)
        self._refresh_header()

    def _run(self) -> None:
        cfg = self.controls.build_config()
        self.clock.reconfigure(cfg)
        self.shot_charts.reset()
        self.schematic.set_context(
            self.clock.plugin.schematic_kind(),
            cfg.slug,
            bool(cfg.mixins.get("degenerate_boron")),
        )
        self.site_io.set_config(cfg)
        self._apply_mode_layout(cfg)
        self.clock.start()
        self.controls.btn_pause.setText("PAUSE")
        self._refresh_header()

    def _pause(self) -> None:
        self.clock.pause()
        self.controls.btn_pause.setText("RESUME" if self.clock.paused else "PAUSE")
        self._refresh_header()

    def _abort(self) -> None:
        self.clock.abort()
        self.controls.btn_pause.setText("PAUSE")
        self._refresh_header()

    def _reset(self) -> None:
        self.clock.reset()
        self.alarms.reset()
        self.shot_charts.reset()
        self.report_view.clear()
        self.controls.btn_pause.setText("PAUSE")
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
        prev = self.clock.run_state
        self.clock.tick()
        self.schematic.set_bus(self.clock.bus)
        if self._is_lab():
            self.shot_charts.update_from_bus(self.clock.bus)
        else:
            self.charts.update_from_bus(self.clock.bus)
            self.site_io.update_from_bus(self.clock.bus)
        self.alarms.update_from_bus(self.clock.bus)
        self._refresh_header()
        if prev != RunState.SHOT_END and self.clock.run_state == RunState.SHOT_END:
            self._report()

    def _refresh_header(self) -> None:
        cfg = self.clock.config
        st: RunState = self.clock.run_state
        pos = f"POS★ {cfg.pos_star:.0f}" if cfg.pos_star is not None else "POS★ —"
        rank = f"#{cfg.plant_odds_rank}" if cfg.plant_odds_rank else ""
        novel = f"  |  {cfg.novel_tag}" if cfg.novel_tag else ""
        if self._is_lab():
            t_ms = self.clock.bus.get("shot_t_ms")
            etot = self.clock.bus.get("E_tot_kJ")
            te = self.clock.bus.get("T_e_avg_keV")
            rem = self.clock.bus.get("preprod_remaining_s")
            cur = self.clock.commission.current
            stage = ""
            if cur and cur.plasma and rem > 0:
                wall_left = rem / max(cur.duration_s, 1e-9) * 8.0
                stage = f"  ·  {rem*1000:.1f} ms sim left (~{wall_left:.1f}s wall)"
            elif st == RunState.SHOT_END:
                stage = "  ·  shot complete"
            self.header.setText(
                f"{cfg.name}  [{cfg.slug}]  ·  {st.value}  ·  "
                f"shot t={t_ms:5.1f} ms  ·  Etot={etot:.1f} kJ  ·  Te={te:.2f} keV"
                f"{stage}  ·  {pos} {rank}  ·  lab_shot{novel}"
            )
        else:
            health = self.clock.bus.get("twin_health", 1.0)
            batt = self.clock.bus.get("batt_SOC", 1.0)
            qpl = self.clock.bus.get("Q_plant", 0.0)
            self.header.setText(
                f"{cfg.name}  [{cfg.slug}]  ·  {st.value}  ·  t={self.clock.t:6.1f}s  ·  "
                f"{pos} {rank}  ·  Q_plant={qpl:.3g}  ·  batt {100*batt:.0f}%  ·  "
                f"health {health:.2f}  ·  continuous{novel}"
            )
