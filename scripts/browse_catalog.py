#!/usr/bin/env python3
"""Browse the p11b catalog as denormalized tables in a local web UI.

  python scripts/browse_catalog.py
"""

from __future__ import annotations

import json
import sqlite3
import webbrowser
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "p11b_catalog.sqlite"
HOST = "127.0.0.1"
PORT = 8765

VIEWS: list[dict[str, str]] = [
    {
        "id": "plant_odds",
        "title": "Plant odds",
        "blurb": "Ranked p–¹¹B electricity paths (POS★). The diligence horse race.",
    },
    {
        "id": "scorecard",
        "title": "Scorecard",
        "blurb": "Zeroth-order gates F–H as one wide row per architecture.",
    },
    {
        "id": "catalog",
        "title": "Catalog",
        "blurb": "Who / time / confinement / fuel / kinetics / status, with lead orgs.",
    },
    {
        "id": "prototypes",
        "title": "Prototypes",
        "blurb": "Machines, facilities, concepts, and digital twins.",
    },
    {
        "id": "references",
        "title": "References",
        "blurb": "Bibliography with authors collapsed into one field.",
    },
    {
        "id": "entities",
        "title": "People & orgs",
        "blurb": "Everyone named in the survey, with how they show up.",
    },
    {
        "id": "patents",
        "title": "Patents",
        "blurb": "Representative grants and applications from the legal sweep.",
    },
]


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]


