"""Paper-style lab-shot stripcharts vs shot time (ms), not wall clock."""

from __future__ import annotations

from collections import deque

import pyqtgraph as pg
from PySide6.QtWidgets import QVBoxLayout, QWidget

from simulator.plant.streams import StreamBus

pg.setConfigOptions(antialias=True, background="#121618", foreground="#c8d4ce")


class ShotChartPanel(QWidget):
    """C-2W-like diagnostic stacks on 0–T_shot ms axis."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.plot = pg.GraphicsLayoutWidget()
        layout.addWidget(self.plot)

        self._t: deque[float] = deque(maxlen=800)
        self._ys: dict[str, deque[float]] = {}
        self._curves: dict[str, pg.PlotDataItem] = {}
        self._plots: list[pg.PlotItem] = []

        stacks = [
            (
                "FRC size / flux / density / energy",
                [
                    ("r_dphi_m", "#3dd6c6", "rΔφ (m)"),
                    ("phi_p_mWb", "#6aa9ff", "φp (mWb)"),
                    ("n_e_19", "#ffd27a", "ne (1e19)"),
                    ("E_tot_kJ", "#ff8b6a", "Etot (kJ)"),
                ],
            ),
            (
                "Te / NBI / bias",
                [
                    ("T_e_avg_keV", "#7dffb3", "Te avg"),
                    ("T_e_max_keV", "#90be6d", "Te max"),
                    ("P_NBI_MW", "#6aa9ff", "PNBI (MW)"),
                    ("bias_kV", "#c79bff", "bias (kV)"),
                ],
            ),
            (
                "MHD / rotation",
                [
                    ("mode_n1", "#ff8b6a", "n=1"),
                    ("mode_n2", "#f0d060", "n=2"),
                    ("omega_imp_krad_s", "#8ecae6", "Ωimp"),
                ],
            ),
        ]
        for row, (title, series) in enumerate(stacks):
            plt = self.plot.addPlot(row=row, col=0, title=title)
            plt.showGrid(x=True, y=True, alpha=0.2)
            plt.addLegend(offset=(8, 8))
            plt.setLabel("bottom", "shot time", units="ms")
            if row < len(stacks) - 1:
                plt.hideAxis("bottom")
            self._plots.append(plt)
            for key, color, label in series:
                self._ys[key] = deque(maxlen=800)
                pen = pg.mkPen(color, width=1.6)
                self._curves[key] = plt.plot(pen=pen, name=label)

    def reset(self) -> None:
        self._t.clear()
        for d in self._ys.values():
            d.clear()
        for c in self._curves.values():
            c.setData([], [])

    def update_from_bus(self, bus: StreamBus) -> None:
        t_ms = bus.get("shot_t_ms")
        if t_ms <= 0 and bus.get("plasma_playback") < 0.5 and not self._t:
            return
        if t_ms < 0:
            return
        # New shot: clear if time went backwards
        if self._t and t_ms + 1e-6 < self._t[-1]:
            self.reset()
        if bus.get("plasma_playback") >= 0.5 or t_ms > 0:
            self._t.append(t_ms)
            for key, buf in self._ys.items():
                buf.append(bus.get(key))
        if len(self._t) < 2:
            return
        tt = list(self._t)
        for key, curve in self._curves.items():
            yy = list(self._ys[key])
            n = min(len(tt), len(yy))
            curve.setData(tt[-n:], yy[-n:])
        t_end = bus.get("shot_duration_s") * 1000.0 or max(tt[-1], 40.0)
        for plt in self._plots:
            plt.setXRange(0.0, max(t_end, tt[-1]) * 1.02, padding=0.0)
