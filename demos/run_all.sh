#!/usr/bin/env bash
# Run all three package demos sequentially.
# Tip: pass --headless for non-interactive batch runs.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "=== DipolEq ==="
"${ROOT}/dipoleq/run.sh" "$@"
echo "=== OpenMC ==="
"${ROOT}/openmc/run.sh" "$@"
echo "=== ASCOT5 ==="
"${ROOT}/ascot5/run.sh" "$@"
echo "All demos finished. See demos/output/"
