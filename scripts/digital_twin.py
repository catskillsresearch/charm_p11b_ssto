#!/usr/bin/env python3
"""Digital-twin design picker over catalog qualifiers.

Pick time / confinement / fuel / kinetics (and optional path type). Matching
catalog architectures are listed; a complete selection with no hits mints or
recalls a novel-N tag.

  python scripts/digital_twin.py
"""

from __future__ import annotations

import json
import sqlite3
import threading
import webbrowser
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "p11b_catalog.sqlite"
NOVEL_PATH = ROOT / "data" / "novel_twins.json"
HOST = "127.0.0.1"
PORT = 8766

# Axes required before a novel tag can be minted
REQUIRED_AXES = ("time", "confinement", "fuel", "kinetics")
OPTIONAL_AXES = ("path_type",)

_novel_lock = threading.Lock()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]


def fingerprint(selection: dict[str, str | None]) -> str:
    parts = []
    for axis in (*REQUIRED_AXES, *OPTIONAL_AXES):
        val = (selection.get(axis) or "").strip()
        if val:
            parts.append(f"{axis}={val}")
    return "|".join(parts)


def load_novels() -> dict:
    if not NOVEL_PATH.exists():
        return {"next_id": 1, "by_fingerprint": {}}
    return json.loads(NOVEL_PATH.read_text(encoding="utf-8"))


def save_novels(data: dict) -> None:
    NOVEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOVEL_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_novel(selection: dict[str, str | None]) -> dict | None:
    """Return or mint novel-N when all required axes are set."""
    if not all((selection.get(a) or "").strip() for a in REQUIRED_AXES):
        return None
    fp = fingerprint(selection)
    with _novel_lock:
        data = load_novels()
        existing = data["by_fingerprint"].get(fp)
        if existing:
            return {**existing, "created": False, "fingerprint": fp}
        n = int(data["next_id"])
        tag = f"novel-{n}"
        record = {
            "tag": tag,
            "id": n,
            "selection": {a: selection.get(a) for a in (*REQUIRED_AXES, *OPTIONAL_AXES) if selection.get(a)},
        }
        data["by_fingerprint"][fp] = record
        data["next_id"] = n + 1
        save_novels(data)
        return {**record, "created": True, "fingerprint": fp}


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    with connect() as conn:
        axes = {
            "time": rows_to_dicts(
                conn.execute(
                    "SELECT id, name FROM time_mode ORDER BY name"
                ).fetchall()
            ),
            "confinement": rows_to_dicts(
                conn.execute(
                    """
                    SELECT id, name, short_name
                    FROM confinement_family
                    ORDER BY name
                    """
                ).fetchall()
            ),
            "fuel": rows_to_dicts(
                conn.execute(
                    """
                    SELECT id, name, is_p11b_clean
                    FROM fuel_end_state
                    ORDER BY name
                    """
                ).fetchall()
            ),
            "kinetics": rows_to_dicts(
                conn.execute(
                    "SELECT id, name FROM kinetics_regime ORDER BY name"
                ).fetchall()
            ),
            "path_type": rows_to_dicts(
                conn.execute("SELECT id, name FROM path_type ORDER BY name").fetchall()
            ),
        }

        architectures = rows_to_dicts(
            conn.execute(
                """
                SELECT
                    a.id,
                    a.slug,
                    a.name,
                    a.catalog_status AS status,
                    a.source_section AS section,
                    tm.name AS time,
                    cf.name AS confinement,
                    cf.short_name AS confinement_short,
                    fe.name AS fuel,
                    fe.is_p11b_clean AS p11b_clean,
                    kr.name AS kinetics,
                    pt.name AS path_type,
                    CASE WHEN po.architecture_id IS NOT NULL THEN po.rank END AS plant_odds_rank,
                    po.pos_star AS pos_star,
                    COALESCE(
                        (SELECT GROUP_CONCAT(
                            CASE WHEN e.short_name IS NOT NULL AND e.short_name != ''
                                 THEN e.short_name ELSE e.canonical_name END, ', ')
                         FROM architecture_entity ae
                         JOIN entity e ON e.id = ae.entity_id
                         WHERE ae.architecture_id = a.id AND ae.role = 'lead'),
                        ''
                    ) AS lead,
                    COALESCE(
                        (SELECT GROUP_CONCAT(p.name || ' [' || pk.name || ']', ', ')
                         FROM prototype p
                         JOIN prototype_kind pk ON pk.id = p.kind_id
                         WHERE p.architecture_id = a.id),
                        ''
                    ) AS prototypes,
                    EXISTS(
                        SELECT 1 FROM hedp_degenerate_host h
                        WHERE h.architecture_id = a.id
                    ) AS hedp_degenerate_host
                FROM architecture a
                LEFT JOIN time_mode tm ON tm.id = a.time_mode_id
                LEFT JOIN confinement_family cf ON cf.id = a.confinement_family_id
                LEFT JOIN fuel_end_state fe ON fe.id = a.fuel_end_state_id
                LEFT JOIN kinetics_regime kr ON kr.id = a.kinetics_regime_id
                LEFT JOIN path_type pt ON pt.id = a.path_type_id
                LEFT JOIN plant_odds po ON po.architecture_id = a.id
                ORDER BY COALESCE(po.rank, 999), a.name
                """
            ).fetchall()
        )

        matrix = rows_to_dicts(
            conn.execute(
                """
                SELECT code, name, plain_question, typical_answers, sort_order
                FROM matrix_axis
                ORDER BY sort_order
                """
            ).fetchall()
        )

    for row in architectures:
        row["p11b_clean"] = bool(row["p11b_clean"])
        row["hedp_degenerate_host"] = bool(row["hedp_degenerate_host"])

    return {
        "axes": axes,
        "architectures": architectures,
        "matrix": matrix,
        "required_axes": list(REQUIRED_AXES),
        "optional_axes": list(OPTIONAL_AXES),
    }


