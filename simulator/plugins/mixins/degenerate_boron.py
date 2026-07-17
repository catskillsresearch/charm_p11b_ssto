"""Compressed-degenerate boron catcher mixin (survey §3.2 / ref 91)."""

from __future__ import annotations

from simulator.plant.config import PlantConfig
from simulator.plant.streams import StreamBus


class DegenerateBoronMixin:
    code = "degenerate_boron"
    label = "Compressed-degenerate boron"
    survey_note = (
        "Target upgrade for pulsed laser/HEDP only — not magnetic or Orbitron cores."
    )

    def is_allowed(self, config: PlantConfig) -> bool:
        return bool(config.hedp_degenerate_host)

    def patch_coeffs(
        self,
        config: PlantConfig,
        coeffs: dict[str, float],
        bus: StreamBus,
    ) -> dict[str, float]:
        if not config.mixins.get(self.code) or not self.is_allowed(config):
            bus.set("mixin_gain", 1.0)
            return coeffs
        out = dict(coeffs)
        # Theater: less stopping / coupling, more fusion yield per driver joule
        out["fusion_scale"] = out.get("fusion_scale", 1.0) * 2.4
        out["couple_scale"] = out.get("couple_scale", 1.0) * 0.55
        out["rad_scale"] = out.get("rad_scale", 1.0) * 0.7
        out["target_density"] = out.get("target_density", 1.0) * 12.0
        bus.set("mixin_gain", 2.4)
        return out