@lru_cache(maxsize=1)
def load_bundle() -> dict:
    """Load all denormalized sheets once (DB is small and static)."""
    with connect() as conn:
        score_levels = rows_to_dicts(
            conn.execute(
                """
                SELECT code, symbol, numeric_value, label, description
                FROM score_level
                ORDER BY CASE code
                    WHEN 'full' THEN 1 WHEN 'partial' THEN 2
                    WHEN 'weak' THEN 3 ELSE 4 END
                """
            ).fetchall()
        )
        gates = rows_to_dicts(
            conn.execute(
                """
                SELECT code, name, question, used_in_pos
                FROM diligence_gate
                ORDER BY sort_order
                """
            ).fetchall()
        )
        pos_metric = conn.execute(
            """
            SELECT name, formula, description
            FROM scoring_metric WHERE code = 'POS'
            """
        ).fetchone()
        kappa_rows = rows_to_dicts(
            conn.execute(
                "SELECT kappa, when_used FROM kappa_factor ORDER BY kappa DESC"
            ).fetchall()
        )
        plant_odds = rows_to_dicts(
            conn.execute(
                """
                SELECT
                    po.rank AS rank,
                    a.name AS path,
                    pt.name AS type,
                    po.pos AS POS,
                    po.kappa AS kappa,
                    po.pos_star AS "POS★",
                    po.q_ge_1_window AS "Q≳1",
                    po.prototype_window AS prototype,
                    po.grid_product_window AS "grid / product",
                    CASE WHEN po.pos_approximate THEN 'approx' ELSE '' END AS note,
                    po.rationale AS rationale,
                    a.slug AS _slug
                FROM plant_odds po
                JOIN architecture a ON a.id = po.architecture_id
                LEFT JOIN path_type pt ON pt.id = a.path_type_id
                ORDER BY po.rank
                """
            ).fetchall()
        )

        scorecard = rows_to_dicts(
            conn.execute(
                """
                SELECT
                    a.name AS architecture,
                    MAX(CASE WHEN ags.gate_code = 'C' THEN ags.confinement_label END) AS C,
                    MAX(CASE WHEN ags.gate_code = 'F' THEN sl.symbol END) AS F,
                    MAX(CASE WHEN ags.gate_code = 'K' THEN sl.symbol END) AS K,
                    MAX(CASE WHEN ags.gate_code = 'R' THEN sl.symbol END) AS R,
                    MAX(CASE WHEN ags.gate_code = 'A' THEN sl.symbol END) AS A,
                    MAX(CASE WHEN ags.gate_code = 'L' THEN sl.symbol END) AS L,
                    MAX(CASE WHEN ags.gate_code = 'M' THEN sl.symbol END) AS M,
                    MAX(CASE WHEN ags.gate_code = 'T' THEN sl.symbol END) AS T,
                    MAX(CASE WHEN ags.gate_code = 'S' THEN sl.symbol END) AS S,
                    MAX(CASE WHEN ags.gate_code = 'H' THEN sl.symbol END) AS H,
                    COALESCE(
                        (SELECT GROUP_CONCAT(e.short_name, ', ')
                         FROM architecture_entity ae
                         JOIN entity e ON e.id = ae.entity_id
                         WHERE ae.architecture_id = a.id AND ae.role = 'lead'),
                        ''
                    ) AS lead,
                    a.slug AS _slug
                FROM architecture a
                JOIN architecture_gate_score ags ON ags.architecture_id = a.id
                LEFT JOIN score_level sl ON sl.code = ags.score_code
                WHERE a.in_scorecard = 1 OR a.in_plant_odds = 1
                GROUP BY a.id
                ORDER BY a.name
                """
            ).fetchall()
        )

        catalog = rows_to_dicts(
            conn.execute(
                """
                SELECT
                    a.name AS who,
                    tm.name AS time,
                    cf.name AS confinement,
                    fe.name AS fuel,
                    kr.name AS kinetics,
                    pt.name AS path_type,
                    a.catalog_status AS status,
                    COALESCE(
                        (SELECT GROUP_CONCAT(
                            CASE WHEN e.short_name IS NOT NULL AND e.short_name != ''
                                 THEN e.short_name ELSE e.canonical_name END
                            || ' (' || ae.role || ')', ', ')
                         FROM architecture_entity ae
                         JOIN entity e ON e.id = ae.entity_id
                         WHERE ae.architecture_id = a.id),
                        ''
                    ) AS entities,
                    a.source_section AS section,
                    a.slug AS _slug
                FROM architecture a
                LEFT JOIN time_mode tm ON tm.id = a.time_mode_id
                LEFT JOIN confinement_family cf ON cf.id = a.confinement_family_id
                LEFT JOIN fuel_end_state fe ON fe.id = a.fuel_end_state_id
                LEFT JOIN kinetics_regime kr ON kr.id = a.kinetics_regime_id
                LEFT JOIN path_type pt ON pt.id = a.path_type_id
                ORDER BY a.name
                """
            ).fetchall()
        )

        prototypes = rows_to_dicts(
            conn.execute(
                """
                SELECT
                    p.name AS prototype,
                    pk.name AS kind,
                    p.status AS status,
                    a.name AS architecture,
                    COALESCE(
                        (SELECT GROUP_CONCAT(
                            CASE WHEN e.short_name IS NOT NULL AND e.short_name != ''
                                 THEN e.short_name ELSE e.canonical_name END
                            || ' (' || pe.role || ')', ', ')
                         FROM prototype_entity pe
                         JOIN entity e ON e.id = pe.entity_id
                         WHERE pe.prototype_id = p.id),
                        ''
                    ) AS entities,
                    p.description AS description,
                    dt.license_openness AS openness,
                    dt.repo AS repo,
                    dt.claim AS twin_claim,
                    p.slug AS _slug,
                    a.slug AS _arch_slug
                FROM prototype p
                JOIN prototype_kind pk ON pk.id = p.kind_id
                LEFT JOIN architecture a ON a.id = p.architecture_id
                LEFT JOIN digital_twin_tool dt ON dt.prototype_id = p.id
                ORDER BY
                    CASE pk.name
                        WHEN 'machine' THEN 1
                        WHEN 'facility' THEN 2
                        WHEN 'lab_campaign' THEN 3
                        WHEN 'digital_twin' THEN 4
                        WHEN 'concept' THEN 5
                        ELSE 6
                    END,
                    p.name
                """
            ).fetchall()
        )

        references = rows_to_dicts(
            conn.execute(
                """
                SELECT
                    r.id AS "ref",
                    r.year AS year,
                    COALESCE(
                        (SELECT GROUP_CONCAT(e.canonical_name, '; ')
                         FROM reference_author ra
                         JOIN entity e ON e.id = ra.entity_id
                         WHERE ra.reference_id = r.id
                         ORDER BY ra.author_position),
                        ''
                    ) AS authors,
                    r.title AS title,
                    r.venue AS venue,
                    r.doi AS doi,
                    r.url AS url,
                    CASE WHEN r.is_patent THEN 'patent' ELSE '' END AS patent,
                    COALESCE(
                        (SELECT GROUP_CONCAT(a.name, '; ')
                         FROM architecture_reference ar
                         JOIN architecture a ON a.id = ar.architecture_id
                         WHERE ar.reference_id = r.id),
                        ''
                    ) AS cited_by_paths,
                    r.id AS _id
                FROM reference r
                ORDER BY r.id
                """
            ).fetchall()
        )

        entities = rows_to_dicts(
            conn.execute(
                """
                SELECT
                    e.canonical_name AS name,
                    ek.name AS kind,
                    e.short_name AS short,
                    e.country AS country,
                    e.website AS website,
                    (SELECT COUNT(*) FROM reference_author ra WHERE ra.entity_id = e.id) AS as_author,
                    (SELECT COUNT(*) FROM architecture_entity ae WHERE ae.entity_id = e.id) AS arch_links,
                    (SELECT COUNT(*) FROM prototype_entity pe WHERE pe.entity_id = e.id) AS proto_links,
                    (SELECT COUNT(*) FROM mention m WHERE m.entity_id = e.id) AS mentions,
                    COALESCE(
                        (SELECT GROUP_CONCAT(x.item, ', ')
                         FROM (
                           SELECT DISTINCT ae.role || ':' || a.slug AS item
                           FROM architecture_entity ae
                           JOIN architecture a ON a.id = ae.architecture_id
                           WHERE ae.entity_id = e.id
                         ) AS x),
                        ''
                    ) AS architecture_roles,
                    e.id AS _id
                FROM entity e
                JOIN entity_kind ek ON ek.id = e.kind_id
                ORDER BY
                    CASE ek.name WHEN 'person' THEN 1 ELSE 0 END,
                    e.canonical_name
                """
            ).fetchall()
        )

        patents = rows_to_dicts(
            conn.execute(
                """
                SELECT
                    p.number AS number,
                    p.title_short AS title,
                    COALESCE(e.short_name, e.canonical_name, '') AS entity,
                    p.assignee_notes AS notes,
                    p.reference_id AS "ref",
                    COALESCE(
                        (SELECT GROUP_CONCAT(
                            pce.direction || ': ' || pce.related_description, ' | ')
                         FROM patent_citation_edge pce
                         WHERE pce.seed_patent_id = p.id),
                        ''
                    ) AS citation_graph,
                    p.id AS _id
                FROM patent p
                LEFT JOIN entity e ON e.id = p.entity_id
                ORDER BY p.number
                """
            ).fetchall()
        )

    return {
        "sheets": {
            "plant_odds": plant_odds,
            "scorecard": scorecard,
            "catalog": catalog,
            "prototypes": prototypes,
            "references": references,
            "entities": entities,
            "patents": patents,
        },
        "legend": {
            "scores": score_levels,
            "gates": gates,
            "pos": dict(pos_metric) if pos_metric else None,
            "kappa": kappa_rows,
        },
    }


