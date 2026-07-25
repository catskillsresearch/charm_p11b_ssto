#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Single numpy source of truth for the CHARM SSTO sizing-constraint system.

This module is the *only* place that should contain the numbers behind
arxiv.md's mass/power sizing chain (Sections 6-9) and the CHARM bottom-up
subsystem breakdown (magnets, cryo). Nothing here calls an LLM — every
number is either a cited/imputed input constant (`Params`) or a plain
arithmetic/numpy derivation of those inputs (`Results`).

Downstream consumers:
  - scripts/update_arxiv_constants.py   -> rewrites <!--gen KEY:FMT--> spans
                                            in arxiv.md
  - scripts/apply_constants_to_assembly.py -> patches assembly.json /
                                            vehicle_spec.json "size" blocks
  - research/figures/cad/build_fusion_plant_skid_blender.py -> reads
                                            constants.generated.json for
                                            N_coil / N_AL630 counts

Run directly to (re)write constants.generated.json and print a summary::

    poetry run python research/figures/cad/constants_model.py
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

CAD_DIR = Path(__file__).resolve().parent
GENERATED_JSON = CAD_DIR / "constants.generated.json"


def sci(value: float, sig: int) -> tuple[str, int]:
    """Split `value` into (mantissa string, base-10 exponent) at `sig`
    significant figures, e.g. sci(196100, 4) -> ("1.961", 5).
    """
    if value == 0:
        return f"{0:.{sig - 1}f}", 0
    exp = int(math.floor(math.log10(abs(value))))
    decimals = sig - 1
    mantissa = round(value / (10.0**exp), decimals)
    if abs(mantissa) >= 10.0:
        mantissa /= 10.0
        exp += 1
    return f"{mantissa:.{decimals}f}", exp


def latex_thousands(value: float) -> str:
    """e.g. 66700 -> '66\\,700' (LaTeX thin-space thousands grouping)."""
    return f"{value:,.0f}".replace(",", "\\,")


def latex_pow10(exp: int) -> str:
    """Match arxiv.md's existing style: braces only for multi-digit/negative
    exponents, e.g. exp=4 -> '10^4', exp=-2 -> '10^{-2}', exp=12 -> '10^{12}'.
    """
    return f"10^{exp}" if 0 <= exp <= 9 else f"10^{{{exp}}}"


