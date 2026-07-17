#!/usr/bin/env python3
"""Build a normalized SQLite catalog from pb11.md survey tables and references."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "data" / "schema.sql"
SOURCE = ROOT / "pb11.md"
DB_PATH = ROOT / "data" / "p11b_catalog.sqlite"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def connect(db_path: Path) -> sqlite3.Connection:
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return conn


def eid(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM entity WHERE canonical_name = ?", (name,)).fetchone()
    if not row:
        raise KeyError(f"Unknown entity: {name}")
    return row[0]


def aid(conn: sqlite3.Connection, slug: str) -> int:
    row = conn.execute("SELECT id FROM architecture WHERE slug = ?", (slug,)).fetchone()
    if not row:
        raise KeyError(f"Unknown architecture: {slug}")
    return row[0]


def pid(conn: sqlite3.Connection, slug: str) -> int:
    row = conn.execute("SELECT id FROM prototype WHERE slug = ?", (slug,)).fetchone()
    if not row:
        raise KeyError(f"Unknown prototype: {slug}")
    return row[0]


def kind_id(conn: sqlite3.Connection, table: str, name: str) -> int:
    row = conn.execute(f"SELECT id FROM {table} WHERE name = ?", (name,)).fetchone()
    if not row:
        raise KeyError(f"Unknown {table}: {name}")
    return row[0]


def ensure_entity(
    conn: sqlite3.Connection,
    name: str,
    kind: str,
    *,
    short_name: str | None = None,
    country: str | None = None,
    website: str | None = None,
    notes: str | None = None,
    aliases: list[str] | None = None,
) -> int:
    existing = conn.execute(
        "SELECT id FROM entity WHERE canonical_name = ?", (name,)
    ).fetchone()
    if existing:
        ent_id = existing[0]
    else:
        kid = kind_id(conn, "entity_kind", kind)
        cur = conn.execute(
            """
            INSERT INTO entity (canonical_name, kind_id, short_name, country, website, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, kid, short_name, country, website, notes),
        )
        ent_id = cur.lastrowid
    for alias in aliases or []:
        conn.execute(
            "INSERT OR IGNORE INTO entity_alias (entity_id, alias) VALUES (?, ?)",
            (ent_id, alias),
        )
    return ent_id


def resolve_entity(conn: sqlite3.Connection, raw: str) -> int | None:
    name = normalize_person_or_org(raw)
    if not name:
        return None
    row = conn.execute(
        "SELECT id FROM entity WHERE canonical_name = ?", (name,)
    ).fetchone()
    if row:
        return row[0]
    row = conn.execute("SELECT entity_id FROM entity_alias WHERE alias = ?", (name,)).fetchone()
    if row:
        return row[0]
    # Soft match on short_name / stripped punctuation
    row = conn.execute(
        "SELECT id FROM entity WHERE short_name = ? OR canonical_name = ?",
        (name, name.rstrip(".")),
    ).fetchone()
    if row:
        return row[0]
    return None


ORG_TOKENS = re.compile(
    r"\b(Inc|LLC|GmbH|Ltd|Corp|Corporation|University|Institute|Laboratory|"
    r"Laboratories|Technologies|Energy|Fusion|Systems|Foundation|Academy|"
    r"National|Team|contributors|Group|Digital|NVIDIA|OpenMC|UKAEA|ORNL|"
    r"INFN|ELI|NIFS|DOE|NASA|PPPL|CAEP|IAPCM|RAS|COST)\b",
    re.I,
)


def looks_like_org(name: str) -> bool:
    if name.endswith(("GmbH", "Inc.", "Inc", "Ltd.", "Corp.", "Foundation", "University")):
        return True
    if ORG_TOKENS.search(name):
        return True
    if "," not in name and len(name.split()) <= 4 and name[:1].isupper():
        # Company-style single token or Title Case without surname comma
        if re.match(r"^[A-Z][A-Za-z0-9&.\- ]+$", name) and not re.search(
            r"\b[A-Z]\.\s*[A-Z]\.?\b", name
        ):
            # Prefer org if no initial pattern like "T. H."
            if not re.search(r"\b[A-Z]\.", name):
                return True
    return False


def normalize_person_or_org(raw: str) -> str:
    s = raw.strip().rstrip(".").strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("’", "'")
    if s.lower() in {"et al", "et al."}:
        return ""
    return s


_INITIALS = re.compile(
    r"""^
    [A-Z]
    (?:
        \.-[A-Z]          # Y.-K
      | \.[A-Z]           # .H
      | -[A-Z]            # -K (rare)
    )*
    \.?                   # optional trailing period
    (?:
        \s+[A-Z](?:\.-[A-Z]|\.[A-Z]|-[A-Z])*\.?
    )*                    # optional extra initial groups in same token
    $""",
    re.X,
)


def _is_initials(tok: str) -> bool:
    compact = tok.strip()
    if not compact:
        return False
    # Single letter or dotted initials / hyphenated initials
    if _INITIALS.fullmatch(compact.replace(" ", "")):
        return True
    if re.fullmatch(r"[A-Z](?:\.[A-Z]\.?|\.-[A-Z]\.?)+", compact):
        return True
    if re.fullmatch(r"[A-Z]\.(?:\s*[A-Z]\.)+", compact):
        return True
    return False


def split_author_block(block: str) -> tuple[list[str], bool]:
    """Split a bold author block into names; return (names, has_etal)."""
    text = block.strip()
    has_etal = bool(re.search(r"\bet al\.?\b", text, re.I))
    text = re.sub(r",?\s*et al\.?", "", text, flags=re.I).strip().rstrip(",").strip()
    parts: list[str] = []
    text = re.sub(r"\s+&\s+", " ||| ", text)
    text = re.sub(r"\s+and\s+", " ||| ", text)
    for chunk in [c.strip() for c in text.split("|||")]:
        tokens = [t.strip() for t in chunk.split(",") if t.strip()]
        buffer: list[str] = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if buffer and _is_initials(tok):
                # Absorb consecutive initial tokens (e.g. Y.-K. + M.)
                buffer.append(tok)
                j = i + 1
                while j < len(tokens) and _is_initials(tokens[j]):
                    buffer.append(tokens[j])
                    j += 1
                parts.append(", ".join(buffer))
                buffer = []
                i = j
                continue
            if buffer:
                parts.append(", ".join(buffer))
            buffer = [tok]
            i += 1
        if buffer:
            parts.append(", ".join(buffer))
    names = [n for n in (normalize_person_or_org(p) for p in parts) if n]
    if not names and text:
        names = [n for n in [normalize_person_or_org(text)] if n]
    return names, has_etal


def parse_references(md: str) -> list[dict]:
    m = re.search(r"^## References \{#sec:references\}\s*\n(.*)\Z", md, re.M | re.S)
    if not m:
        raise RuntimeError("Could not find References section")
    body = m.group(1).strip()
    entries: list[dict] = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        rm = re.match(r"^(\d+)\.\s+(.*)$", line)
        if not rm:
            continue
        ref_id = int(rm.group(1))
        rest = rm.group(2)
        author_m = re.match(r"\*\*(.+?)\*\*\s*(.*)$", rest)
        author_block = author_m.group(1) if author_m else ""
        after = author_m.group(2) if author_m else rest
        year = None
        ym = re.match(r"^\(([^)]+)\)\.\s*(.*)$", after)
        if ym:
            year_raw = ym.group(1)
            after = ym.group(2)
            ym2 = re.search(r"(19|20)\d{2}", year_raw)
            if ym2:
                year = int(ym2.group(0))
        title = None
        tm = re.search(r"\*([^*]+)\*", after)
        if tm:
            title = tm.group(1).strip()
        doi = None
        dm = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", after)
        if dm:
            doi = dm.group(0).rstrip(".,;)")
        url = None
        um = re.search(r"https?://[^\s\)]+", after)
        if um:
            url = um.group(0).rstrip(".,;)")
        venue = None
        # Heuristic: italic title then venue before DOI/URL
        if tm:
            tail = after[tm.end() :].strip(" .")
            venue = re.split(r"https?://|doi\.org|DOI|Preprint|arXiv", tail, maxsplit=1)[
                0
            ].strip(" .,;")
            if len(venue) > 240:
                venue = venue[:240]
        is_patent = 1 if re.search(r"\bU\.?S\.?\s+Patent\b|\bPatent No\b|Patent Application", after, re.I) else 0
        names, has_etal = split_author_block(author_block) if author_block else ([], False)
        entries.append(
            {
                "id": ref_id,
                "year": year,
                "title": title,
                "venue": venue or None,
                "doi": doi,
                "url": url,
                "raw_text": line,
                "is_patent": is_patent,
                "authors": names,
                "has_etal": has_etal,
            }
        )
    return entries


# ---------------------------------------------------------------------------
# Seed static taxonomy
# ---------------------------------------------------------------------------


