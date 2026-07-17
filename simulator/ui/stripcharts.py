"""pyqtgraph stripchart panel for key plant streams."""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Qt
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
        self._plots: list[pg.PlotItem] = []
        specs = [
            ("power MW", ["P_f", "P_driver", "P_rad", "P_net"], "MW"),
            ("gain (Q=1 dashed)", ["Q_plasma", "Q_eng", "Q_plant", "Q_ref"], "Q"),
            ("battery / health", ["batt_SOC", "twin_health"], ""),
            ("site kW", ["batt_draw_kW", "grid_export_kW", "batt_charge_kW"], "kW"),
        ]
        colors = {
            "P_f": "#3dd6c6",
            "P_driver": "#6aa9ff",
            "P_rad": "#ff8b6a",
            "P_net": "#f0d060",
            "Q_plasma": "#7dffb3",
            "Q_eng": "#c79bff",
            "Q_plant": "#ffd27a",
            "Q_ref": "#888888",
            "batt_SOC": "#8ecae6",
            "twin_health": "#90be6d",
            "batt_draw_kW": "#ff8b6a",
            "grid_export_kW": "#3dd6c6",
            "batt_charge_kW": "#6aa9ff",
        }
        for row, (title, names, _unit) in enumerate(specs):
            plt = self.plot.addPlot(row=row, col=0, title=title)
            plt.showGrid(x=True, y=True, alpha=0.2)
            plt.addLegend(offset=(8, 8))
            if row < len(specs) - 1:
                plt.hideAxis("bottom")
            self._plots.append(plt)
            for name in names:
                pen = pg.mkPen(colors.get(name, "#fff"), width=1.5)
                if name == "Q_ref":
                    pen.setStyle(Qt.PenStyle.DashLine)
                c = plt.plot(pen=pen, name=name)
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

        # After long commission warps, zoom to the shot window (or last ~30 s)
        t0 = bus.get("chart_zoom_t0")
        t_end = t[-1]
        if t0 > 0 and t_end >= t0:
            pad = max(0.02, 0.25 * max(t_end - t0, 1e-3))
            x0, x1 = t0 - pad, t_end + pad
        elif t_end - t[0] > 60:
            x0, x1 = t_end - 30.0, t_end + 0.5
        else:
            return
        for plt in self._plots:
            plt.setXRange(x0, x1, padding=0.0)
