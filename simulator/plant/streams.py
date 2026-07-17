"""Named I/O streams for the 0-order plant bus."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


# Canonical stream names (UI binds only to these)
STREAM_META: dict[str, str] = {
    "t": "s",
    "P_f": "MW",
    "P_driver": "MW",
    "P_rad": "MW",
    "P_wall": "MW",
    "P_i_to_e": "MW",
    "P_gross": "MW",
    "P_recirc": "MW",
    "P_net": "MW",
    "P_import": "MW",
    "P_reject": "MW",
    "Q_plasma": "",
    "Q_eng": "",
    "Q_plant": "",
    "n_e": "1e20/m3",
    "T_i": "keV",
    "T_e": "keV",
    "Z_eff": "",
    "fuel_H": "mg/s",
    "fuel_B11": "mg/s",
    "ash_He": "mg",
    "store_SOC": "",
    "magnet_SOC": "",
    "cap_SOC": "",
    "HV_kV": "kV",
    "rep_rate": "Hz",
    "shot_phase": "",
    "blast": "",
    "orbit_phase": "",
    "plasma_brightness": "",
    "mixin_gain": "",
    "energy_residual": "",
    "twin_health": "",
    # Genset-style site I/O
    "batt_SOC": "",
    "batt_kWh": "kWh",
    "batt_kWh_cap": "kWh",
    "batt_V": "V",
    "batt_A": "A",
    "batt_draw_kW": "kW",
    "batt_charge_kW": "kW",
    "batt_used_kWh": "kWh",
    "grid_export_kW": "kW",
    "grid_export_kWh": "kWh",
    "H_in_g": "g",
    "B11_in_g": "g",
    "He_out_g": "g",
    "rad_out_g": "g",
    "Q_ref": "",  # constant 1.0 reference line
    "apu_ramp": "",  # 0→1 pre-production fraction
    "apu_bootstrap_s": "s",
    "preprod_remaining_s": "s",
    "batt_charge_C": "",
}


@dataclass
class AlarmEvent:
    t: float
    level: str  # info | warn | trip
    code: str
    message: str


@dataclass
class StreamBus:
    """Latest values + ring buffers for stripcharts."""

    history_len: int = 600
    values: dict[str, float] = field(default_factory=dict)
    history: dict[str, deque[float]] = field(default_factory=dict)
    time_hist: deque[float] = field(default_factory=lambda: deque(maxlen=600))
    alarms: deque[AlarmEvent] = field(default_factory=lambda: deque(maxlen=200))

    def __post_init__(self) -> None:
        self.time_hist = deque(maxlen=self.history_len)
        for name in STREAM_META:
            self.values.setdefault(name, 0.0)
            self.history[name] = deque(maxlen=self.history_len)

    def set(self, name: str, value: float) -> None:
        self.values[name] = float(value)
        if name not in self.history:
            self.history[name] = deque(maxlen=self.history_len)
        # history appended on commit_sample

    def get(self, name: str, default: float = 0.0) -> float:
        return float(self.values.get(name, default))

    def commit_sample(self, t: float) -> None:
        self.time_hist.append(t)
        for name, buf in self.history.items():
            buf.append(self.values.get(name, 0.0))

    def alarm(self, t: float, level: str, code: str, message: str) -> None:
        self.alarms.appendleft(AlarmEvent(t=t, level=level, code=code, message=message))

    def snapshot(self) -> dict[str, float]:
        return dict(self.values)