# ---------------------------------------------------------------------------
# Params — every hand-picked / cited input constant lives here, nowhere else.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Params:
    # --- Top-level design targets (§9.1, §8) ---
    P_star_w: float = 1.0e9
    alpha_C_target_w_per_kg: float = 15.0e3  # 15 kW/kg reference hole
    g0: float = 9.80665

    # --- Vacuum rocket-equation freeze (§8) ---
    delta_v_vac_m_s: float = 4.0e3
    isp_s: float = 2000.0

    # --- Fixed structural / systems mass lines (§7.1, §7.3) ---
    m_af_kg: float = 72.0e3
    m_gear_kg: float = 4.0e3
    m_ctrl_kg: float = 3.0e3
    m_crew_kg: float = 8.5e3
    m_pl_kg: float = 24.4e3
    m_eng_kg: float = 15.0e3
    m_bat_kg: float = 2.0e3
    m_f_kg: float = 0.5e3

    # --- CHARM magnets: anchored on WHAM (Wisconsin HTS Axisymmetric
    # Mirror), a real operating HTS mirror machine — a far closer
    # architectural analog to CHARM's chambered rotating mirror than a
    # tokamak TF coil. WHAM's two magnets are real, delivered hardware:
    # <2 t each, 17 T bore / 20 T on tape REBCO, "self-contained systems"
    # with integrated cryo refrigeration (on-coil cold head bundled in).
    # [CFS WHAM press release; IEEE TASC "Design of High Field HTS Coils
    # for Magnetic Mirror"] ---
    n_coil: int = 6  # 2 end-mirror coils x 2 chambers + 2 HEX shaping coils
    m_magnet_each_t: float = 1.8  # WHAM real hardware, "<2 tons"

    # --- Cryo compressor bay: N_AL630 Cryomech AL630-class compressor
    # PACKAGES only (cold heads are already inside m_magnet_each_t above,
    # per WHAM/CFS's "self-contained per-magnet" cryo philosophy).
    # Bare CPA1114 datasheet: 191 kg, 12.7 kW (60 Hz), 100 W @ 20 K per
    # AL630 cold head. ---
    n_al630: int = 6  # one dedicated compressor package per magnet
    al630_compressor_kg: float = 191.0
    al630_power_kw: float = 12.7
    al630_cooling_w: float = 100.0

    # --- IMPUTED, UNSOURCED design guesses (flagged explicitly in prose):
    # remanufacturing an existing efficient *ground* cryocooler design for
    # flight (vibration qualification, radiator/pumped-loop heat rejection
    # instead of building chilled water) is assumed materially cheaper in
    # mass than developing new lightweight cryocooler tech from scratch.
    # No vendor or test data backs either multiplier. ---
    flight_mass_mult: float = 1.5  # user-selected option (A)
    flight_power_mult: float = 1.15  # radiator/pumped-loop penalty, guessed
    integration_margin: float = 1.4  # structure/lines/manifolds, guessed

    # --- Conservative risk case: SPARC TFMC per-coil heat load (measured,
    # not imputed) if CHARM's coils do NOT beat that demonstration ---
    tfmc_w_per_coil: float = 600.0
    tfmc_coil_low: int = 4
    tfmc_coil_high: int = 8
    al630_full_unit_kg: float = 235.0  # 44 kg cold head + 191 kg compressor

    # --- Ceiling check: NASA 20 W/20 K flight-cryocooler program,
    # state-of-the-art specific mass (measured, not imputed) ---
    nasa_soa_kg_per_w: float = 18.7


# ---------------------------------------------------------------------------
# Results — pure numpy/arithmetic derivations of Params. No fitting, no AI.
# ---------------------------------------------------------------------------


@dataclass
class Results:
    values: dict[str, float] = field(default_factory=dict)
    strings: dict[str, str] = field(default_factory=dict)

    def set(self, key: str, value: float) -> float:
        self.values[key] = value
        return value

    def set_str(self, key: str, s: str) -> None:
        self.strings[key] = s


