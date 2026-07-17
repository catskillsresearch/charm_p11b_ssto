"""Architecture plugin interface + registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from simulator.plant.config import PlantConfig
from simulator.plant.streams import StreamBus


class ArchitecturePlugin(ABC):
    family: str = "generic"

    def __init__(self, config: PlantConfig) -> None:
        self.config = config
        self.mixins: list[Any] = []

    def attach_mixins(self, mixins: list[Any]) -> None:
        self.mixins = mixins

    @abstractmethod
    def reset_state(self) -> dict[str, float]:
        ...

    @abstractmethod
    def step(
        self,
        state: dict[str, float],
        bus: StreamBus,
        dt: float,
        running: bool,
    ) -> dict[str, float]:
        ...

    def schematic_kind(self) -> str:
        return self.family

    def apply_mixin_patches(
        self, coeffs: dict[str, float], bus: StreamBus
    ) -> dict[str, float]:
        out = dict(coeffs)
        for m in self.mixins:
            out = m.patch_coeffs(self.config, out, bus)
        return out


def get_plugin(config: PlantConfig) -> ArchitecturePlugin:
    from simulator.plugins.laser_hedp import LaserHedpPlugin
    from simulator.plugins.magnetic import MagneticCompactPlugin
    from simulator.plugins.mec import MecOrbitronPlugin
    from simulator.plugins.generic import GenericPlugin

    mapping: dict[str, type[ArchitecturePlugin]] = {
        "magnetic_compact": MagneticCompactPlugin,
        "laser_hedp": LaserHedpPlugin,
        "mec_orbitron": MecOrbitronPlugin,
        "generic": GenericPlugin,
    }
    cls = mapping.get(config.family, GenericPlugin)
    return cls(config)
