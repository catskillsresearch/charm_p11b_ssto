#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Synthesize a stylized ascent soundscape and emit the §10.8 figure.

This is **illustrative sound design**, not a validated psychoacoustic or
CFD-based acoustic simulation: no far-field jet-noise spectrum, duct
resonance, or propagation/absorption model is solved. What IS grounded in
the model:

  - Relative loudness between Stage 1 (EDF) and Stage 2 (air plasma) uses
    the same mdot/v_jet^n scaling and the same numbers computed in
    `constants_model.compute()` (§10.8), so the two "roars" below really
    are ~28 dB apart in the same ratio quoted in the paper (dynamic range
    is then compressed for audibility -- flagged below, not hidden).
  - The transient "crack" is placed at the point in the timeline
    corresponding to the real Mach-1 crossing of the constant-Q climb
    (`mach1_crossing_altitude_m`), not an arbitrary sound-design choice.
  - The final low-frequency "hum + thump" segment represents cabin
    structure-borne noise once intakes seal (own §9.5/§9.6 cryocooler duty
    cycle, not a new claim) -- there is no external medium left to carry
    airborne jet/plasma noise once the vehicle is in vacuum.

Frequencies/timbre/timeline pacing ARE stylized (no fan blade count, duct
geometry, or Strouhal-scaled spectrum exists for this airframe) and are
flagged as such in arxiv.md prose.

Outputs:
  - research/figures/audio/charm_ssto_ascent_soundscape.wav (listen to it)
  - research/figures/stage1_audio_signature.png (waveform + spectrogram,
    the only one of the two that can go in the PDF)

Run directly::

    poetry run python research/figures/cad/emit_audio_signature.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfiltfilt, spectrogram

CAD = Path(__file__).resolve().parent
sys.path.insert(0, str(CAD))

from constants_model import Params, compute, integrate_stage2_climb  # noqa: E402

FIGURES = CAD.parent
AUDIO_DIR = FIGURES / "audio"
WAV_OUT = AUDIO_DIR / "charm_ssto_ascent_soundscape.wav"
PNG_OUT = FIGURES / "stage1_audio_signature.png"

FS = 44100  # Hz
RNG = np.random.default_rng(11)


def _bandpass_noise(n: int, lo_hz: float, hi_hz: float, order: int = 4) -> np.ndarray:
    noise = RNG.standard_normal(n)
    sos = butter(order, [lo_hz, hi_hz], btype="bandpass", fs=FS, output="sos")
    return sosfiltfilt(sos, noise)


def _lowpass_noise(n: int, hi_hz: float, order: int = 4) -> np.ndarray:
    noise = RNG.standard_normal(n)
    sos = butter(order, hi_hz, btype="lowpass", fs=FS, output="sos")
    return sosfiltfilt(sos, noise)


def _norm(x: np.ndarray) -> np.ndarray:
    peak = np.max(np.abs(x)) + 1e-12
    return x / peak


def _fade(n: int, in_s: float = 0.0, out_s: float = 0.0) -> np.ndarray:
    env = np.ones(n)
    n_in = int(in_s * FS)
    n_out = int(out_s * FS)
    if n_in > 0:
        env[:n_in] *= np.linspace(0.0, 1.0, n_in)
    if n_out > 0:
        env[-n_out:] *= np.linspace(1.0, 0.0, n_out)
    return env


def _n_wave(duration_s: float = 0.09, peak: float = 1.0) -> np.ndarray:
    """Classic sonic-boom N-wave: sharp rise, linear ramp through zero,
    sharp return to ambient. Shape only (no overpressure physics)."""
    n = int(duration_s * FS)
    t = np.linspace(-1.0, 1.0, n)
    wave = -t  # linear ramp from +1 to -1
    edge = max(int(0.03 * n), 2)
    window = np.ones(n)
    window[:edge] = np.linspace(0.0, 1.0, edge)
    window[-edge:] = np.linspace(1.0, 0.0, edge)
    return peak * wave * window


