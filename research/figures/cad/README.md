# CATSKILLS-SSTO CAD

## Sources of truth

| File | Role |
|------|------|
| [`assembly.json`](assembly.json) | **Geometry / topology** — hierarchy, ports, joints, sizes, station labels |
| [`assembly_hierarchy.mmd`](assembly_hierarchy.mmd) | Mermaid of that tree (`python emit_assembly_mermaid.py`) |
| [`vehicle_spec.json`](vehicle_spec.json) | Temporary OpenVSP *implementation* binding (builders); not the product tree |

```text
assembly.json  →  OpenVSP exterior (VSPAERO later)  →  .stl shell
               →  Blender cutaway / interior placement along the same tree
```

## Hierarchy idea

- **Drop-in modules:** `crew_capsule`, `airlock`, `cargo_bay`
- **Leaves:** captain chair, galley, hatch, elevon, …
- **Joints:** named ports (`crew_capsule.hatch_aft` ↔ `airlock.hatch_fwd`)

Regenerate diagram:

```bash
poetry run python research/figures/cad/emit_assembly_mermaid.py
```

## Interactive outliner (Blender-style hierarchy)

Left: expand/collapse tree (starts fully collapsed). Right: Mermaid of only the
visible parts (grey = contains, teal = connects). No extra npm packages — plain
HTML/JS + Mermaid CDN.

```bash
./research/figures/cad/serve_hierarchy_app.sh
# open http://127.0.0.1:8765/hierarchy_app/
```

## Build (OpenVSP figures)

```bash
make install-openvsp   # once
make cad-figures
make cad-validate
```