DETAIL_QUERIES = {
    "architecture": """
        SELECT json_object(
            'slug', a.slug,
            'name', a.name,
            'path_type', pt.name,
            'time', tm.name,
            'confinement', cf.name,
            'fuel', fe.name,
            'kinetics', kr.name,
            'status', a.catalog_status,
            'section', a.source_section,
            'notes', a.notes,
            'entities', (
                SELECT json_group_array(json_object(
                    'name', e.canonical_name,
                    'short', e.short_name,
                    'role', ae.role
                ))
                FROM architecture_entity ae
                JOIN entity e ON e.id = ae.entity_id
                WHERE ae.architecture_id = a.id
            ),
            'prototypes', (
                SELECT json_group_array(json_object(
                    'name', p.name,
                    'kind', pk.name,
                    'status', p.status
                ))
                FROM prototype p
                JOIN prototype_kind pk ON pk.id = p.kind_id
                WHERE p.architecture_id = a.id
            ),
            'gate_scores', (
                SELECT json_group_array(json_object(
                    'gate', ags.gate_code,
                    'score', sl.symbol,
                    'confinement', ags.confinement_label
                ))
                FROM architecture_gate_score ags
                LEFT JOIN score_level sl ON sl.code = ags.score_code
                WHERE ags.architecture_id = a.id
            ),
            'plant_odds', (
                SELECT json_object(
                    'rank', po.rank,
                    'pos', po.pos,
                    'kappa', po.kappa,
                    'pos_star', po.pos_star,
                    'rationale', po.rationale
                )
                FROM plant_odds po WHERE po.architecture_id = a.id
            ),
            'references', (
                SELECT json_group_array(ar.reference_id)
                FROM architecture_reference ar
                WHERE ar.architecture_id = a.id
            )
        )
        FROM architecture a
        LEFT JOIN path_type pt ON pt.id = a.path_type_id
        LEFT JOIN time_mode tm ON tm.id = a.time_mode_id
        LEFT JOIN confinement_family cf ON cf.id = a.confinement_family_id
        LEFT JOIN fuel_end_state fe ON fe.id = a.fuel_end_state_id
        LEFT JOIN kinetics_regime kr ON kr.id = a.kinetics_regime_id
        WHERE a.slug = ?
    """,
    "prototype": """
        SELECT json_object(
            'slug', p.slug,
            'name', p.name,
            'kind', pk.name,
            'status', p.status,
            'description', p.description,
            'architecture', a.name,
            'architecture_slug', a.slug,
            'entities', (
                SELECT json_group_array(json_object(
                    'name', e.canonical_name,
                    'role', pe.role
                ))
                FROM prototype_entity pe
                JOIN entity e ON e.id = pe.entity_id
                WHERE pe.prototype_id = p.id
            ),
            'digital_twin', (
                SELECT json_object(
                    'claim', dt.claim,
                    'openness', dt.license_openness,
                    'access', dt.access_how,
                    'repo', dt.repo
                )
                FROM digital_twin_tool dt WHERE dt.prototype_id = p.id
            )
        )
        FROM prototype p
        JOIN prototype_kind pk ON pk.id = p.kind_id
        LEFT JOIN architecture a ON a.id = p.architecture_id
        WHERE p.slug = ?
    """,
    "reference": """
        SELECT json_object(
            'id', r.id,
            'year', r.year,
            'title', r.title,
            'venue', r.venue,
            'doi', r.doi,
            'url', r.url,
            'is_patent', r.is_patent,
            'raw', r.raw_text,
            'authors', (
                SELECT json_group_array(json_object(
                    'name', e.canonical_name,
                    'kind', ek.name,
                    'position', ra.author_position
                ))
                FROM reference_author ra
                JOIN entity e ON e.id = ra.entity_id
                JOIN entity_kind ek ON ek.id = e.kind_id
                WHERE ra.reference_id = r.id
                ORDER BY ra.author_position
            ),
            'architectures', (
                SELECT json_group_array(a.name)
                FROM architecture_reference ar
                JOIN architecture a ON a.id = ar.architecture_id
                WHERE ar.reference_id = r.id
            )
        )
        FROM reference r
        WHERE r.id = ?
    """,
    "entity": """
        SELECT json_object(
            'id', e.id,
            'name', e.canonical_name,
            'kind', ek.name,
            'short', e.short_name,
            'country', e.country,
            'website', e.website,
            'notes', e.notes,
            'aliases', (
                SELECT json_group_array(ea.alias)
                FROM entity_alias ea WHERE ea.entity_id = e.id
            ),
            'architectures', (
                SELECT json_group_array(json_object(
                    'name', a.name,
                    'role', ae.role
                ))
                FROM architecture_entity ae
                JOIN architecture a ON a.id = ae.architecture_id
                WHERE ae.entity_id = e.id
            ),
            'prototypes', (
                SELECT json_group_array(json_object(
                    'name', p.name,
                    'role', pe.role
                ))
                FROM prototype_entity pe
                JOIN prototype p ON p.id = pe.prototype_id
                WHERE pe.entity_id = e.id
            ),
            'authored_refs', (
                SELECT json_group_array(ra.reference_id)
                FROM reference_author ra WHERE ra.entity_id = e.id
            ),
            'mentions', (
                SELECT json_group_array(m.context)
                FROM mention m WHERE m.entity_id = e.id
            )
        )
        FROM entity e
        JOIN entity_kind ek ON ek.id = e.kind_id
        WHERE e.id = ?
    """,
}


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>p11b catalog</title>
<style>
  :root {
    --bg: #f3efe6;
    --panel: #fffdf8;
    --ink: #1c1a16;
    --muted: #6a645a;
    --line: #d9d0c0;
    --accent: #0f5c4c;
    --accent-soft: #d9ebe5;
    --row-hover: #f0e9db;
    --selected: #e4f2ed;
    --shadow: 0 1px 0 rgba(28,26,22,.06);
    font-family: "IBM Plex Sans", "Source Sans 3", "Segoe UI", sans-serif;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    color: var(--ink);
    background:
      radial-gradient(1200px 500px at 10% -10%, #e7f2ee 0%, transparent 55%),
      radial-gradient(900px 400px at 100% 0%, #f7e9d8 0%, transparent 50%),
      var(--bg);
    min-height: 100vh;
  }
  header {
    display: flex;
    align-items: baseline;
    gap: 1rem;
    padding: 1.1rem 1.4rem .7rem;
    border-bottom: 1px solid var(--line);
    background: color-mix(in srgb, var(--panel) 88%, transparent);
    backdrop-filter: blur(6px);
    position: sticky;
    top: 0;
    z-index: 5;
  }
  header h1 {
    font-family: "IBM Plex Serif", "Source Serif 4", Georgia, serif;
    font-size: 1.35rem;
    font-weight: 600;
    margin: 0;
    letter-spacing: -.01em;
  }
  header p { margin: 0; color: var(--muted); font-size: .92rem; }
  .layout {
    display: grid;
    grid-template-columns: 220px 1fr 320px;
    gap: 0;
    min-height: calc(100vh - 64px);
  }
  nav {
    padding: 1rem .75rem 1.5rem;
    border-right: 1px solid var(--line);
    background: color-mix(in srgb, var(--panel) 70%, transparent);
  }
  nav button {
    display: block;
    width: 100%;
    text-align: left;
    border: 0;
    background: transparent;
    color: var(--ink);
    padding: .55rem .7rem;
    border-radius: 8px;
    cursor: pointer;
    font: inherit;
    margin-bottom: .2rem;
  }
  nav button:hover { background: var(--row-hover); }
  nav button.active {
    background: var(--accent-soft);
    color: var(--accent);
    font-weight: 600;
  }
  nav .blurb {
    margin: .35rem .7rem 1rem;
    color: var(--muted);
    font-size: .8rem;
    line-height: 1.35;
    min-height: 2.7em;
  }
  main { padding: 1rem 1.1rem 2rem; min-width: 0; }
  .toolbar {
    display: flex;
    gap: .75rem;
    align-items: center;
    margin-bottom: .75rem;
  }
  .toolbar input {
    flex: 1;
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: .55rem .75rem;
    font: inherit;
    background: var(--panel);
    color: var(--ink);
  }
  .toolbar input:focus {
    outline: 2px solid color-mix(in srgb, var(--accent) 45%, white);
    border-color: var(--accent);
  }
  .count { color: var(--muted); font-size: .85rem; white-space: nowrap; }
  .toolbar button.legend-btn {
    border: 1px solid var(--line);
    background: var(--panel);
    border-radius: 8px;
    padding: .45rem .7rem;
    font: inherit;
    font-size: .85rem;
    cursor: pointer;
    color: var(--accent);
    white-space: nowrap;
  }
  .toolbar button.legend-btn:hover { background: var(--accent-soft); }
  .legend-banner {
    display: none;
    border: 1px solid var(--line);
    border-radius: 12px;
    background: var(--panel);
    padding: .75rem 1rem;
    margin-bottom: .75rem;
    font-size: .82rem;
    line-height: 1.4;
  }
  .legend-banner.open { display: block; }
  .legend-banner h3 {
    margin: 0 0 .45rem;
    font-size: .78rem;
    text-transform: uppercase;
    letter-spacing: .04em;
    color: var(--muted);
  }
  .legend-banner .scores {
    display: flex;
    flex-wrap: wrap;
    gap: .5rem 1rem;
    margin-bottom: .65rem;
  }
  .legend-banner .scores span { white-space: nowrap; }
  .legend-banner .scores b { font-size: 1.05rem; margin-right: .25rem; }
  .legend-banner .gates {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: .35rem .75rem;
  }
  .legend-banner .gate code {
    font-weight: 600;
    color: var(--accent);
    margin-right: .25rem;
  }
  .legend-banner .pos {
    margin-top: .65rem;
    padding-top: .55rem;
    border-top: 1px solid var(--line);
    color: var(--muted);
  }
  .table-wrap {
    border: 1px solid var(--line);
    border-radius: 12px;
    background: var(--panel);
    box-shadow: var(--shadow);
    overflow: auto;
    max-height: calc(100vh - 150px);
  }
  table {
    border-collapse: collapse;
    width: 100%;
    font-size: .86rem;
  }
  th, td {
    padding: .45rem .6rem;
    border-bottom: 1px solid var(--line);
    vertical-align: top;
    text-align: left;
  }
  th {
    position: sticky;
    top: 0;
    background: #faf6ee;
    color: var(--muted);
    font-weight: 600;
    font-size: .75rem;
    text-transform: uppercase;
    letter-spacing: .04em;
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
  }
  th:hover { color: var(--ink); }
  tr { cursor: pointer; }
  tr:hover td { background: var(--row-hover); }
  tr.selected td { background: var(--selected); }
  td {
    max-width: 28rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  td.wrap {
    white-space: normal;
    max-width: 36rem;
    line-height: 1.35;
  }
  aside {
    border-left: 1px solid var(--line);
    background: var(--panel);
    padding: 1rem 1rem 2rem;
    overflow: auto;
    max-height: calc(100vh - 64px);
  }
  aside h2 {
    font-family: "IBM Plex Serif", Georgia, serif;
    font-size: 1.05rem;
    margin: 0 0 .5rem;
  }
  aside .empty {
    color: var(--muted);
    font-size: .9rem;
    line-height: 1.4;
    margin-top: 2rem;
  }
  aside .kv { margin: 0 0 .85rem; }
  aside .kv dt {
    color: var(--muted);
    font-size: .72rem;
    text-transform: uppercase;
    letter-spacing: .04em;
    margin-bottom: .15rem;
  }
  aside .kv dd {
    margin: 0;
    font-size: .9rem;
    line-height: 1.4;
    word-break: break-word;
  }
  aside a { color: var(--accent); }
  aside ul { margin: .2rem 0 0; padding-left: 1.1rem; }
  aside li { margin: .15rem 0; font-size: .9rem; }
  .chip {
    display: inline-block;
    background: var(--accent-soft);
    color: var(--accent);
    border-radius: 999px;
    padding: .1rem .45rem;
    font-size: .75rem;
    margin: .1rem .2rem .1rem 0;
  }
  @media (max-width: 1100px) {
    .layout { grid-template-columns: 180px 1fr; }
    aside { display: none; }
    aside.open {
      display: block;
      position: fixed;
      right: 0; top: 64px; bottom: 0;
      width: min(360px, 92vw);
      z-index: 10;
      box-shadow: -8px 0 24px rgba(0,0,0,.12);
    }
  }
</style>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Serif:wght@600&display=swap" rel="stylesheet" />
</head>
<body>
<header>
  <h1>p11b catalog</h1>
  <p>Denormalized browse of the survey database — click a row for detail.</p>
</header>
<div class="layout">
  <nav id="nav"></nav>
  <main>
    <div class="toolbar">
      <input id="q" type="search" placeholder="Filter this sheet…" autocomplete="off" />
      <button type="button" class="legend-btn" id="legendBtn" title="Gate & score legend">Legend</button>
      <span class="count" id="count"></span>
    </div>
    <div class="legend-banner" id="legendBanner"></div>
    <div class="table-wrap">
      <table>
        <thead id="thead"></thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
  </main>
  <aside id="detail">
    <p class="empty">Select a row to see related fields and links.</p>
  </aside>
</div>
<script>
const VIEWS = __VIEWS__;
let sheets = null;
let legend = null;
let viewId = "plant_odds";
let sortKey = null;
let sortDir = 1;
let selectedIdx = -1;
let legendOpen = false;

const nav = document.getElementById("nav");
const thead = document.getElementById("thead");
const tbody = document.getElementById("tbody");
const q = document.getElementById("q");
const count = document.getElementById("count");
const detail = document.getElementById("detail");
const legendBtn = document.getElementById("legendBtn");
const legendBanner = document.getElementById("legendBanner");

function visibleCols(rows) {
  if (!rows.length) return [];
  return Object.keys(rows[0]).filter(k => !k.startsWith("_"));
}

function renderLegendBanner() {
  if (!legend) return;
  const scores = (legend.scores || []).map(s => {
    const pts = s.numeric_value == null ? "n/a for POS" : `= ${s.numeric_value} for POS`;
    return `<span><b>${escapeHtml(s.symbol)}</b> ${escapeHtml(s.label)} <span style="color:var(--muted)">(${pts})</span></span>`;
  }).join("");
  const gates = (legend.gates || []).map(g =>
    `<div class="gate"><code>${escapeHtml(g.code)}</code><strong>${escapeHtml(g.name)}</strong><div style="color:var(--muted);font-size:.78rem">${escapeHtml(g.question)}</div></div>`
  ).join("");
  let pos = "";
  if (legend.pos) {
    const kappa = (legend.kappa || []).map(k =>
      `<div><code>κ=${k.kappa}</code> — ${escapeHtml(k.when_used)}</div>`
    ).join("");
    pos = `<div class="pos"><strong>${escapeHtml(legend.pos.name)}</strong>: ${escapeHtml(legend.pos.formula)}<br/>${escapeHtml(legend.pos.description || "")}<div style="margin-top:.4rem">${kappa}</div></div>`;
  }
  legendBanner.innerHTML = `
    <h3>Score symbols</h3>
    <div class="scores">${scores}</div>
    <h3>Diligence gates</h3>
    <div class="gates">${gates}</div>
    ${pos}
  `;
  legendBanner.classList.toggle("open", legendOpen);
  const scoringViews = viewId === "scorecard" || viewId === "plant_odds";
  legendBtn.style.display = scoringViews ? "" : "none";
  if (!scoringViews) {
    legendBanner.classList.remove("open");
  }
}

function showLegendInDetail() {
  if (!legend) return;
  const scores = (legend.scores || []).map(s =>
    `<li><strong>${escapeHtml(s.symbol)}</strong> ${escapeHtml(s.label)} — ${escapeHtml(s.description || "")}</li>`
  ).join("");
  const gates = (legend.gates || []).map(g =>
    `<li><span class="chip">${escapeHtml(g.code)}</span> <strong>${escapeHtml(g.name)}</strong><br/><span style="color:var(--muted)">${escapeHtml(g.question)}</span></li>`
  ).join("");
  detail.innerHTML = `
    <h2>Gates legend</h2>
    <p class="empty" style="margin:0 0 .75rem">From the survey diligence checklist (Xie frame).</p>
    <div class="kv"><dt>Symbols</dt><dd><ul>${scores}</ul></dd></div>
    <div class="kv"><dt>Gates</dt><dd><ul>${gates}</ul></dd></div>
    ${legend.pos ? kv("POS", legend.pos.formula) : ""}
  `;
  detail.classList.add("open");
}

function renderNav() {
  nav.innerHTML = "";
  for (const v of VIEWS) {
    const b = document.createElement("button");
    b.textContent = v.title;
    b.className = v.id === viewId ? "active" : "";
    b.onclick = () => {
      viewId = v.id;
      sortKey = null;
      selectedIdx = -1;
      q.value = "";
      if (viewId === "scorecard" || viewId === "plant_odds") legendOpen = true;
      renderNav();
      renderTable();
      renderLegendBanner();
      if (viewId === "scorecard" || viewId === "plant_odds") showLegendInDetail();
      else detail.innerHTML = `<p class="empty">${v.blurb}</p>`;
    };
    nav.appendChild(b);
  }
  const blurb = document.createElement("div");
  blurb.className = "blurb";
  blurb.textContent = VIEWS.find(v => v.id === viewId).blurb;
  nav.appendChild(blurb);
}

function filteredRows() {
  let rows = sheets[viewId] || [];
  const needle = q.value.trim().toLowerCase();
  if (needle) {
    rows = rows.filter(r =>
      Object.entries(r)
        .filter(([k]) => !k.startsWith("_"))
        .some(([, v]) => String(v ?? "").toLowerCase().includes(needle))
    );
  }
  if (sortKey) {
    rows = [...rows].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * sortDir;
      return String(av).localeCompare(String(bv), undefined, {numeric: true}) * sortDir;
    });
  }
  return rows;
}

function renderTable() {
  const rows = filteredRows();
  const cols = visibleCols(sheets[viewId] || []);
  thead.innerHTML = "<tr>" + cols.map(c =>
    `<th data-k="${c}">${c}${sortKey === c ? (sortDir > 0 ? " ↑" : " ↓") : ""}</th>`
  ).join("") + "</tr>";
  for (const th of thead.querySelectorAll("th")) {
    th.onclick = () => {
      const k = th.dataset.k;
      if (sortKey === k) sortDir *= -1;
      else { sortKey = k; sortDir = 1; }
      renderTable();
    };
  }
  const wrapCols = new Set(["rationale", "status", "description", "twin_claim", "notes", "citation_graph", "authors", "title", "entities", "architecture_roles"]);
  tbody.innerHTML = rows.map((r, i) => {
    const tds = cols.map(c => {
      const cls = wrapCols.has(c) ? ' class="wrap"' : "";
      const val = r[c] == null ? "" : String(r[c]);
      return `<td${cls} title="${val.replaceAll('"', '&quot;')}">${escapeHtml(val)}</td>`;
    }).join("");
    return `<tr data-i="${i}" class="${i === selectedIdx ? "selected" : ""}">${tds}</tr>`;
  }).join("");
  for (const tr of tbody.querySelectorAll("tr")) {
    tr.onclick = () => {
      selectedIdx = Number(tr.dataset.i);
      renderTable();
      showDetail(rows[selectedIdx]);
    };
  }
  count.textContent = `${rows.length} row${rows.length === 1 ? "" : "s"}`;
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, ch => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  })[ch]);
}

