#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regenerate every <!--gen KEY:FMT-->...<!--/gen--> span in arxiv.md in place.

`constants_model.py` is re-run fresh every time (no stale cache trusted).
Each marker pair looks like::

    <!--gen charm.m_cryo_t:.1f-->2.4<!--/gen-->

`KEY` is looked up in the model's `values` dict (numeric, formatted with the
Python format-spec `FMT`) or, if not found there, its `strings` dict (used
verbatim, `FMT` must be empty: `<!--gen mass.m0_kg_sci-->...<!--/gen-->`).
Only the text between the markers is replaced; nothing else in the file is
touched, so hand-written prose is never at risk of being clobbered.

Usage::

    poetry run python scripts/update_arxiv_constants.py [arxiv.md]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "figures" / "cad"))

from constants_model import Params, compute, write_generated_json  # noqa: E402

MARKER_RE = re.compile(
    r"<!--gen\s+([A-Za-z0-9_.]+)(?::([^\s>-]+))?-->.*?<!--/gen-->",
    re.DOTALL,
)


def render(match: re.Match, values: dict, strings: dict) -> str:
    key, fmt = match.group(1), match.group(2)
    if key in values:
        value = values[key]
        text = format(value, fmt) if fmt else str(value)
    elif key in strings:
        if fmt:
            raise ValueError(f"string constant {key!r} may not have a format spec ({fmt!r})")
        text = strings[key]
    else:
        raise KeyError(f"unknown constants key in arxiv.md marker: {key!r}")
    tag_open = match.group(0).split("-->", 1)[0] + "-->"
    return f"{tag_open}{text}<!--/gen-->"


def update_file(path: Path) -> bool:
    r = compute(Params())
    write_generated_json(r)

    original = path.read_text()
    updated, n = MARKER_RE.subn(lambda m: render(m, r.values, r.strings), original)
    if n == 0:
        print(f"warning: no <!--gen--> markers found in {path}", file=sys.stderr)
    if updated != original:
        path.write_text(updated)
        print(f"updated {n} generated span(s) in {path}")
        return True
    print(f"{n} generated span(s) in {path} already up to date")
    return False


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "arxiv.md"
    update_file(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
