#!/usr/bin/env python3
"""Define and emit the 3 paper-embedded Mermaid figures from assembly.json.

Figures 7, 8, 9 in `arxiv.md` claim to be "drawn from assembly.json" / "1-1
with that JSON tree", but until now were hand-authored static text that
could silently drift from the JSON single source of truth. This script
defines each figure as an explicit `(scope_root, expand_ids, direction)`
spec — the non-interactive equivalent of clicking through the interactive
hierarchy app's twisties (`research/figures/cad/hierarchy_app/`) — and
renders it with the shared `lib/mermaid_builder.py` algorithm.

Run standalone to preview all three on stdout::

    python3 research/figures/cad/emit_paper_mermaid.py

`scripts/update_arxiv_mermaid.py` imports `FIGURES` from here to regenerate
the `<!--mermaid-gen KEY-->...<!--/mermaid-gen-->` blocks in `arxiv.md`.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

CAD = Path(__file__).resolve().parent
sys.path.insert(0, str(CAD))

from lib.assembly_parser import load_assembly  # noqa: E402
from lib.mermaid_builder import (  # noqa: E402
    FUNCTIONAL_JOINT_TYPES,
    build_mermaid,
    collect_visible_ids,
)

ASM = CAD / "assembly.json"


@dataclass(frozen=True)
class FigureSpec:
    key: str
    """Matches the `<!--mermaid-gen KEY-->` marker in arxiv.md."""
    scope_root: str | None
    """Hard-scope this figure to a single assembly's subtree (boundary
    stubs for anything leaving it), or None for whole-vehicle scope."""
    expand_ids: tuple[str, ...] = field(default_factory=tuple)
    """Node ids to expand (show children of), beyond the scope root itself."""
    direction: str = "TB"


# Fig. 7 — single-assembly scope: only charm_power_plant's own subtree is
# real; the one joint leaving it (plant bus -> engine's propulsion bus
# coupler) becomes a boundary stub instead of pulling in the whole engine.
FIG_FUSION_PLANT = FigureSpec(
    key="fusion_electric_plant",
    scope_root="charm_power_plant",
    expand_ids=(
        "charm_power_plant",
        "fusion_plant_skid",
        "charm",
        "charm_chamber_string",
        "fuel_services",
    ),
    direction="TB",
)

# Fig. 8 — whole-vehicle scope, top-level stations + one level into the
# fusion plant and engine (mirrors the old hand-curated "profile stations"
# diagram's depth).
FIG_PROFILE_STATIONS = FigureSpec(
    key="profile_stations",
    scope_root=None,
    expand_ids=(
        "vehicle",
        "charm_power_plant",
        "combined_cycle_engine",
    ),
    direction="TD",
)

# Fig. 9 — whole-vehicle scope, crew capsule expanded down to system level
# (flight deck / seats / WCS / galley / ECLSS / hatch, but not each seat or
# tank inside them); airlock and cargo bay stay single boxes; plant/engine
# one level.
FIG_FLOORPLAN = FigureSpec(
    key="floorplan",
    scope_root=None,
    expand_ids=(
        "vehicle",
        "crew_capsule",
        "pressure_vessel",
        "crew_compartment",
        "charm_power_plant",
        "combined_cycle_engine",
    ),
    direction="LR",
)

FIGURES: dict[str, FigureSpec] = {
    f.key: f
    for f in (FIG_FUSION_PLANT, FIG_PROFILE_STATIONS, FIG_FLOORPLAN)
}


def render_figure(assembly: dict, spec: FigureSpec) -> dict:
    root = assembly["root"]
    start_id = spec.scope_root or root["id"]
    visible = collect_visible_ids(root, set(spec.expand_ids), start_id=start_id)
    return build_mermaid(
        assembly,
        visible,
        scope_root=spec.scope_root,
        direction=spec.direction,
        include_joint_types=FUNCTIONAL_JOINT_TYPES,
    )


def main() -> int:
    asm = load_assembly(ASM)
    for key, spec in FIGURES.items():
        result = render_figure(asm, spec)
        print(f"=== {key} (scope={spec.scope_root or 'whole vehicle'}) ===")
        print(
            f"nodes={result['n_nodes']} contain={result['n_contain']} "
            f"connect={result['n_connect']} boundary={result['n_boundary']}"
        )
        print(result["src"])
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