async function showDetail(row) {
  detail.classList.add("open");
  detail.innerHTML = "<p class='empty'>Loading…</p>";
  let kind = null, key = null;
  if (viewId === "plant_odds" || viewId === "scorecard" || viewId === "catalog") {
    kind = "architecture"; key = row._slug;
  } else if (viewId === "prototypes") {
    kind = "prototype"; key = row._slug;
  } else if (viewId === "references") {
    kind = "reference"; key = row._id;
  } else if (viewId === "entities") {
    kind = "entity"; key = row._id;
  } else if (viewId === "patents") {
    detail.innerHTML = renderPatentDetail(row);
    return;
  }
  if (kind == null) {
    detail.innerHTML = renderGeneric(row);
    return;
  }
  try {
    const res = await fetch(`/api/detail?kind=${kind}&key=${encodeURIComponent(key)}`);
    const data = await res.json();
    detail.innerHTML = renderRichDetail(kind, data);
  } catch (e) {
    detail.innerHTML = `<p class="empty">Could not load detail.</p>${renderGeneric(row)}`;
  }
}

function renderPatentDetail(row) {
  return `
    <h2>${escapeHtml(row.number || "Patent")}</h2>
    ${kv("Title", row.title)}
    ${kv("Entity", row.entity)}
    ${kv("Notes", row.notes)}
    ${kv("Survey ref", row.ref != null ? "[" + row.ref + "]" : "")}
    ${kv("Citation graph", row.citation_graph)}
  `;
}

