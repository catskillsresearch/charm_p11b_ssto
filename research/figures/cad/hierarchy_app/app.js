/**
 * Blender-like outliner + Mermaid view of assembly.json
 * All subtrees start collapsed; click twisty or name to expand/collapse.
 */
(() => {
  const CONTAIN = "#9a9a9a";
  const CONNECT = "#0d7a6f";

  /**
   * Soft fills for neighboring expanded siblings (and their descendant parts).
   * Distinct enough to pick out stage-1 / 2 / 3 without adding subgraph boxes.
   */
  const SIBLING_TINTS = [
    { fill: "#e4f0e2", stroke: "#4f7a48", text: "#1e3320" }, // sage
    { fill: "#e2f1f4", stroke: "#3d6f7c", text: "#1a3036" }, // teal mist
    { fill: "#f5efe3", stroke: "#8a6e42", text: "#3a2e18" }, // sand
    { fill: "#f3e8e8", stroke: "#8a5558", text: "#3a1e20" }, // rose dust
    { fill: "#eceedf", stroke: "#6a7a40", text: "#2a3218" }, // olive
    { fill: "#ebe8f2", stroke: "#5a5578", text: "#242038" }, // slate lilac
  ];

  /** @type {any} */
  let assembly = null;
  /** @type {Map<string, any>} */
  const byId = new Map();
  /** @type {Set<string>} nodes that are expanded (children visible) */
  const expanded = new Set();
  let selected = "vehicle";

  const treePane = document.getElementById("tree-pane");
  const statusEl = document.getElementById("status");
  const mermaidSrc = document.getElementById("mermaid-src");

  function indexTree(node, parentId = null) {
    byId.set(node.id, { node, parentId });
    for (const ch of node.children || []) indexTree(ch, node.id);
  }

  function hasChildren(node) {
    return Array.isArray(node.children) && node.children.length > 0;
  }

  /** Organizational bag of parts — not a single physical item (e.g. Fuselage, Whole vehicle). */
  function isCollection(node) {
    return node.kind === "assembly" || node.collection === true;
  }

  /** Visible iff every ancestor is expanded (root always visible). */
  function isVisible(id) {
    let cur = id;
    while (true) {
      const entry = byId.get(cur);
      if (!entry) return false;
      if (entry.parentId == null) return true;
      if (!expanded.has(entry.parentId)) return false;
      cur = entry.parentId;
    }
  }

  function collectVisibleIds() {
    const ids = [];
    function walk(node) {
      if (!isVisible(node.id)) return;
      ids.push(node.id);
      if (expanded.has(node.id)) {
        for (const ch of node.children || []) walk(ch);
      }
    }
    walk(assembly.root);
    return ids;
  }

  function esc(s) {
    return String(s).replace(/"/g, "'").replace(/</g, "&lt;");
  }

  /** Mermaid treats ()[]{}|/ in edge labels as shape syntax — keep labels plain. */
  function escEdgeLabel(s) {
    return esc(s)
      .replace(/[()[\]{}|/]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  /** Walk up to the nearest visible ancestor (or self). */
  function nearestVisible(id, vis) {
    let cur = id;
    while (cur) {
      if (vis.has(cur)) return cur;
      const entry = byId.get(cur);
      if (!entry || entry.parentId == null) return null;
      cur = entry.parentId;
    }
    return null;
  }

  /**
   * Color neighboring siblings under the same expanded parent differently;
   * descendants inherit the nearest tinted ancestor so a whole stage reads as one wash.
   * @returns {Map<string, number>}
   */
  function computeSiblingTints(visible) {
    const vis = new Set(visible);
    /** @type {Map<string, number>} */
    const tintRoot = new Map();
    /** @type {Map<string, string[]>} */
    const kidsByParent = new Map();

    for (const id of visible) {
      const { parentId } = byId.get(id);
      if (!parentId || !vis.has(parentId)) continue;
      if (!kidsByParent.has(parentId)) kidsByParent.set(parentId, []);
      kidsByParent.get(parentId).push(id);
    }

    for (const kids of kidsByParent.values()) {
      if (kids.length < 2) continue;
      kids.forEach((id, i) => {
        tintRoot.set(id, i % SIBLING_TINTS.length);
      });
    }

    /** @type {Map<string, number>} */
    const tintOf = new Map();
    for (const id of visible) {
      let cur = id;
      while (cur) {
        if (tintRoot.has(cur)) {
          tintOf.set(id, tintRoot.get(cur));
          break;
        }
        const entry = byId.get(cur);
        if (!entry || entry.parentId == null) break;
        cur = entry.parentId;
      }
    }
    return tintOf;
  }

  function buildMermaid(visible) {
    const vis = new Set(visible);
    const tintOf = computeSiblingTints(visible);
    const lines = [
      "flowchart TB",
      `  linkStyle default stroke:${CONTAIN},stroke-width:1.5px`,
      "  classDef collection fill:#e7eef8,stroke:#5a6f8c,stroke-width:1.8px,stroke-dasharray:6 4,color:#243447",
      "  classDef part fill:#ffffff,stroke:#333,stroke-width:1.5px,color:#222",
    ];
    SIBLING_TINTS.forEach((t, i) => {
      lines.push(
        `  classDef tint${i}c fill:${t.fill},stroke:${t.stroke},stroke-width:1.8px,stroke-dasharray:6 4,color:${t.text}`,
      );
      lines.push(
        `  classDef tint${i}p fill:${t.fill},stroke:${t.stroke},stroke-width:1.5px,color:${t.text}`,
      );
    });

    let nContain = 0;
    /** @type {Map<string, string[]>} className -> ids */
    const classBuckets = new Map();

    function bucket(cls, id) {
      if (!classBuckets.has(cls)) classBuckets.set(cls, []);
      classBuckets.get(cls).push(id);
    }

    for (const id of visible) {
      const { node } = byId.get(id);
      const label = node.label || id;
      const coll = isCollection(node);
      if (coll) {
        lines.push(`  ${id}(["${esc(label)}"])`);
      } else {
        lines.push(`  ${id}["${esc(label)}"]`);
      }
      const ti = tintOf.get(id);
      if (ti != null) {
        bucket(coll ? `tint${ti}c` : `tint${ti}p`, id);
      } else {
        bucket(coll ? "collection" : "part", id);
      }
    }
    for (const [cls, ids] of classBuckets) {
      lines.push(`  class ${ids.join(",")} ${cls}`);
    }

    for (const id of visible) {
      const { parentId } = byId.get(id);
      if (parentId && vis.has(parentId) && vis.has(id)) {
        lines.push(`  ${parentId} --> ${id}`);
        nContain += 1;
      }
    }

    lines.push("  %% connections");
    let nConnect = 0;
    const seen = new Set();
    const jointWords = {
      module_seat: "sits inside",
      pressure_hatch: "pressure door",
      skin_cutout: "cut into skin",
      fixed: "bolted to",
      revolute: "hinged to",
      duct: "duct to",
      keel_mount: "keel-mounted aft of",
      floor_mount: "bolted to floor of",
      umbilical: "power cable",
      power_cable: "power cable",
      alpha_path: "alphas to DEC",
      rf_feed: "waveguides to",
      waveguide: "waveguides to",
      magnet_bus: "magnet leads to",
      magnet_power: "powers",
      coolant_loop: "coolant loop",
      cryo_cool: "cools",
      fuel_feed: "feed to",
      solid_feed: "solid feed to",
      startup_power: "startup power",
      rotation_drive: "rotation drive",
      chamber_neck: "necks into",
    };
    for (const j of assembly.joints || []) {
      const aReal = j.a.split(".")[0];
      const bReal = j.b.split(".")[0];
      if (aReal === bReal) continue;
      const aDisp = nearestVisible(aReal, vis);
      const bDisp = nearestVisible(bReal, vis);
      if (!aDisp || !bDisp || aDisp === bDisp) continue;
      const key = [aReal, bReal, j.type].sort().join("|");
      if (seen.has(key)) continue;
      seen.add(key);
      const edgeLabel = jointWords[j.type] || j.type;
      lines.push(`  ${aDisp} ==>|${escEdgeLabel(edgeLabel)}| ${bDisp}`);
      nConnect += 1;
    }

    if (nContain) {
      const idx = Array.from({ length: nContain }, (_, i) => i).join(",");
      lines.push(
        `  linkStyle ${idx} stroke:${CONTAIN},stroke-width:1.5px,color:${CONTAIN}`,
      );
    }
    if (nConnect) {
      const idx = Array.from(
        { length: nConnect },
        (_, i) => nContain + i,
      ).join(",");
      lines.push(
        `  linkStyle ${idx} stroke:${CONNECT},stroke-width:2.5px,color:${CONNECT}`,
      );
    }

    return { src: lines.join("\n"), nContain, nConnect, nNodes: visible.length };
  }

  function renderTree() {
    treePane.innerHTML = "";
    const root = document.createElement("div");
    const tintOf = computeSiblingTints(collectVisibleIds());

    function addRow(node, depth) {
      const row = document.createElement("div");
      const collection = isCollection(node);
      row.className =
        "row" +
        (collection ? " collection" : "") +
        (node.id === selected ? " selected" : "");
      row.style.paddingLeft = `${0.25 + depth * 0.9}rem`;
      const ti = tintOf.get(node.id);
      if (ti != null) {
        const t = SIBLING_TINTS[ti];
        row.style.borderLeft = `3px solid ${t.stroke}`;
        row.dataset.tint = String(ti);
      }

      const twisty = document.createElement("span");
      twisty.className = "twisty" + (hasChildren(node) ? "" : " leaf");
      const open = expanded.has(node.id);
      twisty.textContent = hasChildren(node) ? (open ? "▼" : "▶") : "·";
      twisty.title = open ? "Collapse" : "Expand";
      twisty.addEventListener("click", (e) => {
        e.stopPropagation();
        toggle(node.id);
      });

      const label = document.createElement("span");
      label.className = "label" + (collection ? " collection-label" : "");
      label.textContent = node.label || node.id;
      label.addEventListener("click", () => {
        selected = node.id;
        if (hasChildren(node)) toggle(node.id);
        else {
          renderTree();
          renderDiagram();
        }
      });

      row.appendChild(twisty);
      row.appendChild(label);
      if (collection) {
        const bag = document.createElement("span");
        bag.className = "collection-badge";
        bag.textContent = "collection";
        bag.title = "Organizational group — not a single physical part";
        row.appendChild(bag);
      } else if (node.kind) {
        const k = document.createElement("span");
        k.className = "kind";
        k.textContent = node.kind;
        row.appendChild(k);
      }
      root.appendChild(row);

      if (hasChildren(node) && expanded.has(node.id)) {
        for (const ch of node.children) addRow(ch, depth + 1);
      }
    }

    addRow(assembly.root, 0);
    treePane.appendChild(root);
  }

  function toggle(id) {
    if (!hasChildren(byId.get(id).node)) return;
    if (expanded.has(id)) expanded.delete(id);
    else expanded.add(id);
    selected = id;
    renderTree();
    renderDiagram();
  }

  async function renderDiagram() {
    const visible = collectVisibleIds();
    const { src, nContain, nConnect, nNodes } = buildMermaid(visible);
    statusEl.textContent = `${nNodes} parts shown · ${nContain} containment · ${nConnect} connections`;

    const wrap = document.getElementById("mermaid-wrap");
    wrap.innerHTML = "";
    const pre = document.createElement("pre");
    pre.className = "mermaid";
    pre.textContent = src;
    wrap.appendChild(pre);

    const mermaid = window.__mermaid;
    if (!mermaid) {
      statusEl.textContent = "Loading diagram engine…";
      return;
    }
    try {
      const id = `mmd-${Date.now()}`;
      const { svg } = await mermaid.render(id, src);
      wrap.innerHTML = svg;
    } catch (err) {
      wrap.innerHTML = `<pre style="color:#800">${esc(String(err))}\n\n${esc(src)}</pre>`;
    }
  }

  function collapseAll() {
    expanded.clear();
    renderTree();
    renderDiagram();
  }

  function expandTop() {
    expanded.clear();
    expanded.add(assembly.root.id);
    renderTree();
    renderDiagram();
  }

  function expandAll() {
    expanded.clear();
    for (const id of byId.keys()) {
      if (hasChildren(byId.get(id).node)) expanded.add(id);
    }
    renderTree();
    renderDiagram();
  }

  document.getElementById("btn-collapse-all").onclick = collapseAll;
  document.getElementById("btn-expand-one").onclick = expandTop;
  document.getElementById("btn-expand-all").onclick = expandAll;
  document.getElementById("btn-reload").onclick = () => boot({ preserveExpand: true });

  async function boot(opts = {}) {
    const preserveExpand = !!opts.preserveExpand;
    const prevExpanded = preserveExpand ? new Set(expanded) : null;
    const prevSelected = preserveExpand ? selected : null;

    const res = await fetch(`../assembly.json?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`Failed to load assembly.json (${res.status})`);
    assembly = await res.json();
    byId.clear();
    indexTree(assembly.root);

    expanded.clear();
    if (prevExpanded) {
      for (const id of prevExpanded) {
        if (byId.has(id) && hasChildren(byId.get(id).node)) expanded.add(id);
      }
    }
    if (!expanded.size) {
      // Start fully collapsed — only the whole vehicle row
    }
    selected =
      prevSelected && byId.has(prevSelected) ? prevSelected : assembly.root.id;

    const plant = [...byId.values()].find(
      (e) => e.node.id === "charm_power_plant",
    )?.node;
    const plantBits = (plant?.children || []).map((c) => c.label).join(", ");

    const start = () => {
      renderTree();
      renderDiagram();
      const nFunc = (assembly.joints || []).filter((j) =>
        [
          "alpha_path",
          "waveguide",
          "fuel_feed",
          "solid_feed",
          "magnet_power",
          "magnet_bus",
          "cryo_cool",
          "coolant_loop",
          "startup_power",
          "rotation_drive",
          "power_cable",
        ].includes(j.type),
      ).length;
      const rev = assembly.meta?.rev || "unversioned";
      const revEl = document.getElementById("data-rev");
      if (revEl) {
        revEl.textContent =
          `Data rev ${rev} · ${nFunc} functional links · Fusion plant: ${plantBits || "(missing)"}`;
      }
      statusEl.textContent =
        `${statusEl.textContent} · loaded ${new Date().toLocaleTimeString()} · rev ${rev}`;
    };
    if (window.__mermaid) start();
    else window.addEventListener("mermaid-ready", start, { once: true });
  }

  boot().catch((err) => {
    statusEl.textContent = String(err);
    treePane.textContent =
      "Could not load ../assembly.json. Serve the cad/ folder over HTTP (see serve script).";
  });
})();
