#!/usr/bin/env bash
# Zenodo deposit: zenodo.pdf + .zenodo.json (metadata source of truth).
set -euo pipefail
cd "$(dirname "$0")/.."

PDF="zenodo.pdf"
META=".zenodo.json"
OUT_DIR="dist"
ZIP="${OUT_DIR}/zenodo_submit.zip"

if [[ "${1:-}" != "--zip-only" ]]; then
  if [[ ! -f "$PDF" ]]; then
    echo "==> Building zenodo.pdf first"
    ./scripts/rebuild_zenodo.sh
    exit 0
  fi
fi

for f in "$PDF" "$META"; do
  if [[ ! -f "$f" ]]; then
    echo "error: missing $f" >&2
    exit 1
  fi
done

mkdir -p "$OUT_DIR"
rm -f "$ZIP"
zip -j "$ZIP" "$PDF" "$META"

echo "wrote $ZIP ($(du -h "$ZIP" | cut -f1))"
echo
echo "Zenodo upload:"
echo "  1. https://zenodo.org/deposit/new"
echo "  2. Upload dist/zenodo_submit.zip"
echo "  3. Metadata autofill from .zenodo.json (edit that file to change categories)"
echo
echo "CITATION.cff stays in the repo for GitHub only; not included in this zip."
