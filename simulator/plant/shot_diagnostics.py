"""0-order synthetic shot diagnostics (TAE/C-2W paper-style traces).

Not real reconstructions — survey-scaled theater matching published order-of-magnitude
shapes: rΔφ, φp, ne, Etot, Te, NBI, bias, n=1/2 modes over a ~40 ms window.
"""

from __future__ import annotations

import math

from simulator.plant.config import PlantConfig
from simulator.plant.streams import StreamBus


def publish_frc_shot_diagnostics(
    bus: StreamBus,
    cfg: PlantConfig,
    *,
    t_shot_s: float,
    t_shot_end_s: float,
) -> None:
    """Publish diagnostics for t_shot in [0, t_shot_end]."""
    T = max(t_shot_end_s, 1e-6)
    tau = max(0.0, min(1.0, t_shot_s / T))  # 0→1 over shot
    # Formation / merge ~ first 5 ms, then beam-driven flattop, die at NB end
    t_ms = t_shot_s * 1000.0
    form = 1.0 - math.exp(-t_ms / 2.5)  # rise
    # Collapse after NB: soft roll-off in last 10% of pulse
    die = 1.0
    if tau > 0.9:
        die = max(0.0, 1.0 - (tau - 0.9) / 0.1)

    # Driver / NBI flat-top (MW electrical class from setpoint)
    p_nbi = cfg.driver_power_MW * form * die
    # Bias electrode (kV, kA) — paper class ~1–3 kV, ~1–2 kA
    bias_kV = 1.7 * form * die
    bias_kA = 1.5 * form * die

    # Excluded-flux radius (m): ~0.35 → ~0.48 then hold (paper ~0.45–0.5 m)
    r_dphi = (0.32 + 0.16 * form) * die
    # Trapped poloidal flux (mWb): ~4 → ~16
    phi_p_mWb = (3.5 + 12.0 * form * (0.6 + 0.4 * cfg.nonthermal)) * die
    # ne inside separatrix (1e19 m^-3 theater → display as 1e19): paper ~few e19
    n_e_19 = (1.2 + 2.0 * form * cfg.fueling_H) * die
    # Te avg / max (keV): toward ~0.5–1 keV class
    te_scale = 0.35 + 0.55 * form * (0.5 + 0.5 * (cfg.driver_power_MW / 20.0))
    te_avg = te_scale * die
    te_max = te_avg * (1.35 + 0.1 * cfg.nonthermal)
    # Total plasma energy (kJ): paper ~13 kJ class
    e_tot_kJ = (2.0 + 11.0 * form * (p_nbi / max(cfg.driver_power_MW, 0.1))) * die
    e_th_kJ = 0.55 * e_tot_kJ

    # MHD: quiescent mid-shot, grow if bias weak or late
    wobble = 0.08 * (1.0 - 0.7 * form) + 0.25 * max(0.0, tau - 0.85)
    n2 = 0.05 * (1.0 - 0.6 * (bias_kV / 1.7)) + 0.35 * max(0.0, tau - 0.88)
    # Impurity rotation (krad/s theater): electron-diamagnetic when biased
    omega_imp = 80.0 * (bias_kV / 1.7) * form * die

    # Crude Te(r) snapshot coeffs for profile widget (parabolic-ish)
    # te_r0.. use bus scalars: te_core, te_edge
    te_core = te_max
    te_edge = 0.25 * te_avg

    bus.set("shot_t_ms", t_ms)
    bus.set("shot_tau", tau)
    bus.set("r_dphi_m", r_dphi)
    bus.set("phi_p_mWb", phi_p_mWb)
    bus.set("n_e_19", n_e_19)
    bus.set("E_tot_kJ", e_tot_kJ)
    bus.set("E_th_kJ", e_th_kJ)
    bus.set("T_e_avg_keV", te_avg)
    bus.set("T_e_max_keV", te_max)
    bus.set("T_e_core_keV", te_core)
    bus.set("T_e_edge_keV", te_edge)
    bus.set("P_NBI_MW", p_nbi)
    bus.set("bias_kV", bias_kV)
    bus.set("bias_kA", bias_kA)
    bus.set("mode_n1", wobble)
    bus.set("mode_n2", n2)
    bus.set("omega_imp_krad_s", omega_imp)
    # Drive schematic from diagnostics
    bus.set("plasma_brightness", min(1.0, e_tot_kJ / 12.0))
    bus.set("P_driver", p_nbi)
    bus.set("P_f", p_nbi * 1e-6)  # Q≪1
    bus.set("P_net", -p_nbi)
    bus.set("P_import", p_nbi)
    bus.set("Q_plasma", 1e-6)
    bus.set("Q_eng", 1e-6)
    bus.set("Q_plant", 0.0)
    bus.set("n_e", n_e_19 / 10.0)  # keep old stream roughly populated
    bus.set("T_e", te_avg)
    bus.set("T_i", te_avg * 2.5)


def idle_shot_diagnostics(bus: StreamBus) -> None:
    for k in (
        "shot_t_ms",
        "shot_tau",
        "r_dphi_m",
        "phi_p_mWb",
        "n_e_19",
        "E_tot_kJ",
        "E_th_kJ",
        "T_e_avg_keV",
        "T_e_max_keV",
        "T_e_core_keV",
        "T_e_edge_keV",
        "P_NBI_MW",
        "bias_kV",
        "bias_kA",
        "mode_n1",
        "mode_n2",
        "omega_imp_krad_s",
    ):
        bus.set(k, 0.0)
