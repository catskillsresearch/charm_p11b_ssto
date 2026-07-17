"""Plant clock: advances plugin + StreamBus + site I/O + commission sequence."""

from __future__ import annotations

from enum import Enum

from simulator.plant.commission import (
    CommissionState,
    apply_commission_tick,
    fresh_commission,
    sequences_for_slug,
    stage_power_MW,
)
from simulator.plant.config import PlantConfig
from simulator.plant.site_io import SiteIOState, fresh_site_io, gate_pre_production, step_site_io
from simulator.plant.streams import StreamBus
from simulator.plugins.base import ArchitecturePlugin, get_plugin
from simulator.plugins.mixins.degenerate_boron import DegenerateBoronMixin


class RunState(str, Enum):
    IDLE = "Idle"
    PREPPING = "Prepping"
    PLASMA = "Plasma"
    PULSE = "Pulse"
    PAUSED = "Paused"
    TRIP = "Trip"
    SHOT_END = "Shot end"


class PlantClock:
    def __init__(self, config: PlantConfig) -> None:
        self.bus = StreamBus()
        self.t = 0.0
        self.dt = 0.05
        self.running = False
        self.paused = False
        self.run_state = RunState.IDLE
        self._state_before_pause: RunState = RunState.IDLE
        self._trip_latched = False
        self.config = config
        self.plugin: ArchitecturePlugin = get_plugin(config)
        self._attach_mixins()
        self.state = self.plugin.reset_state()
        self.site: SiteIOState = fresh_site_io(config)
        self.commission: CommissionState = fresh_commission(config.slug)
        self._publish_idle_site()

    def _attach_mixins(self) -> None:
        mixins = []
        if self.config.mixins.get("degenerate_boron"):
            m = DegenerateBoronMixin()
            if m.is_allowed(self.config):
                mixins.append(m)
        self.plugin.attach_mixins(mixins)

    def _has_commission(self) -> bool:
        return bool(sequences_for_slug(self.config.slug))

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
        self.commission = fresh_commission(config.slug)
        self.t = 0.0
        self._trip_latched = False
        self.running = False
        self.paused = False
        self.run_state = RunState.IDLE
        self._publish_idle_site()
        if was_running:
            self.start()

    def start(self) -> None:
        self.running = True
        self.paused = False
        self._trip_latched = False
        self.site = fresh_site_io(self.config)
        self.commission = fresh_commission(self.config.slug)
        if self._has_commission():
            self.run_state = RunState.PREPPING
            n = len(self.commission.stages)
            self.bus.alarm(
                self.t,
                "info",
                "RUN",
                f"Run started — {self.config.slug} | batt {self.site.batt_kWh_cap:.1f} kWh | "
                f"{n} commission stages (warps for long facility steps)",
            )
        else:
            t_prod = self.site.time_to_production_s
            self.run_state = RunState.PREPPING if t_prod > 0 else (
                RunState.PULSE
                if self.config.family in {"laser_hedp", "mec_orbitron"}
                else RunState.PLASMA
            )
            self.bus.alarm(
                self.t,
                "info",
                "RUN",
                f"Run started — {self.config.slug} | batt {self.site.batt_kWh_cap:.1f} kWh "
                f"| t_prod {t_prod:g}s ({self.config.spec_data_quality})",
            )

    def pause(self) -> None:
        if not self.running or self._trip_latched:
            return
        if self.paused:
            self.paused = False
            self.run_state = self._state_before_pause
            self.bus.alarm(self.t, "info", "PAUSE", "Resumed")
        else:
            self._state_before_pause = self.run_state
            self.paused = True
            self.run_state = RunState.PAUSED
            self.bus.alarm(self.t, "info", "PAUSE", "Paused — clock frozen")

    def abort(self) -> None:
        self.running = False
        self.paused = False
        self.run_state = RunState.TRIP if self._trip_latched else RunState.IDLE
        self.bus.alarm(self.t, "warn", "ABORT", "Operator abort")

    def reset(self) -> None:
        self.running = False
        self.paused = False
        self._trip_latched = False
        self.t = 0.0
        self.state = self.plugin.reset_state()
        self.bus = StreamBus()
        self.site = fresh_site_io(self.config)
        self.commission = fresh_commission(self.config.slug)
        self.run_state = RunState.IDLE
        self._attach_mixins()
        self._publish_idle_site()

    def tick(self) -> None:
        self.bus.set("t", self.t)
        self.bus.set("Q_ref", 1.0)
        if self.paused:
            self.bus.commit_sample(self.t)
            return

        active = self.running and not self._trip_latched
        if not active:
            self.state = self.plugin.step(self.state, self.bus, self.dt, False)
            step_site_io(self.site, self.config, self.bus, dt=0.0, running=False)
            self.bus.commit_sample(self.t)
            return

        step_dt = self.dt
        plasma = False

        if self._has_commission() and not self.commission.done:
            self.t, plasma, step_dt = apply_commission_tick(
                self.commission, self.site, self.bus, self.dt, self.t
            )
            self.state = self.plugin.step(self.state, self.bus, step_dt, plasma)
            if not plasma:
                gate_pre_production(self.bus, self.config, 0.0)
                cur = self.commission.current
                disp = stage_power_MW(cur) if cur and cur.batt_powered else 0.0
                # Prep electrical already applied inside commission; site_io publishes only
                step_site_io(
                    self.site,
                    self.config,
                    self.bus,
                    dt=step_dt,
                    running=True,
                    force_need_MW=disp,
                    skip_fuel=True,
                )
            else:
                step_site_io(
                    self.site,
                    self.config,
                    self.bus,
                    dt=step_dt,
                    running=True,
                    advance_t_run=False,
                    force_producing=True,
                )
            self.run_state = RunState.PLASMA if plasma else RunState.PREPPING
            if self.config.family in {"laser_hedp", "mec_orbitron"} and plasma:
                self.run_state = RunState.PULSE

            if self.commission.shot_complete:
                self.running = False
                self.run_state = RunState.SHOT_END
                self.bus.alarm(
                    self.t,
                    "info",
                    "END",
                    "Commission sequence complete — research shot/window ended (Q≪1 islanded)",
                )
        else:
            # Legacy t_prod gate for architectures without a sequence
            t_run_next = self.site.t_run + self.dt
            t_prod = max(0.0, self.config.time_to_production_s)
            plasma = t_prod <= 0.0 or t_run_next + 1e-12 >= t_prod
            self.state = self.plugin.step(self.state, self.bus, self.dt, plasma)
            if not plasma:
                gate_pre_production(self.bus, self.config, t_run_next)
            step_site_io(self.site, self.config, self.bus, self.dt, True)
            if plasma and self.run_state == RunState.PREPPING:
                self.run_state = (
                    RunState.PULSE
                    if self.config.family in {"laser_hedp", "mec_orbitron"}
                    else RunState.PLASMA
                )
            self.t += self.dt

        # Battery / hard trips
        if self.bus.alarms and self.bus.alarms[0].level == "trip" and self.running:
            if self.bus.alarms[0].t >= self.t - step_dt - 1e-9:
                self._trip_latched = True
                self.running = False
                self.run_state = RunState.TRIP

        # Islanded Q≪1: if producing and still importing hard, battery will drain;
        # empty battery already trips. Also stop if SOC hit zero this tick.
        if self.site.batt_kWh <= 0 and self.running:
            self._trip_latched = True
            self.running = False
            self.run_state = RunState.TRIP

        self._publish_commission_ui()
        self.bus.commit_sample(self.t)

    def _publish_commission_ui(self) -> None:
        cur = self.commission.current
        if cur is None:
            self.bus.set("commission_label", 0.0)
            return
        # Encode remaining for header
        rem = max(0.0, cur.duration_s - self.commission.stage_elapsed_s)
        self.bus.set("preprod_remaining_s", rem)
        self.bus.set("apu_bootstrap_s", cur.duration_s)
