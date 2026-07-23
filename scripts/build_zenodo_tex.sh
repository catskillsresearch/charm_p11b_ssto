#!/usr/bin/env bash
# Generate zenodo.tex and figures from arxiv.md (no arXiv subject classes).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/build_arxiv_tex.py --target zenodo "$@"
