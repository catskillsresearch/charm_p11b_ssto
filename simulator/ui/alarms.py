"""Scrolling alarm / trip rail."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget, QLabel

from simulator.plant.streams import StreamBus


class AlarmRail(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        title = QLabel("ALARM RAIL")
        title.setStyleSheet("color:#8fa89e; font-size:11px; font-weight:600;")
        layout.addWidget(title)
        self.list = QListWidget()
        self.list.setStyleSheet(
            "QListWidget{background:#101416;color:#d7e0dc;border:1px solid #2a3632;}"
        )
        self.list.setFont(QFont("IBM Plex Mono", 10))
        layout.addWidget(self.list)
        self._seen = 0

    def update_from_bus(self, bus: StreamBus) -> None:
        # Prepend new alarms
        alarms = list(bus.alarms)
        if len(alarms) == self._seen:
            return
        self.list.clear()
        for a in alarms[:40]:
            item = QListWidgetItem(f"[{a.t:6.1f}] {a.level.upper():4} {a.code}: {a.message}")
            if a.level == "trip":
                item.setForeground(QColor("#ff6b6b"))
            elif a.level == "warn":
                item.setForeground(QColor("#ffd93d"))
            else:
                item.setForeground(QColor("#9ad1c0"))
            self.list.addItem(item)
        self._seen = len(alarms)

    def reset(self) -> None:
        self.list.clear()
        self._seen = 0
