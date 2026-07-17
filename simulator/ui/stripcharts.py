"""pyqtgraph stripchart panel for key plant streams."""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtWidgets import QVBoxLayout, QWidget

from simulator.plant.streams import StreamBus

pg.setConfigOptions(antialias=True, background="#121618", foreground="#c8d4ce")


class StripChartPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.plot = pg.GraphicsLayoutWidget()
        layout.addWidget(self.plot)

        self._curves: dict[str, pg.PlotDataItem] = {}
        specs = [
            ("power", ["P_f", "P_driver", "P_rad", "P_net"], "MW"),
            ("gain", ["Q_plasma", "Q_eng", "Q_plant"], "Q"),
            ("store", ["store_SOC", "twin_health"], ""),
        ]
        colors = {
            "P_f": "#3dd6c6",
            "P_driver": "#6aa9ff",
            "P_rad": "#ff8b6a",
            "P_net": "#f0d060",
            "Q_plasma": "#7dffb3",
            "Q_eng": "#c79bff",
            "Q_plant": "#ffd27a",
            "store_SOC": "#8ecae6",
            "twin_health": "#90be6d",
        }
        for row, (title, names, _unit) in enumerate(specs):
            plt = self.plot.addPlot(row=row, col=0, title=title)
            plt.showGrid(x=True, y=True, alpha=0.2)
            plt.addLegend(offset=(8, 8))
            if row < len(specs) - 1:
                plt.hideAxis("bottom")
            for name in names:
                c = plt.plot(pen=pg.mkPen(colors.get(name, "#fff"), width=1.5), name=name)
                self._curves[name] = c

    def update_from_bus(self, bus: StreamBus) -> None:
        t = list(bus.time_hist)
        if len(t) < 2:
            return
        for name, curve in self._curves.items():
            y = list(bus.history.get(name, []))
            n = min(len(t), len(y))
            if n >= 2:
                curve.setData(t[-n:], y[-n:])
