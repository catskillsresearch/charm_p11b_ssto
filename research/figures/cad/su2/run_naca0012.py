#!/usr/bin/env python3
"""Run the SU2 NACA0012 inviscid tutorial under program control and plot Cp."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
SU2_BIN = ROOT / "third_party/su2/bin"
CASE = Path(__file__).resolve().parent / "naca0012"
CFG = CASE / "inv_NACA0012.cfg"
MESH = CASE / "mesh_NACA0012_inv.su2"
PLOT = CASE / "naca0012_cp.png"


def _ensure_case() -> None:
    CASE.mkdir(parents=True, exist_ok=True)
    base = "https://raw.githubusercontent.com/su2code/Tutorials/master/design/Inviscid_2D_Unconstrained_NACA0012"
    if not CFG.is_file():
        subprocess.check_call(["curl", "-fsSL", "-o", str(CFG), f"{base}/inv_NACA0012_basic.cfg"])
        text = CFG.read_text()
        CFG.write_text(text.replace("RESTART_SOL= YES", "RESTART_SOL= NO"))
    if not MESH.is_file():
        subprocess.check_call(["curl", "-fsSL", "-o", str(MESH), f"{base}/mesh_NACA0012_inv.su2"])


def _run_su2(threads: int) -> None:
    exe = SU2_BIN / "SU2_CFD"
    if not exe.is_file():
        raise SystemExit(f"Missing {exe}; unpack SU2 under third_party/su2/")
    env = os.environ.copy()
    env["PATH"] = f"{SU2_BIN}:{env.get('PATH','')}"
    env["SU2_RUN"] = str(SU2_BIN)
    print(f"==> SU2_CFD -t {threads} {CFG.name}")
    subprocess.check_call([str(exe), "-t", str(threads), CFG.name], cwd=CASE, env=env)


def _plot_cp() -> None:
    csv = CASE / "surface_flow.csv"
    data = np.genfromtxt(csv, delimiter=",", names=True, dtype=None, encoding=None)
    names = data.dtype.names
    x = data[names[1]].astype(float)
    y = data[names[2]].astype(float)
    rho = data[names[3]].astype(float)
    mx = data[names[4]].astype(float)
    my = data[names[5]].astype(float)
    e = data[names[6]].astype(float)
    gamma = 1.4
    ke = 0.5 * (mx**2 + my**2) / np.maximum(rho, 1e-30)
    p_s = (gamma - 1.0) * (e - ke)
    mach = 0.8
    p_inf = 1.0 / gamma
    q_inf = 0.5 * gamma * p_inf * mach**2
    cp = (p_s - p_inf) / q_inf

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), dpi=140)
    fig.patch.set_facecolor("#f4f6f8")
    sc = axes[0].scatter(x, y, c=cp, cmap="coolwarm", s=18, vmin=-1.2, vmax=1.2)
    axes[0].set_aspect("equal")
    axes[0].set_xlabel("x/c")
    axes[0].set_ylabel("y/c")
    axes[0].set_title("NACA 0012 surface · SU2 inviscid · M=0.8, α=1.25°")
    axes[0].grid(True, alpha=0.3)
    fig.colorbar(sc, ax=axes[0], shrink=0.85).set_label("Cp")
    order = np.argsort(x)
    axes[1].plot(x[order], -cp[order], "o", ms=2.5, color="#1f4e79", alpha=0.85)
    axes[1].set_xlabel("x/c")
    axes[1].set_ylabel("−Cp")
    axes[1].set_title("Pressure distribution (−Cp)")
    axes[1].grid(True, alpha=0.35)
    fig.suptitle("SU2 under script control", fontsize=11)
    fig.tight_layout()
    fig.savefig(PLOT)
    plt.close(fig)
    print(f"wrote {PLOT.relative_to(ROOT)}")


def main() -> int:
    threads = int(os.environ.get("SU2_THREADS", "8"))
    _ensure_case()
    _run_su2(threads)
    _plot_cp()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
