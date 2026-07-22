"""Shared helpers for interactive physics demos."""

from __future__ import annotations

import argparse
import os
import sys


def add_display_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Save plots only (no GUI). Default is interactive windows.",
    )


def configure_matplotlib(headless: bool):
    """Import pyplot with an interactive backend unless --headless."""
    import matplotlib

    if headless or not os.environ.get("DISPLAY"):
        matplotlib.use("Agg", force=True)
    # else: leave default (QtAgg / TkAgg / etc.)
    import matplotlib.pyplot as plt

    return plt


def present(plt, fig, path, *, headless: bool, title: str = "") -> None:
    """Save figure, then show interactively (blocks until window closed)."""
    fig.savefig(path, dpi=140)
    print(f"  wrote {path}")
    if headless:
        plt.close(fig)
        return
    if title:
        print(f"  → showing: {title}")
    else:
        print(f"  → showing figure (close the window to continue)")
    try:
        plt.show(block=True)
    except Exception as exc:
        print(f"  (interactive display failed: {exc}; plot still saved)")
        plt.close(fig)
    else:
        plt.close("all")
