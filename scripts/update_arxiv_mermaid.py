#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regenerate every <!--mermaid-gen KEY-->...<!--/mermaid-gen--> block in arxiv.md.

`assembly.json` is re-loaded fresh every time (no stale cache trusted), and
each figure spec in `research/figures/cad/emit_paper_mermaid.py` (`FIGURES`)
is re-rendered through the shared `lib/mermaid_builder.py` algorithm — the
same visible-set/nearest-ancestor logic the interactive hierarchy app uses.

Each marker pair looks like::

    <!--mermaid-gen fusion_electric_plant-->
    ```mermaid
    flowchart TB
      ...
    ```
    <!--/mermaid-gen-->

`KEY` must match a key in `emit_paper_mermaid.FIGURES`. Only the fenced
block between the markers is replaced; the `<!-- mermaid-caption: ... -->`
line above it (used by `build_arxiv_tex.py` for figure numbering) and all
other prose is left untouched.

Usage::

    poetry run python scripts/update_arxiv_mermaid.py [arxiv.md]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAD = ROOT / "research" / "figures" / "cad"
sys.path.insert(0, str(CAD))

from emit_paper_mermaid import FIGURES, render_figure  # noqa: E402
from lib.assembly_parser import load_assembly  # noqa: E402

ASM = CAD / "assembly.json"

MARKER_RE = re.compile(
    r"<!--mermaid-gen\s+([A-Za-z0-9_]+)-->.*?<!--/mermaid-gen-->",
    re.DOTALL,
)


def render(match: re.Match, sources: dict[str, str]) -> str:
    key = match.group(1)
    if key not in sources:
        raise KeyError(f"unknown mermaid figure key in arxiv.md marker: {key!r}")
    body = f"```mermaid\n{sources[key]}\n```"
    return f"<!--mermaid-gen {key}-->\n{body}\n<!--/mermaid-gen-->"


def update_file(path: Path) -> bool:
    asm = load_assembly(ASM)
    sources = {key: render_figure(asm, spec)["src"] for key, spec in FIGURES.items()}

    original = path.read_text()
    updated, n = MARKER_RE.subn(lambda m: render(m, sources), original)
    if n == 0:
        print(f"warning: no <!--mermaid-gen--> markers found in {path}", file=sys.stderr)
    if updated != original:
        path.write_text(updated)
        print(f"updated {n} mermaid block(s) in {path}")
        return True
    print(f"{n} mermaid block(s) in {path} already up to date")
    return False


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "arxiv.md"
    update_file(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