function renderGeneric(row) {
  const parts = Object.entries(row)
    .filter(([k]) => !k.startsWith("_"))
    .map(([k, v]) => kv(k, v));
  return `<h2>Row</h2>${parts.join("")}`;
}

function kv(label, value) {
  if (value == null || value === "") return "";
  return `<div class="kv"><dt>${escapeHtml(label)}</dt><dd>${linkify(String(value))}</dd></div>`;
}

function linkify(s) {
  const esc = escapeHtml(s);
  return esc
    .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>')
    .replace(/\b(10\.\d{4,9}\/[-._;()/:A-Za-z0-9]+)/g, '<a href="https://doi.org/$1" target="_blank" rel="noopener">$1</a>');
}

function renderRichDetail(kind, data) {
  if (!data) return `<p class="empty">No detail.</p>`;
  if (kind === "architecture") {
    const gates = (data.gate_scores || []).map(g =>
      `<span class="chip">${g.gate}: ${g.score || g.confinement || "—"}</span>`
    ).join(" ");
    const ents = (data.entities || []).map(e =>
      `<li>${escapeHtml(e.short || e.name)} <span class="chip">${escapeHtml(e.role)}</span></li>`
    ).join("");
    const protos = (data.prototypes || []).map(p =>
      `<li>${escapeHtml(p.name)} <span class="chip">${escapeHtml(p.kind)}</span> ${escapeHtml(p.status || "")}</li>`
    ).join("");
    const po = data.plant_odds;
    return `
      <h2>${escapeHtml(data.name)}</h2>
      ${kv("Path type", data.path_type)}
      ${kv("Time", data.time)}
      ${kv("Confinement", data.confinement)}
      ${kv("Fuel", data.fuel)}
      ${kv("Kinetics", data.kinetics)}
      ${kv("Status", data.status)}
      ${kv("Section", data.section)}
      ${po ? kv("Plant odds", `#${po.rank} · POS ${po.pos} · κ ${po.kappa} · POS★ ${po.pos_star}`) : ""}
      ${po ? kv("Rationale", po.rationale) : ""}
      <div class="kv"><dt>Gates</dt><dd>${gates || "—"}</dd></div>
      <div class="kv"><dt>Entities</dt><dd><ul>${ents || "<li>—</li>"}</ul></dd></div>
      <div class="kv"><dt>Prototypes</dt><dd><ul>${protos || "<li>—</li>"}</ul></dd></div>
      ${kv("References", (data.references || []).map(n => "[" + n + "]").join(" "))}
    `;
  }
  if (kind === "prototype") {
    const ents = (data.entities || []).map(e =>
      `<li>${escapeHtml(e.name)} <span class="chip">${escapeHtml(e.role)}</span></li>`
    ).join("");
    const dt = data.digital_twin;
    return `
      <h2>${escapeHtml(data.name)}</h2>
      ${kv("Kind", data.kind)}
      ${kv("Status", data.status)}
      ${kv("Architecture", data.architecture)}
      ${kv("Description", data.description)}
      <div class="kv"><dt>Entities</dt><dd><ul>${ents || "<li>—</li>"}</ul></dd></div>
      ${dt ? kv("Twin claim", dt.claim) : ""}
      ${dt ? kv("Openness", dt.openness) : ""}
      ${dt ? kv("Repo", dt.repo) : ""}
      ${dt ? kv("Access", dt.access) : ""}
    `;
  }
  if (kind === "reference") {
    const authors = (data.authors || []).map(a =>
      `<li>${escapeHtml(a.name)} <span class="chip">${escapeHtml(a.kind)}</span></li>`
    ).join("");
    return `
      <h2>[${data.id}] ${escapeHtml(data.title || "Reference")}</h2>
      ${kv("Year", data.year)}
      ${kv("Venue", data.venue)}
      ${kv("DOI", data.doi)}
      ${kv("URL", data.url)}
      <div class="kv"><dt>Authors</dt><dd><ul>${authors || "<li>—</li>"}</ul></dd></div>
      ${kv("Cited by paths", (data.architectures || []).join("; "))}
      ${kv("Raw", data.raw)}
    `;
  }
  if (kind === "entity") {
    const arch = (data.architectures || []).map(a =>
      `<li>${escapeHtml(a.name)} <span class="chip">${escapeHtml(a.role)}</span></li>`
    ).join("");
    const protos = (data.prototypes || []).map(p =>
      `<li>${escapeHtml(p.name)} <span class="chip">${escapeHtml(p.role)}</span></li>`
    ).join("");
    return `
      <h2>${escapeHtml(data.name)}</h2>
      ${kv("Kind", data.kind)}
      ${kv("Short name", data.short)}
      ${kv("Country", data.country)}
      ${kv("Website", data.website)}
      ${kv("Notes", data.notes)}
      ${kv("Aliases", (data.aliases || []).join(", "))}
      <div class="kv"><dt>Architectures</dt><dd><ul>${arch || "<li>—</li>"}</ul></dd></div>
      <div class="kv"><dt>Prototypes</dt><dd><ul>${protos || "<li>—</li>"}</ul></dd></div>
      ${kv("Authored refs", (data.authored_refs || []).map(n => "[" + n + "]").join(" "))}
      ${kv("Mentions", (data.mentions || []).join(" · "))}
    `;
  }
  return renderGeneric(data);
}

async function boot() {
  renderNav();
  const res = await fetch("/api/bundle");
  const data = await res.json();
  sheets = data.sheets;
  legend = data.legend;
  legendOpen = true;
  renderLegendBanner();
  showLegendInDetail();
  renderTable();
  q.addEventListener("input", () => { selectedIdx = -1; renderTable(); });
  legendBtn.addEventListener("click", () => {
    legendOpen = !legendBanner.classList.contains("open");
    renderLegendBanner();
    showLegendInDetail();
  });
}
boot();
</script>
</body>
</html>
""".replace("__VIEWS__", json.dumps(VIEWS))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # quieter
        if args and str(args[0]).startswith("GET /api"):
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
        parsed = urlparse(self.path)
        path = parsed.path

        if path in {"/", "/index.html"}:
            self._send(200, HTML_PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return

        if path == "/api/bundle":
            payload = json.dumps(load_bundle(), ensure_ascii=False).encode("utf-8")
            self._send(200, payload, "application/json; charset=utf-8")
            return

        if path == "/api/detail":
            qs = parse_qs(parsed.query)
            kind = (qs.get("kind") or [""])[0]
            key = (qs.get("key") or [""])[0]
            sql = DETAIL_QUERIES.get(kind)
            if not sql or not key:
                self._send(400, b'{"error":"bad request"}', "application/json")
                return
            with connect() as conn:
                param: str | int = int(key) if kind in {"reference", "entity"} else key
                row = conn.execute(sql, (param,)).fetchone()
            if not row or row[0] is None:
                self._send(404, b"null", "application/json")
                return
            # sqlite json_object returns text
            raw = row[0] if isinstance(row[0], str) else json.dumps(dict(row))
            self._send(200, raw.encode("utf-8"), "application/json; charset=utf-8")
            return

        if path == "/api/health":
            self._send(200, b'{"ok":true}', "application/json")
            return

        self._send(404, b"not found", "text/plain")


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}\nRun: python scripts/build_catalog_db.py")
    # Warm cache / fail fast
    bundle = load_bundle()
    n = sum(len(v) for v in bundle["sheets"].values())
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"p11b catalog browser", flush=True)
    print(f"  {url}", flush=True)
    print(f"  {n} denormalized rows from {DB_PATH.name}", flush=True)
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
