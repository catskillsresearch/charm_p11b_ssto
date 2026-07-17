#!/usr/bin/env bash
# Launch the p11b operator twin (survey theater).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
elif command -v poetry >/dev/null 2>&1; then
  exec poetry run python -m simulator.app "$@"
else
  echo "No .venv or poetry found. Run: poetry install --with simulator" >&2
  exit 1
fi

# Ensure simulator deps are importable
if ! "$PY" -c "import PySide6, pyqtgraph" 2>/dev/null; then
  echo "Missing PySide6/pyqtgraph. Run: poetry install --with simulator" >&2
  echo "  or: .venv/bin/pip install 'PySide6>=6.8,<6.12' 'pyqtgraph>=0.14,<0.15'" >&2
  exit 1
fi

exec "$PY" -m simulator.app "$@"
