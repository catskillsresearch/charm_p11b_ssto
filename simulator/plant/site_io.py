"""Genset-style site I/O ledger: starter battery, fuels, ash, byproducts."""

from __future__ import annotations

from dataclasses import dataclass

from simulator.plant.config import PlantConfig
from simulator.plant.streams import StreamBus


@dataclass
class SiteIOState:
    batt_kWh: float = 0.0
    batt_kWh_cap: float = 1.0
    batt_V: float = 400.0
    H_consumed_g: float = 0.0
    B11_consumed_g: float = 0.0
    He_out_g: float = 0.0
    rad_byproduct_proxy_g: float = 0.0  # activated / neutron-driven theater mass proxy
    energy_from_batt_kWh: float = 0.0
    energy_to_grid_kWh: float = 0.0
    energy_to_batt_kWh: float = 0.0


def fresh_site_io(cfg: PlantConfig) -> SiteIOState:
    cap = max(cfg.starter_battery_kWh, 0.1)
    return SiteIOState(
        batt_kWh=cap,  # fully charged at start of run
        batt_kWh_cap=cap,
        batt_V=max(cfg.starter_battery_V, 48.0),
    )


def step_site_io(
    site: SiteIOState,
    cfg: PlantConfig,
    bus: StreamBus,
    dt: float,
    running: bool,
) -> SiteIOState:
    """Update battery + material books from plant bus powers."""
    if not running or dt <= 0:
        _publish(site, bus, draw_kW=0.0, grid_kW=0.0, charge_kW=0.0)
        return site

    # Electrical: treat negative P_net as draw from starter battery (islanded genset model)
    P_net_MW = bus.get("P_net")
    P_import_MW = bus.get("P_import")
    # Prefer explicit import; else deficit vs net
    need_MW = max(P_import_MW, max(0.0, -P_net_MW))
    export_MW = max(0.0, P_net_MW)

    # Charge battery from surplus (drip / regenerator), limited by charger power
    # ~5% of rated net or 50 kW floor in kW terms
    max_charge_MW = max(0.05, 0.1 * max(cfg.rated_net_MW, 0.01))
    charge_MW = min(export_MW * 0.15, max_charge_MW) if export_MW > 0 else 0.0
    grid_MW = max(0.0, export_MW - charge_MW)

    # Integrate energy (MW * s → kWh): 1 MW·s = 1/3.6 kWh
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

    # Fuels: knobs are relative multipliers on design mg/s
    h_mg_s = cfg.design_fuel_H_mg_s * cfg.fueling_H
    b_mg_s = cfg.design_fuel_B11_mg_s * cfg.fueling_B11
    if cfg.fuel_mode == "dt_learning":
        b_mg_s *= 0.05  # mostly D–T path
    # Scale feed a bit with driver (more power → more fuel attempt)
    drive_fac = 0.5 + 0.5 * (cfg.driver_power_MW / max(cfg.rated_driver_MW, 0.01))
    h_mg_s *= drive_fac
    b_mg_s *= drive_fac

    site.H_consumed_g += h_mg_s * dt * 1e-3
    site.B11_consumed_g += b_mg_s * dt * 1e-3

    # Helium ash: convert bus ash_He (mg theater) increments via P_f proxy
    # Prefer differential from P_f: ~0.12 mg/s per MW in balance → grams
    he_mg_s = 0.12 * max(bus.get("P_f"), 0.0)
    site.He_out_g += he_mg_s * dt * 1e-3

    # Other radioactive / activation byproducts (theater):
    # neutron_energy_fraction * (P_f + side) as a mass-proxy production rate
    n_frac = cfg.neutron_energy_fraction
    if cfg.fuel_mode == "dt_learning":
        n_frac = max(n_frac, 0.8)
    rad_mg_s = n_frac * (0.05 * max(bus.get("P_f"), 0.0) + 0.02 * max(bus.get("P_driver"), 0.0))
    site.rad_byproduct_proxy_g += rad_mg_s * dt * 1e-3

    draw_kW = need_MW * 1000.0
    _publish(site, bus, draw_kW=draw_kW, grid_kW=grid_MW * 1000.0, charge_kW=charge_MW * 1000.0)
    bus.set("fuel_H", h_mg_s)
    bus.set("fuel_B11", b_mg_s)
    return site


def _publish(
    site: SiteIOState,
    bus: StreamBus,
    *,
    draw_kW: float,
    grid_kW: float,
    charge_kW: float,
) -> None:
    soc = site.batt_kWh / max(site.batt_kWh_cap, 1e-9)
    amps = (draw_kW * 1000.0) / max(site.batt_V, 1.0) if draw_kW > 0 else 0.0
    # If charging, show negative amps convention on batt current
    if charge_kW > draw_kW:
        amps = -(charge_kW * 1000.0) / max(site.batt_V, 1.0)

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
    bus.set("store_SOC", soc)  # keep store strip meaningful as battery
