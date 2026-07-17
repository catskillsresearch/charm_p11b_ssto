"""Post-run metric report aligned with diligence-style streams."""

from __future__ import annotations

from dataclasses import dataclass

from simulator.plant.clock import PlantClock
from simulator.plant.config import PlantConfig


@dataclass
class RunReport:
    slug: str
    name: str
    family: str
    novel_tag: str | None
    t_end: float
    mixins: dict[str, bool]
    metrics: dict[str, float]
    gate_proxy: dict[str, str]
    narrative: str

    def as_text(self) -> str:
        lines = [
            f"p11b operator twin report — {self.name} ({self.slug})",
            f"family={self.family}  t={self.t_end:.1f}s  novel={self.novel_tag or '—'}",
            f"mixins={self.mixins}",
            "",
            "Metrics (time-average / last):",
        ]
        for k, v in self.metrics.items():
            lines.append(f"  {k}: {v:.4g}")
        lines.append("")
        lines.append("Diligence gate proxies (theater):")
        for g, s in self.gate_proxy.items():
            lines.append(f"  {g}: {s}")
        lines.append("")
        lines.append(self.narrative)
        return "\n".join(lines)


def build_report(clock: PlantClock) -> RunReport:
    cfg: PlantConfig = clock.config
    bus = clock.bus

    def avg(name: str) -> float:
        h = bus.history.get(name)
        if not h:
            return bus.get(name)
        return sum(h) / len(h)

    metrics = {
        "P_f_avg_MW": avg("P_f"),
        "P_driver_avg_MW": avg("P_driver"),
        "P_rad_avg_MW": avg("P_rad"),
        "P_net_avg_MW": avg("P_net"),
        "Q_plasma_avg": avg("Q_plasma"),
        "Q_eng_avg": avg("Q_eng"),
        "Q_plant_avg": avg("Q_plant"),
        "ash_He_final": bus.get("ash_He"),
        "twin_health_avg": avg("twin_health"),
        "energy_residual_avg": avg("energy_residual"),
        "mixin_gain": bus.get("mixin_gain", 1.0),
        "batt_SOC_final": bus.get("batt_SOC"),
        "batt_used_kWh": bus.get("batt_used_kWh"),
        "grid_export_kWh": bus.get("grid_export_kWh"),
        "H_in_g": bus.get("H_in_g"),
        "B11_in_g": bus.get("B11_in_g"),
        "He_out_g": bus.get("He_out_g"),
        "rad_out_g": bus.get("rad_out_g"),
        "starter_battery_kWh_cap": cfg.starter_battery_kWh,
        "rated_net_MW": cfg.rated_net_MW,
    }

    # Crude gate proxies from metrics
    def sym(ok: bool, partial: bool = False) -> str:
        if ok:
            return "●"
        if partial:
            return "◐"
        return "○"

    qp = metrics["Q_plasma_avg"]
    gate_proxy = {
        "F": sym(cfg.fuel_mode == "p11b" or "p–¹¹B" in cfg.fuel or "p-11" in cfg.fuel.lower(), True),
        "K": sym(cfg.nonthermal > 0.5, cfg.nonthermal > 0.3),
        "R": sym(metrics["P_rad_avg_MW"] < metrics["P_f_avg_MW"] * 1.1, True),
        "A": sym(metrics["ash_He_final"] < 25.0, metrics["ash_He_final"] < 50.0),
        "L": sym(qp > 0.5, qp > 0.05),
        "M": "◐",
        "T": "◐" if cfg.novel_tag is None else "○",
        "S": sym(metrics["twin_health_avg"] > 0.7, True),
        "H": "◐",
    }

    narrative = (
        f"0-order survey theater run for {cfg.slug}. "
        f"POS★ catalog={cfg.pos_star if cfg.pos_star is not None else 'n/a'}. "
    )
    if cfg.mixins.get("degenerate_boron"):
        narrative += "Degenerate-boron mixin engaged (laser/HEDP host). "
    if cfg.fuel_mode == "dt_learning":
        narrative += "D–T learning mode — do not read Q_plant as p–¹¹B plant odds. "
    if cfg.novel_tag:
        narrative += f"Novel configuration tag {cfg.novel_tag}. "

    return RunReport(
        slug=cfg.slug,
        name=cfg.name,
        family=cfg.family,
        novel_tag=cfg.novel_tag,
        t_end=clock.t,
        mixins=dict(cfg.mixins),
        metrics=metrics,
        gate_proxy=gate_proxy,
        narrative=narrative.strip(),
    )
