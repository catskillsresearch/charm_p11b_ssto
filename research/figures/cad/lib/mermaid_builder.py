# SPDX-License-Identifier: Apache-2.0
"""Shared Mermaid emission for assembly.json-derived figures.

Ported from `research/figures/cad/hierarchy_app/app.js`'s `buildMermaid()` /
`nearestVisible()` (the interactive outliner's renderer), so the standalone
`assembly_hierarchy.mmd` export and the paper figures (Figs. 7-9 in
`arxiv.md`) share exactly one node/edge-styling and visible-set algorithm
instead of three hand-rolled ones.

New here (not in the JS original): a **hard-scope** mode. When `scope_root`
is given to `build_mermaid`, only descendants of that node count as real,
drawable nodes — any joint whose other endpoint falls outside `scope_root`'s
subtree is rendered as a small dashed **boundary stub** (e.g. `"-> Combined
-cycle engine"`) instead of pulling the external part's box into the
figure. This is what lets a single-assembly figure (e.g. Fig. 7, scoped to
`charm_power_plant`) show that a connection leaves the assembly without
drawing lines to parts that live outside its own scope.
"""

from __future__ import annotations

CONTAIN_STROKE = "#9a9a9a"
CONNECT_STROKE = "#0d7a6f"
BOUNDARY_STROKE = "#9a5a3a"

# Same set of human-readable joint-type words used by app.js's buildMermaid()
# and emit_assembly_mermaid.py (kept in sync here as the one shared copy).
JOINT_WORDS = {
    "module_seat": "sits inside",
    "pressure_hatch": "pressure door",
    "skin_cutout": "cut into skin",
    "fixed": "bolted to",
    "revolute": "hinged to",
    "duct": "duct to",
    "keel_mount": "keel-mounted aft of",
    "floor_mount": "bolted to floor of",
    "aligns_with": "aligns with",
    "umbilical": "power cable",
    "power_cable": "power cable",
    "alpha_path": "alphas to DEC",
    "rf_feed": "waveguides to",
    "waveguide": "waveguides to",
    "magnet_bus": "magnet leads to",
    "magnet_power": "powers",
    "coolant_loop": "coolant loop",
    "cryo_cool": "cools",
    "fuel_feed": "feed to",
    "solid_feed": "solid feed to",
    "startup_power": "startup power",
    "rotation_drive": "rotation drive",
    "chamber_neck": "necks into",
    "air_path": "air path",
    "cryo_line": "cryo line",
    "fan_exhaust": "fan exhaust to",
    "he_ash_dump": "He ash to",
    "microwave": "microwave feed",
    "plasma_exhaust": "plasma exhaust to",
    "power": "powers",
    "propellant_feed": "propellant feed",
    "vacuum": "vacuum line",
}

#: Joint types that represent a resource/signal *flow* (fuel, power, RF,
#: coolant, vacuum, crew passage, ...) as opposed to pure mechanical mounting
#: ("fixed", "revolute", "floor_mount", "module_seat", "skin_cutout",
#: "contains", "rf_wall"). Paper figures use this to only draw the
#: connections that carry real information — assembly.json's ~80 structural
#: bolt-together joints would otherwise bury the handful of interesting
#: functional links under noise (the interactive outliner and
#: `assembly_hierarchy.mmd` intentionally do *not* apply this filter, so
#: every real joint is still inspectable there).
FUNCTIONAL_JOINT_TYPES = {
    "air_path",
    "alpha_path",
    "chamber_neck",
    "coolant_loop",
    "cryo_line",
    "cryo_cool",
    "duct",
    "fan_exhaust",
    "fuel_feed",
    "he_ash_dump",
    "magnet_bus",
    "magnet_power",
    "microwave",
    "plasma_exhaust",
    "power",
    "power_cable",
    "pressure_hatch",
    "propellant_feed",
    "rf_feed",
    "rotation_drive",
    "solid_feed",
    "startup_power",
    "umbilical",
    "vacuum",
    "waveguide",
}

