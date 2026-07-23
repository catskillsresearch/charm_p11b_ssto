#!/usr/bin/env bash
# Serve the assembly outliner (needs HTTP so the page can fetch assembly.json).
set -euo pipefail
CAD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8765}"
echo "Assembly outliner: http://127.0.0.1:${PORT}/hierarchy_app/"
echo "Serving $CAD"
cd "$CAD"
exec python3 -m http.server "$PORT" --bind 127.0.0.1