def match_architectures(selection: dict[str, str | None], catalog: dict) -> list[dict]:
    hits = []
    for arch in catalog["architectures"]:
        ok = True
        for axis in (*REQUIRED_AXES, *OPTIONAL_AXES):
            want = (selection.get(axis) or "").strip()
            if not want:
                continue
            if (arch.get(axis) or "") != want:
                ok = False
                break
        if ok:
            hits.append(arch)
    return hits


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>p11b digital twin</title>
<style>
  :root {
    --bg: #eef2f1;
    --panel: #fbfcfb;
    --ink: #15201c;
    --muted: #5c6b64;
    --line: #c9d4ce;
    --accent: #0b6e4f;
    --accent-2: #b45309;
    --soft: #d7ebe3;
    --novel: #f3e6d4;
    --shadow: 0 10px 30px rgba(21,32,28,.06);
    font-family: "IBM Plex Sans", "Source Sans 3", "Segoe UI", sans-serif;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    color: var(--ink);
    min-height: 100vh;
    background:
      linear-gradient(165deg, #dfece7 0%, transparent 42%),
      linear-gradient(320deg, #f4e8d8 0%, transparent 40%),
      var(--bg);
  }
  header {
    padding: 1.25rem 1.5rem 1rem;
    border-bottom: 1px solid var(--line);
    background: color-mix(in srgb, var(--panel) 90%, transparent);
    backdrop-filter: blur(8px);
    position: sticky; top: 0; z-index: 3;
  }
  header h1 {
    margin: 0;
    font-family: "IBM Plex Serif", Georgia, serif;
    font-size: 1.45rem;
    font-weight: 600;
  }
  header p { margin: .35rem 0 0; color: var(--muted); max-width: 52rem; line-height: 1.4; }
  .layout {
    display: grid;
    grid-template-columns: minmax(280px, 340px) 1fr;
    gap: 0;
    min-height: calc(100vh - 96px);
  }
  .picker {
    padding: 1.1rem 1.1rem 2rem;
    border-right: 1px solid var(--line);
    background: color-mix(in srgb, var(--panel) 75%, transparent);
  }
  .picker h2 {
    margin: 0 0 .75rem;
    font-size: .75rem;
    text-transform: uppercase;
    letter-spacing: .05em;
    color: var(--muted);
  }
  .field { margin-bottom: .9rem; }
  .field label {
    display: block;
    font-size: .82rem;
    font-weight: 600;
    margin-bottom: .3rem;
  }
  .field .hint {
    color: var(--muted);
    font-size: .75rem;
    font-weight: 400;
    margin-top: .15rem;
    line-height: 1.3;
  }
  .field select {
    width: 100%;
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: .55rem .65rem;
    font: inherit;
    background: var(--panel);
    color: var(--ink);
  }
  .field select:focus {
    outline: 2px solid color-mix(in srgb, var(--accent) 40%, white);
    border-color: var(--accent);
  }
  .actions {
    display: flex;
    gap: .5rem;
    margin-top: 1rem;
  }
  .actions button {
    border: 1px solid var(--line);
    background: var(--panel);
    border-radius: 10px;
    padding: .5rem .75rem;
    font: inherit;
    cursor: pointer;
  }
  .actions button.primary {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
  }
  .actions button:hover { filter: brightness(1.03); }
  .result { padding: 1.1rem 1.3rem 2.5rem; min-width: 0; }
  .status {
    display: flex;
    flex-wrap: wrap;
    gap: .6rem;
    align-items: center;
    margin-bottom: 1rem;
  }
  .pill {
    display: inline-flex;
    align-items: center;
    gap: .35rem;
    border-radius: 999px;
    padding: .28rem .7rem;
    font-size: .82rem;
    background: var(--soft);
    color: var(--accent);
    font-weight: 600;
  }
  .pill.novel { background: var(--novel); color: var(--accent-2); }
  .pill.muted { background: #e7ebe9; color: var(--muted); font-weight: 500; }
  .tag-box {
    border: 1px solid var(--line);
    border-radius: 14px;
    background: var(--panel);
    box-shadow: var(--shadow);
    padding: 1rem 1.1rem;
    margin-bottom: 1rem;
  }
  .tag-box.novel-hit {
    border-color: color-mix(in srgb, var(--accent-2) 45%, var(--line));
    background: linear-gradient(180deg, #fff9f1, var(--panel));
  }
  .tag-box h3 {
    margin: 0 0 .35rem;
    font-family: "IBM Plex Serif", Georgia, serif;
    font-size: 1.15rem;
  }
  .tag-box .tag {
    font-family: ui-monospace, "IBM Plex Mono", monospace;
    font-size: 1.35rem;
    font-weight: 600;
    color: var(--accent-2);
    letter-spacing: .02em;
  }
  .tag-box p { margin: .45rem 0 0; color: var(--muted); line-height: 1.4; font-size: .92rem; }
  .selection-chips { display: flex; flex-wrap: wrap; gap: .35rem; margin-top: .7rem; }
  .chip {
    font-size: .75rem;
    background: #eef4f1;
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: .2rem .55rem;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: .75rem;
  }
  .card {
    border: 1px solid var(--line);
    border-radius: 14px;
    background: var(--panel);
    padding: .9rem 1rem;
    box-shadow: var(--shadow);
  }
  .card h4 {
    margin: 0 0 .25rem;
    font-size: 1rem;
    font-family: "IBM Plex Serif", Georgia, serif;
  }
  .card .slug {
    font-family: ui-monospace, monospace;
    font-size: .78rem;
    color: var(--accent);
  }
  .card dl {
    margin: .65rem 0 0;
    display: grid;
    grid-template-columns: auto 1fr;
    gap: .2rem .55rem;
    font-size: .8rem;
  }
  .card dt { color: var(--muted); }
  .card dd { margin: 0; }
  .empty {
    color: var(--muted);
    padding: 1.5rem 0;
    line-height: 1.45;
  }
  @media (max-width: 900px) {
    .layout { grid-template-columns: 1fr; }
    .picker { border-right: 0; border-bottom: 1px solid var(--line); }
  }
</style>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@600&family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Serif:wght@600&display=swap" rel="stylesheet" />
</head>
<body>
<header>
  <h1>p11b digital twin</h1>
  <p>
    Choose design-relevant qualifiers from the survey taxonomy. Matching catalog
    architectures appear as known twins; a fully specified combo with no catalog
    hit proposes a <strong>novel-N</strong> tag.
  </p>
</header>
<div class="layout">
  <aside class="picker">
    <h2>Design qualifiers</h2>
    <div id="fields"></div>
    <div class="actions">
      <button type="button" class="primary" id="resolveBtn">Resolve twin</button>
      <button type="button" id="resetBtn">Reset</button>
    </div>
  </aside>
  <main class="result">
    <div class="status" id="status"></div>
    <div id="novelBox"></div>
    <div id="matches"></div>
  </main>
</div>
<script>
const AXIS_META = {
  time: { label: "Time", required: true },
  confinement: { label: "Confinement family", required: true },
  fuel: { label: "Fuel end-state", required: true },
  kinetics: { label: "Kinetics", required: true },
  path_type: { label: "Path type", required: false },
};

let catalog = null;
let matrixHints = {};

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, ch => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  })[ch]);
}

