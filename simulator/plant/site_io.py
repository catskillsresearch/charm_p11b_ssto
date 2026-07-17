"""Genset-style site I/O ledger: starter battery, fuels, ash, byproducts.

Startup is architecture-justified (see plant_spec), not a fake APU theater:
  - Before time_to_production_s: fusion/driver are gated off; battery pays only
    continuous house/aux + one-shot magnet/bank energy spread over that window.
  - After production: islanded bus follows real P_import / P_net from the books.
  - Wall-plug driver (NBI, full laser average) is NOT assumed to come from the
    starter battery during prep — that would be dishonest for MW-class beams.
"""

from __future__ import annotations

from dataclasses import dataclass

from simulator.plant.config import PlantConfig
from simulator.plant.streams import StreamBus

# Powers zeroed while waiting for justified first production
_GATED_POWER_KEYS = (
    "P_f",
    "P_driver",
    "P_rad",
    "P_wall",
    "P_i_to_e",
    "P_gross",
    "P_recirc",
    "P_net",
    "P_import",
    "P_reject",
    "Q_plasma",
    "Q_eng",
    "Q_plant",
)


@dataclass
class SiteIOState:
    batt_kWh: float = 0.0
    batt_kWh_cap: float = 1.0
    batt_V: float = 400.0
    H_consumed_g: float = 0.0
    B11_consumed_g: float = 0.0
    He_out_g: float = 0.0
    rad_byproduct_proxy_g: float = 0.0
    energy_from_batt_kWh: float = 0.0
    energy_to_grid_kWh: float = 0.0
    energy_to_batt_kWh: float = 0.0
    t_run: float = 0.0
    time_to_production_s: float = 0.0
    startup_aux_MW: float = 0.0
    startup_energy_kWh: float = 0.0
    production_on: bool = False
    startup_announced: bool = False
    production_announced: bool = False


def fresh_site_io(cfg: PlantConfig) -> SiteIOState:
    cap = max(cfg.starter_battery_kWh, 0.1)
    return SiteIOState(
        batt_kWh=cap,
        batt_kWh_cap=cap,
        batt_V=max(cfg.starter_battery_V, 48.0),
        time_to_production_s=max(0.0, cfg.time_to_production_s),
        startup_aux_MW=max(0.0, cfg.startup_aux_MW),
        startup_energy_kWh=max(0.0, cfg.startup_energy_kWh),
    )


def gate_pre_production(bus: StreamBus, cfg: PlantConfig, t_run: float) -> bool:
    """Zero fusion/driver books until justified first-production time.

    Returns True if production is allowed this tick.
    """
    t_prod = max(0.0, cfg.time_to_production_s)
    if t_run + 1e-12 >= t_prod:
        return True
    for k in _GATED_POWER_KEYS:
        bus.set(k, 0.0)
    bus.set("plasma_brightness", 0.0)
    bus.set("blast", 0.0)
    return False


