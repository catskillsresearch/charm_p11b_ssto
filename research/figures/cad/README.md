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

### Crew capsule cutaway (Blender)

```bash
make cad-crew-capsule
# → research/figures/crew_capsule_top.png
# → research/figures/cad/crew_capsule_cutaway.blend
./bl.sh   # open the .blend in the GUI
```

Script: [`build_crew_capsule_blender.py`](build_crew_capsule_blender.py) — primitives from `assembly.json`, orthographic top-down. Not AI.

### Reusable source assets

[`assets/manifest.json`](assets/manifest.json) records every downloaded model's
source, reuse terms, checksum, and mapped `assembly.json` part. The first
verified import is NASA's Crew Lock Bag GLB, used for cabin stowage. Downloaded
marketplace/BlenderKit assets are excluded because their reuse terms do not
allow committing editable source models to this repository.

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
