"""Pulsed laser / HEDP plugin with shot clock and blast phase."""

from __future__ import annotations

import math
import random

from simulator.plant.balance import close_plant_books, rider_channel
from simulator.plant.streams import StreamBus
from simulator.plugins.base import ArchitecturePlugin


class LaserHedpPlugin(ArchitecturePlugin):
    family = "laser_hedp"

    def reset_state(self) -> dict[str, float]:
        return {
            "phase_t": 0.0,
            "phase": 0.0,  # 0 charge, 1 fire, 2 stagnate, 3 recover
            "ash_He": 0.0,
            "cap_SOC": 0.4,
            "shot": 0.0,
            "misfire_streak": 0.0,
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

        period = 1.0 / max(cfg.rep_rate_Hz, 0.2)
        state["phase_t"] += dt
        # phase fractions of period
        frac = (state["phase_t"] % period) / period
        if frac < 0.45:
            phase = 0  # charge
        elif frac < 0.55:
            phase = 1  # fire / blast
        elif frac < 0.72:
            phase = 2  # stagnate / burn
        else:
            phase = 3  # recover
        state["phase"] = float(phase)

        coeffs = {
            "fusion_scale": 1.0,
            "couple_scale": 1.0,
            "rad_scale": 1.0,
            "target_density": 1.0,
        }
        coeffs = self.apply_mixin_patches(coeffs, bus)

        # Capacitor bank
        if phase == 0:
            state["cap_SOC"] = min(1.0, state["cap_SOC"] + dt * 0.8 / period)
            P_driver = 0.15 * cfg.driver_power_MW
            blast = 0.0
            P_f = 0.0
        elif phase == 1:
            # fire: dump store
            misfire = random.random() < 0.04 + 0.01 * state["misfire_streak"]
            if misfire or state["cap_SOC"] < 0.35:
                bus.alarm(bus.get("t"), "warn", "MISFIRE", "Shot aborted — bank/optics")
                state["misfire_streak"] += 1
                P_driver = 0.2 * cfg.driver_power_MW
                blast = 0.1
                P_f = 0.0
            else:
                state["misfire_streak"] = max(0.0, state["misfire_streak"] - 1)
                state["shot"] += 1
                state["cap_SOC"] = max(0.05, state["cap_SOC"] - 0.55)
                P_driver = cfg.driver_power_MW
                blast = 1.0
                P_f = 0.02 * cfg.driver_power_MW  # prompt yield small
        elif phase == 2:
            P_driver = 0.3 * cfg.driver_power_MW
            blast = 0.55 + 0.2 * math.sin(frac * 40)
            # Burn / catcher yield — mixin amplifies
            dens = coeffs["target_density"]
            P_f = (
                0.08
                * cfg.driver_power_MW
                * dens**0.35
                * (0.6 + 0.5 * cfg.nonthermal)
                * coeffs["fusion_scale"]
                * cfg.fueling_B11
                * cfg.fueling_H
            )
            # still ~orders below breakeven theater unless mixin+high driver
            P_f *= 0.35
        else:
            P_driver = 0.2 * cfg.driver_power_MW
            blast = 0.05
            P_f = 0.01 * state.get("_last_Pf", 0.0)
            state["cap_SOC"] = min(1.0, state["cap_SOC"] + dt * 0.5)

        state["_last_Pf"] = P_f
        state["ash_He"] += 0.05 * P_f * dt

        n_e = 1.2 * coeffs.get("target_density", 1.0) ** 0.2
        T_i = 40.0 * cfg.nonthermal + 10.0
        T_e = 15.0
        P_i_to_e, P_rad = rider_channel(
            T_i=T_i, T_e=T_e, n_e=n_e, Z_eff=cfg.Z_eff, nonthermal=cfg.nonthermal
        )
        P_i_to_e *= coeffs["couple_scale"]
        P_rad *= coeffs["rad_scale"]
        if phase in (1, 2):
            P_rad *= 1.8  # X-ray flash

        recharge = (1.0 - state["cap_SOC"]) * 0.5 * cfg.driver_power_MW
        books = close_plant_books(
            P_f=P_f,
            P_driver=P_driver,
            P_i_to_e=P_i_to_e,
            P_rad=P_rad,
            transport_frac=0.5,
            dec_eta=0.45,
            thermal_eta=0.25,
            house_base_MW=2.0,
            store_recharge_MW=recharge,
        )

        bus.set("P_f", books.P_f)
        bus.set("P_driver", P_driver)
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
        bus.set("n_e", n_e)
        bus.set("T_i", T_i)
        bus.set("T_e", T_e)
        bus.set("Z_eff", cfg.Z_eff)
        bus.set("fuel_H", cfg.fueling_H)
        bus.set("fuel_B11", cfg.fueling_B11)
        bus.set("ash_He", state["ash_He"])
        bus.set("cap_SOC", state["cap_SOC"])
        bus.set("store_SOC", state["cap_SOC"])
        bus.set("magnet_SOC", 0.0)
        bus.set("rep_rate", cfg.rep_rate_Hz)
        bus.set("shot_phase", float(phase))
        bus.set("blast", blast)
        bus.set("plasma_brightness", blast)
        bus.set("orbit_phase", frac)
        bus.set("energy_residual", books.energy_residual)
        bus.set("twin_health", max(0.0, 1.0 - books.energy_residual * 3.0))

        if books.Q_plasma < 1e-3 and phase == 2:
            bus.alarm(bus.get("t"), "info", "GAIN", "Yield far below driver breakeven (survey ~4 orders)")
        return state

    def _idle(self, bus: StreamBus, state: dict[str, float]) -> None:
        for k in ("P_f", "P_driver", "P_rad", "P_net", "blast", "plasma_brightness"):
            bus.set(k, 0.0)
        bus.set("cap_SOC", state.get("cap_SOC", 0.4))
        bus.set("store_SOC", state.get("cap_SOC", 0.4))
        bus.set("shot_phase", 0.0)
        bus.set("twin_health", 1.0)
        bus.set("mixin_gain", 1.0)
