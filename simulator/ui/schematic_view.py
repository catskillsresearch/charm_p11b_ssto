"""2D vessel / core schematic with animated overlays."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PySide6.QtWidgets import QWidget

from simulator.plant.streams import StreamBus


class SchematicView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bus = StreamBus()
        self.kind = "generic"
        self.slug = ""
        self.mixin_on = False
        self.setMinimumHeight(280)
        self.setAutoFillBackground(True)

    def set_context(self, kind: str, slug: str, mixin_on: bool = False) -> None:
        self.kind = kind
        self.slug = slug
        self.mixin_on = mixin_on
        self.update()

    def set_bus(self, bus: StreamBus) -> None:
        self.bus = bus
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(8, 8, -8, -8)
        p.fillRect(self.rect(), QColor(18, 22, 24))
        p.setPen(QPen(QColor(60, 80, 75), 1))
        p.drawRect(r)

        if self.kind == "magnetic_compact":
            self._paint_magnetic(p, r)
        elif self.kind == "laser_hedp":
            self._paint_laser(p, r)
        elif self.kind == "mec_orbitron":
            self._paint_mec(p, r)
        else:
            self._paint_generic(p, r)

        # I/O arrows legend strip
        p.setPen(QColor(160, 180, 170))
        p.setFont(QFont("IBM Plex Sans", 9))
        pf = self.bus.get("P_f")
        pin = self.bus.get("P_import")
        pnet = self.bus.get("P_net")
        p.drawText(
            r.adjusted(10, 6, -10, -6),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            f"{self.slug}  |  Pin {pin:.2f} MW  Pf {pf:.2f} MW  Pnet {pnet:.2f} MW",
        )
        if self.mixin_on:
            p.setPen(QColor(230, 160, 60))
            p.drawText(
                r.adjusted(10, 22, -10, -6),
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                "mixin: degenerate-boron ON",
            )

    def _paint_magnetic(self, p: QPainter, r: QRectF) -> None:
        # Linear vessel
        cy = r.center().y()
        vessel = QRectF(r.left() + 40, cy - 40, r.width() - 80, 80)
        p.setPen(QPen(QColor(120, 150, 140), 2))
        p.setBrush(QBrush(QColor(28, 36, 34)))
        p.drawRoundedRect(vessel, 12, 12)

        # Plasma blob
        bright = self.bus.get("plasma_brightness", 0.0)
        phase = self.bus.get("orbit_phase", 0.0)
        wobble = 6 * math.sin(phase * 6.28)
        blob = QRectF(
            vessel.center().x() - 50 + wobble,
            vessel.center().y() - 22,
            100,
            44,
        )
        glow = QColor(40, 200, 160, int(40 + 180 * bright))
        p.setBrush(QBrush(glow))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(blob)

        # NBI arrow
        p.setPen(QPen(QColor(100, 180, 255), 3))
        y = vessel.center().y() - 10
        p.drawLine(QPointF(vessel.left() - 20, y), QPointF(vessel.left() + 30, y))
        p.drawText(QPointF(vessel.left() - 35, y - 8), "NBI")

        # Alpha exhaust
        p.setPen(QPen(QColor(255, 180, 80), 2))
        p.drawLine(
            QPointF(vessel.right() - 10, vessel.center().y()),
            QPointF(vessel.right() + 35, vessel.center().y() - 15),
        )
        p.drawText(QPointF(vessel.right() + 8, vessel.center().y() - 20), "α")

        # Fuel in
        p.setPen(QPen(QColor(180, 220, 120), 2))
        p.drawLine(
            QPointF(vessel.center().x(), vessel.top() - 25),
            QPointF(vessel.center().x(), vessel.top() + 5),
        )
        p.drawText(QPointF(vessel.center().x() + 6, vessel.top() - 10), "H/B")

    def _paint_laser(self, p: QPainter, r: QRectF) -> None:
        chamber = QRectF(r.center().x() - 90, r.center().y() - 70, 180, 140)
        p.setPen(QPen(QColor(140, 140, 160), 2))
        p.setBrush(QBrush(QColor(24, 24, 32)))
        p.drawEllipse(chamber)

        # Target / catcher
        dens = 1.0 + (self.bus.get("mixin_gain", 1.0) - 1.0)
        tgt = QRectF(
            chamber.center().x() - 10 * dens**0.2,
            chamber.center().y() - 8,
            20 * dens**0.2,
            16,
        )
        p.setBrush(QBrush(QColor(90, 90, 110)))
        p.drawRect(tgt)

        blast = self.bus.get("blast", 0.0)
        if blast > 0.05:
            p.setBrush(QBrush(QColor(255, 220, 120, int(60 + 180 * blast))))
            p.setPen(Qt.PenStyle.NoPen)
            rad = 20 + 50 * blast
            p.drawEllipse(chamber.center(), rad, rad)

        # Lasers
        p.setPen(QPen(QColor(255, 80, 80), 3))
        p.drawLine(
            QPointF(r.left() + 20, chamber.center().y() - 30),
            QPointF(chamber.left() + 20, chamber.center().y() - 10),
        )
        p.drawLine(
            QPointF(r.left() + 20, chamber.center().y() + 30),
            QPointF(chamber.left() + 20, chamber.center().y() + 10),
        )
        p.drawText(QPointF(r.left() + 16, chamber.center().y() - 40), "CPA")

        phase = int(self.bus.get("shot_phase", 0))
        labels = ["CHARGE", "FIRE", "BURN", "RECOVER"]
        p.setPen(QColor(200, 200, 220))
        p.drawText(
            QPointF(chamber.center().x() - 30, chamber.bottom() + 24),
            labels[min(phase, 3)],
        )

        # Debris / ash out
        p.setPen(QPen(QColor(180, 140, 100), 2))
        p.drawLine(
            QPointF(chamber.right() - 10, chamber.center().y() + 20),
            QPointF(chamber.right() + 40, chamber.center().y() + 40),
        )
        p.drawText(QPointF(chamber.right() + 10, chamber.center().y() + 55), "debris/He")

    def _paint_mec(self, p: QPainter, r: QRectF) -> None:
        cx, cy = r.center().x(), r.center().y()
        # Cathode / anode rings
        p.setPen(QPen(QColor(180, 160, 80), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), 70, 70)
        p.drawEllipse(QPointF(cx, cy), 28, 28)
        p.drawText(QPointF(cx + 76, cy), "HV")

        # Orbiting ions
        phase = self.bus.get("orbit_phase", 0.0) * 6.2832
        bright = self.bus.get("plasma_brightness", 0.0)
        for i in range(5):
            ang = phase + i * 1.256
            x = cx + 48 * math.cos(ang)
            y = cy + 48 * math.sin(ang)
            p.setBrush(QBrush(QColor(80, 200, 255, int(80 + 150 * bright))))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(x, y), 5, 5)

        hv = self.bus.get("HV_kV", 0.0)
        p.setPen(QColor(220, 200, 120))
        p.drawText(QPointF(cx - 40, cy + 100), f"{hv:.0f} kV Orbitron")

        # Power in / out
        p.setPen(QPen(QColor(120, 220, 140), 2))
        p.drawLine(QPointF(r.left() + 30, cy), QPointF(cx - 75, cy))
        p.drawText(QPointF(r.left() + 30, cy - 10), "grid")
        p.setPen(QPen(QColor(255, 180, 80), 2))
        p.drawLine(QPointF(cx + 75, cy), QPointF(r.right() - 30, cy))
        p.drawText(QPointF(r.right() - 70, cy - 10), "Pnet")

    def _paint_generic(self, p: QPainter, r: QRectF) -> None:
        box = QRectF(r.center().x() - 80, r.center().y() - 50, 160, 100)
        p.setPen(QPen(QColor(100, 120, 130), 2, Qt.PenStyle.DashLine))
        p.setBrush(QBrush(QColor(30, 34, 38)))
        p.drawRect(box)
        p.setPen(QColor(180, 190, 200))
        p.drawText(box, Qt.AlignmentFlag.AlignCenter, "abstract chamber\n(novel / generic)")
        bright = self.bus.get("plasma_brightness", 0.0)
        if bright > 0:
            p.setBrush(QBrush(QColor(100, 180, 160, int(200 * bright))))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(box.center(), 30 * bright + 10, 20 * bright + 8)
