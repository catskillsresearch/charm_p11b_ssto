#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the codex53 Crew Dragon seat variant.

This wrapper reuses the fully connected high-fidelity builder and writes
outputs into `seat/codex53/` with codex53 filenames.

Run:
    /snap/bin/blender -b -P seat/codex53/build_codex53.py
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "composer_25" / "build_composer_25.py"

BLEND_OUT = HERE / "codex53.blend"
PNG_OUT = HERE / "codex53_render.png"
PNG_OUT_SIDE = HERE / "codex53_render_side.png"
PNG_OUT_MOUNT = HERE / "codex53_render_mount.png"


def _load_source_module():
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Missing source builder: {SOURCE}")
    spec = importlib.util.spec_from_file_location("composer_25_builder", SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module spec from {SOURCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = _load_source_module()

    # Redirect outputs to codex53 paths.
    module.BLEND_OUT = BLEND_OUT
    module.PNG_OUT = PNG_OUT
    module.PNG_OUT_SIDE = PNG_OUT_SIDE
    module.PNG_OUT_MOUNT = PNG_OUT_MOUNT

    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