def seed_static(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO score_level (code, symbol, numeric_value, label, description) VALUES (?,?,?,?,?)",
        [
            ("full", "●", 2, "Full", "Publicly articulated strategy with supporting hardware, analysis, or design review"),
            ("partial", "◐", 1, "Partial", "Partial / roadmap-level / component-only"),
            ("weak", "○", 0, "Weak", "Weak, absent, or not yet public"),
            ("na", "—", None, "N/A", "Not applicable; treated as 0 for plant-odds POS"),
        ],
    )

    gates = [
        ("F", "Fuel & nuclear data", "Are measured p+¹¹B→3α cross-sections good enough for design? Spin polarization or laser-field enhancement claimed?", 1, 1),
        ("K", "Kinetics / Rider", "Thermonuclear Maxwellian, softened Ti/Te window, beam-target / block ignition, or structural non-equilibrium? How is Pi→e vs Pf managed?", 2, 1),
        ("R", "Radiation", "Bremsstrahlung and synchrotron: thin or thick? Suppressed? Reflected / reabsorbed / converted?", 3, 1),
        ("A", "Ash & impurities", "How is ⁴He removed on a timescale ≪ τE? Wall/Zeff poisoning controlled?", 4, 1),
        ("L", "Lawson / engineering Q", "Stated nτT or plant Q target; pulsed yield vs continuous gain; power-density / wall-load consistency.", 5, 1),
        ("C", "Confinement class", "MCF (ST, FRC, helical, open-field), ICF/HEDP, magneto-inertial/DPF, MEC/IEC, or hybrid?", 6, 0),
        ("M", "Materials & energy capture", "First wall, electrodes/grids, switches, divertor; thermal cycle vs DEC.", 7, 1),
        ("B", "Breeding", "N/A for pure p–¹¹B; relevant only for sister D–T / D–³He paths.", 8, 0),
        ("T", "Technology-to-market (T2M)", "Device generation on the floor, federal milestones, capital, IP, and brand maturity.", 9, 1),
        ("S", "In-silico / digital-twin iteration", "Can the team close design loops in software faster than hardware rebuilds?", 10, 1),
        ("H", "Hardware iteration", "Physical build/test cadence (new vessel, magnet set, or shot campaign per week/month/year).", 11, 1),
    ]
    conn.executemany(
        "INSERT INTO diligence_gate (code, name, question, sort_order, used_in_pos) VALUES (?,?,?,?,?)",
        gates,
    )

    conn.executemany(
        "INSERT INTO scoring_metric (code, name, formula, denominator, description) VALUES (?,?,?,?,?)",
        [
            (
                "POS",
                "Plant Odds Score",
                "POS = [2(K+R+A+L) + 1.5(T+H) + (F+M+S)] / 28 × 100",
                28.0,
                "Editorial composite from scorecard cells (●=2, ◐=1, ○/—=0). Physics path weighted heaviest.",
            ),
            (
                "POS_STAR",
                "Plant Odds Score (kappa-adjusted)",
                "POS★ = κ × POS",
                None,
                "POS after end-state / maturity factor κ from tab:kappa-factors.",
            ),
        ],
    )
    conn.executemany(
        "INSERT INTO scoring_metric_weight (metric_code, gate_code, weight) VALUES (?,?,?)",
        [
            ("POS", "K", 2.0),
            ("POS", "R", 2.0),
            ("POS", "A", 2.0),
            ("POS", "L", 2.0),
            ("POS", "T", 1.5),
            ("POS", "H", 1.5),
            ("POS", "F", 1.0),
            ("POS", "M", 1.0),
            ("POS", "S", 1.0),
        ],
    )

    conn.executemany(
        "INSERT INTO kappa_factor (kappa, when_used) VALUES (?,?)",
        [
            (1.0, "Dedicated p–¹¹B company or lab campaign (fuel end-state is boron–proton)"),
            (0.40, "Staged claim: near-term program is D–T (or other); p–¹¹B is design-capable / later pack only (Avalanche)"),
            (0.50, "Imputed / hypothetical plant: theory or in-silico paper sketched as if it were a full electricity path"),
            (0.35, "Facility / consortium / beamline infrastructure (science enabler, not a plant owner)"),
        ],
    )

    conn.executemany(
        "INSERT INTO matrix_axis (code, name, plain_question, typical_answers, sort_order) VALUES (?,?,?,?,?)",
        [
            ("time", "Time", "Does the machine run steadily, or in shots/pulses?", "Continuous / quasi-steady magnetic plants; pulsed lasers; pulsed pinches / colliding FRC plasmoids; nanosecond vacuum discharges", 1),
            ("confinement", "Confinement family", "What holds the fuel together long enough to fuse?", "Closed magnetic (tokamak, ST, stellarator); compact magnetic (FRC); open magnetic / rotating mirror (CHARM); laser / ICF / beam-target; magneto-inertial / DPF; electrostatic / MEC including Orbitron and NVD–IEC", 2),
            ("fuel", "Fuel end-state", "What is the intended commercial fuel—not the learning fuel?", "Pure p–¹¹B; sister advanced fuels (D–³He); D–T now with p–¹¹B claimed later; D–T only (sister spinouts)", 3),
            ("kinetics", "Kinetics", "Is the fuel a hot thermal soup, or a nonthermal / beam / structured distribution?", "Maxwellian thermal; softened hot-ion windows; beam-target / laser block; multi-chamber differential confinement; other Rider-bypass schemes", 4),
        ],
    )

    for name in [
        "Continuous",
        "Quasi-steady",
        "Pulsed",
        "Pulsed ns",
        "Compact MEC",
        "Facility / consortium",
        "Continuous open-field concept",
    ]:
        conn.execute("INSERT INTO time_mode (name) VALUES (?)", (name,))

    for name, short in [
        ("Spherical torus (ST)", "ST"),
        ("Beam-driven FRC", "FRC"),
        ("Rotating multi-chamber mirror", "CHARM"),
        ("Laser block ignition", "Laser ICF"),
        ("Laser / nano-ICF", "Nano-ICF"),
        ("Dense plasma focus (DPF)", "DPF"),
        ("Orbitron (magneto-electrostatic)", "Orbitron MEC"),
        ("NVD–IEC virtual cathode", "NVD–IEC"),
        ("FRC / PFRC", "PFRC"),
        ("Planar-coil stellarator", "Stellarator"),
        ("Helical / laser targets", "Helical/laser"),
        ("Beam-target HEDP", "Beam-target"),
        ("Consortium / multi-facility", "Consortium"),
        ("Kinetic theory (muon)", "μCF theory"),
        ("Pulsed FRC", "Pulsed FRC"),
        ("Imputed theory path", "Theory"),
    ]:
        conn.execute(
            "INSERT INTO confinement_family (name, short_name) VALUES (?, ?)",
            (name, short),
        )

    for name, clean in [
        ("p–¹¹B", 1),
        ("p–¹¹B (options)", 1),
        ("Advanced / p–¹¹B", 1),
        ("D–T now; p–¹¹B claimed", 0),
        ("D–³He", 0),
        ("D–T", 0),
        ("p–¹¹B experiments", 1),
        ("Staged D–T → D–³He → p–¹¹B", 0),
    ]:
        conn.execute(
            "INSERT INTO fuel_end_state (name, is_p11b_clean) VALUES (?, ?)",
            (name, clean),
        )

    for name in [
        "Near-thermal with hot-ion / beam assists",
        "Nonthermal block ignition",
        "Nonthermal orbiting ions",
        "Compressed plasmoids",
        "Beam-target / laser",
        "Multi-chamber differential confinement",
        "Megatesla / pinch",
        "Thermal MCF",
        "Not specified",
    ]:
        conn.execute("INSERT INTO kinetics_regime (name) VALUES (?)", (name,))

    for name in [
        "Company",
        "Company (early)",
        "Company (staged)",
        "National / company",
        "Lab",
        "Lab (component)",
        "Facility",
        "Facility / project",
        "Consortium",
        "Imputed theory",
        "Sister / other fuel",
    ]:
        conn.execute("INSERT INTO path_type (name) VALUES (?)", (name,))

    for name in [
        "person",
        "company",
        "university",
        "lab",
        "consortium",
        "government",
        "facility",
        "other_org",
    ]:
        conn.execute("INSERT INTO entity_kind (name) VALUES (?)", (name,))

    for name in [
        "machine",
        "digital_twin",
        "concept",
        "facility",
        "lab_campaign",
        "imputed_theory",
    ]:
        conn.execute("INSERT INTO prototype_kind (name) VALUES (?)", (name,))

    tables = [
        ("tab:matrix-axes", "Four-axis mental matrix", "§1.2"),
        ("tab:catalog-glance", "Catalog at a glance (executive, mid-2026)", "§1.3"),
        ("tab:diligence-gates", "Zeroth-order diligence gates", "§1.7"),
        ("tab:hedp-degenerate-hosts", "Pulsed laser / HEDP degenerate-boron hosts", "§3.2"),
        ("tab:aneutronic-channels", "Candidate aneutronic primary channels", "§5"),
        ("tab:sister-fuels", "Who pursues sister aneutronic fuels", "§5"),
        ("tab:pppl-spinouts", "Princeton / PPPL spinout comparative prognosis", "§6.7"),
        ("tab:scorecard", "Zeroth-order scorecard for key projects", "§8"),
        ("tab:digital-twin-software", "Selected fusion design / digital-twin software", "§9.2"),
        ("tab:legal-footprint", "Corporate / brand legal footprint", "§11"),
        ("tab:patents-sweep", "Representative patents and applications", "§11"),
        ("tab:citation-graph", "Citation graph (cross-firm prior art)", "§11"),
        ("tab:kappa-factors", "Plant-odds end-state / maturity factors (kappa)", "§12.1"),
        ("tab:plant-odds", "Ranked p–¹¹B plant odds", "§12.1"),
    ]
    conn.executemany(
        "INSERT INTO document_table (table_id, title, section) VALUES (?,?,?)",
        tables,
    )


# ---------------------------------------------------------------------------
# Organizations + people (seeded before reference ingest)
# ---------------------------------------------------------------------------


