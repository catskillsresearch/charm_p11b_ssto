"""Fallback abstract chamber for novel / unmapped families."""

from __future__ import annotations

from simulator.plugins.magnetic import MagneticCompactPlugin


class GenericPlugin(MagneticCompactPlugin):
    """Reuse magnetic ledger with abstract schematic kind."""

    family = "generic"

    def schematic_kind(self) -> str:
        return "generic"
