#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Patch research/figures/cad/assembly.json's CHARM magnet/cryo nodes from
constants.generated.json, so the JSON single source of truth always agrees
with arxiv.md §9.6 and constants_model.py.

Only touches specific known node ids (`charm`, `charm_magnet_rack`,
`mirror_magnets`, `cryo_compressor_bay`, `cryocooler`) via targeted
dict/list walks; every other field in assembly.json is left untouched.
Re-run any time constants_model.py's Params change.

Usage::

    poetry run python scripts/apply_constants_to_assembly.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CAD_DIR = ROOT / "research" / "figures" / "cad"
ASSEMBLY_JSON = CAD_DIR / "assembly.json"
VEHICLE_SPEC_JSON = CAD_DIR / "vehicle_spec.json"

sys.path.insert(0, str(CAD_DIR))
from constants_model import Params, compute  # noqa: E402


def find_node(node: Any, node_id: str) -> dict | None:
    """Depth-first search for a dict with `"id": node_id` under `node`
    (which may be a dict with a "children" list, or a list of such dicts).
    """
    if isinstance(node, dict):
        if node.get("id") == node_id:
            return node
        for child in node.get("children", []):
            found = find_node(child, node_id)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = find_node(item, node_id)
            if found is not None:
                return found
    return None


def round_mass_t(value_t: float) -> float:
    """Match assembly.json's existing style: bare int when within 0.05 t of
    one, else one decimal place."""
    rounded_int = round(value_t)
    return float(rounded_int) if abs(value_t - rounded_int) < 0.05 else round(value_t, 1)


def apply(assembly: dict, values: dict[str, float]) -> list[str]:
    changes: list[str] = []

    charm = find_node(assembly, "charm")
    if charm is not None:
        new_mass = round_mass_t(values["charm.m_c_t"])
        old_mass = charm.get("size", {}).get("mass_t_ref")
        if old_mass != new_mass:
            charm.setdefault("size", {})["mass_t_ref"] = new_mass
            changes.append(f"charm.size.mass_t_ref: {old_mass} -> {new_mass}")

    magnet_rack = find_node(assembly, "charm_magnet_rack")
    if magnet_rack is not None:
        magnet_rack["size"] = {
            "mass_t_ref": round(values["charm.m_magnets_t"], 1),
            "note": "Bottom-up known mass (magnets only; rack frame not independently sized). See arxiv.md \u00a79.6.",
        }
        changes.append("charm_magnet_rack.size refreshed")

    mirror_magnets = find_node(assembly, "mirror_magnets")
    if mirror_magnets is not None:
        n_coil = int(values["charm.n_coil"])
        m_each = values["charm.m_magnet_each_t"]
        m_total = values["charm.m_magnets_t"]
        mirror_magnets["count"] = n_coil
        mirror_magnets["size"] = {
            "mass_each_t": m_each,
            "mass_t_ref": round(m_total, 1),
            "layout": "two_end_mirror_coils_per_chamber_plus_two_hex_shaping",
        }
        mirror_magnets["note"] = (
            f"Mirror / chamber field coils \u2014 live in the CHARM Magnet rack, seated on the "
            f"fusion chamber ODs. N_coil={n_coil}, {m_each:.1f} t each "
            f"({m_total:.1f} t total), WHAM-anchored (arxiv.md \u00a79.6, refs [34]-[36]); "
            "on-coil cold head mass is bundled into mass_each_t."
        )
        changes.append("mirror_magnets.count/size/note refreshed")

    magnet_cryostats = find_node(assembly, "magnet_cryostats")
    if magnet_cryostats is not None:
        n_coil = int(values["charm.n_coil"])
        magnet_cryostats["count"] = n_coil
        changes.append("magnet_cryostats.count refreshed")

    cryo_bay = find_node(assembly, "cryo_compressor_bay")
    if cryo_bay is not None:
        m_cryo_t = values["charm.m_cryo_t"]
        p_cryo_kw = values["charm.p_cryo_kw"]
        n_al630 = int(values["charm.n_al630"])
        cryo_bay["size"] = {
            "mass_t_ref": round(m_cryo_t, 2),
            "power_kw_ref": round(p_cryo_kw, 1),
        }
        cryo_bay["note"] = (
            f"Skid compressor plant. Cold heads live on CHARM magnets. Sized in arxiv.md "
            f"\u00a79.6: N_AL630={n_al630} flight-remanufactured Cryomech AL630-class compressor "
            f"packages (\u00d71.5 flight-mass guess, \u00d71.4 integration margin) \u2192 "
            f"{m_cryo_t:.2f} t, {p_cryo_kw:.1f} kW electrical, "
            f"{values['charm.q20k_w']:.0f} W @ 20 K total "
            f"({values['charm.pct_cryo']:.1f}% of the CHARM island mass budget). "
            "Conservative SPARC-TFMC-anchored risk case (24-48 units, 8-16 t) and NASA "
            "flight-cryocooler ceiling case (45-90 t) also carried in \u00a79.6."
        )
        changes.append("cryo_compressor_bay.size/note refreshed")

    cryocooler = find_node(assembly, "cryocooler")
    if cryocooler is not None:
        n_al630 = int(values["charm.n_al630"])
        cryocooler["count"] = n_al630
        cryocooler["size"] = {
            "mass_each_bare_kg": 191,
            "flight_mass_mult": values["charm.flight_mass_mult"],
            "mass_each_flight_kg": round(191 * values["charm.flight_mass_mult"], 1),
            "power_each_kw": 12.7,
        }
        cryocooler["note"] = (
            f"Helium / cryogen COMPRESSOR and oil management \u2014 the noisy plant package on "
            f"the skid. It does NOT cryocool the magnets by itself; short cryogen lines feed "
            f"the magnet cold heads and bath on the CHARM island. count={n_al630} "
            "(one dedicated compressor package per magnet); mass/power in size block are "
            "flight-remanufactured-from-ground-hardware estimates, see arxiv.md \u00a79.6."
        )
        changes.append("cryocooler.count/size/note refreshed")

    return changes


