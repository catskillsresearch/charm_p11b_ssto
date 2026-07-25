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

### Drop-in cutaways (Blender)

```bash
make cad-drop-ins        # crew capsule + airlock + cargo skid
# or individually:
make cad-crew-capsule    # → research/figures/crew_capsule_top.png + cad/crew_capsule_cutaway.blend
make cad-airlock         # → research/figures/airlock_top.png + cad/airlock_cutaway.blend
make cad-cargo-skid      # → research/figures/cargo_skid_top.png + cad/cargo_skid_cutaway.blend
./bl.sh   # open the crew-capsule .blend in the GUI
```

Each figure has its own placement script, all reading `assembly.json` directly and sharing helpers from `lib/`:

```text
research/figures/cad/
├── lib/
│   ├── assembly_parser.py       # load_assembly, find_node_in_doc, envelope/port lookups
│   ├── procedural_geometry.py   # box/cylinder/text_label primitives +
│   │                            #   pressure_shell, ring_hatch, hinged_door_leaf,
│   │                            #   clamshell_bay_door, tank, tie_down_grid kits
│   └── render_utils.py          # clear_scene, render_to, setup_topdown_camera
├── build_crew_capsule_blender.py
├── build_airlock_blender.py
└── build_cargo_skid_blender.py
```

Not AI — every hatch, seat row, tank, and door is placed procedurally from `assembly.json` station/envelope data, using the reusable kits in `lib/procedural_geometry.py` so hatch and shell geometry isn't reinvented per figure.

**Engineering-drawing style.** `render_to()` renders with Freestyle outlines on by default (`lib/render_utils.py`, `enable_technical_outline`) and lights have shadows disabled, so parts read as flat vector-style fills with crisp black edges rather than soft-shaded 3D primitives. Labels use three annotation kits from `lib/procedural_geometry.py` instead of bare floating text:

- `callout()` — a dot on the part, a leader line, and text at the end (most part labels)
- `dimension_line()` — extension lines + a measurement line + centered text (overall length/width)
- `legend()` — a stacked color-swatch key for the figure's subsystem materials

Each figure computes its own camera `cam_y`/`ortho_scale` explicitly in `main()` (via `setup_topdown_camera`) to fit its actual annotation bounds — the legend, dimension lines, and parked roof cover/title text make every composition asymmetric, so the naive symmetric-footprint default undershoots the frame.

The fusion-plant skid (CHARM chambers) and combined-cycle engine skid (scoops/duct/nozzle/water tanks) are **not yet** migrated to this pattern — they need genuinely new procedural geometry with no library equivalent, and are tracked as a follow-up.

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