def compute(p: Params = Params()) -> Results:
    r = Results()

    # ----- Echo a few Params through as Results so arxiv.md markers can
    # reference them without a second lookup table -----
    r.set("charm.n_coil", p.n_coil)
    r.set("charm.m_magnet_each_t", p.m_magnet_each_t)
    r.set("charm.n_al630", p.n_al630)
    r.set("charm.flight_mass_mult", p.flight_mass_mult)
    r.set("charm.flight_power_mult", p.flight_power_mult)
    r.set("charm.integration_margin", p.integration_margin)

    # ----- CHARM magnets (bottom-up, WHAM-anchored) -----
    m_magnets_t = r.set("charm.m_magnets_t", p.n_coil * p.m_magnet_each_t)

    # ----- CHARM cryo compressor bay (bottom-up, AL630 + flight guess) -----
    m_cryo_bare_kg = p.n_al630 * p.al630_compressor_kg * p.flight_mass_mult
    m_cryo_bare_t = r.set("charm.m_cryo_bare_t", m_cryo_bare_kg / 1e3)
    m_cryo_t = r.set("charm.m_cryo_t", m_cryo_bare_t * p.integration_margin)
    p_cryo_kw = r.set(
        "charm.p_cryo_kw", p.n_al630 * p.al630_power_kw * p.flight_power_mult
    )
    q20k_w = r.set("charm.q20k_w", p.n_al630 * p.al630_cooling_w)
    r.set("charm.q20k_w_per_coil", q20k_w / p.n_coil)
    r.set("charm.p_cryo_frac_bus_pct", p_cryo_kw * 1e3 / p.P_star_w * 100.0)

    # ----- CHARM island roll-up: bottom-up known vs. top-down target -----
    m_bottom_up_known_t = r.set("charm.m_bottom_up_known_t", m_magnets_t + m_cryo_t)
    m_c_target_t = r.set("charm.m_c_target_t", p.P_star_w / p.alpha_C_target_w_per_kg / 1e3)
    m_remainder_t = r.set(
        "charm.m_remainder_t", max(m_c_target_t - m_bottom_up_known_t, 0.0)
    )
    # m_C is the max of the top-down target and the bottom-up known total
    # (with zero additional floor assumed for RF/shield/structure, since we
    # have no sourced number for that floor) -- if bottom-up known pieces
    # ever exceed the top-down target, m_C (and everything downstream)
    # grows automatically.
    m_c_t = r.set("charm.m_c_t", max(m_c_target_t, m_bottom_up_known_t))
    r.set("charm.alpha_c_implied_kw_per_kg", p.P_star_w / (m_c_t * 1e3) / 1e3)
    r.set("charm.pct_magnets", m_magnets_t / m_c_t * 100.0)
    r.set("charm.pct_cryo", m_cryo_t / m_c_t * 100.0)
    r.set("charm.pct_remainder", m_remainder_t / m_c_t * 100.0)

    # ----- Conservative risk case: TFMC-measured per-coil heat load -----
    q_low_kw = r.set("cons.q_low_kw", p.tfmc_coil_low * p.tfmc_w_per_coil / 1e3)
    q_high_kw = r.set("cons.q_high_kw", p.tfmc_coil_high * p.tfmc_w_per_coil / 1e3)
    n_low = r.set("cons.n_al630_low", math.ceil(q_low_kw * 1e3 / p.al630_cooling_w))
    n_high = r.set("cons.n_al630_high", math.ceil(q_high_kw * 1e3 / p.al630_cooling_w))
    m_bare_low_t = r.set("cons.m_bare_low_t", n_low * p.al630_full_unit_kg / 1e3)
    m_bare_high_t = r.set("cons.m_bare_high_t", n_high * p.al630_full_unit_kg / 1e3)
    r.set("cons.m_installed_low_t", m_bare_low_t * p.integration_margin)
    r.set("cons.m_installed_high_t", m_bare_high_t * p.integration_margin)
    r.set("cons.p_low_kw", n_low * p.al630_power_kw)
    r.set("cons.p_high_kw", n_high * p.al630_power_kw)

    # ----- Ceiling check: NASA flight-cryocooler SOA specific mass -----
    r.set("ceil.m_low_t", q_low_kw * 1e3 * p.nasa_soa_kg_per_w / 1e3)
    r.set("ceil.m_high_t", q_high_kw * 1e3 * p.nasa_soa_kg_per_w / 1e3)

    # ----- Structural mass roll-up (§7.1) -----
    m_str_kg = r.set(
        "mass.m_str_kg", p.m_af_kg + p.m_gear_kg + p.m_ctrl_kg + p.m_crew_kg
    )

    # ----- Closed dry / wet mass (§7.4, §8) -----
    m_dry_kg = r.set(
        "mass.m_dry_kg",
        m_str_kg + p.m_pl_kg + p.m_eng_kg + m_c_t * 1e3 + p.m_bat_kg + p.m_f_kg,
    )
    v_e = p.isp_s * p.g0
    mu = r.set("mass.mu", float(np.exp(p.delta_v_vac_m_s / v_e)))
    m_w_kg = r.set("mass.m_w_kg", m_dry_kg * (mu - 1.0))
    m0_kg = r.set("mass.m0_kg", m_dry_kg * mu)
    r.set("mass.m_ins_kg", m_dry_kg)
    r.set("mass.m_ins_t", m_dry_kg / 1e3)
    r.set("mass.v_e_km_s", v_e / 1e3)
    r.set("mass.mu_minus1", mu - 1.0)
    r.set("mass.m_str_t", m_str_kg / 1e3)
    r.set("mass.m_dry_t", m_dry_kg / 1e3)
    r.set("mass.m_w_t", m_w_kg / 1e3)
    r.set("mass.m0_t", m0_kg / 1e3)

    # ----- Sensitivity table: alpha_C in {5, 10, 15, 25} kW/kg -----
    for label, alpha in (("5", 5.0e3), ("10", 10.0e3), ("15", 15.0e3), ("25", 25.0e3)):
        m_c_sens_kg = p.P_star_w / alpha
        m_dry_sens_kg = m_str_kg + p.m_pl_kg + p.m_eng_kg + m_c_sens_kg + p.m_bat_kg + p.m_f_kg
        mu_sens = mu  # same Delta v / Isp assumption across the sensitivity sweep
        m_w_sens_kg = m_dry_sens_kg * (mu_sens - 1.0)
        m0_sens_kg = m_dry_sens_kg * mu_sens
        r.set(f"sens{label}.m_c_t", m_c_sens_kg / 1e3)
        r.set(f"sens{label}.m_dry_t", m_dry_sens_kg / 1e3)
        r.set(f"sens{label}.m_w_t", m_w_sens_kg / 1e3)
        r.set(f"sens{label}.m0_t", m0_sens_kg / 1e3)

    # ----- Pre-formatted strings for direct arxiv.md drop-in -----
    mant, exp = sci(m_dry_kg, 4)
    r.set_str("mass.m_dry_kg_sci", f"{mant}\\times {latex_pow10(exp)}")
    mant, exp = sci(m0_kg, 4)
    r.set_str("mass.m0_kg_sci", f"{mant}\\times {latex_pow10(exp)}")
    mant, exp = sci(m_w_kg, 3)
    r.set_str("mass.m_w_kg_sci", f"{mant}\\times {latex_pow10(exp)}")
    mant, exp = sci(m_c_t * 1e3, 3)
    r.set_str("charm.m_c_kg_sci", f"{mant}\\times {latex_pow10(exp)}")
    mant, exp = sci(m_str_kg, 3)
    r.set_str("mass.m_str_kg_sci", f"{mant}\\times {latex_pow10(exp)}")
    r.set_str("charm.m_c_kg_latex", latex_thousands(m_c_t * 1e3))
    r.set_str("mass.m_dry_kg_latex", latex_thousands(m_dry_kg))

    return r


