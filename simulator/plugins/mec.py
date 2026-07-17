"""Compact MEC / Orbitron plugin (Avalanche-style theater)."""

from __future__ import annotations

import math

from simulator.plant.balance import close_plant_books, rider_channel
from simulator.plant.streams import StreamBus
from simulator.plugins.base import ArchitecturePlugin


class MecOrbitronPlugin(ArchitecturePlugin):
    family = "mec_orbitron"

    def reset_state(self) -> dict[str, float]:
        return {
            "t_run": 0.0,
            "ash_He": 0.0,
            "cap_SOC": 0.7,
            "orbit": 0.0,
            "breakdown_risk": 0.0,
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

        state["t_run"] += dt
        state["orbit"] = math.fmod(state["orbit"] + dt * (0.5 + cfg.HV_kV / 300.0), 1.0)

        # Fuel mode: D–T learning vs p11B claim
        dt_mode = cfg.fuel_mode == "dt_learning"
        fuel_scale = 1.4 if dt_mode else 0.55  # easier neutrons vs hard boron

        state["cap_SOC"] = min(
            1.0,
            max(0.2, state["cap_SOC"] + dt * (0.1 - 0.02 * cfg.driver_power_MW)),
        )

        # HV breakdown risk climbs with voltage and Z
        state["breakdown_risk"] = min(
            1.0, 0.15 * (cfg.HV_kV / 300.0) ** 2 + 0.05 * cfg.Z_eff
        )
        tripped = False
        if state["breakdown_risk"] > 0.85 and (int(state["t_run"] * 10) % 47 == 0):
            bus.alarm(bus.get("t"), "trip", "HV", "Vacuum breakdown — Orbitron standoff")
            tripped = True

        n_e = 0.6 + 0.3 * cfg.fueling_H
        T_i = 15.0 + 0.04 * cfg.HV_kV
        T_e = 6.0
        P_i_to_e, P_rad = rider_channel(
            T_i=T_i,
            T_e=T_e,
            n_e=n_e,
            Z_eff=cfg.Z_eff,
            nonthermal=cfg.nonthermal,
        )

        P_driver = 0.0 if tripped else cfg.driver_power_MW
        P_f = (
            0.0
            if tripped
            else (
                0.25
                * P_driver
                * fuel_scale
                * (cfg.HV_kV / 250.0)
                * cfg.nonthermal
                * (0.8 + 0.2 * math.sin(state["orbit"] * 6.28))
            )
        )
        # κ narrative: don't claim boron plant Q when in D–T learning
        plant_kappa = 0.4 if dt_mode else 1.0

        state["ash_He"] += (0.2 if dt_mode else 0.08) * P_f * dt

        books = close_plant_books(
            P_f=P_f,
            P_driver=P_driver,
            P_i_to_e=P_i_to_e,
            P_rad=P_rad,
            transport_frac=0.4,
            dec_eta=0.25 if dt_mode else 0.4,
            thermal_eta=0.4 if dt_mode else 0.2,
            house_base_MW=0.05 + 0.0002 * cfg.HV_kV,
            store_recharge_MW=0.03 * P_driver + (1.0 - state["cap_SOC"]) * 0.02,
        )

        bus.set("P_f", books.P_f)
        bus.set("P_driver", P_driver)
        bus.set("P_i_to_e", books.P_i_to_e)
        bus.set("P_rad", books.P_rad)
        bus.set("P_wall", books.P_wall)
        bus.set("P_gross", books.P_gross)
        bus.set("P_recirc", books.P_recirc)
        bus.set("P_net", books.P_net * plant_kappa)
        bus.set("P_import", books.P_import)
        bus.set("P_reject", books.P_reject)
        bus.set("Q_plasma", books.Q_plasma)
        bus.set("Q_eng", books.Q_eng * plant_kappa)
        bus.set("Q_plant", books.Q_plant * plant_kappa)
        bus.set("n_e", n_e)
        bus.set("T_i", T_i)
        bus.set("T_e", T_e)
        bus.set("Z_eff", cfg.Z_eff)
        bus.set("fuel_H", cfg.fueling_H)
        bus.set("fuel_B11", 0.0 if dt_mode else cfg.fueling_B11)
        bus.set("ash_He", state["ash_He"])
        bus.set("HV_kV", 0.0 if tripped else cfg.HV_kV)
        bus.set("cap_SOC", state["cap_SOC"])
        bus.set("store_SOC", state["cap_SOC"])
        bus.set("rep_rate", cfg.rep_rate_Hz)
        bus.set("orbit_phase", state["orbit"])
        bus.set("shot_phase", 1.0 if not tripped else 0.0)
        bus.set("blast", 0.0)
        bus.set("plasma_brightness", 0.0 if tripped else min(1.0, P_f * 3.0))
        bus.set("energy_residual", books.energy_residual)
        bus.set("twin_health", max(0.0, 1.0 - books.energy_residual * 3.0 - state["breakdown_risk"] * 0.3))
        bus.set("mixin_gain", 1.0)

        if dt_mode and int(state["t_run"]) % 8 == 0 and dt > 0:
            bus.alarm(
                bus.get("t"),
                "info",
                "KAPPA",
                "D–T learning mode — plant odds κ=0.4 for p–¹¹B end-state",
            )
        return state

    def _idle(self, bus: StreamBus, state: dict[str, float]) -> None:
        for k in ("P_f", "P_driver", "P_rad", "P_net", "plasma_brightness"):
            bus.set(k, 0.0)
        bus.set("HV_kV", self.config.HV_kV)
        bus.set("cap_SOC", state.get("cap_SOC", 0.7))
        bus.set("store_SOC", state.get("cap_SOC", 0.7))
        bus.set("twin_health", 1.0)
