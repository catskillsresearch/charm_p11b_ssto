#!/usr/bin/env bash
# Launch the DipolEq comprehensive demo using the repo Poetry/.venv.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Missing ${PY}. Create the project venv first."
  exit 1
fi
if ! "$PY" -c "import dipoleq" 2>/dev/null; then
  echo "Installing dipoleq into .venv ..."
  "$PY" -m pip install -q "dipoleq>=0.11"
fi
exec "$PY" "${ROOT}/demos/dipoleq/demo_dipoleq.py" "$@"