def step_site_io(
    site: SiteIOState,
    cfg: PlantConfig,
    bus: StreamBus,
    dt: float,
    running: bool,
    *,
    force_need_MW: float | None = None,
    skip_fuel: bool = False,
    advance_t_run: bool = True,
    force_producing: bool | None = None,
) -> SiteIOState:
    """Update battery + material books from plant bus powers."""
    if not running or dt <= 0:
        _publish(site, bus, cfg, draw_kW=0.0, grid_kW=0.0, charge_kW=0.0)
        return site

    # Commission prep: clock already debited battery / advanced t_run — publish only
    if force_need_MW is not None:
        _publish(site, bus, cfg, draw_kW=max(0.0, force_need_MW) * 1000.0, grid_kW=0.0, charge_kW=0.0)
        bus.set("fuel_H", 0.0)
        bus.set("fuel_B11", 0.0)
        return site

    if not site.startup_announced:
        site.startup_announced = True

    if advance_t_run:
        site.t_run += dt
    if force_producing is not None:
        producing = force_producing
    else:
        producing = site.t_run + 1e-12 >= site.time_to_production_s
    site.production_on = producing

    if producing and not site.production_announced:
        bus.alarm(
            bus.get("t"),
            "info",
            "START",
            "Production window — bus follows P_import/P_net (Q≪1 ⇒ battery drains)",
        )
        site.production_announced = True

    if not producing:
        one_shot_MW = 0.0
        if site.time_to_production_s > 0 and site.startup_energy_kWh > 0:
            one_shot_MW = site.startup_energy_kWh * 3.6 / site.time_to_production_s
        need_MW = site.startup_aux_MW + one_shot_MW
        export_MW = 0.0
    else:
        P_import_MW = max(bus.get("P_import"), 0.0)
        P_net_MW = bus.get("P_net")
        need_MW = max(P_import_MW, max(0.0, -P_net_MW))
        export_MW = max(0.0, P_net_MW)

    # Starter pack is a battery (not a pulse capacitor): limit recharge by C-rate.
    # 1C ⇒ full pack energy in 1 hour → P_max[MW] = kWh_cap / 1000.
    c_rate = max(0.05, cfg.batt_max_charge_C)
    max_charge_MW = (site.batt_kWh_cap / 1000.0) * c_rate
    headroom_kWh = max(0.0, site.batt_kWh_cap - site.batt_kWh)
    if export_MW > 0 and headroom_kWh > 1e-9:
        # Trickle from surplus only; never more than C-rate allows
        charge_MW = min(export_MW * 0.05, max_charge_MW)
    else:
        charge_MW = 0.0
    grid_MW = max(0.0, export_MW - charge_MW)

    to_kWh = dt / 3.6
    draw_kWh = need_MW * to_kWh
    grid_kWh = grid_MW * to_kWh
    charge_kWh = charge_MW * to_kWh

    site.batt_kWh = min(site.batt_kWh_cap, site.batt_kWh - draw_kWh + charge_kWh)
    if site.batt_kWh <= 0:
        site.batt_kWh = 0.0
        bus.alarm(bus.get("t"), "trip", "BATT", "Starter battery depleted — islanded plant offline")

    site.energy_from_batt_kWh += draw_kWh
    site.energy_to_grid_kWh += grid_kWh
    site.energy_to_batt_kWh += charge_kWh

    if producing and not skip_fuel:
        h_mg_s = cfg.design_fuel_H_mg_s * cfg.fueling_H
        b_mg_s = cfg.design_fuel_B11_mg_s * cfg.fueling_B11
        if cfg.fuel_mode == "dt_learning":
            b_mg_s *= 0.05
        drive_fac = 0.5 + 0.5 * (cfg.driver_power_MW / max(cfg.rated_driver_MW, 0.01))
        h_mg_s *= drive_fac
        b_mg_s *= drive_fac
        site.H_consumed_g += h_mg_s * dt * 1e-3
        site.B11_consumed_g += b_mg_s * dt * 1e-3
        site.He_out_g += 0.12 * max(bus.get("P_f"), 0.0) * dt * 1e-3
        n_frac = cfg.neutron_energy_fraction
        if cfg.fuel_mode == "dt_learning":
            n_frac = max(n_frac, 0.8)
        rad_mg_s = n_frac * (
            0.05 * max(bus.get("P_f"), 0.0) + 0.02 * max(bus.get("P_driver"), 0.0)
        )
        site.rad_byproduct_proxy_g += rad_mg_s * dt * 1e-3
        bus.set("fuel_H", h_mg_s)
        bus.set("fuel_B11", b_mg_s)
    else:
        bus.set("fuel_H", 0.0)
        bus.set("fuel_B11", 0.0)

    _publish(
        site,
        bus,
        cfg,
        draw_kW=need_MW * 1000.0,
        grid_kW=grid_MW * 1000.0,
        charge_kW=charge_MW * 1000.0,
    )
    return site


def _publish(
    site: SiteIOState,
    bus: StreamBus,
    cfg: PlantConfig,
    *,
    draw_kW: float,
    grid_kW: float,
    charge_kW: float,
) -> None:
    soc = site.batt_kWh / max(site.batt_kWh_cap, 1e-9)
    amps = (draw_kW * 1000.0) / max(site.batt_V, 1.0) if draw_kW > 0 else 0.0
    if charge_kW > draw_kW:
        amps = -(charge_kW * 1000.0) / max(site.batt_V, 1.0)

    ramp = 1.0 if site.production_on else (
        site.t_run / site.time_to_production_s if site.time_to_production_s > 0 else 0.0
    )
    ramp = max(0.0, min(1.0, ramp))

    bus.set("batt_SOC", soc)
    bus.set("batt_kWh", site.batt_kWh)
    bus.set("batt_kWh_cap", site.batt_kWh_cap)
    bus.set("batt_V", site.batt_V)
    bus.set("batt_A", amps)
    bus.set("batt_draw_kW", max(0.0, draw_kW))
    bus.set("grid_export_kW", max(0.0, grid_kW))
    bus.set("batt_charge_kW", max(0.0, charge_kW))
    bus.set("batt_used_kWh", site.energy_from_batt_kWh)
    bus.set("grid_export_kWh", site.energy_to_grid_kWh)
    bus.set("H_in_g", site.H_consumed_g)
    bus.set("B11_in_g", site.B11_consumed_g)
    bus.set("He_out_g", site.He_out_g)
    bus.set("rad_out_g", site.rad_byproduct_proxy_g)
    bus.set("store_SOC", soc)
    remaining = max(0.0, site.time_to_production_s - site.t_run)
    bus.set("apu_ramp", ramp)  # pre-production fraction (UI label: startup)
    bus.set("apu_bootstrap_s", site.time_to_production_s)
    bus.set("preprod_remaining_s", remaining)
    bus.set("batt_charge_C", cfg.batt_max_charge_C)