function selection() {
  const out = {};
  for (const axis of Object.keys(AXIS_META)) {
    const el = document.getElementById("axis-" + axis);
    out[axis] = el && el.value ? el.value : null;
  }
  return out;
}

function requiredComplete(sel) {
  return catalog.required_axes.every(a => sel[a]);
}

function clientMatch(sel) {
  return catalog.architectures.filter(arch => {
    for (const axis of [...catalog.required_axes, ...catalog.optional_axes]) {
      if (!sel[axis]) continue;
      if ((arch[axis] || "") !== sel[axis]) return false;
    }
    return true;
  });
}

function renderFields() {
  const root = document.getElementById("fields");
  const order = [...catalog.required_axes, ...catalog.optional_axes];
  root.innerHTML = order.map(axis => {
    const meta = AXIS_META[axis];
    const hint = matrixHints[axis] || "";
    const opts = catalog.axes[axis].map(o => {
      const label = o.short_name ? `${o.name} (${o.short_name})` : o.name;
      const extra = axis === "fuel" && o.is_p11b_clean != null
        ? (o.is_p11b_clean ? " · p–¹¹B-clean" : " · not p–¹¹B-clean")
        : "";
      return `<option value="${escapeHtml(o.name)}">${escapeHtml(label + extra)}</option>`;
    }).join("");
    return `
      <div class="field">
        <label for="axis-${axis}">${escapeHtml(meta.label)}${meta.required ? "" : " <span style='color:var(--muted);font-weight:400'>(optional)</span>"}</label>
        <select id="axis-${axis}">
          <option value="">Any</option>
          ${opts}
        </select>
        ${hint ? `<div class="hint">${escapeHtml(hint)}</div>` : ""}
      </div>`;
  }).join("");

  for (const axis of order) {
    document.getElementById("axis-" + axis).addEventListener("change", () => resolve(false));
  }
}

