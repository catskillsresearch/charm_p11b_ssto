#!/usr/bin/env bash
# Build arxiv.tex from arxiv.md (mermaid PDFs + converted research/figures assets).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Building arxiv.tex + figures/ from arxiv.md"
python3 scripts/build_arxiv_tex.py