ORG_SEED: list[dict] = [
    # Companies / programs
    {"name": "ENN Energy Research Institute", "kind": "company", "short": "ENN", "country": "CN", "aliases": ["ENN", "ENN (China)", "ENN Energy"]},
    {"name": "TAE Technologies", "kind": "company", "short": "TAE", "country": "US", "website": "https://tae.com", "aliases": ["TAE", "Tri Alpha Energy", "Tae Technologies, Inc."]},
    {"name": "Pale Blue Fusion", "kind": "company", "short": "Pale Blue", "country": "US", "aliases": ["Pale Blue", "Pale Blue / CHARM", "Pale Blue / CHARM (Princeton)"]},
    {"name": "HB11 Energy", "kind": "company", "short": "HB11", "country": "AU", "aliases": ["HB11", "HB11 Energy Holdings"]},
    {"name": "Marvel Fusion", "kind": "company", "short": "Marvel", "country": "DE", "website": "https://marvelfusion.com", "aliases": ["Marvel Fusion GmbH", "Marvel / Blue Laser / Anubal"]},
    {"name": "Blue Laser Fusion", "kind": "company", "short": "Blue Laser", "country": "US", "website": "https://bluelaserfusion.com", "aliases": ["Blue Laser Fusion, Inc.", "Blue Laser Fusion Inc."]},
    {"name": "Anubal Fusion", "kind": "company", "short": "Anubal", "country": "US", "aliases": ["Anubal"]},
    {"name": "LPPFusion", "kind": "company", "short": "LPPFusion", "country": "US", "website": "https://lppfusion.com", "aliases": ["Lawrenceville Plasma Physics, Inc.", "LPPFusion (DPF)"]},
    {"name": "Avalanche Energy", "kind": "company", "short": "Avalanche", "country": "US", "website": "https://www.avalanchefusion.com", "aliases": ["Avalanche", "Avalanche Energy / Crusoe"]},
    {"name": "Helion Energy", "kind": "company", "short": "Helion", "country": "US", "website": "https://www.helionenergy.com", "aliases": ["Helion", "Helion Energy, Inc.", "Helion / PFS"]},
    {"name": "Thea Energy", "kind": "company", "short": "Thea", "country": "US", "website": "https://thea.energy", "aliases": ["Thea", "Thea Energy, Inc.", "Princeton Stellarators"]},
    {"name": "Princeton Fusion Systems", "kind": "company", "short": "PFS", "country": "US", "aliases": ["PFS", "PFS / PFRC", "Princeton Fusion Systems (PFS)"]},
    {"name": "Princeton Satellite Systems", "kind": "company", "short": "PSS", "country": "US", "aliases": ["PSS", "PFS / PSS", "Princeton Satellite Systems, Inc."]},
    {"name": "Kronos Fusion Energy", "kind": "company", "short": "Kronos", "country": "US"},
    {"name": "Stellar Furnace", "kind": "company", "short": "Stellar Furnace", "country": "US"},
    {"name": "General Fusion", "kind": "company", "short": "General Fusion", "country": "CA", "aliases": ["General Fusion Inc."]},
    {"name": "Energy Matter Conversion Corporation", "kind": "company", "short": "EMC2", "country": "US", "aliases": ["EMC2", "EMC2 (Polywell)"]},
    {"name": "Zap Energy", "kind": "company", "short": "Zap", "country": "US"},
    {"name": "Beam Alpha", "kind": "company", "short": "Beam Alpha"},
    {"name": "Fuse Energy", "kind": "company", "short": "Fuse"},
    {"name": "nTtau Digital", "kind": "company", "short": "nTtau", "website": "https://nttaudigital.com", "aliases": ["nTtau NuPlant"]},
    {"name": "VeloAlpha", "kind": "company", "short": "VeloAlpha", "country": "CN", "aliases": ["VeloAlpha FusionAlpha", "FusionAlpha"]},
    {"name": "UJK Management GmbH", "kind": "company", "short": "UJK", "country": "DE"},
    {"name": "LH3M", "kind": "company", "short": "LH3M", "notes": "Lunar ³He miner / supply-chain entity"},
    {"name": "Magna Petra", "kind": "company", "short": "Magna Petra", "notes": "Lunar ³He miner / supply-chain entity"},
    {"name": "FusionWERX", "kind": "facility", "short": "FusionWERX", "country": "US", "notes": "Avalanche industry test infrastructure (Richland)"},
    {"name": "BRA Inc.", "kind": "company", "short": "BRA", "notes": "Historical KARAT manual publisher"},
    # Labs / universities / gov
    {"name": "Joint Institute for High Temperatures of the Russian Academy of Sciences", "kind": "lab", "short": "JIHT", "country": "RU", "aliases": ["JIHT", "JIHT / Kurilenkov", "JIHT / Kurilenkov NVD", "JIHT RAS", "JIHT RAS Kurilenkov NVD"]},
    {"name": "National Institute for Fusion Science", "kind": "lab", "short": "NIFS", "country": "JP", "aliases": ["NIFS", "LHD / NIFS"]},
    {"name": "Large Helical Device", "kind": "facility", "short": "LHD", "country": "JP", "aliases": ["LHD"]},
    {"name": "Princeton University", "kind": "university", "short": "Princeton", "country": "US", "aliases": ["Princeton", "Trustees of Princeton University", "The Trustees of Princeton University"]},
    {"name": "Princeton Plasma Physics Laboratory", "kind": "lab", "short": "PPPL", "country": "US", "aliases": ["PPPL"]},
    {"name": "Xi'an Jiaotong University", "kind": "university", "short": "XJTU", "country": "CN", "aliases": ["XJTU", "XJTU / CN HEDP"]},
    {"name": "Chinese HEDP program", "kind": "consortium", "short": "CN HEDP", "country": "CN", "aliases": ["CN HEDP", "Chinese HEDP", "CN HEDP / XJTU + PROBONO lasers"]},
    {"name": "PROBONO COST Action CA21128", "kind": "consortium", "short": "PROBONO", "aliases": ["PROBONO", "PROBONO / FUSION-project laser platforms"]},
    {"name": "FUSION Project (INFN)", "kind": "facility", "short": "FUSION Project", "country": "IT", "aliases": ["FUSION Project", "FUSION INFN project"]},
    {"name": "Istituto Nazionale di Fisica Nucleare", "kind": "lab", "short": "INFN", "country": "IT", "aliases": ["INFN", "INFN / ELI Beamlines"]},
    {"name": "ELI Beamlines", "kind": "facility", "short": "ELI", "country": "CZ"},
    {"name": "Nanjing University muon-catalyzed fusion group", "kind": "lab", "short": "Nanjing μCF", "country": "CN", "aliases": ["Nanjing μCF"]},
    {"name": "Massachusetts Institute of Technology", "kind": "university", "short": "MIT", "country": "US", "aliases": ["MIT"]},
    {"name": "University of California", "kind": "university", "short": "UC", "country": "US", "aliases": ["UC", "Regents of the University of California", "Rostoker / UC (TAE root)"]},
    {"name": "University of Florida Research Foundation", "kind": "other_org", "short": "UFRF", "country": "US"},
    {"name": "UK Atomic Energy Authority", "kind": "lab", "short": "UKAEA", "country": "GB", "aliases": ["UKAEA", "UKAEA / Fusion Power Plant Framework"]},
    {"name": "Oak Ridge National Laboratory", "kind": "lab", "short": "ORNL", "country": "US", "aliases": ["ORNL"]},
    {"name": "Los Alamos National Laboratory", "kind": "lab", "short": "LANL", "country": "US", "aliases": ["LANL"]},
    {"name": "U.S. Department of Energy", "kind": "government", "short": "DOE", "country": "US", "aliases": ["DOE"]},
    {"name": "ARPA-E", "kind": "government", "short": "ARPA-E", "country": "US"},
    {"name": "NASA", "kind": "government", "short": "NASA", "country": "US"},
    {"name": "NVIDIA", "kind": "company", "short": "NVIDIA", "country": "US", "website": "https://www.nvidia.com"},
    {"name": "OpenMC Development Team", "kind": "other_org", "short": "OpenMC", "aliases": ["OpenMC"]},
    {"name": "Colorado State University", "kind": "university", "short": "CSU", "country": "US"},
    {"name": "PALS laser facility", "kind": "facility", "short": "PALS", "country": "CZ"},
    {"name": "Microsoft", "kind": "company", "short": "Microsoft", "country": "US", "notes": "Helion offtake narrative"},
    {"name": "Google", "kind": "company", "short": "Google", "country": "US", "notes": "TAE plasma-control software collaboration"},
    {"name": "Crusoe", "kind": "company", "short": "Crusoe", "notes": "Avalanche multi-cloud HPC partner"},
    {"name": "CAEP / IAPCM", "kind": "lab", "short": "CAEP/IAPCM", "country": "CN"},
    {"name": "USTC Press", "kind": "other_org", "short": "USTC Press", "country": "CN"},
    {"name": "Radiation Safety Information Computational Center", "kind": "other_org", "short": "RSICC", "country": "US"},
    {"name": "Catania α-avalanche MCF (imputed)", "kind": "other_org", "short": "Catania α-avalanche", "notes": "Imputed theory path from Moustaizis et al."},
    {"name": "Wikipedia contributors", "kind": "other_org", "short": "Wikipedia"},
    {"name": "r/fusion contributors", "kind": "other_org", "short": "r/fusion"},
    {"name": "Lyncean Group", "kind": "other_org", "short": "Lyncean"},
    {"name": "CB Insights", "kind": "company", "short": "CB Insights"},
    {"name": "South China Morning Post", "kind": "other_org", "short": "SCMP"},
    {"name": "Digital Trends", "kind": "other_org", "short": "Digital Trends"},
    {"name": "TechCrunch", "kind": "other_org", "short": "TechCrunch"},
    {"name": "Nautilus", "kind": "other_org", "short": "Nautilus"},
    {"name": "Imagine5", "kind": "other_org", "short": "Imagine5"},
    {"name": "Science (news)", "kind": "other_org", "short": "Science"},
    {"name": "WarpX community", "kind": "other_org", "short": "WarpX"},
    {"name": "Fusion Power Plant Framework", "kind": "other_org", "short": "FPPF"},
]


def seed_organizations(conn: sqlite3.Connection) -> None:
    for org in ORG_SEED:
        ensure_entity(
            conn,
            org["name"],
            org["kind"],
            short_name=org.get("short"),
            country=org.get("country"),
            website=org.get("website"),
            notes=org.get("notes"),
            aliases=org.get("aliases"),
        )


# ---------------------------------------------------------------------------
# Architectures, prototypes, scores
# ---------------------------------------------------------------------------


def seed_architectures(conn: sqlite3.Connection) -> None:
    rows = [
        # slug, name, path_type, time, confinement, fuel, kinetics, status, section, scorecard, plant_odds
        ("enn", "ENN (spherical torus)", "National / company", "Continuous", "Spherical torus (ST)", "p–¹¹B", "Near-thermal with hot-ion / beam assists", "Largest national ST + nuclear-data program; demo roadmap ~2030s", "§6.4", 1, 1),
        ("tae", "TAE Technologies (beam-driven FRC)", "Company", "Quasi-steady", "Beam-driven FRC", "p–¹¹B", "Near-thermal with hot-ion / beam assists", "Deepest private FRC capital; Rostoker→Norman→Da Vinci lineage; LHD alphas", "§6.1", 1, 1),
        ("pale-blue-charm", "Pale Blue / CHARM", "Company (early)", "Continuous open-field concept", "Rotating multi-chamber mirror", "p–¹¹B", "Multi-chamber differential confinement", "Strong theory + young IP; still incorporating; software-first", "§6.6", 1, 1),
        ("hb11", "HB11 Energy (laser block ignition)", "Company", "Pulsed", "Laser block ignition", "p–¹¹B", "Nonthermal block ignition", "Commercial laser path; ~4 orders below driver breakeven", "§6.2", 1, 1),
        ("marvel", "Marvel Fusion (nano-ICF)", "Company", "Pulsed", "Laser / nano-ICF", "p–¹¹B (options)", "Beam-target / laser", "European laser startup; CSU facility; nanostructured targets", "§6.5", 1, 1),
        ("blue-laser", "Blue Laser Fusion", "Company", "Pulsed", "Laser block ignition", "p–¹¹B (options)", "Beam-target / laser", "Nakamura lasers + INFUSE; boron option", "§6.5", 1, 1),
        ("anubal", "Anubal Fusion", "Company (early)", "Pulsed", "Laser / nano-ICF", "p–¹¹B (options)", "Beam-target / laser", "Early (2024) academic collaborations", "§6.5", 1, 1),
        ("lppfusion", "LPPFusion (DPF)", "Company", "Pulsed", "Dense plasma focus (DPF)", "Advanced / p–¹¹B", "Megatesla / pinch", "Long-running DPF company", "§6.3", 0, 1),
        ("avalanche", "Avalanche Energy (Orbitron)", "Company (staged)", "Compact MEC", "Orbitron (magneto-electrostatic)", "D–T now; p–¹¹B claimed", "Nonthermal orbiting ions", "High hardware cadence; FusionWERX; p–¹¹B-capable claim", "§6.8", 1, 1),
        ("jiht-nvd", "JIHT / Kurilenkov NVD–IEC", "Lab", "Pulsed ns", "NVD–IEC virtual cathode", "p–¹¹B", "Beam-target / laser", "Russian lab alphas + KARAT PIC scaling", "§6.8", 1, 1),
        ("helion", "Helion Energy (pulsed FRC)", "Sister / other fuel", "Pulsed", "Pulsed FRC", "D–³He", "Compressed plasmoids", "Serious capital; cleaner than D–T, not p–¹¹B-clean", "§5 / §6", 1, 0),
        ("pfs-pfrc", "Princeton Fusion Systems (PFRC)", "Sister / other fuel", "Pulsed", "FRC / PFRC", "D–³He", "Compressed plasmoids", "Microreactor / propulsion line", "§6.7", 1, 0),
        ("thea", "Thea Energy (planar stellarator)", "Sister / other fuel", "Continuous", "Planar-coil stellarator", "D–T", "Thermal MCF", "Princeton spinout; DOE Helios path", "§6.7", 1, 0),
        ("lhd-nifs", "LHD / NIFS", "Facility", "Facility / consortium", "Helical / laser targets", "p–¹¹B experiments", "Beam-target / laser", "Magnetic p–¹¹B alpha demo; not a plant design", "§6 / §8", 1, 1),
        ("xjtu-cn-hedp", "XJTU / CN HEDP", "Lab (component)", "Pulsed", "Beam-target HEDP", "p–¹¹B", "Beam-target / laser", "Record foam yields; component path", "§6.5", 1, 1),
        ("probono", "PROBONO", "Consortium", "Facility / consortium", "Consortium / multi-facility", "p–¹¹B experiments", "Beam-target / laser", "EU laser/plasma p–¹¹B coordination", "§6.5", 1, 1),
        ("fusion-project", "FUSION Project (INFN)", "Facility / project", "Pulsed", "Laser / nano-ICF", "p–¹¹B experiments", "Beam-target / laser", "PALS diagnostics/targetry", "§6.5", 1, 1),
        ("nanjing-mucf", "Nanjing μCF", "Imputed theory", "Pulsed", "Kinetic theory (muon)", "p–¹¹B", "Beam-target / laser", "Muon screening proposal; speculative L", "§7", 1, 1),
        ("degenerate-catcher", "Degenerate-catcher plant", "Imputed theory", "Pulsed", "Beam-target HEDP", "p–¹¹B", "Beam-target / laser", "Imputed theory plant from compressed-degenerate boron [91]", "§3.2 / §12.1", 0, 1),
        ("catania-avalanche", "Catania α-avalanche MCF", "Imputed theory", "Continuous", "Imputed theory path", "p–¹¹B", "Near-thermal with hot-ion / beam assists", "Imputed theory from Moustaizis et al. [43]", "§12.1", 0, 1),
        ("radiation-trapping", "Radiation-trapping regime", "Imputed theory", "Pulsed", "Imputed theory path", "p–¹¹B", "Beam-target / laser", "Ochs–Kolmes–Fisch compressed p–¹¹B radiation-trapping [3]", "§12.1", 0, 1),
    ]
    for r in rows:
        conn.execute(
            """
            INSERT INTO architecture (
                slug, name, path_type_id, time_mode_id, confinement_family_id,
                fuel_end_state_id, kinetics_regime_id, catalog_status, source_section,
                in_scorecard, in_plant_odds
            ) VALUES (
                ?, ?,
                (SELECT id FROM path_type WHERE name = ?),
                (SELECT id FROM time_mode WHERE name = ?),
                (SELECT id FROM confinement_family WHERE name = ?),
                (SELECT id FROM fuel_end_state WHERE name = ?),
                (SELECT id FROM kinetics_regime WHERE name = ?),
                ?, ?, ?, ?
            )
            """,
            (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10]),
        )

    # Entity ↔ architecture
    links = [
        ("enn", "ENN Energy Research Institute", "lead"),
        ("tae", "TAE Technologies", "lead"),
        ("pale-blue-charm", "Pale Blue Fusion", "lead"),
        ("pale-blue-charm", "Princeton University", "spinout_of"),
        ("pale-blue-charm", "ARPA-E", "host"),
        ("hb11", "HB11 Energy", "lead"),
        ("marvel", "Marvel Fusion", "lead"),
        ("blue-laser", "Blue Laser Fusion", "lead"),
        ("anubal", "Anubal Fusion", "lead"),
        ("lppfusion", "LPPFusion", "lead"),
        ("avalanche", "Avalanche Energy", "lead"),
        ("avalanche", "FusionWERX", "host"),
        ("jiht-nvd", "Joint Institute for High Temperatures of the Russian Academy of Sciences", "lead"),
        ("helion", "Helion Energy", "lead"),
        ("pfs-pfrc", "Princeton Fusion Systems", "lead"),
        ("pfs-pfrc", "Princeton Satellite Systems", "collaborator"),
        ("pfs-pfrc", "Princeton University", "spinout_of"),
        ("thea", "Thea Energy", "lead"),
        ("thea", "Princeton University", "spinout_of"),
        ("thea", "Princeton Plasma Physics Laboratory", "collaborator"),
        ("lhd-nifs", "National Institute for Fusion Science", "lead"),
        ("lhd-nifs", "Large Helical Device", "host"),
        ("xjtu-cn-hedp", "Xi'an Jiaotong University", "lead"),
        ("xjtu-cn-hedp", "Chinese HEDP program", "program"),
        ("probono", "PROBONO COST Action CA21128", "lead"),
        ("fusion-project", "FUSION Project (INFN)", "lead"),
        ("fusion-project", "Istituto Nazionale di Fisica Nucleare", "host"),
        ("nanjing-mucf", "Nanjing University muon-catalyzed fusion group", "lead"),
        ("degenerate-catcher", "Chinese HEDP program", "program"),
        ("catania-avalanche", "Catania α-avalanche MCF (imputed)", "lead"),
        ("radiation-trapping", "Princeton University", "program"),
    ]
    for slug, ent, role in links:
        conn.execute(
            """
            INSERT INTO architecture_entity (architecture_id, entity_id, role)
            VALUES (?, ?, ?)
            """,
            (aid(conn, slug), eid(conn, ent), role),
        )