function renderMatches(hits) {
  const box = document.getElementById("matches");
  if (!hits.length) {
    box.innerHTML = `<p class="empty">No catalog architectures match the current filters.</p>`;
    return;
  }
  box.innerHTML = `<div class="grid">${hits.map(a => `
    <article class="card">
      <div class="slug">${escapeHtml(a.slug)}</div>
      <h4>${escapeHtml(a.name)}</h4>
      <dl>
        <dt>Time</dt><dd>${escapeHtml(a.time || "—")}</dd>
        <dt>Confinement</dt><dd>${escapeHtml(a.confinement_short || a.confinement || "—")}</dd>
        <dt>Fuel</dt><dd>${escapeHtml(a.fuel || "—")}</dd>
        <dt>Kinetics</dt><dd>${escapeHtml(a.kinetics || "—")}</dd>
        <dt>Path</dt><dd>${escapeHtml(a.path_type || "—")}</dd>
        <dt>Lead</dt><dd>${escapeHtml(a.lead || "—")}</dd>
        <dt>POS★</dt><dd>${a.pos_star != null ? `#${a.plant_odds_rank} · ${a.pos_star}` : "—"}</dd>
        <dt>Prototypes</dt><dd>${escapeHtml(a.prototypes || "—")}</dd>
      </dl>
    </article>
  `).join("")}</div>`;
}

