/**
 * Blender-like outliner + Mermaid view of assembly.json
 * All subtrees start collapsed; click twisty or name to expand/collapse.
 */
(() => {
  const CONTAIN = "#9a9a9a";
  const CONNECT = "#0d7a6f";

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

  function buildMermaid(visible) {
    const vis = new Set(visible);
    const lines = [
      "flowchart TB",
      `  linkStyle default stroke:${CONTAIN},stroke-width:1.5px`,
      "  classDef collection fill:#e7eef8,stroke:#5a6f8c,stroke-width:1.8px,stroke-dasharray:6 4,color:#243447",
      "  classDef part fill:#ffffff,stroke:#333,stroke-width:1.5px,color:#222",
    ];
    let nContain = 0;
    const collectionIds = [];
    const partIds = [];

    for (const id of visible) {
      const { node } = byId.get(id);
      const label = node.label || id;
      if (isCollection(node)) {
        lines.push(`  ${id}(["${esc(label)}"])`);
        collectionIds.push(id);
      } else {
        lines.push(`  ${id}["${esc(label)}"]`);
        partIds.push(id);
      }
    }
    if (collectionIds.length) {
      lines.push(`  class ${collectionIds.join(",")} collection`);
    }
    if (partIds.length) {
      lines.push(`  class ${partIds.join(",")} part`);
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

    function addRow(node, depth) {
      const row = document.createElement("div");
      const collection = isCollection(node);
      row.className =
        "row" +
        (collection ? " collection" : "") +
        (node.id === selected ? " selected" : "");
      row.style.paddingLeft = `${0.25 + depth * 0.9}rem`;

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

  async function boot() {
    const res = await fetch("../assembly.json");
    if (!res.ok) throw new Error(`Failed to load assembly.json (${res.status})`);
    assembly = await res.json();
    byId.clear();
    indexTree(assembly.root);
    // Start fully collapsed — only the whole vehicle row (and empty diagram of just root)
    expanded.clear();
    selected = assembly.root.id;

    const start = () => {
      renderTree();
      renderDiagram();
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