def seed_plant_specs(conn: sqlite3.Connection) -> None:
    """Survey-informed editorial envelopes for operator-twin site I/O.

    Ratings/sizes prefer public scale cues (Norman hall, Orbitron desk-scale,
    ST halls). Startup fields are *black-start / first-production* estimates:
    battery pays house/aux + one-shot magnet or capacitor energy — not the full
    wall-plug NBI/laser average. time_to_production_s=0 means the 0D model
    allows instantaneous driver/fusion books (no prep gate).
    """
    # slug, foot, L, D, gross, net, driver, batt_kWh, batt_V, H, B, n_frac,
    # t_prod_s, aux_MW, E_kWh, startup_notes, quality, notes
    specs: list[tuple] = [
        (
            "avalanche", 12, 1.2, 0.8, 0.05, 0.01, 0.15, 25, 400, 0.05, 0.02, 0.85,
            3.0, 0.02, 0.05,
            "HV supply + orbit enable on desk-scale pack; first beam/orbit in a few seconds.",
            "editorial",
            "Desk-scale Orbitron / modular kWe pack; D–T learning neutrons dominate byproducts.",
        ),
        (
            "jiht-nvd", 8, 0.6, 0.4, 0.002, 0.0005, 0.02, 5, 200, 0.02, 0.02, 0.05,
            5.0, 0.005, 0.02,
            "Small IEC/NVD HV ramp and vacuum interlocks; lab-scale.",
            "editorial",
            "Lab NVD–IEC; tiny net; low but nonzero side neutrons.",
        ),
        (
            "tae", 2500, 30, 4, 0, 0, 20, 200, 1000, 2.0, 1.5, 0.02,
            0.0, 1.0, 12.0,
            "Commission sequence in simulator (vacuum warp → 8 min shot cycle → arm → 40 ms NBI). "
            "Rated driver ~20 MW matches C-2W NBI electrical class. Gross/net=0: no published Q>1.",
            "survey",
            "Norman/C-2W research hall (~30 m); plasma ≤40 ms NB-limited; not a power plant.",
        ),
        (
            "enn", 1800, 8, 6, 100, 50, 40, 250, 1000, 1.5, 1.2, 0.02,
            150.0, 2.0, 80.0,
            "ST TF/PF + aux ramp longer than FRC; ~2 MW house + coil energy before NBI/ICRF.",
            "editorial",
            "ST hall + nuclear-data program; demo-class net power aspirational.",
        ),
        (
            "pale-blue-charm", 900, 12, 3, 80, 40, 25, 120, 800, 1.0, 1.0, 0.01,
            180.0, 1.0, 35.0,
            "Rotating-mirror / CHARM field spin-up editorial; still incorporating.",
            "aspirational",
            "Still incorporating; open-field CHARM concept scale.",
        ),
        (
            "hb11", 1200, 10, 10, 120, 50, 100, 80, 800, 0.8, 1.2, 0.001,
            8.0, 4.0, 12.0,
            "First-shot gate = plant-scale capacitor/charger fill (~seconds). "
            "Published dual-laser sketch is ~30 kJ+3 kJ lab; plant bank here is editorial "
            "scaled to rated driver, not the 30 kJ point. Average laser wall-plug after "
            "first shot follows P_import — not assumed on starter batt during prep.",
            "editorial",
            "Amplifier / laser plant sketch; driver bank >> net until gain closes.",
        ),
        (
            "marvel", 1500, 12, 8, 80, 40, 60, 60, 800, 0.6, 1.0, 0.001,
            10.0, 3.0, 10.0,
            "Laser facility bank charge to first shot; CSU-class scale cue.",
            "editorial",
            "CSU laser facility class; plant L early.",
        ),
        (
            "blue-laser", 800, 8, 6, 40, 15, 40, 40, 800, 0.4, 0.6, 0.001,
            8.0, 2.5, 8.0,
            "Company laser/target bank charge to first shot.",
            "editorial",
            "Company laser/target stack; boron path thinner publicly.",
        ),
        (
            "anubal", 200, 4, 3, 5, 1, 8, 15, 400, 0.1, 0.2, 0.001,
            6.0, 0.4, 2.0,
            "Small laser collaboration; short bank fill.",
            "editorial",
            "Early academic collaborations; small envelope.",
        ),
        (
            "xjtu-cn-hedp", 400, 5, 3, 2, 0.2, 10, 20, 400, 0.2, 0.3, 0.001,
            10.0, 0.5, 3.0,
            "Beam-target / component path; charger + vacuum before shot.",
            "editorial",
            "Component / beam-target science path, not integrated plant.",
        ),
        (
            "lppfusion", 150, 3, 2, 5, 1, 8, 15, 480, 0.3, 0.4, 0.05,
            2.0, 0.15, 0.8,
            "DPF capacitor charge dominates time-to-shot; lab electrode-limited.",
            "editorial",
            "Lab DPF; electrode/rep-rate limited.",
        ),
        (
            "helion", 2000, 20, 5, 80, 50, 40, 150, 1000, 1.5, 0.0, 0.15,
            20.0, 2.0, 30.0,
            "Pulsed FRC compression/capacitor bank + aux before first pulse train.",
            "editorial",
            "Polaris-class pulsed FRC; D–³He — not p11B-clean; side neutrons.",
        ),
        (
            "pfs-pfrc", 120, 4, 2, 1, 0.2, 1.5, 25, 480, 0.2, 0.0, 0.1,
            30.0, 0.1, 2.0,
            "PFRC microreactor RF/coil enable; small house load.",
            "editorial",
            "PFRC microreactor line; D–³He.",
        ),
        (
            "thea", 2200, 15, 10, 200, 100, 50, 400, 1000, 0.0, 0.0, 0.8,
            600.0, 3.0, 150.0,
            "Stellarator coil/cryo black-start is long vs FRC/laser; editorial 10 min ready-hall "
            "(true cold cryo is hours — not modeled).",
            "editorial",
            "Eos/Helios D–T stellarator; tritium/activation dominate byproducts.",
        ),
        (
            "lhd-nifs", 5000, 40, 10, 0, 0, 20, 80, 480, 0.1, 0.1, 0.02,
            120.0, 1.0, 20.0,
            "Experiment-support bus only; not a plant owner. Prep = facility aux before shot/pulse.",
            "survey",
            "Science facility; not a plant owner — ratings are experiment-support only.",
        ),
        (
            "probono", 0, 0, 0, 0, 0, 0, 10, 400, 0.05, 0.05, 0.001,
            0.0, 0.0, 0.0,
            "No pad — instantaneous model (coordination only).",
            "editorial",
            "Consortium coordination — no single reactor pad.",
        ),
        (
            "fusion-project", 300, 5, 3, 0, 0, 5, 15, 400, 0.1, 0.1, 0.001,
            15.0, 0.3, 2.0,
            "PALS-class targetry: bank/diagnostics ready before shot.",
            "editorial",
            "PALS-class targetry/diagnostics.",
        ),
        (
            "nanjing-mucf", 50, 2, 1, 0, 0, 0.5, 5, 200, 0.05, 0.05, 0.0,
            0.0, 0.0, 0.0,
            "Theory path — no hardware; instantaneous books.",
            "aspirational",
            "Imputed muon theory path — no hardware plant.",
        ),
        (
            "degenerate-catcher", 400, 5, 3, 10, 2, 20, 40, 400, 0.3, 0.5, 0.001,
            12.0, 1.0, 8.0,
            "Imputed HEDP catcher bank fill before first shot.",
            "aspirational",
            "Imputed theory plant from [91] mixin.",
        ),
        (
            "catania-avalanche", 100, 3, 2, 1, 0.1, 2, 15, 400, 0.1, 0.1, 0.01,
            60.0, 0.2, 5.0,
            "Imputed MCF scan: modest magnet/aux before flattop.",
            "aspirational",
            "Imputed α-avalanche MCF scans.",
        ),
        (
            "radiation-trapping", 100, 3, 2, 1, 0.1, 2, 15, 400, 0.1, 0.1, 0.01,
            60.0, 0.2, 5.0,
            "Imputed compressed-plasma prep window.",
            "aspirational",
            "Imputed radiation-trapping paper plant.",
        ),
    ]
    for row in specs:
        (
            slug, foot, length, diam, gross, net, driver, bkwh, bv,
            h, b, nfrac, t_prod, aux, e_kwh, start_notes, quality, notes,
        ) = row
        conn.execute(
            """
            INSERT INTO plant_spec (
                architecture_id, footprint_m2, vessel_length_m, vessel_diameter_m,
                rated_gross_MW, rated_net_MW, rated_driver_MW,
                starter_battery_kWh, starter_battery_V,
                design_fuel_H_mg_s, design_fuel_B11_mg_s, neutron_energy_fraction,
                time_to_production_s, startup_aux_MW, startup_energy_kWh, startup_notes,
                notes, data_quality
            ) VALUES (
                (SELECT id FROM architecture WHERE slug = ?),
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )
            """,
            (
                slug, foot, length, diam, gross, net, driver, bkwh, bv,
                h, b, nfrac, t_prod, aux, e_kwh, start_notes, notes, quality,
            ),
        )


