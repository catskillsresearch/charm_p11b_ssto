"""Magnetic compact plugin: lab-shot FRC diagnostics or continuous plant books."""

from __future__ import annotations

import math

from simulator.plant.balance import close_plant_books, rider_channel
from simulator.plant.shot_diagnostics import idle_shot_diagnostics, publish_frc_shot_diagnostics
from simulator.plant.streams import StreamBus
from simulator.plugins.base import ArchitecturePlugin


class MagneticCompactPlugin(ArchitecturePlugin):
    family = "magnetic_compact"

    def reset_state(self) -> dict[str, float]:
        return {
            "t_flattop": 0.0,
            "ash_He": 0.0,
            "magnet_SOC": 0.6,
            "n_e": 0.8,
            "T_i": 20.0,
            "T_e": 12.0,
            "plasma_on": 0.0,
        }

    def step(
        self,
        state: dict[str, float],
        bus: StreamBus,
        dt: float,
        running: bool,
    ) -> dict[str, float]:
        cfg = self.config
        if not running:
            self._idle(bus, state)
            return state

        state["plasma_on"] = 1.0
        state["t_flattop"] += dt

        # Lab single-shot: paper-style FRC diagnostics over the NBI window
        if cfg.operation_mode == "lab_shot":
            t_end = bus.get("shot_duration_s") or 0.040
            publish_frc_shot_diagnostics(
                bus, cfg, t_shot_s=state["t_flattop"], t_shot_end_s=t_end
            )
            bus.set("twin_health", 1.0)
            bus.set("energy_residual", 0.0)
            bus.set("shot_phase", state["t_flattop"] / max(t_end, 1e-9))
            bus.set("blast", 0.0)
            bus.set("orbit_phase", math.fmod(state["t_flattop"] * 40.0, 1.0))
            bus.set("Z_eff", cfg.Z_eff)
            bus.set("magnet_SOC", 0.7)
            bus.set("store_SOC", 0.7)
            return state

        # Continuous / plant theater books
        state["n_e"] = min(3.0, 0.5 + 0.4 * cfg.fueling_H + 0.3 * cfg.fueling_B11)
        state["ash_He"] += 0.02 * cfg.driver_power_MW * dt
        poison = min(0.7, state["ash_He"] / 40.0)
        Z = cfg.Z_eff + 1.8 * poison
        state["T_i"] = 8.0 + 2.2 * cfg.driver_power_MW * (0.7 + 0.5 * cfg.nonthermal)
        state["T_e"] = max(4.0, state["T_i"] * (0.55 + 0.2 * (1.0 - cfg.nonthermal)))

        coeffs = {"fusion_scale": 1.0, "couple_scale": 1.0, "rad_scale": 1.0}
        coeffs = self.apply_mixin_patches(coeffs, bus)
        P_i_to_e, P_rad = rider_channel(
            T_i=state["T_i"],
            T_e=state["T_e"],
            n_e=state["n_e"],
            Z_eff=Z,
            nonthermal=cfg.nonthermal,
        )
        P_i_to_e *= coeffs["couple_scale"]
        P_rad *= coeffs["rad_scale"]
        reactivity = max(0.2, (state["T_i"] / 25.0) ** 1.5 * state["n_e"] ** 1.3)
        P_f = (
            0.55
            * cfg.driver_power_MW
            * reactivity
            * (0.5 + cfg.nonthermal)
            * coeffs["fusion_scale"]
            * (1.0 - 0.55 * poison)
            * (0.7 + 0.15 * cfg.B_T)
        )
        if cfg.slug in {"enn", "pale-blue-charm"}:
            P_f *= 1e-4

        state["magnet_SOC"] = min(
            1.0, max(0.15, state["magnet_SOC"] + dt * (0.02 * cfg.B_T - 0.01))
        )
        recharge = 0.4 * cfg.B_T + 0.1 * cfg.driver_power_MW
        books = close_plant_books(
            P_f=P_f,
            P_driver=cfg.driver_power_MW,
            P_i_to_e=P_i_to_e,
            P_rad=P_rad,
            transport_frac=0.35,
            dec_eta=0.35 if "frc" in cfg.confinement.lower() else 0.15,
            thermal_eta=0.35,
            house_base_MW=1.2 + 0.3 * cfg.B_T,
            store_recharge_MW=recharge,
        )
        self._publish(bus, cfg, state, books, Z)
        bus.set("twin_health", max(0.0, 1.0 - books.energy_residual * 3.0))
        bus.set("energy_residual", books.energy_residual)
        bus.set("plasma_brightness", min(1.0, max(0.15, 1.0 - poison)))
        bus.set("shot_phase", 0.0)
        bus.set("blast", 0.0)
        return state

    def _idle(self, bus: StreamBus, state: dict[str, float]) -> None:
        for k in (
            "P_f",
            "P_driver",
            "P_rad",
            "P_net",
            "P_gross",
            "Q_plasma",
            "Q_eng",
            "Q_plant",
            "plasma_brightness",
        ):
            bus.set(k, 0.0)
        idle_shot_diagnostics(bus)
        bus.set("magnet_SOC", state.get("magnet_SOC", 0.6))
        bus.set("store_SOC", state.get("magnet_SOC", 0.6))
        bus.set("twin_health", 1.0)

    def _publish(self, bus: StreamBus, cfg, state, books, Z: float) -> None:
        bus.set("P_f", books.P_f)
        bus.set("P_driver", cfg.driver_power_MW)
        bus.set("P_i_to_e", books.P_i_to_e)
        bus.set("P_rad", books.P_rad)
        bus.set("P_wall", books.P_wall)
        bus.set("P_gross", books.P_gross)
        bus.set("P_recirc", books.P_recirc)
        bus.set("P_net", books.P_net)
        bus.set("P_import", books.P_import)
        bus.set("P_reject", books.P_reject)
        bus.set("Q_plasma", books.Q_plasma)
        bus.set("Q_eng", books.Q_eng)
        bus.set("Q_plant", books.Q_plant)
        bus.set("n_e", state["n_e"])
        bus.set("T_i", state["T_i"])
        bus.set("T_e", state["T_e"])
        bus.set("Z_eff", Z)
        bus.set("fuel_H", cfg.fueling_H)
        bus.set("fuel_B11", cfg.fueling_B11)
        bus.set("ash_He", state["ash_He"])
        bus.set("magnet_SOC", state["magnet_SOC"])
        bus.set("store_SOC", state["magnet_SOC"])
        bus.set("rep_rate", 0.0)
        # mild animation phase for plasma blob
        bus.set("orbit_phase", math.fmod(state["t_flattop"] * 0.7, 1.0))
