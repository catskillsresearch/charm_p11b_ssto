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
VEHICLE_SPEC_JSON = CAD_DIR / "vehicle_spec.json"

# ---------------------------------------------------------------------------
# US Standard Atmosphere, 1976 — closed-form piecewise layers [37].
# Textbook physics, not a guess: used by the stage-2 climb integrator below.
# ---------------------------------------------------------------------------

_R_AIR = 287.053  # J/(kg K)
_GAMMA_AIR = 1.4
_G0_STD = 9.80665

# (base geopotential height m, lapse rate K/m, base temp K, base pressure Pa)
_US76_LAYERS: tuple[tuple[float, float, float, float], ...] = (
    (0.0, -0.0065, 288.15, 101325.0),
    (11000.0, 0.0, 216.65, 22632.06),
    (20000.0, 0.0010, 216.65, 5474.889),
    (32000.0, 0.0028, 228.65, 868.0187),
    (47000.0, 0.0, 270.65, 110.9063),
    (51000.0, -0.0028, 270.65, 66.93887),
    (71000.0, -0.0020, 214.65, 3.956420),
    (84852.0, 0.0, 186.87, 0.3733989),
)


def us_standard_atmosphere(h_m: np.ndarray | float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized US Standard Atmosphere 1976 [37]: rho(h), T(h), P(h) for
    h in [0, 84852] m (clipped outside that range)."""
    h = np.clip(np.atleast_1d(np.asarray(h_m, dtype=float)), 0.0, _US76_LAYERS[-1][0])
    T = np.empty_like(h)
    P = np.empty_like(h)
    for i, (Hb, L, Tb, Pb) in enumerate(_US76_LAYERS):
        Htop = _US76_LAYERS[i + 1][0] if i + 1 < len(_US76_LAYERS) else np.inf
        mask = (h >= Hb) & (h <= Htop) if i + 1 < len(_US76_LAYERS) else (h >= Hb)
        if not np.any(mask):
            continue
        dh = h[mask] - Hb
        if abs(L) < 1e-12:
            T[mask] = Tb
            P[mask] = Pb * np.exp(-_G0_STD * dh / (_R_AIR * Tb))
        else:
            T[mask] = Tb + L * dh
            P[mask] = Pb * (Tb / T[mask]) ** (_G0_STD / (_R_AIR * L))
    rho = P / (_R_AIR * T)
    return rho, T, P


def wing_reference_area_m2(spec_path: Path = VEHICLE_SPEC_JSON) -> float:
    """Trapezoid-panel planform area of the double-delta main wing, computed
    directly from vehicle_spec.json's SSOT wing geometry (span/chords) —
    cross-checks against OpenVSP's own ~229 m^2 computed area."""
    spec = json.loads(Path(spec_path).read_text())
    wing = next(pt for pt in spec["parts"] if pt["id"] == "main_wing")["openvsp"]
    half_span = wing["span_m"] / 2.0
    s_inner = wing["inner_span_frac"] * half_span
    s_outer = half_span - s_inner
    area_inner = 0.5 * (wing["root_chord_m"] + wing["kink_chord_m"]) * s_inner
    area_outer = 0.5 * (wing["kink_chord_m"] + wing["tip_chord_m"]) * s_outer
    return 2.0 * (area_inner + area_outer)


def fuselage_frontal_area_m2(spec_path: Path = VEHICLE_SPEC_JSON) -> float:
    """Rectangle approximation of the fuselage cross-section (width x height)
    from vehicle_spec.json's OML — shared by the drag model (wave/parasite
    reference) and the §9.9 shield-bulkhead area (same fuselage, one seam)."""
    spec = json.loads(Path(spec_path).read_text())
    oml = spec["oml"]
    return oml["fuselage_width_m"] * oml["fuselage_height_m"]


# 3-breakpoint generic hypersonic lifting-body/waverider-class CD(M) table
# [38] — flagged: no CHARM-specific CFD or wind-tunnel data exists for this
# airframe. Subsonic cruise-drag floor, transonic peak, hypersonic falloff.
_MACH_BREAKPOINTS = np.array([0.0, 0.8, 1.05, 1.3, 2.0, 3.0, 6.0, 10.0])
_CD_BREAKPOINTS = np.array([0.045, 0.048, 0.090, 0.075, 0.060, 0.052, 0.050, 0.050])


def drag_coefficient(mach: np.ndarray | float) -> np.ndarray:
    """Interpolated generic hypersonic CD(M) table [38]."""
    return np.interp(np.atleast_1d(np.asarray(mach, dtype=float)), _MACH_BREAKPOINTS, _CD_BREAKPOINTS)


def _ground_roll_m(
    mass_kg: float,
    thrust_n: float,
    v_lof_m_s: float,
    s_m2: float,
    rho: float,
    cl: float,
    cd: float,
    mu: float,
    g0: float,
    dv: float = 0.5,
) -> tuple[float, float]:
    """Integrate ground roll to V_lof. Returns (distance_m, time_s).

    a = (T − D − μ(W−L))/m with L,D from constant CL/CD during the roll.
    """
    weight_n = mass_kg * g0
    v = 0.0
    s = 0.0
    t = 0.0
    while v < v_lof_m_s - 1e-9:
        q = 0.5 * rho * v * v
        lift = q * s_m2 * cl
        drag = q * s_m2 * cd
        friction = mu * max(weight_n - lift, 0.0)
        accel = (thrust_n - drag - friction) / mass_kg
        if accel <= 0.05:
            # Cannot accelerate to liftoff — return a huge sentinel distance.
            return 1.0e9, 1.0e9
        v_next = min(v + dv, v_lof_m_s)
        # ds = V dV / a  (use mid-point V)
        v_mid = 0.5 * (v + v_next)
        ds = v_mid * (v_next - v) / accel
        dt = (v_next - v) / accel
        s += ds
        t += dt
        v = v_next
    return float(s), float(t)


def integrate_stage2_climb(
    v1_m_s: float,
    v_ab_m_s: float,
    q_ascent_pa: float,
    thrust_n: float,
    mass_kg: float,
    g0: float,
    n_steps: int = 2000,
) -> tuple[float, float, float]:
    """Constant-dynamic-pressure (Bryson-style energy-height) climb from
    v1 to v_ab. Along a constant-Q path, h(v) is fixed by rho(h)=2Q/v^2, so
    the 2D trajectory collapses to a 1D quadrature in v:

        dt/dv = m*(g0*dh/dv + v) / ((T - D(v))*v),   D(v) = Q*S*CD(M(v,h(v)))

    Returns (t2_s, h_seal_m, mach_at_handoff). h_seal falls OUT of the
    integration (not assumed) — it is h(v_ab) under the constant-Q schedule.
    """
    S = wing_reference_area_m2()
    v_grid = np.linspace(v1_m_s, v_ab_m_s, n_steps + 1)
    h_grid = np.linspace(0.0, 84000.0, 20000)
    rho_grid, T_grid, _ = us_standard_atmosphere(h_grid)
    target_rho = 2.0 * q_ascent_pa / v_grid**2
    # rho_grid decreases monotonically with h_grid -> reverse for np.interp
    h_of_v = np.interp(target_rho, rho_grid[::-1], h_grid[::-1])
    T_of_v = np.interp(h_of_v, h_grid, T_grid)
    a_of_v = np.sqrt(_GAMMA_AIR * _R_AIR * T_of_v)
    mach = v_grid / a_of_v
    drag_n = q_ascent_pa * S * drag_coefficient(mach)
    dh_dv = np.gradient(h_of_v, v_grid)
    excess_n = np.maximum(thrust_n - drag_n, 1.0)  # guard against stall in the model
    dt_dv = mass_kg * (g0 * dh_dv + v_grid) / (excess_n * v_grid)
    trapz = getattr(np, "trapezoid", None) or np.trapz
    t2_s = float(trapz(dt_dv, v_grid))
    return t2_s, float(h_of_v[-1]), float(mach[-1])


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

    # --- Stage 1 (EDF): existing §10.2/§10.3 constants, now wired through
    # this model instead of hand-typed, so P1/T1/m_EDF track m0 ---
    thrust_to_weight_min: float = 0.25
    eta_m: float = 0.90
    eta_prop: float = 0.80
    k_fan: float = 1.35
    alpha_mot_w_per_kg: float = 16.0e3
    # Takeoff lift closure (§10.3). Clean-wing CL from VSPAERO M=0.3, α=8°;
    # CL_max_takeoff is a flagged high-lift assumption (flaps/elevon droop —
    # not yet in the OpenVSP exterior). k_lof = V_lof / V_s.
    rho_sl_kg_m3: float = 1.225
    cl_clean_vspaero: float = 0.478
    cl_max_takeoff: float = 1.65  # flagged high-lift (flaps / elevon droop)
    k_lof: float = 1.12
    mu_roll: float = 0.025
    cl_ground_roll: float = 0.55  # partial lift during roll (flagged)
    cd_ground_roll: float = 0.090  # gear+flaps parasite (flagged)
    runway_available_m: float = 3500.0  # long municipal / G6 class

    # --- Stage 2 (microwave air plasma): existing §10.2/§10.4 constants,
    # reused as-is, plus new ascent-physics inputs for the climb integrator.
    # v1/Q_ascent are flagged planning guesses; v_ab is the *existing*
    # air-breathing delta-v credit reused as the stage-2 handoff speed. ---
    eta_mu: float = 0.55
    eta_j2: float = 0.45
    v_j2_m_s: float = 600.0
    P_hotel_w: float = 5.0e6
    v1_m_s: float = 300.0  # flagged guess: transonic stage-1->2 handoff
    v_ab_m_s: float = 3500.0  # reused from §6's v_ab = 3.5 km/s
    q_ascent_pa: float = 25.0e3  # flagged design Q, X-15/Shuttle-class order

    # --- Stage 3 (water plasma): existing §10.2/§10.5 constant, reused ---
    eta_jet: float = 0.55

    # --- Top-down energy check (§4/§8), reused ---
    kappa_e_assumed: float = 3.0
    e_orb_j: float = 6.49e12

    # --- §9.9 shielding: photon (bremsstrahlung/X-ray) + residual-neutron
    # source terms are flagged order-of-magnitude fractions of P_star, not a
    # CHARM-specific power balance (none published, §9.6). Attenuation
    # coefficients are cited (NIST XCOM [39]; standard removal cross
    # sections [40]), not fitted. ---
    f_gamma_residual: float = 0.005  # flagged: residual photon power / P_star
    f_n_residual: float = 0.005  # flagged: <=~1% of a D-T-equivalent yield
    mu_rho_water_photon_cm2_g: float = 0.1186  # NIST XCOM @ ~300 keV [39]
    mu_rho_poly_photon_cm2_g: float = 0.1211  # NIST XCOM @ ~300 keV [39]
    rho_water_g_cm3: float = 1.00
    rho_poly_g_cm3: float = 0.94
    sigma_r_water_per_cm: float = 0.103  # fast-neutron removal xsec [40]
    sigma_r_poly_per_cm: float = 0.100  # fast-neutron removal xsec [40]
    target_attenuation_decades: float = 3.0  # flagged design requirement (1000x)
    water_slab_depth_m: float = 4.0  # new water-tank envelope length (§11)

    # --- §9.9 RF/microwave leakage (B3): separate non-ionizing hazard,
    # Faraday-cage shielding-effectiveness order-of-magnitude estimate ---
    rf_freq_hz: float = 2.45e9  # flagged: representative RF frequency, unspecified in [1]
    rf_skin_thickness_mm: float = 1.0  # representative structural Al skin
    rf_conductivity_s_per_m: float = 3.5e7  # aluminum


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

    # ----- Aero/atmosphere reference constants (§10.2), echoed for markers -----
    r.set("aero.wing_area_m2", wing_reference_area_m2())
    r.set("stage.q_ascent_kpa", p.q_ascent_pa / 1e3)
    r.set("stage.v1_m_s", p.v1_m_s)
    r.set("stage.v_ab_m_s", p.v_ab_m_s)
    r.set("stage.v_ab_km_s", p.v_ab_m_s / 1e3)

    # ----- Stage 1 (EDF): takeoff lift closure, then T1/P1/m_EDF -----
    eta1 = r.set("stage.eta1", p.eta_m * p.eta_prop)
    t1_n = r.set("stage.t1_n", p.thrust_to_weight_min * m0_kg * p.g0)
    r.set("stage.t1_kn", t1_n / 1e3)
    S = wing_reference_area_m2()
    weight_n = m0_kg * p.g0
    r.set("stage.cl_clean_vspaero", p.cl_clean_vspaero)
    r.set("stage.cl_max_takeoff", p.cl_max_takeoff)
    # Stall / liftoff speeds: V_s = sqrt(2W/(ρ S CL)), V_lof = k_lof V_s
    vs_clean = math.sqrt(
        2.0 * weight_n / (p.rho_sl_kg_m3 * S * p.cl_clean_vspaero)
    )
    vs_to = math.sqrt(2.0 * weight_n / (p.rho_sl_kg_m3 * S * p.cl_max_takeoff))
    v_lof = r.set("stage.v_lof_m_s", p.k_lof * vs_to)
    r.set("stage.v_stall_clean_m_s", vs_clean)
    r.set("stage.v_stall_to_m_s", vs_to)
    r.set("stage.v_to_m_s", v_lof)  # EDF power reference = liftoff speed
    s_g, t_g = _ground_roll_m(
        mass_kg=m0_kg,
        thrust_n=t1_n,
        v_lof_m_s=v_lof,
        s_m2=S,
        rho=p.rho_sl_kg_m3,
        cl=p.cl_ground_roll,
        cd=p.cd_ground_roll,
        mu=p.mu_roll,
        g0=p.g0,
    )
    r.set("stage.ground_roll_m", s_g)
    r.set("stage.ground_roll_km", s_g / 1e3)
    r.set("stage.ground_roll_s", t_g)
    r.set("stage.runway_available_m", p.runway_available_m)
    r.set("stage.runway_margin_m", p.runway_available_m - s_g)
    # Clean-wing counterfactual (no flaps): same thrust, VSPAERO CL only.
    v_lof_clean = p.k_lof * vs_clean
    s_g_clean, _ = _ground_roll_m(
        mass_kg=m0_kg,
        thrust_n=t1_n,
        v_lof_m_s=v_lof_clean,
        s_m2=S,
        rho=p.rho_sl_kg_m3,
        cl=min(p.cl_ground_roll, 0.35),
        cd=0.06,
        mu=p.mu_roll,
        g0=p.g0,
    )
    r.set("stage.v_lof_clean_m_s", v_lof_clean)
    r.set("stage.ground_roll_clean_m", s_g_clean)
    # Bus power at liftoff speed (not an arbitrary 80 m/s).
    p1_w = r.set("stage.p1_w", t1_n * v_lof / eta1)
    r.set("stage.p1_mw", p1_w / 1e6)
    m_edf_kg = r.set("stage.m_edf_kg", p.k_fan * p1_w / p.alpha_mot_w_per_kg)
    r.set("stage.m_edf_t", m_edf_kg / 1e3)
    # Stage-1 energy to handoff: ground roll + climb/accel impulse to v1.
    t_climb_s = max(m0_kg * (p.v1_m_s - v_lof) / t1_n, 0.0)
    t1_s = r.set("stage.t1_s", t_g + t_climb_s)
    e1_j = r.set("stage.e1_j", p1_w * t1_s)
    r.set("stage.e1_mwh", e1_j / 3.6e9)

    # ----- Stage 2 (microwave air plasma): real climb integrator -----
    p2_star_w = r.set("stage.p2_star_w", p.P_star_w - p.P_hotel_w)
    r.set("stage.p2_star_mw", p2_star_w / 1e6)
    t2_ratio = r.set("stage.t2_over_p2_n_per_kw", 2.0 * p.eta_mu * p.eta_j2 / p.v_j2_m_s * 1e3)
    t2_n = r.set("stage.t2_n", t2_ratio * 1e-3 * p2_star_w)
    r.set("stage.t2_kn", t2_n / 1e3)
    t2_s, h_seal_m, mach_seal = integrate_stage2_climb(
        v1_m_s=p.v1_m_s,
        v_ab_m_s=p.v_ab_m_s,
        q_ascent_pa=p.q_ascent_pa,
        thrust_n=t2_n,
        mass_kg=m0_kg,
        g0=p.g0,
    )
    r.set("stage.t2_s", t2_s)
    r.set("stage.t2_min", t2_s / 60.0)
    r.set("stage.h_seal_m", h_seal_m)
    r.set("stage.h_seal_km", h_seal_m / 1e3)
    r.set("stage.mach_seal", mach_seal)
    e2_j = r.set("stage.e2_j", p2_star_w * t2_s)
    r.set("stage.e2_mwh", e2_j / 3.6e9)

    # ----- Stage 3 (water plasma): closed-form invariant E3 -----
    p3_star_w = r.set("stage.p3_star_w", p.P_star_w - p.P_hotel_w)
    r.set("stage.p3_star_mw", p3_star_w / 1e6)
    t3_n = r.set("stage.t3_n", 2.0 * p.eta_jet * p3_star_w / v_e)
    r.set("stage.t3_kn", t3_n / 1e3)
    mdot_w = r.set("stage.mdot_w_kg_s", t3_n / v_e)
    t3_s = r.set("stage.t3_s", m_w_kg / mdot_w)
    r.set("stage.t3_h", t3_s / 3600.0)
    # Closed form: E3 = 1/2 m_w v_e^2 / eta_jet -- a physical invariant of
    # (m_w, v_e, eta_jet) alone, independent of whatever power ceiling is
    # assumed for P3 (matches p3_star_w * t3_s exactly by construction).
    e3_j = r.set("stage.e3_j", 0.5 * m_w_kg * v_e**2 / p.eta_jet)
    r.set("stage.e3_mwh", e3_j / 3.6e9)

    # ----- Reconciliation: bottom-up stage energies vs top-down kappa_E -----
    e_hotel_j = r.set("stage.e_hotel_j", p.P_hotel_w * (t1_s + t2_s + t3_s))
    r.set("stage.e_hotel_mwh", e_hotel_j / 3.6e9)
    e_bottom_up_j = r.set("stage.e_bottom_up_j", e1_j + e2_j + e3_j + e_hotel_j)
    r.set("stage.e_bottom_up_mwh", e_bottom_up_j / 3.6e9)
    r.set("stage.e_bottom_up_tj", e_bottom_up_j / 1e12)
    r.set("stage.kappa_e_implied", e_bottom_up_j / p.e_orb_j)
    e_src_topdown_j = r.set("stage.e_src_topdown_j", p.kappa_e_assumed * p.e_orb_j)
    r.set("stage.e_src_topdown_mwh", e_src_topdown_j / 3.6e9)
    r.set(
        "stage.e_bottom_up_over_topdown_pct",
        e_bottom_up_j / e_src_topdown_j * 100.0,
    )

    # ----- §9.9 shielding: B1 permanent bulkhead, B2 water bonus, B3 RF ----
    area_m2 = r.set("shield.area_m2", fuselage_frontal_area_m2())
    hvl_water_gamma_cm = r.set(
        "shield.hvl_water_gamma_cm",
        math.log(2.0) / (p.mu_rho_water_photon_cm2_g * p.rho_water_g_cm3),
    )
    hvl_poly_gamma_cm = r.set(
        "shield.hvl_poly_gamma_cm",
        math.log(2.0) / (p.mu_rho_poly_photon_cm2_g * p.rho_poly_g_cm3),
    )
    hvl_water_n_cm = r.set("shield.hvl_water_n_cm", math.log(2.0) / p.sigma_r_water_per_cm)
    hvl_poly_n_cm = r.set("shield.hvl_poly_n_cm", math.log(2.0) / p.sigma_r_poly_per_cm)
    n_hvl_target = r.set(
        "shield.n_hvl_target", p.target_attenuation_decades / math.log10(2.0)
    )
    r.set("shield.target_db", p.target_attenuation_decades * 10.0)

    # B1: permanent polyethylene bulkhead, sized for BOTH hazards (take the
    # thicker requirement), zero water assumed present.
    t_b1_gamma_cm = n_hvl_target * hvl_poly_gamma_cm
    t_b1_n_cm = n_hvl_target * hvl_poly_n_cm
    r.set("shield.b1_thickness_gamma_cm", t_b1_gamma_cm)
    r.set("shield.b1_thickness_n_cm", t_b1_n_cm)
    t_b1_cm = r.set("shield.b1_thickness_cm", max(t_b1_gamma_cm, t_b1_n_cm))
    r.set("shield.b1_thickness_m", t_b1_cm / 100.0)
    m_b1_kg = r.set(
        "shield.b1_mass_kg", (t_b1_cm / 100.0) * area_m2 * (p.rho_poly_g_cm3 * 1e3)
    )
    m_b1_t = r.set("shield.b1_mass_t", m_b1_kg / 1e3)
    r.set("shield.b1_pct_of_remainder", m_b1_t / m_remainder_t * 100.0)
    m_remainder_after_b1_t = r.set(
        "charm.m_remainder_after_b1_t", max(m_remainder_t - m_b1_t, 0.0)
    )

    # B2: bonus attenuation the (consumable) water slab provides when full,
    # at the SAME target methodology, purely as a supplemental check.
    n_hvl_water_gamma = r.set(
        "shield.n_hvl_water_gamma", p.water_slab_depth_m * 100.0 / hvl_water_gamma_cm
    )
    n_hvl_water_n = r.set(
        "shield.n_hvl_water_n", p.water_slab_depth_m * 100.0 / hvl_water_n_cm
    )
    r.set("shield.water_gamma_db", n_hvl_water_gamma * math.log10(2.0) * 10.0)
    r.set("shield.water_n_db", n_hvl_water_n * math.log10(2.0) * 10.0)

    # B3: RF/microwave leakage -- Faraday-cage skin-depth shielding
    # effectiveness for a conductive aluminum skin (order-of-magnitude;
    # penetrations/seams are the real risk, not called out here).
    mu0 = 4.0 * math.pi * 1e-7
    skin_depth_m = r.set(
        "shield.rf_skin_depth_m",
        math.sqrt(1.0 / (math.pi * p.rf_freq_hz * mu0 * p.rf_conductivity_s_per_m)),
    )
    r.set("shield.rf_skin_depth_um", skin_depth_m * 1e6)
    t_over_delta = (p.rf_skin_thickness_mm * 1e-3) / skin_depth_m
    r.set("shield.rf_thickness_over_skin_depths", t_over_delta)
    r.set("shield.rf_se_db", 8.686 * t_over_delta)

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
    print()
    print("Stage energy budget (bottom-up):")
    print(f"  stage 1: P1={r.values['stage.p1_mw']:.1f} MW, t1={r.values['stage.t1_s']:.0f} s, "
          f"E1={r.values['stage.e1_mwh']:.2f} MWh")
    print(f"  stage 2: P2*={r.values['stage.p2_star_mw']:.0f} MW, t2={r.values['stage.t2_min']:.1f} min, "
          f"h_seal={r.values['stage.h_seal_km']:.1f} km, Mach={r.values['stage.mach_seal']:.1f}, "
          f"E2={r.values['stage.e2_mwh']:.1f} MWh")
    print(f"  stage 3: P3*={r.values['stage.p3_star_mw']:.0f} MW, t3={r.values['stage.t3_h']:.2f} h, "
          f"E3={r.values['stage.e3_mwh']:.1f} MWh")
    print(f"  hotel  : E_hotel={r.values['stage.e_hotel_mwh']:.1f} MWh")
    print(f"  bottom-up total = {r.values['stage.e_bottom_up_mwh']:.0f} MWh "
          f"(kappa_E implied = {r.values['stage.kappa_e_implied']:.2f}, "
          f"top-down @ kappa=3 = {r.values['stage.e_src_topdown_mwh']:.0f} MWh)")
    print()
    print("Shielding (§9.9):")
    print(f"  B1 permanent poly bulkhead: {r.values['shield.b1_thickness_cm']:.0f} cm, "
          f"{r.values['shield.b1_mass_t']:.1f} t "
          f"({r.values['shield.b1_pct_of_remainder']:.0f}% of the {r.values['charm.m_remainder_t']:.1f} t remainder)")
    print(f"  B2 water bonus (full tank): {r.values['shield.water_gamma_db']:.0f} dB gamma, "
          f"{r.values['shield.water_n_db']:.0f} dB neutron (target {r.values['shield.target_db']:.0f} dB)")
    print(f"  B3 RF leakage: {r.values['shield.rf_se_db']:.0f} dB shielding effectiveness "
          f"from a {Params().rf_skin_thickness_mm:.0f} mm Al skin (not a mass driver)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