def seed_gate_scores(conn: sqlite3.Connection) -> None:
    # Map symbols to codes
    sym = {"●": "full", "◐": "partial", "○": "weak", "—": "na", "-": "na"}
    # Project → C label + F K R A L M T S H (no B in scorecard)
    scorecard = {
        "enn": ("ST (MCF)", "●", "◐", "◐", "◐", "◐", "◐", "●", "◐", "●"),
        "tae": ("FRC", "●", "●", "●", "◐", "◐", "◐", "●", "◐", "●"),
        "lhd-nifs": ("Helical", "●", "◐", "—", "—", "○", "—", "●", "◐", "●"),
        "hb11": ("Laser ICF", "●", "◐", "◐", "◐", "◐", "◐", "◐", "◐", "◐"),
        "marvel": ("Nano-ICF", "●", "●", "◐", "◐", "○", "◐", "◐", "◐", "◐"),
        "xjtu-cn-hedp": ("Beam-target", "●", "●", "●", "—", "○", "○", "◐", "◐", "●"),
        "blue-laser": ("Laser ICF", "●", "◐", "◐", "◐", "○", "◐", "◐", "◐", "○"),
        "anubal": ("Laser ICF", "◐", "◐", "○", "○", "○", "○", "○", "○", "○"),
        "probono": ("Consortium", "●", "●", "◐", "◐", "—", "—", "●", "◐", "●"),
        "fusion-project": ("Laser targets", "●", "●", "◐", "—", "○", "○", "◐", "◐", "●"),
        "pale-blue-charm": ("Rot. mirror", "●", "●", "●", "●", "◐", "◐", "○", "●", "○"),
        "nanjing-mucf": ("Kinetic theory", "●", "●", "—", "—", "○", "○", "○", "●", "○"),
        "thea": ("Planar stellarator", "—", "—", "—", "—", "●", "◐", "●", "●", "◐"),
        "pfs-pfrc": ("PFRC", "—", "—", "◐", "◐", "◐", "◐", "◐", "◐", "●"),
        "helion": ("Pulsed FRC", "—", "—", "◐", "◐", "◐", "◐", "●", "◐", "●"),
        "avalanche": ("Orbitron (MEC)", "◐", "◐", "◐", "◐", "◐", "◐", "●", "●", "●"),
        "jiht-nvd": ("NVD–IEC", "●", "●", "◐", "◐", "○", "◐", "○", "●", "●"),
        # Imputed rows from §12.1 notes
        "degenerate-catcher": ("Beam-target", "●", "●", "●", "◐", "◐", "◐", "○", "●", "○"),
        "catania-avalanche": ("MCF (imputed)", "●", "●", "◐", "◐", "◐", "○", "○", "●", "○"),
        "radiation-trapping": ("Compressed plasma", "●", "●", "●", "○", "○", "○", "○", "●", "○"),
    }
    gates_order = ["F", "K", "R", "A", "L", "M", "T", "S", "H"]
    for slug, vals in scorecard.items():
        c_label, *scores = vals
        arch = aid(conn, slug)
        conn.execute(
            """
            INSERT INTO architecture_gate_score (architecture_id, gate_code, score_code, confinement_label)
            VALUES (?, 'C', NULL, ?)
            """,
            (arch, c_label),
        )
        for g, s in zip(gates_order, scores, strict=True):
            conn.execute(
                """
                INSERT INTO architecture_gate_score (architecture_id, gate_code, score_code)
                VALUES (?, ?, ?)
                """,
                (arch, g, sym[s]),
            )


