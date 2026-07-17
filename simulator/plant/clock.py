"""Plant clock: advances plugin + StreamBus + site I/O ledger."""

from __future__ import annotations

from enum import Enum

from simulator.plant.config import PlantConfig
from simulator.plant.site_io import SiteIOState, fresh_site_io, step_site_io
from simulator.plant.streams import StreamBus
from simulator.plugins.base import ArchitecturePlugin, get_plugin
from simulator.plugins.mixins.degenerate_boron import DegenerateBoronMixin


class RunState(str, Enum):
    IDLE = "Idle"
    PREPPING = "Prepping"
    PLASMA = "Plasma"
    PULSE = "Pulse"
    TRIP = "Trip"


class PlantClock:
    def __init__(self, config: PlantConfig) -> None:
        self.bus = StreamBus()
        self.t = 0.0
        self.dt = 0.05
        self.running = False
        self.run_state = RunState.IDLE
        self._trip_latched = False
        self.config = config
        self.plugin: ArchitecturePlugin = get_plugin(config)
        self._attach_mixins()
        self.state = self.plugin.reset_state()
        self.site: SiteIOState = fresh_site_io(config)
        self._publish_idle_site()

    def _attach_mixins(self) -> None:
        mixins = []
        if self.config.mixins.get("degenerate_boron"):
            m = DegenerateBoronMixin()
            if m.is_allowed(self.config):
                mixins.append(m)
        self.plugin.attach_mixins(mixins)

    def _publish_idle_site(self) -> None:
        self.bus.set("Q_ref", 1.0)
        step_site_io(self.site, self.config, self.bus, dt=0.0, running=False)

    def reconfigure(self, config: PlantConfig) -> None:
        was_running = self.running
        self.config = config
        self.plugin = get_plugin(config)
        self._attach_mixins()
        self.state = self.plugin.reset_state()
        self.bus = StreamBus()
        self.site = fresh_site_io(config)
        self.t = 0.0
        self._trip_latched = False
        self.running = False
        self.run_state = RunState.IDLE
        self._publish_idle_site()
        if was_running:
            self.start()

    def start(self) -> None:
        self.running = True
        self._trip_latched = False
        # Full charge at each RUN
        self.site = fresh_site_io(self.config)
        if self.config.family in {"laser_hedp", "mec_orbitron"}:
            self.run_state = RunState.PULSE
        else:
            self.run_state = RunState.PLASMA
        self.bus.alarm(
            self.t,
            "info",
            "RUN",
            f"Run started — {self.config.slug} | batt {self.site.batt_kWh_cap:.1f} kWh @ {self.site.batt_V:.0f} V",
        )

    def abort(self) -> None:
        self.running = False
        self.run_state = RunState.TRIP if self._trip_latched else RunState.IDLE
        self.bus.alarm(self.t, "warn", "ABORT", "Operator abort")

    def reset(self) -> None:
        self.running = False
        self._trip_latched = False
        self.t = 0.0
        self.state = self.plugin.reset_state()
        self.bus = StreamBus()
        self.site = fresh_site_io(self.config)
        self.run_state = RunState.IDLE
        self._attach_mixins()
        self._publish_idle_site()

    def tick(self) -> None:
        self.bus.set("t", self.t)
        self.bus.set("Q_ref", 1.0)
        active = self.running and not self._trip_latched
        self.state = self.plugin.step(self.state, self.bus, self.dt, active)
        self.site = step_site_io(self.site, self.config, self.bus, self.dt, active)
        # Latch hard trips from newest alarms
        if self.bus.alarms and self.bus.alarms[0].level == "trip" and self.running:
            if self.bus.alarms[0].t >= self.t - self.dt - 1e-9:
                self._trip_latched = True
                self.running = False
                self.run_state = RunState.TRIP
        self.bus.commit_sample(self.t)
        if self.running:
            self.t += self.dt
            if self.run_state == RunState.IDLE:
                self.run_state = RunState.PREPPING
