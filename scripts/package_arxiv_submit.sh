#!/usr/bin/env bash
# Build arxiv.tex and zip everything arXiv needs to compile it (pdfLaTeX).
#
# Narrative lives in one arxiv.tex; mermaid figure PDFs and converted raster/SVG
# assets ship under figures/.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck source=scripts/arxiv_pdf_checks.sh
source "$(dirname "$0")/arxiv_pdf_checks.sh"

TEX="arxiv.tex"
FIGURES_DIR="figures"
OUT_DIR="dist"
ZIP="${OUT_DIR}/arxiv_submit.zip"

if [[ "${1:-}" != "--skip-tex-build" ]]; then
  echo "==> Regenerating arxiv.tex and figures from arxiv.md"
  bash scripts/build_arxiv_tex.sh
  echo "==> Compiling arxiv.pdf (see scripts/build_arxiv_pdf.sh)"
  bash scripts/build_arxiv_pdf.sh --pdf-only
fi

missing=0
if [[ ! -f "$TEX" ]]; then
  echo "error: missing $TEX" >&2
  missing=1
fi
fig_count="$(find "$FIGURES_DIR" -type f \( -name '*.pdf' -o -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' \) 2>/dev/null | wc -l)"
if [[ "$fig_count" -eq 0 ]]; then
  echo "error: no figure assets in $FIGURES_DIR" >&2
  missing=1
fi
if [[ "$missing" -ne 0 ]]; then
  exit 1
fi

mkdir -p "$OUT_DIR"
rm -f "$ZIP"

echo "==> Writing 00README.json (main tex + figure assets + any lstinputlisting deps)"
python3 - <<'PY'
import json
import re
import sys
from pathlib import Path

tex = Path("arxiv.tex").read_text(encoding="utf-8")
listing_paths = sorted(
    set(re.findall(r"\\lstinputlisting(?:\[[^\]]*\])?\{([^}]+)\}", tex))
)
missing = [p for p in listing_paths if not Path(p).is_file()]
if missing:
    print("error: arxiv.tex references missing listing files:", ", ".join(missing), file=sys.stderr)
    sys.exit(1)

include_paths = sorted(
    set(re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex))
)
missing_img = [p for p in include_paths if not Path(p).is_file()]
if missing_img:
    print("error: arxiv.tex references missing images:", ", ".join(missing_img), file=sys.stderr)
    sys.exit(1)

sources = [{"filename": "arxiv.tex", "usage": "toplevel"}]
for path in listing_paths:
    sources.append({"filename": path, "usage": "include"})
for path in include_paths:
    sources.append({"filename": path, "usage": "include"})
readme = {"process": {"compiler": "pdflatex"}, "sources": sources}
Path("00README.json").write_text(json.dumps(readme, indent=2) + "\n")
Path(".arxiv_main_listings").write_text("\n".join(listing_paths) + ("\n" if listing_paths else ""))
Path(".arxiv_main_images").write_text("\n".join(include_paths) + ("\n" if include_paths else ""))
print(f"  {len(sources)} sources ({len(listing_paths)} listing(s), {len(include_paths)} image(s))")
PY

echo "==> Packaging"
zip_args=(00README.json "$TEX")
if [[ -s .arxiv_main_listings ]]; then
  mapfile -t main_listings < .arxiv_main_listings
  zip_args+=("${main_listings[@]}")
fi
if [[ -s .arxiv_main_images ]]; then
  mapfile -t main_images < .arxiv_main_images
  zip_args+=("${main_images[@]}")
fi
# Keep directory layout for paths like figures/assets/foo.png
zip -r "$ZIP" "${zip_args[@]}"
rm -f .arxiv_main_listings .arxiv_main_images

echo "wrote $ZIP ($(du -h "$ZIP" | cut -f1))"
echo "==> arXiv preflight checks"
if [[ -f arxiv.pdf ]]; then
  check_pdf_fonts_embedded arxiv.pdf "arxiv.pdf"
fi
check_submission_size "$ZIP"
echo "Contents:"
zipinfo -1 "$ZIP" | sed 's/^/  /' | head -40
echo
echo "Upload $ZIP to arXiv (pdfLaTeX; arxiv.tex line 1 is \\\\pdfoutput=1)."
echo "On arXiv Add Files: Delete All before uploading (uploads merge, they do not replace)."
