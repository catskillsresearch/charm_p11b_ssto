#!/usr/bin/env bash
# Full rebuild: CAD figures + arxiv.md → zenodo.tex, figures, zenodo.pdf, zip
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> CAD vehicle figures (Blender)"
make cad-figures

echo "==> Generating zenodo.tex and figures"
python3 scripts/build_arxiv_tex.py --target zenodo

echo "==> Compiling zenodo.pdf"
latexmk -pdf -interaction=nonstopmode -jobname=zenodo zenodo.tex

echo "==> Packaging Zenodo submit zip"
./scripts/package_zenodo.sh --zip-only