async function resolve(mintNovel) {
  const sel = selection();
  const hits = clientMatch(sel);
  const complete = requiredComplete(sel);
  const status = document.getElementById("status");
  const novelBox = document.getElementById("novelBox");

  const active = Object.entries(sel).filter(([, v]) => v);
  status.innerHTML = `
    <span class="pill muted">${active.length} qualifier${active.length===1?"":"s"} set</span>
    <span class="pill">${hits.length} known twin${hits.length===1?"":"s"}</span>
    ${complete ? "" : `<span class="pill muted">Set all four matrix axes to mint novel-N</span>`}
  `;

  const chips = active.map(([k, v]) =>
    `<span class="chip"><strong>${escapeHtml(AXIS_META[k].label)}:</strong> ${escapeHtml(v)}</span>`
  ).join("");

  if (hits.length) {
    novelBox.innerHTML = `
      <div class="tag-box">
        <h3>Known architecture${hits.length===1?"":"s"}</h3>
        <p>Selection maps onto the catalog. Twin identity is the slug below — no novel tag.</p>
        <div class="selection-chips">${chips}</div>
      </div>`;
    renderMatches(hits);
    return;
  }

  if (!complete) {
    novelBox.innerHTML = `
      <div class="tag-box">
        <h3>Narrowing…</h3>
        <p>No exact catalog hits yet for the active filters. Keep choosing, or fill Time, Confinement, Fuel, and Kinetics to propose a novel twin.</p>
        <div class="selection-chips">${chips}</div>
      </div>`;
    renderMatches(hits);
    return;
  }

  // Complete selection, zero hits → novel
  if (mintNovel) {
    const res = await fetch("/api/novel", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(sel),
    });
    const novel = await res.json();
    novelBox.innerHTML = `
      <div class="tag-box novel-hit">
        <h3>${novel.created ? "Proposed novel twin" : "Recalled novel twin"}</h3>
        <div class="tag">${escapeHtml(novel.tag)}</div>
        <p>${novel.created
          ? "No catalog architecture has this qualifier combo. Tag persisted in data/novel_twins.json."
          : "This combo was minted earlier — same fingerprint returns the same tag."}</p>
        <div class="selection-chips">${chips}</div>
      </div>`;
    status.innerHTML += `<span class="pill novel">${escapeHtml(novel.tag)}</span>`;
  } else {
    novelBox.innerHTML = `
      <div class="tag-box novel-hit">
        <h3>No catalog twin</h3>
        <p>This fully specified design is not in the survey catalog. Click <strong>Resolve twin</strong> to mint or recall a <code>novel-N</code> tag.</p>
        <div class="selection-chips">${chips}</div>
      </div>`;
  }
  renderMatches(hits);
}

async function boot() {
  const res = await fetch("/api/catalog");
  catalog = await res.json();
  matrixHints = {};
  for (const m of catalog.matrix || []) {
    // matrix codes: time, confinement, fuel, kinetics
    matrixHints[m.code] = m.plain_question;
  }
  renderFields();
  document.getElementById("resolveBtn").onclick = () => resolve(true);
  document.getElementById("resetBtn").onclick = () => {
    for (const axis of Object.keys(AXIS_META)) {
      const el = document.getElementById("axis-" + axis);
      if (el) el.value = "";
    }
    resolve(false);
  };
  resolve(false);
}
boot();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        if args and str(args[0]).startswith(("GET /api", "POST /api")):
            return
        super().log_message(fmt, *args)

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/catalog":
            payload = json.dumps(load_catalog(), ensure_ascii=False).encode("utf-8")
            self._send(200, payload, "application/json; charset=utf-8")
            return
        if path == "/api/health":
            self._send(200, b'{"ok":true}', "application/json")
            return
        if path == "/api/novels":
            payload = json.dumps(load_novels(), ensure_ascii=False).encode("utf-8")
            self._send(200, payload, "application/json; charset=utf-8")
            return
        self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/api/novel":
            self._send(404, b"not found", "text/plain")
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            selection = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send(400, b'{"error":"invalid json"}', "application/json")
            return
        if not isinstance(selection, dict):
            self._send(400, b'{"error":"expected object"}', "application/json")
            return

        catalog = load_catalog()
        hits = match_architectures(selection, catalog)
        if hits:
            body = json.dumps(
                {
                    "tag": None,
                    "reason": "catalog_match",
                    "matches": [h["slug"] for h in hits],
                },
                ensure_ascii=False,
            ).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
            return

        novel = resolve_novel(selection)
        if novel is None:
            self._send(
                400,
                json.dumps(
                    {
                        "error": "incomplete",
                        "message": "Set time, confinement, fuel, and kinetics before minting novel-N",
                    }
                ).encode(),
                "application/json",
            )
            return
        self._send(
            200,
            json.dumps(novel, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}\nRun: python scripts/build_catalog_db.py")
    n = len(load_catalog()["architectures"])
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print("p11b digital twin", flush=True)
    print(f"  {url}", flush=True)
    print(f"  {n} catalog architectures · novels → {NOVEL_PATH.name}", flush=True)
    print("  Ctrl+C to stop", flush=True)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)


if __name__ == "__main__":
    main()
