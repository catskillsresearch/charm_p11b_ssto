"""Shared 0-order power / inventory ledger helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LedgerResult:
    P_f: float
    P_i_to_e: float
    P_rad: float
    P_wall: float
    P_gross: float
    P_recirc: float
    P_net: float
    P_import: float
    P_reject: float
    Q_plasma: float
    Q_eng: float
    Q_plant: float
    ash_dHe: float
    energy_residual: float


def close_plant_books(
    *,
    P_f: float,
    P_driver: float,
    P_i_to_e: float,
    P_rad: float,
    transport_frac: float,
    dec_eta: float,
    thermal_eta: float,
    house_base_MW: float,
    store_recharge_MW: float,
) -> LedgerResult:
    """Map core powers into busbar-facing quantities."""
    P_wall = max(0.0, transport_frac * (P_f + P_driver * 0.15) + 0.2 * P_rad)
    # Recovery: DEC on charged products + thermal on wall/rad
    P_gross = dec_eta * 0.7 * P_f + thermal_eta * (P_wall + 0.5 * P_rad)
    P_recirc = house_base_MW + store_recharge_MW + 0.05 * P_driver
    P_import = max(0.0, P_driver + P_recirc - P_gross)
    P_net = P_gross - P_recirc
    P_reject = max(0.0, P_driver + P_f - P_gross - 0.1 * P_rad)

    Q_plasma = P_f / max(P_driver, 1e-9)
    Q_eng = P_f / max(P_recirc + 0.3 * P_driver, 1e-9)
    Q_plant = P_net / max(P_import, 1e-9) if P_import > 1e-6 else (2.0 if P_net > 0 else 0.0)

    # 3 alphas per reaction; crude mass proxy from P_f (8.7 MeV)
    # mg/s scale for theater: ash_dHe proportional to P_f
    ash_dHe = 0.12 * max(P_f, 0.0)

    # Energy conservation residual (twin health)
    in_e = P_driver + P_import
    out_e = P_gross + P_reject + P_rad * 0.3
    energy_residual = abs(in_e + P_f * 0.05 - out_e) / max(in_e + P_f, 1e-6)

    return LedgerResult(
        P_f=P_f,
        P_i_to_e=P_i_to_e,
        P_rad=P_rad,
        P_wall=P_wall,
        P_gross=P_gross,
        P_recirc=P_recirc,
        P_net=P_net,
        P_import=P_import,
        P_reject=P_reject,
        Q_plasma=Q_plasma,
        Q_eng=Q_eng,
        Q_plant=Q_plant,
        ash_dHe=ash_dHe,
        energy_residual=energy_residual,
    )


def rider_channel(
    *,
    T_i: float,
    T_e: float,
    n_e: float,
    Z_eff: float,
    nonthermal: float,
) -> tuple[float, float]:
    """Return (P_i_to_e proxy, P_rad proxy) in MW-ish theater units."""
    # Soft Rider: coupling grows with n * Te and Z^2; nonthermal reduces coupling
    couple = 0.35 * n_e * (T_i / max(T_e, 0.5)) * (1.0 - 0.55 * nonthermal)
    P_i_to_e = max(0.05, couple)
    P_rad = 0.25 * n_e**2 * (T_e**0.5) * (Z_eff**2) * (1.0 - 0.3 * nonthermal)
    return P_i_to_e, max(0.02, P_rad)