def write_generated_json(r: Results, path: Path = GENERATED_JSON) -> None:
    payload = {"values": r.values, "strings": r.strings}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def load_generated_json(path: Path = GENERATED_JSON) -> dict:
    """Regenerate fresh (never trust a stale cache) and return the payload."""
    r = compute(Params())
    write_generated_json(r, path)
    return {"values": r.values, "strings": r.strings}


def main() -> int:
    r = compute(Params())
    write_generated_json(r)
    print(f"wrote {GENERATED_JSON}")
    print()
    print("CHARM island roll-up:")
    print(f"  magnets     : {r.values['charm.m_magnets_t']:.1f} t "
          f"({r.values['charm.pct_magnets']:.1f}% of m_C)")
    print(f"  cryo bay    : {r.values['charm.m_cryo_t']:.2f} t "
          f"({r.values['charm.pct_cryo']:.1f}% of m_C), "
          f"{r.values['charm.p_cryo_kw']:.1f} kW, "
          f"{r.values['charm.q20k_w']:.0f} W @ 20 K")
    print(f"  remainder   : {r.values['charm.m_remainder_t']:.1f} t "
          f"({r.values['charm.pct_remainder']:.1f}% of m_C, unsized RF/shield/structure)")
    print(f"  m_C         : {r.values['charm.m_c_t']:.1f} t "
          f"(alpha_C implied = {r.values['charm.alpha_c_implied_kw_per_kg']:.2f} kW/kg)")
    print()
    print("Vehicle mass chain:")
    print(f"  m_str  = {r.values['mass.m_str_kg'] / 1e3:.1f} t")
    print(f"  m_dry  = {r.values['mass.m_dry_kg'] / 1e3:.1f} t")
    print(f"  mu     = {r.values['mass.mu']:.3f}")
    print(f"  m_w    = {r.values['mass.m_w_kg'] / 1e3:.1f} t")
    print(f"  m0     = {r.values['mass.m0_kg'] / 1e3:.1f} t  (GLOW)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