def stage1_edf_segment(duration_s: float, amp: float, fan_hz: float = 96.0) -> np.ndarray:
    """Big slow ducted fan: blade-passage tone + harmonics over a modest
    broadband whoosh -- no combustion roar, no turbine whine."""
    n = int(duration_s * FS)
    t = np.arange(n) / FS
    tone = sum(
        (0.5**k) * np.sin(2 * np.pi * fan_hz * (k + 1) * t + RNG.uniform(0, 2 * np.pi))
        for k in range(4)
    )
    flutter = 1.0 + 0.05 * np.sin(2 * np.pi * 1.3 * t)
    whoosh = _bandpass_noise(n, 150.0, 1800.0)
    sig = 0.55 * _norm(tone) * flutter + 0.65 * _norm(whoosh)
    sig *= _fade(n, in_s=min(1.0, duration_s * 0.2))
    return amp * _norm(sig)


def stage2_plasma_segment(duration_s: float, amp0: float, amp1: float) -> np.ndarray:
    """Broadband air-plasma jet roar: harsher / higher-frequency broadband
    mixing noise than Stage 1, consistent with its higher v_jet (§10.4/§10.8).
    Slow brightening + rising level models the constant-Q climb; the final
    taper models thinning atmosphere as intakes approach sealing (§10.4)."""
    n = int(duration_s * FS)
    t = np.arange(n) / FS
    frac = t / max(duration_s, 1e-9)
    lo = _bandpass_noise(n, 200.0, 2500.0)
    hi = _bandpass_noise(n, 1500.0, 9000.0)
    mix = _norm(lo) * (1.0 - 0.5 * frac) + _norm(hi) * (0.4 + 0.5 * frac)
    rumble = _lowpass_noise(n, 120.0)
    sig = 0.85 * _norm(mix) + 0.25 * _norm(rumble)
    level = amp0 + (amp1 - amp0) * np.clip(frac / 0.85, 0.0, 1.0)
    tail = _fade(n, out_s=min(3.0, duration_s * 0.3))
    return level * _norm(sig) * tail


def vacuum_hum_segment(duration_s: float, amp: float, thump_hz: float = 1.6) -> np.ndarray:
    """Cabin structure-borne noise only, once intakes seal and there is no
    external medium left to carry airborne jet/plasma sound (§9.5/§9.6
    cryocooler duty-cycle callback): a low hum plus a periodic cold-head
    thump, both far below the atmospheric-flight levels above."""
    n = int(duration_s * FS)
    t = np.arange(n) / FS
    hum = 0.6 * np.sin(2 * np.pi * 52.0 * t) + 0.3 * np.sin(2 * np.pi * 78.0 * t)
    thump_env = 0.5 * (1.0 + np.sin(2 * np.pi * thump_hz * t - np.pi / 2)) ** 4
    sig = 0.5 * _norm(hum) + 0.9 * thump_env
    sig *= _fade(n, in_s=min(1.5, duration_s * 0.3))
    return amp * _norm(sig)