SIBLING_TINTS = [
    {"fill": "#e4f0e2", "stroke": "#4f7a48", "text": "#1e3320"},  # sage
    {"fill": "#e2f1f4", "stroke": "#3d6f7c", "text": "#1a3036"},  # teal mist
    {"fill": "#f5efe3", "stroke": "#8a6e42", "text": "#3a2e18"},  # sand
    {"fill": "#f3e8e8", "stroke": "#8a5558", "text": "#3a1e20"},  # rose dust
    {"fill": "#eceedf", "stroke": "#6a7a40", "text": "#2a3218"},  # olive
    {"fill": "#ebe8f2", "stroke": "#5a5578", "text": "#242038"},  # slate lilac
]


def is_collection(node: dict) -> bool:
    """Organizational bag of parts — not a single physical item."""
    return node.get("kind") == "assembly" or node.get("collection") is True


def esc(s: str) -> str:
    return str(s).replace('"', "'").replace("<", "&lt;")


def esc_edge_label(s: str) -> str:
    """Mermaid treats ()[]{}|/ in edge labels as shape syntax — keep them plain."""
    out = esc(s)
    for ch in "()[]{}|/":
        out = out.replace(ch, " ")
    return " ".join(out.split())


def index_tree(root: dict) -> dict[str, dict]:
    """id -> {"node": node, "parent_id": id|None}, same shape as app.js's `byId`."""
    by_id: dict[str, dict] = {}

    def walk(node: dict, parent_id: str | None) -> None:
        by_id[node["id"]] = {"node": node, "parent_id": parent_id}
        for ch in node.get("children") or []:
            walk(ch, node["id"])

    walk(root, None)
    return by_id


def collect_visible_ids(
    root: dict,
    expanded_ids: set[str],
    *,
    start_id: str | None = None,
) -> list[str]:
    """Walk the tree collecting visible ids, mirroring app.js's `collectVisibleIds()`.

    A node is visible iff every ancestor between it and the walk's starting
    point is in `expanded_ids` (the starting point itself is always visible).
    `start_id` lets a figure scope its own "local root" (e.g. `charm_power_plant`)
    without needing that node's own ancestors to be expanded.
    """
    by_id = index_tree(root)
    start = start_id or root["id"]
    ids: list[str] = []

    def walk(node: dict) -> None:
        ids.append(node["id"])
        if node["id"] == start or node["id"] in expanded_ids:
            for ch in node.get("children") or []:
                walk(ch)

    start_node = by_id[start]["node"] if start_id else root
    walk(start_node)
    return ids


def nearest_visible(node_id: str, vis: set[str], by_id: dict[str, dict]) -> str | None:
    """Walk up to the nearest visible ancestor (or self)."""
    cur: str | None = node_id
    while cur is not None:
        if cur in vis:
            return cur
        entry = by_id.get(cur)
        if not entry:
            return None
        cur = entry["parent_id"]
    return None


def is_in_subtree(node_id: str, subtree_root_id: str, by_id: dict[str, dict]) -> bool:
    """True iff `node_id` is `subtree_root_id` or one of its descendants."""
    cur: str | None = node_id
    while cur is not None:
        if cur == subtree_root_id:
            return True
        entry = by_id.get(cur)
        cur = entry["parent_id"] if entry else None
    return False


def _sibling_ancestor(ext_id: str, target_parent_id: str | None, by_id: dict[str, dict]) -> str | None:
    """Walk up from `ext_id` to the ancestor whose parent is `target_parent_id`
    — i.e. the top-level "sibling subtree" of `scope_root` that owns `ext_id`.
    """
    cur: str | None = ext_id
    while cur is not None:
        entry = by_id.get(cur)
        if not entry:
            return None
        if entry["parent_id"] == target_parent_id:
            return cur
        cur = entry["parent_id"]
    return None


def compute_sibling_tints(visible: list[str], by_id: dict[str, dict]) -> dict[str, int]:
    """Port of app.js's `computeSiblingTints()`: color neighboring expanded
    siblings differently; descendants inherit the nearest tinted ancestor.
    """
    vis = set(visible)
    tint_root: dict[str, int] = {}
    kids_by_parent: dict[str, list[str]] = {}

    for node_id in visible:
        parent_id = by_id[node_id]["parent_id"]
        if not parent_id or parent_id not in vis:
            continue
        kids_by_parent.setdefault(parent_id, []).append(node_id)

    for kids in kids_by_parent.values():
        if len(kids) < 2:
            continue
        for i, node_id in enumerate(kids):
            tint_root[node_id] = i % len(SIBLING_TINTS)

    tint_of: dict[str, int] = {}
    for node_id in visible:
        cur: str | None = node_id
        while cur is not None:
            if cur in tint_root:
                tint_of[node_id] = tint_root[cur]
                break
            entry = by_id.get(cur)
            cur = entry["parent_id"] if entry else None
    return tint_of


