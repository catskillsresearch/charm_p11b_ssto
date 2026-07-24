#!/usr/bin/env bash
# Serve the assembly outliner (needs HTTP so the page can fetch assembly.json).
# Disables caching so assembly.json / app.js edits show up after refresh.
set -euo pipefail
CAD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8765}"
echo "Assembly outliner: http://127.0.0.1:${PORT}/hierarchy_app/"
echo "Serving $CAD (Cache-Control: no-store)"
cd "$CAD"
exec python3 - <<PY
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):
        # Keep noise down; still show errors.
        if args and str(args[0]).startswith("4"):
            super().log_message(fmt, *args)

httpd = ThreadingHTTPServer(("127.0.0.1", ${PORT}), NoCacheHandler)
print("Ready.", flush=True)
httpd.serve_forever()
PY