CHARM_STATION_MASS_RE = re.compile(
    r'("id":\s*"charm".*?"mass_t_ref":\s*)([0-9.]+)', re.DOTALL
)


def patch_vehicle_spec_text(text: str, values: dict[str, float]) -> tuple[str, list[str]]:
    """Regex-targeted patch of vehicle_spec.json's `charm` station
    `mass_t_ref` field only. vehicle_spec.json is hand-formatted (compact
    inline arrays, literal unicode) in a style `json.dump` cannot
    round-trip losslessly, so — unlike assembly.json — this file is
    patched as text, touching only the one numeric span, exactly the way
    scripts/update_arxiv_constants.py patches arxiv.md. This also means
    patching it can never trigger an OpenVSP geometry regen: no build
    script parses `mass_t_ref` for geometry, and no other byte in the
    file changes.
    """
    new_mass_str = format_mass_t(round_mass_t(values["charm.m_c_t"]))
    changes: list[str] = []

    def _sub(m: re.Match) -> str:
        old = m.group(2)
        if old != new_mass_str:
            changes.append(f"vehicle_spec charm station mass_t_ref: {old} -> {new_mass_str}")
        return f"{m.group(1)}{new_mass_str}"

    updated = CHARM_STATION_MASS_RE.sub(_sub, text, count=1)
    return updated, changes


def format_mass_t(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)


def main() -> int:
    r = compute(Params())

    assembly = json.loads(ASSEMBLY_JSON.read_text())
    changes = apply(assembly["root"], r.values)
    ASSEMBLY_JSON.write_text(json.dumps(assembly, indent=2) + "\n")
    if changes:
        print(f"patched {ASSEMBLY_JSON}:")
        for c in changes:
            print(f"  - {c}")
    else:
        print(f"{ASSEMBLY_JSON} already up to date")

    spec_text = VEHICLE_SPEC_JSON.read_text()
    updated_spec_text, spec_changes = patch_vehicle_spec_text(spec_text, r.values)
    json.loads(updated_spec_text)  # validate before writing
    if updated_spec_text != spec_text:
        VEHICLE_SPEC_JSON.write_text(updated_spec_text)
    if spec_changes:
        print(f"patched {VEHICLE_SPEC_JSON}:")
        for c in spec_changes:
            print(f"  - {c}")
    else:
        print(f"{VEHICLE_SPEC_JSON} already up to date")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