def build_mermaid(
    assembly: dict,
    visible_ids: list[str],
    *,
    scope_root: str | None = None,
    direction: str = "TB",
    use_tints: bool = True,
    joint_words: dict[str, str] | None = None,
    include_joint_types: set[str] | None = None,
) -> dict:
    """Build a Mermaid `flowchart` source from a chosen visible-node set.

    Same node/edge conventions as app.js's `buildMermaid()`: grey thin
    containment arrows, teal thick connection arrows, dashed stadium shapes
    for organizational "collections". When `scope_root` is set, any joint
    reaching outside that node's subtree is drawn as a dashed brown
    **boundary stub** instead of pulling in the external part.

    `joint_words` overrides the shared `JOINT_WORDS` label dict for callers
    that need to preserve their own historical wording (e.g. the existing
    `assembly_hierarchy.mmd` export).

    `include_joint_types`, if given, restricts *connection* edges (both the
    normal in-scope kind and boundary stubs) to joints of those types —
    e.g. pass `FUNCTIONAL_JOINT_TYPES` to drop mechanical mounting noise
    from a figure without changing which nodes/containment are shown.

    Returns a dict: `{"src", "n_nodes", "n_contain", "n_connect", "n_boundary"}`.
    """
    words = joint_words if joint_words is not None else JOINT_WORDS
    root = assembly["root"]
    by_id = index_tree(root)
    vis = set(visible_ids)
    tint_of = compute_sibling_tints(visible_ids, by_id) if use_tints else {}
    scope_parent_id = by_id[scope_root]["parent_id"] if scope_root else None

    lines: list[str] = [
        f"flowchart {direction}",
        f"  linkStyle default stroke:{CONTAIN_STROKE},stroke-width:1.5px",
        "  classDef collection fill:#e7eef8,stroke:#5a6f8c,stroke-width:1.8px,stroke-dasharray:6 4,color:#243447",
        "  classDef part fill:#ffffff,stroke:#333,stroke-width:1.5px,color:#222",
    ]
    if scope_root is not None:
        lines.append(
            f"  classDef boundary fill:#f6ece4,stroke:{BOUNDARY_STROKE},stroke-width:1.5px,stroke-dasharray:3 3,color:#4a2e1c"
        )
    if use_tints:
        for i, t in enumerate(SIBLING_TINTS):
            lines.append(
                f"  classDef tint{i}c fill:{t['fill']},stroke:{t['stroke']},stroke-width:1.8px,stroke-dasharray:6 4,color:{t['text']}"
            )
            lines.append(
                f"  classDef tint{i}p fill:{t['fill']},stroke:{t['stroke']},stroke-width:1.5px,color:{t['text']}"
            )

    class_buckets: dict[str, list[str]] = {}

    def bucket(cls: str, node_id: str) -> None:
        class_buckets.setdefault(cls, []).append(node_id)

    for node_id in visible_ids:
        node = by_id[node_id]["node"]
        label = node.get("label", node_id)
        collection = is_collection(node)
        if collection:
            lines.append(f'  {node_id}(["{esc(label)}"])')
        else:
            lines.append(f'  {node_id}["{esc(label)}"]')
        ti = tint_of.get(node_id)
        if ti is not None:
            bucket(f"tint{ti}c" if collection else f"tint{ti}p", node_id)
        else:
            bucket("collection" if collection else "part", node_id)

    for cls, ids in class_buckets.items():
        lines.append(f"  class {','.join(ids)} {cls}")

    n_contain = 0
    for node_id in visible_ids:
        parent_id = by_id[node_id]["parent_id"]
        if parent_id and parent_id in vis:
            lines.append(f"  {parent_id} --> {node_id}")
            n_contain += 1

    lines.append("  %% connections")
    n_connect = 0
    seen: set[tuple] = set()
    seen_visual: set[tuple] = set()
    for j in assembly.get("joints") or []:
        a_real = j["a"].split(".")[0]
        b_real = j["b"].split(".")[0]
        if a_real == b_real:
            continue
        if include_joint_types is not None and j["type"] not in include_joint_types:
            continue
        if scope_root is not None:
            if not is_in_subtree(a_real, scope_root, by_id) or not is_in_subtree(b_real, scope_root, by_id):
                continue
        a_disp = nearest_visible(a_real, vis, by_id)
        b_disp = nearest_visible(b_real, vis, by_id)
        if not a_disp or not b_disp or a_disp == b_disp:
            continue
        key = tuple(sorted([a_real, b_real]) + [j["type"]])
        if key in seen:
            continue
        seen.add(key)
        edge_label = words.get(j["type"], j["type"])
        # Several distinct real joints (e.g. proton + boron feeds into two
        # chambers) can collapse to the same visible pair with the same
        # label once nearest_visible walks them up — draw that once.
        visual_key = tuple(sorted([a_disp, b_disp]) + [edge_label])
        if visual_key in seen_visual:
            continue
        seen_visual.add(visual_key)
        lines.append(f"  {a_disp} ==>|{esc_edge_label(edge_label)}| {b_disp}")
        n_connect += 1

    n_boundary = 0
    if scope_root is not None:
        boundary_nodes: dict[str, str] = {}
        boundary_seen: set[tuple] = set()
        for j in assembly.get("joints") or []:
            a_real = j["a"].split(".")[0]
            b_real = j["b"].split(".")[0]
            if a_real == b_real:
                continue
            if include_joint_types is not None and j["type"] not in include_joint_types:
                continue
            in_a = is_in_subtree(a_real, scope_root, by_id)
            in_b = is_in_subtree(b_real, scope_root, by_id)
            if in_a == in_b:
                continue  # both in scope (already drawn above) or both outside (irrelevant)
            inside_id, outside_id = (a_real, b_real) if in_a else (b_real, a_real)
            inside_disp = nearest_visible(inside_id, vis, by_id)
            if not inside_disp:
                continue
            sib = _sibling_ancestor(outside_id, scope_parent_id, by_id)
            if not sib:
                continue
            stub_id = boundary_nodes.get(sib)
            if stub_id is None:
                stub_id = f"_boundary_{sib}"
                boundary_nodes[sib] = stub_id
                sib_label = by_id[sib]["node"].get("label", sib)
                lines.append(f'  {stub_id}(("\u2192 {esc(sib_label)}"))')
                lines.append(f"  class {stub_id} boundary")
            key = (inside_disp, stub_id, j["type"])
            if key in boundary_seen:
                continue
            boundary_seen.add(key)
            edge_label = words.get(j["type"], j["type"])
            visual_key = (inside_disp, stub_id, edge_label)
            if visual_key in boundary_seen:
                continue
            boundary_seen.add(visual_key)
            lines.append(f"  {inside_disp} -.->|{esc_edge_label(edge_label)}| {stub_id}")
            n_boundary += 1

    if n_contain:
        idx = ",".join(str(i) for i in range(n_contain))
        lines.append(f"  linkStyle {idx} stroke:{CONTAIN_STROKE},stroke-width:1.5px,color:{CONTAIN_STROKE}")
    if n_connect:
        idx = ",".join(str(i) for i in range(n_contain, n_contain + n_connect))
        lines.append(f"  linkStyle {idx} stroke:{CONNECT_STROKE},stroke-width:2.5px,color:{CONNECT_STROKE}")
    if n_boundary:
        idx = ",".join(str(i) for i in range(n_contain + n_connect, n_contain + n_connect + n_boundary))
        lines.append(
            f"  linkStyle {idx} stroke:{BOUNDARY_STROKE},stroke-width:1.5px,stroke-dasharray:3 3,color:{BOUNDARY_STROKE}"
        )

    return {
        "src": "\n".join(lines),
        "n_nodes": len(visible_ids),
        "n_contain": n_contain,
        "n_connect": n_connect,
        "n_boundary": n_boundary,
    }