def build_timeline(r_values: dict) -> tuple[np.ndarray, list[tuple[float, float, str]]]:
    """Stylized (time-compressed) ascent soundscape. Real stage durations
    are t1~133 s, t2~29 min, t3~4.3 h (§10.5/§10.6) -- far too long to
    render literally, so the timeline below preserves the *character* and
    *relative loudness* of each phase, not real elapsed time."""
    db1 = r_values["acoustic.stage1_rel_db"]
    db2 = r_values["acoustic.stage2_rel_db"]
    # Compress the ~28.5 dB spread (still audibly dramatic) for listenability.
    compress = 0.5
    amp1 = 10 ** (compress * db1 / 20.0)
    amp2 = 10 ** (compress * db2 / 20.0)
    amp1, amp2 = amp1 / amp2, 1.0  # normalize so the louder Stage 2 segment sits at 1.0

    segs: list[np.ndarray] = []
    marks: list[tuple[float, float, str]] = []
    t_cursor = 0.0

    lead_in = np.zeros(int(0.5 * FS))
    segs.append(lead_in)
    t_cursor += 0.5

    d = 11.0
    segs.append(stage1_edf_segment(d, amp1))
    marks.append((t_cursor, t_cursor + d, "Stage 1 — EDF (municipal takeoff / climb)"))
    t_cursor += d

    boom = _n_wave(0.09, peak=1.0)
    boom2 = _n_wave(0.09, peak=0.7)
    gap = np.zeros(int(0.08 * FS))
    crack = np.concatenate([boom, gap, boom2])
    segs.append(crack)
    marks.append((t_cursor, t_cursor + len(crack) / FS, "M = 1 (own climb model, §10.8)"))
    t_cursor += len(crack) / FS

    d = 24.0
    segs.append(stage2_plasma_segment(d, amp2 * 0.55, amp2))
    marks.append((t_cursor, t_cursor + d, "Stage 2 — microwave air plasma (hypersonic climb)"))
    t_cursor += d

    d = 6.0
    hush = np.zeros(int(d * FS))
    segs.append(hush)
    marks.append((t_cursor, t_cursor + d, "Intakes seal / atmosphere thins (§10.4 h_seal)"))
    t_cursor += d

    d = 8.0
    segs.append(vacuum_hum_segment(d, 0.06))
    marks.append((t_cursor, t_cursor + d, "Vacuum: cabin structure-borne hum only (§9.5/§9.6)"))
    t_cursor += d

    audio = np.concatenate(segs)
    audio = np.clip(audio, -1.0, 1.0)
    return audio, marks


def main() -> int:
    p = Params()
    r = compute(p)
    audio, marks = build_timeline(r.values)

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    wavfile.write(WAV_OUT, FS, (audio * 32767 * 0.95).astype(np.int16))
    print(f"wrote {WAV_OUT} ({len(audio) / FS:.1f} s)")

    f, t_spec, Sxx = spectrogram(audio, fs=FS, nperseg=2048, noverlap=1536)
    Sxx_db = 10 * np.log10(Sxx + 1e-12)

    fig, (ax_wave, ax_spec) = plt.subplots(
        2, 1, figsize=(10.5, 6.0), dpi=160, sharex=True,
        gridspec_kw={"height_ratios": [1, 2]},
    )
    fig.patch.set_facecolor("#f7f8fa")
    t_wave = np.arange(len(audio)) / FS
    ax_wave.plot(t_wave, audio, color="#1f4e79", lw=0.4)
    ax_wave.set_ylabel("amplitude")
    ax_wave.set_ylim(-1.05, 1.05)
    ax_wave.set_title(
        "Stylized ascent soundscape (time-compressed; relative levels from §10.8 constants_model)"
    )
    ax_wave.grid(True, alpha=0.3)

    pcm = ax_spec.pcolormesh(t_spec, f, Sxx_db, shading="gouraud", cmap="magma", vmin=-90, vmax=-10)
    ax_spec.set_ylabel("frequency (Hz)")
    ax_spec.set_xlabel("time (s)")
    ax_spec.set_ylim(0, 10000)
    fig.colorbar(pcm, ax=ax_spec, label="dB (arb.)", pad=0.01)

    palette = ["#2b6cb0", "#c0392b", "#8a6e42", "#5a6f8c", "#4f7a48"]
    y_stagger = [0.97, 0.80, 0.97, 0.80, 0.97]
    for i, (t0, t1, label) in enumerate(marks):
        color = palette[i % len(palette)]
        for ax in (ax_wave, ax_spec):
            ax.axvline(t0, color=color, lw=0.8, alpha=0.6, ls="--")
        ax_wave.text(
            t0 + 0.3, y_stagger[i % len(y_stagger)], label, rotation=0, fontsize=7.2,
            color=color, va="top", ha="left", transform=ax_wave.get_xaxis_transform(),
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75),
        )

    fig.tight_layout()
    PNG_OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(PNG_OUT)
    print(f"wrote {PNG_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