def seed_plant_odds(conn: sqlite3.Connection) -> None:
    rows = [
        # rank, slug, pos, kappa, pos_star, q, proto, grid, approx, rationale
        (1, "tae", 79, 1.0, 79, "~2030–2036", "~2032–2040", "~2038–2050", 0, "Deepest capital + Norm hardware + LHD α proof; L/M (ICC) still open."),
        (2, "pale-blue-charm", 68, 1.0, 68, "~2034–2042", "~2036–2045", "~2040–2055", 0, "Best published A/K/R attack; T/H almost empty."),
        (3, "enn", 64, 1.0, 64, "~2032–2038", "~2033–2040", "~2038–2050", 0, "National ST + nuclear-data machine; hot-ion K contested; clearest demo roadmap."),
        (4, "jiht-nvd", 57, 1.0, 57, "uncertain", "lab-scale only", "N/A as utility", 0, "Real lab p–¹¹B alphas in compact IEC neighborhood; not a capitalized plant."),
        (5, "xjtu-cn-hedp", 55, 1.0, 55, "science track", "—", "—", 0, "Record beam-target yields + [91] theory; not an integrated plant."),
        (6, "hb11", 54, 1.0, 54, "~2034–2042", "~2036–2045", "~2042–2055", 0, "Real laser R&D + reactor sketch; ~4 orders below driver breakeven."),
        (7, "marvel", 54, 1.0, 54, "~2034–2042", "~2036–2045", "~2042–2055", 0, "Strong nano-target K; plant L weaker than HB11; CSU still standing up."),
        (8, "lppfusion", 43, 1.0, 43, "~2035–2045", "~2038–2048", "~2045–2055+", 1, "POS approximate from narrative (not a full scorecard row)."),
        (9, "blue-laser", 41, 1.0, 41, "~2036–2045", "~2038–2048", "~2045–2055+", 0, "Patent/laser stack real; p–¹¹B plant path thinner publicly."),
        (10, "degenerate-catcher", 61, 0.50, 31, "if productized ~2035–2045", "—", "—", 0, "In-silico / theory F>1 beam→compressed-degenerate boron; no company owns a plant."),
        (11, "avalanche", 64, 0.40, 26, "~2035–2045‡", "~2036–2045", "~2040–2050 (modular)", 0, "Strong D–T hardware H/T; p–¹¹B is design-capable later—κ cuts plant odds."),
        (12, "catania-avalanche", 50, 0.50, 25, "speculative", "—", "—", 0, "Low-density multi-fluid Q=Pf/PBrems>1 scans; no machine program."),
        (13, "radiation-trapping", 43, 0.50, 22, "speculative", "—", "—", 0, "Ochs–Kolmes–Fisch compressed p–¹¹B radiation-trapping feasibility; paper plant only."),
        (14, "probono", 61, 0.35, 21, "—", "—", "—", 0, "EU coordination of laser/plasma p–¹¹B; not one reactor owner."),
        (15, "fusion-project", 48, 0.35, 17, "science track", "—", "—", 0, "PALS-class targetry/diagnostics; science enabler."),
        (16, "nanjing-mucf", 29, 0.50, 15, "speculative", "—", "—", 0, "Kinetic muon-screening proposal; speculative L, no hardware path."),
        (17, "lhd-nifs", 39, 0.35, 14, "—", "—", "—", 0, "Magnetic p–¹¹B α demo; not a plant design."),
        (18, "anubal", 11, 1.0, 11, "—", "—", "—", 0, "Too early for plant odds."),
    ]
    for r in rows:
        conn.execute(
            """
            INSERT INTO plant_odds (
                architecture_id, rank, pos, kappa, pos_star,
                q_ge_1_window, prototype_window, grid_product_window,
                pos_approximate, rationale
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (aid(conn, r[1]), r[0], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9]),
        )


def seed_prototypes(conn: sqlite3.Connection) -> None:
    # Machines / facilities / concepts / digital twins (digital twins are prototypes)
    proto_rows = [
        # slug, name, kind, arch_slug, status, description
        ("exl-50u", "EXL-50U", "machine", "enn", "operating", "ENN spherical torus generation on the ST roadmap"),
        ("ehl-2", "EHL-2", "machine", "enn", "planned", "ENN physics-design ST toward demo-class p–¹¹B"),
        ("enn-demo", "ENN DEMO-class ST", "concept", "enn", "concept", "Roadmap demo-class clean-fusion ST"),
        ("c-2", "C-2", "machine", "tae", "retired", "Early TAE FRC device generation"),
        ("c-2u", "C-2U", "machine", "tae", "retired", "TAE FRC upgrade generation"),
        ("norman", "C-2W / Norman", "machine", "tae", "operating", "Warehouse-scale beam-driven FRC"),
        ("norm", "Norm", "machine", "tae", "under_construction", "Shortened NBI-only formation path device"),
        ("copernicus", "Copernicus", "concept", "tae", "concept", "Mid-10^8 K scout on earlier roadmap (later compressed/skipped)"),
        ("da-vinci", "Da Vinci", "concept", "tae", "planned", "Commercial-design p–¹¹B plant concept"),
        ("lhd-pb11", "LHD p–¹¹B alpha campaign", "lab_campaign", "lhd-nifs", "operating", "First magnetically confined p–¹¹B alphas (with TAE)"),
        ("charm-concept", "CHARM multi-chamber mirror", "concept", "pale-blue-charm", "concept", "Centrifugal multi-chamber open-field architecture"),
        ("hb11-dual-laser", "HB11 dual-laser capacitor-coil reactor", "concept", "hb11", "concept", "Laser-1 CPA protons + laser-2 coil B reactor sketch"),
        ("marvel-csu", "Marvel CSU laser facility", "facility", "marvel", "under_construction", "Colorado State University laser site"),
        ("ff-2", "LPPFusion FF-2 / lab DPF", "machine", "lppfusion", "operating", "Laboratory dense plasma focus experiment"),
        ("orbitron", "Orbitron", "machine", "avalanche", "operating", "Desk-scale magneto-electrostatic confinement device"),
        ("fusionwerx", "FusionWERX", "facility", "avalanche", "operating", "Industry test infrastructure in Richland"),
        ("jiht-nvd-device", "JIHT NVD–IEC discharge", "machine", "jiht-nvd", "operating", "Nanosecond vacuum discharge virtual-cathode experiment"),
        ("polaris", "Helion Polaris", "machine", "helion", "under_construction", "Helion pulsed FRC plant-path machine"),
        ("pfrc-2", "PFRC-2", "machine", "pfs-pfrc", "operating", "Princeton Field-Reversed Configuration experiment"),
        ("pfrc-3", "PFRC-3", "machine", "pfs-pfrc", "planned", "Seeking funding upgrade path"),
        ("eos", "Thea Eos", "machine", "thea", "planned", "Thea stellarator build target"),
        ("helios", "Thea Helios", "concept", "thea", "planned", "DOE Milestone-certified pilot-plant preconceptual design"),
        ("xjtu-foam", "XJTU / CN HEDP foam beam-target", "lab_campaign", "xjtu-cn-hedp", "operating", "Record foam / preformed-plasma yield experiments"),
        # Digital twins / design software counted as prototypes
        ("dt-openmc", "OpenMC", "digital_twin", None, "product", "Monte Carlo neutron/photon transport"),
        ("dt-paramak", "Paramak", "digital_twin", None, "product", "Parametric 3D fusion CAD → neutronics geometry"),
        ("dt-bluemira", "Bluemira", "digital_twin", None, "product", "Integrated tokamak/FPP design framework (UKAEA)"),
        ("dt-process", "PROCESS", "digital_twin", None, "product", "0D–1D systems code often driven by Bluemira"),
        ("dt-warpx", "WarpX / pyWarpX", "digital_twin", "avalanche", "product", "Exascale PIC used in industrial rapid-iteration loops"),
        ("dt-karat", "KARAT", "digital_twin", "jiht-nvd", "product", "Fully electromagnetic PIC for NVD/IEC p–¹¹B"),
        ("dt-xie-fusionbook", "Xie fusionbook codes", "digital_twin", None, "product", "Open 0D Lawson / power-balance scripts"),
        ("dt-charm-stack", "Fisch/CHARM stack", "digital_twin", "pale-blue-charm", "concept", "(PB)², S⁵, R³FP, MITNS academic tools"),
        ("dt-freda", "FREDA", "digital_twin", None, "product", "ORNL SciDAC whole-facility digital-twin framework"),
        ("dt-omniverse", "NVIDIA Omniverse (+ Modulus)", "digital_twin", "thea", "product", "Collaborative plant digital twin / visualization"),
        ("dt-nuplant", "nTtau NuPlant", "digital_twin", None, "product", "End-to-end FPP design platform"),
        ("dt-fusionalpha", "VeloAlpha FusionAlpha", "digital_twin", None, "product", "AI simulator for reactor designs (seed stage)"),
        ("dt-mcnp", "MCNP", "digital_twin", None, "product", "Export-controlled Monte Carlo gold standard"),
        # Imputed theory prototypes
        ("imp-degenerate", "Compressed-degenerate boron catcher", "imputed_theory", "degenerate-catcher", "concept", "2024 mixin target upgrade [91]"),
        ("imp-catania", "Catania α-avalanche MCF scan", "imputed_theory", "catania-avalanche", "concept", "Low-density multi-fluid avalanche simulations [43]"),
        ("imp-radtrap", "Radiation-trapping compressed p–¹¹B", "imputed_theory", "radiation-trapping", "concept", "Ochs–Kolmes–Fisch feasibility regime [3]"),
    ]
    for slug, name, kind, arch, status, desc in proto_rows:
        conn.execute(
            """
            INSERT INTO prototype (slug, name, kind_id, architecture_id, status, description)
            VALUES (
                ?, ?,
                (SELECT id FROM prototype_kind WHERE name = ?),
                ?, ?, ?
            )
            """,
            (slug, name, kind, aid(conn, arch) if arch else None, status, desc),
        )

    # Prototype owners
    owners = [
        ("exl-50u", "ENN Energy Research Institute", "owner"),
        ("ehl-2", "ENN Energy Research Institute", "owner"),
        ("norman", "TAE Technologies", "owner"),
        ("norm", "TAE Technologies", "owner"),
        ("da-vinci", "TAE Technologies", "owner"),
        ("lhd-pb11", "National Institute for Fusion Science", "host_facility"),
        ("lhd-pb11", "TAE Technologies", "collaborator"),
        ("charm-concept", "Pale Blue Fusion", "developer"),
        ("charm-concept", "Princeton University", "developer"),
        ("hb11-dual-laser", "HB11 Energy", "owner"),
        ("marvel-csu", "Marvel Fusion", "owner"),
        ("marvel-csu", "Colorado State University", "host_facility"),
        ("ff-2", "LPPFusion", "owner"),
        ("orbitron", "Avalanche Energy", "owner"),
        ("fusionwerx", "Avalanche Energy", "operator"),
        ("fusionwerx", "FusionWERX", "host_facility"),
        ("jiht-nvd-device", "Joint Institute for High Temperatures of the Russian Academy of Sciences", "owner"),
        ("polaris", "Helion Energy", "owner"),
        ("pfrc-2", "Princeton Fusion Systems", "owner"),
        ("eos", "Thea Energy", "owner"),
        ("helios", "Thea Energy", "owner"),
        ("dt-bluemira", "UK Atomic Energy Authority", "developer"),
        ("dt-process", "UK Atomic Energy Authority", "developer"),
        ("dt-warpx", "WarpX community", "developer"),
        ("dt-warpx", "Avalanche Energy", "collaborator"),
        ("dt-karat", "Joint Institute for High Temperatures of the Russian Academy of Sciences", "collaborator"),
        ("dt-freda", "Oak Ridge National Laboratory", "developer"),
        ("dt-freda", "U.S. Department of Energy", "host"),
        ("dt-omniverse", "NVIDIA", "developer"),
        ("dt-omniverse", "UK Atomic Energy Authority", "collaborator"),
        ("dt-nuplant", "nTtau Digital", "owner"),
        ("dt-fusionalpha", "VeloAlpha", "owner"),
        ("dt-mcnp", "Los Alamos National Laboratory", "developer"),
        ("dt-openmc", "OpenMC Development Team", "developer"),
        ("dt-charm-stack", "Princeton University", "developer"),
    ]
    for pslug, ent, role in owners:
        # Fix: FREDA uses role host but check constraint is free text - ok
        conn.execute(
            """
            INSERT OR IGNORE INTO prototype_entity (prototype_id, entity_id, role)
            VALUES (?, ?, ?)
            """,
            (pid(conn, pslug), eid(conn, ent), role),
        )


def seed_secondary_tables(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """
        INSERT INTO aneutronic_channel (reaction, primary_products, q_value_mev, thermal_ignition_vs_dt)
        VALUES (?, ?, ?, ?)
        """,
        [
            ("D + ³He", "⁴He + p", 18.3, "~4× harder"),
            ("D + ⁶Li", "2 ⁴He", 22.4, "Intermediate"),
            ("p + ⁶Li", "⁴He + ³He", 4.0, "Intermediate"),
            ("³He + ⁶Li", "2 ⁴He + p", 16.9, "Hard"),
            ("³He + ³He", "⁴He + 2p", 12.9, "Very hard"),
            ("p + ⁷Li", "2 ⁴He (desired branch)", 17.2, "Intermediate"),
            ("p + ¹¹B", "3 ⁴He", 8.7, "~10× harder"),
            ("p + ¹⁵N", "¹²C + ⁴He", 5.0, "Hard / niche"),
        ],
    )

    sister = [
        ("Helion Energy", "helion", "D–³He end state; breeds ³He via D–D + tritium decay", "No — side-reaction neutrons (percent-level)", "Largest capitalized non-p–¹¹B advanced-fuel commercial path"),
        ("Princeton Fusion Systems", "pfs-pfrc", "D–³He microreactor / propulsion", "No — same D–D / residual-T neutronics", "Rapid T extraction stressed to limit 14 MeV neutrons"),
        ("Kronos Fusion Energy", None, "Staged D–T → D–³He → p–¹¹B", "Stage 2 no; Stage 3 yes (claimed)", "Marketing roadmap; aspirational until hardware/fuel stages public"),
        ("Stellar Furnace", None, "Primary p–¹¹B DPF; He-3 as optional tier", "Primary path yes; He-3 tier no/scarce", "Early DPF company messaging"),
        ("LH3M", None, "Supply chain, not reactors", "N/A", "Lunar ³He miner speculation"),
        ("Magna Petra", None, "Supply chain, not reactors", "N/A", "Lunar ³He miner speculation"),
    ]
    for ent, arch, claim, clean, notes in sister:
        conn.execute(
            """
            INSERT INTO sister_fuel_pursuit (entity_id, architecture_id, fuel_claim, clean_vs_p11b, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (eid(conn, ent), aid(conn, arch) if arch else None, claim, clean, notes),
        )

    for slug, why in [
        ("hb11", "Hybrid burn already pairs compression with CPA protons; degeneracy is an explicit gain lever in related laser literature [90]."),
        ("marvel", "Nanostructured laser ICF targets—compressed/degenerate catchers are a natural target-physics upgrade [8]."),
        ("xjtu-cn-hedp", "Same ZJU–SJTU–XJTU ecosystem; foam / preformed-plasma experiments are empirical neighbors of that upgrade."),
        ("blue-laser", "High-rep laser–target ICF options—same confinement family as Marvel/HB11."),
        ("anubal", "High-rep laser–target ICF options—same confinement family as Marvel/HB11."),
        ("probono", "Multi-facility experimental venues that could test compressed-degenerate catchers [9,10]."),
        ("fusion-project", "Multi-facility experimental venues that could test compressed-degenerate catchers [9,10]."),
    ]:
        conn.execute(
            "INSERT INTO hedp_degenerate_host (architecture_id, why_helps) VALUES (?, ?)",
            (aid(conn, slug), why),
        )

    for slug, fuel, capital, federal, web, outlook in [
        ("thea", "D–T stellarator (Eos/Helios)", "~$130 M private", "DOE Milestone Helios design certified (2026)", "Live (thea.energy)", "Build Eos; top-tier U.S. pilot-plant contender"),
        ("pale-blue-charm", "p–¹¹B CHARM mirror", "ARPA-E ~$1.5 M academic", "OPEN 2021 complete; no Milestone award under brand", "No public site (mid-2026)", "Incorporate + seed; theory→experiment risk"),
        ("pfs-pfrc", "D–³He PFRC", "Mostly non-dilutive (ARPA-E, NASA)", "OPEN, GAMOW, INFUSE", "Live (company site)", "Upgrade PFRC-2; seek PFRC-3 funding"),
    ]:
        conn.execute(
            """
            INSERT INTO pppl_spinout (
                architecture_id, fuel_machine, capital_signal, federal_milestone_signal,
                public_web_brand, outlook_2026_2030
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (aid(conn, slug), fuel, capital, federal, web, outlook),
        )

    # repo: public VCS or container registry when redistributable; NULL if closed/collab-only
    dt_tools = [
        (
            "dt-openmc",
            "Monte Carlo neutron/photon transport; CAD→DAGMC workflows",
            "Open source (MIT)",
            "conda install -c conda-forge openmc; Docker Hub: https://hub.docker.com/r/openmc/openmc ; docs: https://docs.openmc.org",
            "https://github.com/openmc-dev/openmc",
        ),
        (
            "dt-paramak",
            "Parametric 3D fusion CAD → neutronics geometry",
            "Open (MIT)",
            "pip / GitHub; docs: fusion-energy.github.io/paramak",
            "https://github.com/fusion-energy/paramak",
        ),
        (
            "dt-bluemira",
            "Integrated tokamak/FPP design framework",
            "Open LGPL-2.1+; commercial licence for larger orgs",
            "Clone + conda via project scripts; UKAEA contact for commercial licence",
            "https://github.com/Fusion-Power-Plant-Framework/bluemira",
        ),
        (
            "dt-process",
            "0D–1D systems code often driven by Bluemira",
            "Open (see repo)",
            "Installable as Bluemira extra [process]",
            "https://github.com/ukaea/PROCESS",
        ),
        (
            "dt-warpx",
            "Exascale PIC; industrial rapid-iteration loops",
            "Open (BSD-style; DOE ECP lineage)",
            "Spack/containers common",
            "https://github.com/ECP-WarpX/WarpX",
        ),
        (
            "dt-karat",
            "Fully electromagnetic PIC for NVD/IEC p–¹¹B",
            "Proprietary / closed",
            "Collaboration with code author / user groups",
            None,
        ),
        (
            "dt-xie-fusionbook",
            "Open 0D Lawson / power-balance scripts",
            "Open (GitHub)",
            "Also http://hsxie.me/fusionbook",
            "https://github.com/hsxie/fusionbook",
        ),
        (
            "dt-charm-stack",
            "Specialized nonthermal / multi-chamber / radiative FP tools",
            "Academic / not productized",
            "ARPA-E materials; collaboration with Princeton authors",
            None,
        ),
        (
            "dt-freda",
            "Whole-facility plasma+engineering digital-twin framework",
            "Federal R&D; mostly open umbrella",
            "DOE/ORNL SciDAC collaboration — not a public self-serve repo",
            None,
        ),
        (
            "dt-omniverse",
            "Visualization / collaborative digital twin of plants",
            "Closed / commercial",
            "NVIDIA Omniverse licence / lab partnerships",
            None,
        ),
        (
            "dt-nuplant",
            "End-to-end FPP design with AI surrogates",
            "Closed platform + services",
            "nttaudigital.com",
            None,
        ),
        (
            "dt-fusionalpha",
            "AI simulator to test reactor designs before hardware",
            "Closed startup product (seed)",
            "Company/press channels (mid-2026)",
            None,
        ),
        (
            "dt-mcnp",
            "Gold-standard Monte Carlo",
            "Export-controlled / licensed (LANL)",
            "RSICC / institutional licence",
            None,
        ),
    ]
    for pslug, claim, lic, access, repo in dt_tools:
        conn.execute(
            """
            INSERT INTO digital_twin_tool (prototype_id, claim, license_openness, access_how, repo)
            VALUES (?, ?, ?, ?, ?)
            """,
            (pid(conn, pslug), claim, lic, access, repo),
        )

    legal = [
        ("Pale Blue Fusion", "Not registered", "No Pale Blue Fusion entity found", "No clear brand hit", "Still plan to incorporate; IP with Princeton inventors"),
        ("Thea Energy", "Live (thea.energy)", "Delaware / NJ operating company (2022 spinout)", "Brand in commerce", "Strongest Princeton-house T footprint"),
        ("Princeton Fusion Systems", "Live", "Affiliate of Princeton Satellite Systems", "—", "Long-running small-business line"),
        ("TAE Technologies", "Live (tae.com)", "Long-standing CA corp (ex Tri Alpha)", "Active brand", "Deepest private fusion IP portfolio in this survey"),
        ("Helion Energy", "Live (helionenergy.com)", "WA company", "Active brand", "Largest capitalized sister-fuel IP bench"),
        ("HB11 Energy", "Live", "Australian company", "—", "IP narrative via Hora / UJK lineage patents"),
        ("Blue Laser Fusion", "Live", "CA corp", "—", "Rapid 2023–2025 patenting under company assignee"),
        ("Marvel Fusion", "Live", "German GmbH", "—", "Core nano-target U.S. application via Hora Cited by"),
        ("LPPFusion", "Live", "Lawrenceville Plasma Physics, Inc.", "—", "Classic DPF patent still the flagship"),
        ("Avalanche Energy", "Live (avalanchefusion.com)", "WA company", "Active brand", "Orbitron MEC; FusionWERX; under-indexed USPTO crawl"),
        ("Joint Institute for High Temperatures of the Russian Academy of Sciences", "Lab program", "Russian Academy institute line", "—", "Miniature NVD–IEC; not a venture spinout"),
        ("Anubal Fusion", "Early", "—", "—", "No assignee hits in this pass"),
        ("ENN Energy Research Institute", "Live (CN)", "ENN Energy Research Institute", "—", "CNIPA bilingual pass still needed"),
    ]
    for ent, domain, corp, tm, notes in legal:
        conn.execute(
            """
            INSERT INTO legal_footprint (entity_id, domain_status, corp_entity, uspto_trademark, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (eid(conn, ent), domain, corp, tm, notes),
        )

def seed_patents(conn: sqlite3.Connection) -> None:
    patents = [
        ("US 12,620,498 B2", "Planar coil stellarator", "Princeton University", "Trustees of Princeton University; Gates, Zhu, Hammond", 51),
        ("US 12,537,109 B2", "Planar coil stellarator", "Princeton University", "Princeton University continuation family", 52),
        ("US 12,451,260 B2", "Planar coil stellarator including removable field shaping units", "Thea Energy", "Thea Energy, Inc. (company-assigned grant)", None),
        ("US 12,562,286 B2", "System and method for stellarator neutron source", "Princeton University", "Princeton University (Eos/neutron-source track)", None),
        ("US 2024/0395446 A1", "Stellarators using arrays of permanent magnets", "Princeton University", "Princeton University published application", None),
        ("US 9,767,925 B2", "Reduce neutron production in small clean fusion reactors", "Princeton University", "Princeton University; Cohen", 57),
        ("US 10,923,236 B2", "System and method for small, clean, steady-state fusion reactors", "Princeton University", "Princeton University; Cohen", None),
        ("US 10,811,159 B2", "Fueling method for small, steady-state, aneutronic FRC fusion reactors", "Princeton University", "Princeton University", None),
        ("US 9,822,769 B2", "High specific impulse / moderate thrust (DFD-related)", "Princeton Satellite Systems", "Princeton Satellite Systems", None),
        ("US 10,229,756 B2", "In-space startup method for nuclear fusion rocket engines", "Princeton Satellite Systems", "Princeton Satellite Systems, Inc.", None),
        ("US 2025/0324504 A1", "Ultra-high DC voltages in open field line traps", "Princeton University", "Inventors Fisch et al.; assignee Princeton University", 33),
        ("US 19/083,790", "Nonthermal p–¹¹B with separated reactant regions", "Princeton University", "Filed 19 Mar 2025; not yet published A1 in survey pass", 33),
        ("US 19/084,168", "Positive/negative ponderomotive potentials", "Princeton University", "Filed 19 Mar 2025; publication pending", 33),
        ("US 63/794,470", "Differential confinement / mixing / demixing", "Princeton University", "Provisional filed 25 Apr 2025", 33),
        ("US 2004/0213368 A1", "Fusion reactor that produces net power from the p–¹¹B reaction", "University of California", "Rostoker & Monkhorst; abandoned; cited as prior art", 79),
        ("US 4,894,199", "Beam fusion device and method", "University of California", "Norman Rostoker; cited in TAE FRC grant prior-art list", None),
        ("US 10,438,702 B2", "Forming and maintaining a high-performance FRC", "TAE Technologies", "Tae Technologies, Inc.", 58),
        ("US 11,929,182 B2", "Improved sustainment of high-performance FRC", "TAE Technologies", "Tae Technologies (Binderbauer lineage)", None),
        ("US 11,469,003 B2", "Advanced fuel cycle and fusion reactors utilizing the same", "Helion Energy", "Helion Energy, Inc. (Slough, Kirtley, Pihl)", 80),
        ("US 10,410,752 B2", "Laser-based nuclear fusion and laser reactor", "UJK Management GmbH", "UJK Management GmbH; Hora", 60),
        ("WO 2022/040329 A1", "Opto-mechanic driven laser-boron fusion", "HB11 Energy", "Heinrich Hora", None),
        ("WO 2019/101991 A1", "Clean energy from nuclear reactions in a reactor", "HB11 Energy", "Heinrich Hora", None),
        ("US 7,482,607 B2", "X-rays, ion beams and nuclear fusion energy (DPF)", "LPPFusion", "Lawrenceville Plasma Physics, Inc.", 61),
        ("EP 1 989 714 B1", "Same DPF family (EU grant)", "LPPFusion", "Corresponds to US 7,482,607 lineage", None),
        ("US 12,416,822 B1", "DBR mirror laser extraction with piezoelectric layer", "Blue Laser Fusion", "Blue Laser Fusion, Inc.", 62),
        ("US 12,387,853 B1", "Synchronized light source for laser fusion", "Blue Laser Fusion", "Blue Laser Fusion, Inc.", None),
        ("US 12,597,527 B1", "Fuel pellet with internal reflection", "Blue Laser Fusion", "Blue Laser Fusion, Inc.", None),
        ("US 12,597,528 B1", "Single-laser synchronized source", "Blue Laser Fusion", "Blue Laser Fusion, Inc.", None),
        ("US 12,476,014 B1", "Reduced neutron emission target for fusion energy generation", "Blue Laser Fusion", "Blue Laser Fusion, Inc.", None),
        ("US 2025/0182915 A1", "Solid target structure with low ignition temperature", "Blue Laser Fusion", "Blue Laser Fusion, Inc.", None),
        ("US 2024/0158106 A1", "Satellite laser fusion system and method", "Blue Laser Fusion", "Blue Laser Fusion Inc.", None),
        ("US 2023/0073280 A1", "Target for triggering nuclear fusion reactions non-thermally", "Marvel Fusion", "Marvel Fusion GmbH", None),
        ("EP 4 506 734 A1", "Method for analyzing a solid-state nuclear track detector", "Marvel Fusion", "Marvel Fusion GmbH (diagnostics)", None),
        ("US 2015/0380114 A1", "Confining high-energy charged particles in magnetic cusp configuration", "Energy Matter Conversion Corporation", "EMC2; cited in Princeton planar-coil citations", None),
        ("US 9,967,963 B2", "Plasma magnetic-field control", "General Fusion", "General Fusion Inc.", None),
        ("US 10,811,144 B2", "Plasma generation and compression", "General Fusion", "General Fusion Inc.", None),
        ("US 2020/0075178 A1", "Rotating high-density fusion reactor for aneutronic and neutronic fusion", None, "Alfred Y. Wong", None),
    ]
    for number, title, ent, notes, ref in patents:
        conn.execute(
            """
            INSERT INTO patent (number, title_short, entity_id, assignee_notes, reference_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (number, title, eid(conn, ent) if ent else None, notes, ref),
        )

    def patent_id(number: str) -> int:
        row = conn.execute("SELECT id FROM patent WHERE number = ?", (number,)).fetchone()
        if not row:
            raise KeyError(number)
        return row[0]

    citation_seeds = [
        ("US 10,438,702 B2", "cited", "US 4,894,199", "Rostoker beam fusion"),
        ("US 10,438,702 B2", "cited", "US 2004/0213368 A1", "Rostoker/Monkhorst p–¹¹B net-power app"),
        ("US 10,438,702 B2", "citing", None, "Mostly TAE family continuations; General Fusion / Princeton heat-loss FRC neighbors"),
        ("US 7,482,607 B2", "citing", None, "General Fusion compression; Zap Energy Z-pinch; Beam Alpha; Wong rotating aneutronic"),
        ("US 10,410,752 B2", "citing", "US 2023/0073280 A1", "Marvel nonthermal target"),
        ("US 10,410,752 B2", "citing", "US 12,416,822 B1", "Blue Laser Fusion laser/target grants neighborhood"),
        ("US 12,620,498 B2", "cited", "US 9,767,925 B2", "Cohen/PFS neutron-reduction"),
        ("US 12,620,498 B2", "cited", "US 2015/0380114 A1", "EMC2 cusp"),
        ("US 12,620,498 B2", "citing", "US 12,451,260 B2", "Thea company FSU grant"),
        ("US 10,923,236 B2", "citing", None, "Helion cites PSS DFD WO in fuel-cycle neighborhood"),
        ("US 11,469,003 B2", "citing", None, "Establishes Helion as main D–³He commercial assignee"),
        ("US 2025/0324504 A1", "cited", None, "Young A1: no populated Patent Citations table yet"),
    ]
    for seed, direction, related, desc in citation_seeds:
        conn.execute(
            """
            INSERT INTO patent_citation_edge (
                seed_patent_id, direction, related_patent_id, related_description
            ) VALUES (?, ?, ?, ?)
            """,
            (
                patent_id(seed),
                direction,
                patent_id(related) if related else None,
                desc,
            ),
        )


# ---------------------------------------------------------------------------
# References ingest + architecture citation links
# ---------------------------------------------------------------------------


ARCH_REF_MAP: dict[str, list[int]] = {
    "enn": [6, 12, 22, 38, 39],
    "tae": [5, 35, 36, 37, 89],
    "lhd-nifs": [15],
    "hb11": [2, 7, 81, 82, 83, 84, 90, 91],
    "marvel": [8, 91],
    "xjtu-cn-hedp": [12, 27, 91],
    "blue-laser": [91],
    "anubal": [91],
    "probono": [9, 41, 42],
    "fusion-project": [10],
    "pale-blue-charm": [29, 30, 31, 32, 33],
    "nanjing-mucf": [11],
    "thea": [46, 47, 48, 49, 50],
    "pfs-pfrc": [54, 55, 56, 57],
    "helion": [77, 78],
    "avalanche": [66, 67, 87],
    "jiht-nvd": [85, 86, 88],
    "lppfusion": [4, 61],
    "degenerate-catcher": [91],
    "catania-avalanche": [43],
    "radiation-trapping": [3],
}


def ingest_references(conn: sqlite3.Connection, md: str) -> None:
    refs = parse_references(md)
    for ref in refs:
        conn.execute(
            """
            INSERT INTO reference (id, year, title, venue, doi, url, raw_text, is_patent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ref["id"],
                ref["year"],
                ref["title"],
                ref["venue"],
                ref["doi"],
                ref["url"],
                ref["raw_text"],
                ref["is_patent"],
            ),
        )
        pos = 1
        for author in ref["authors"]:
            ent_id = resolve_entity(conn, author)
            if ent_id is None:
                kind = "other_org" if looks_like_org(author) else "person"
                # Prefer company/lab/university when org-like
                if looks_like_org(author):
                    lower = author.lower()
                    if "university" in lower:
                        kind = "university"
                    elif any(x in lower for x in ("laboratory", "institute", "infn", "nifs", "ornl")):
                        kind = "lab"
                    elif any(x in lower for x in ("inc", "gmbh", "ltd", "corp", "technologies", "energy", "fusion", "systems")):
                        kind = "company"
                    else:
                        kind = "other_org"
                ent_id = ensure_entity(conn, normalize_person_or_org(author), kind)
            conn.execute(
                """
                INSERT INTO reference_author (reference_id, entity_id, author_position, is_etal)
                VALUES (?, ?, ?, 0)
                """,
                (ref["id"], ent_id, pos),
            )
            # If org authored the reference, also record organization role
            kind_name = conn.execute(
                """
                SELECT ek.name FROM entity e
                JOIN entity_kind ek ON ek.id = e.kind_id
                WHERE e.id = ?
                """,
                (ent_id,),
            ).fetchone()[0]
            if kind_name != "person":
                conn.execute(
                    """
                    INSERT OR IGNORE INTO reference_organization (reference_id, entity_id, role)
                    VALUES (?, ?, 'author_org')
                    """,
                    (ref["id"], ent_id),
                )
            pos += 1
        if ref["has_etal"]:
            # Sentinel et al. marker row (no entity) skipped — store flag on last author
            if pos > 1:
                conn.execute(
                    """
                    UPDATE reference_author SET is_etal = 1
                    WHERE reference_id = ? AND author_position = ?
                    """,
                    (ref["id"], pos - 1),
                )

    for slug, ref_ids in ARCH_REF_MAP.items():
        for rid in ref_ids:
            conn.execute(
                """
                INSERT OR IGNORE INTO architecture_reference (architecture_id, reference_id)
                VALUES (?, ?)
                """,
                (aid(conn, slug), rid),
            )


def seed_mentions(conn: sqlite3.Connection) -> None:
    """Organizational / program mentions beyond formal lead links."""
    rows = [
        ("Microsoft", "Helion offtake narrative", "helion", None, 77),
        ("Google", "TAE plasma-control software collaboration", "tae", "norman", 89),
        ("Crusoe", "Avalanche multi-cloud WarpX/HPC partner", "avalanche", "dt-warpx", 67),
        ("Colorado State University", "Marvel laser facility host", "marvel", "marvel-csu", None),
        ("ARPA-E", "OPEN 2021 CHARM / Pale Blue funding", "pale-blue-charm", None, 33),
        ("ARPA-E", "PFS OPEN / GAMOW / INFUSE awards", "pfs-pfrc", None, None),
        ("NASA", "PFS non-dilutive funding", "pfs-pfrc", None, None),
        ("U.S. Department of Energy", "Thea Helios Milestone certification", "thea", "helios", 50),
        ("U.S. Department of Energy", "Blue Laser Fusion INFUSE award", "blue-laser", None, 63),
        ("PROBONO COST Action CA21128", "HB11 ecosystem participation", "hb11", None, 41),
        ("ELI Beamlines", "HB11 collaborative network / Catania workshops", "hb11", None, 41),
        ("PALS laser facility", "FUSION Project / HB11 yield records", "fusion-project", None, 90),
        ("UK Atomic Energy Authority", "Omniverse digital-twin evaluation", "thea", "dt-omniverse", 64),
        ("Zap Energy", "Cited-by neighborhood of LPPFusion DPF patent", "lppfusion", None, None),
        ("General Fusion", "Cited in Princeton/Thea stellarator patent citations", "thea", None, None),
        ("Energy Matter Conversion Corporation", "EMC2 cusp prior art cited by Princeton planar-coil", "thea", None, None),
        ("Kronos Fusion Energy", "Staged fuel roadmap (sister fuels table)", None, None, None),
        ("Stellar Furnace", "Early DPF company messaging (sister fuels table)", None, None, None),
        ("LH3M", "Lunar ³He supply-chain entity", None, None, None),
        ("Magna Petra", "Lunar ³He supply-chain entity", None, None, None),
        ("CAEP / IAPCM", "Laser-field cross-section enhancement calculation [92]", None, None, 92),
        ("USTC Press", "Publisher of Xie zeroth-order monograph [40]", None, None, 40),
        ("FusionWERX", "Avalanche industry test facility", "avalanche", "fusionwerx", 87),
        ("VeloAlpha", "FusionAlpha AI digital-twin startup founded by H. Xie", None, "dt-fusionalpha", 75),
        ("nTtau Digital", "NuPlant closed FPP design platform", None, "dt-nuplant", 73),
        ("NVIDIA", "Omniverse plant digital twins", None, "dt-omniverse", 64),
        ("OpenMC Development Team", "Open neutronics stack", None, "dt-openmc", 69),
        ("WarpX community", "Open PIC stack used by Avalanche", "avalanche", "dt-warpx", 67),
        ("Oak Ridge National Laboratory", "FREDA SciDAC framework", None, "dt-freda", 68),
        ("Los Alamos National Laboratory", "MCNP licensing authority", None, "dt-mcnp", None),
        ("Catania α-avalanche MCF (imputed)", "Imputed plant-odds path [43]", "catania-avalanche", "imp-catania", 43),
    ]
    for ent, ctx, arch, proto, ref in rows:
        conn.execute(
            """
            INSERT INTO mention (entity_id, context, architecture_id, prototype_id, reference_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                eid(conn, ent),
                ctx,
                aid(conn, arch) if arch else None,
                pid(conn, proto) if proto else None,
                ref,
            ),
        )


def verify(conn: sqlite3.Connection) -> None:
    checks = {
        "references": "SELECT COUNT(*) FROM reference",
        "entities": "SELECT COUNT(*) FROM entity",
        "persons": "SELECT COUNT(*) FROM entity e JOIN entity_kind k ON k.id=e.kind_id WHERE k.name='person'",
        "orgs": "SELECT COUNT(*) FROM entity e JOIN entity_kind k ON k.id=e.kind_id WHERE k.name!='person'",
        "architectures": "SELECT COUNT(*) FROM architecture",
        "prototypes": "SELECT COUNT(*) FROM prototype",
        "digital_twins": "SELECT COUNT(*) FROM prototype p JOIN prototype_kind k ON k.id=p.kind_id WHERE k.name='digital_twin'",
        "gate_scores": "SELECT COUNT(*) FROM architecture_gate_score",
        "plant_odds": "SELECT COUNT(*) FROM plant_odds",
        "patents": "SELECT COUNT(*) FROM patent",
        "authors_linked": "SELECT COUNT(*) FROM reference_author",
        "plant_specs": "SELECT COUNT(*) FROM plant_spec",
    }
    print("Catalog DB summary:")
    for label, sql in checks.items():
        n = conn.execute(sql).fetchone()[0]
        print(f"  {label}: {n}")
    missing = conn.execute(
        """
        SELECT r.id FROM reference r
        LEFT JOIN reference_author ra ON ra.reference_id = r.id
        WHERE ra.reference_id IS NULL
        ORDER BY r.id
        """
    ).fetchall()
    if missing:
        print(f"  WARNING: references with no authors: {[m[0] for m in missing]}")


def main() -> None:
    md = SOURCE.read_text(encoding="utf-8")
    conn = connect(DB_PATH)
    try:
        seed_static(conn)
        seed_organizations(conn)
        seed_architectures(conn)
        seed_plant_specs(conn)
        seed_gate_scores(conn)
        seed_plant_odds(conn)
        seed_prototypes(conn)
        seed_secondary_tables(conn)
        ingest_references(conn, md)
        seed_patents(conn)
        seed_mentions(conn)
        conn.commit()
        verify(conn)
        print(f"Wrote {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
