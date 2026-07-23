#!/usr/bin/env bash
# Full rebuild: AI figures (cached) + arxiv.md → zenodo.tex, figures, zenodo.pdf, zip
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> AI figures from prompts (skip remote regen unless stale + AI_IMAGE_CMD)"
make ai-figures

echo "==> Generating zenodo.tex and figures"
python3 scripts/build_arxiv_tex.py --target zenodo

echo "==> Compiling zenodo.pdf"
latexmk -pdf -interaction=nonstopmode -jobname=zenodo zenodo.tex

echo "==> Packaging Zenodo submit zip"
./scripts/package_zenodo.sh --zip-only
