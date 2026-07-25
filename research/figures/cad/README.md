# CATSKILLS-SSTO CAD

## Sources of truth

| File | Role |
|------|------|
| [`assembly.json`](assembly.json) | **Geometry / topology** — hierarchy, ports, joints, sizes, station labels |
| [`assembly_hierarchy.mmd`](assembly_hierarchy.mmd) | Mermaid of that tree (`python emit_assembly_mermaid.py`) |
| [`vehicle_spec.json`](vehicle_spec.json) | Temporary OpenVSP *implementation* binding (builders); not the product tree |
| [`constants_model.py`](constants_model.py) | **Numeric sizing constraints** — numpy/dataclass model for the CHARM bottom-up mass roll-up (magnets, cryo) and the full `m_dry`/`mu`/`m_w`/`m0` chain; writes `constants.generated.json`, consumed by `arxiv.md`'s `<!--gen-->` spans, `assembly.json`, `vehicle_spec.json`, and `build_fusion_plant_skid_blender.py` |

```text
assembly.json  →  OpenVSP exterior (VSPAERO later)  →  .stl shell
               →  Blender cutaway / interior placement along the same tree
constants_model.py (numpy)  →  constants.generated.json  →  arxiv.md <!--gen--> spans
                                                          →  assembly.json / vehicle_spec.json size blocks
                                                          →  build_fusion_plant_skid_blender.py magnet/cryo counts
```

### Generated numeric constants

```bash
make paper-constants   # constants_model.py → constants.generated.json
make paper-render      # paper-constants + regenerate arxiv.md <!--gen--> spans + patch assembly.json/vehicle_spec.json
```

`research/figures/cad/constants_model.py` is the single numpy/stdlib source for every derived number in `arxiv.md` §6–§9 (CHARM magnet/cryo bottom-up mass, `m_dry`, `mu`, `m_w`, `m0`, the sensitivity table) — plain arithmetic, never an LLM call, per the "systematic, not vibe-computed" requirement. [`scripts/update_arxiv_constants.py`](../../scripts/update_arxiv_constants.py) regex-replaces only the text inside `<!--gen KEY:FMT-->...<!--/gen-->` markers in `arxiv.md`, leaving prose untouched. [`scripts/apply_constants_to_assembly.py`](../../scripts/apply_constants_to_assembly.py) patches `assembly.json`'s `mirror_magnets`/`cryocooler`/`charm` `size` blocks and `vehicle_spec.json`'s `charm` station `mass_t_ref` the same way — assembly.json via structural JSON edits (targeted node lookups, not a full-file rewrite, since the file's formatting already round-trips through `json.dump`), vehicle_spec.json via a targeted regex patch (its hand-formatted compact-array style does **not** round-trip through `json.dump`, so only the one numeric span is touched). `make arxiv` and `make zenodo-tex` both depend on `paper-render`, so every paper build re-derives these numbers from scratch — they can never silently drift from the JSON SSOT or the Blender renders.

### Drop-in cutaways (Blender)

```bash
make cad-drop-ins        # crew capsule + airlock + cargo skid + fusion plant skid
# or individually:
make cad-crew-capsule    # → research/figures/crew_capsule_top.png + cad/crew_capsule_cutaway.blend
make cad-airlock         # → research/figures/airlock_top.png + cad/airlock_cutaway.blend
make cad-cargo-skid      # → research/figures/cargo_skid_top.png + cad/cargo_skid_cutaway.blend
make cad-fusion-skid     # → research/figures/fusion_plant_skid_top.png + cad/fusion_plant_skid_cutaway.blend
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
├── constants_model.py
├── build_crew_capsule_blender.py
├── build_airlock_blender.py
├── build_cargo_skid_blender.py
└── build_fusion_plant_skid_blender.py
```

Not AI — every hatch, seat row, tank, and door is placed procedurally from `assembly.json` station/envelope data, using the reusable kits in `lib/procedural_geometry.py` so hatch and shell geometry isn't reinvented per figure.

**Engineering-drawing style.** `render_to()` renders with Freestyle outlines on by default (`lib/render_utils.py`, `enable_technical_outline`) and lights have shadows disabled, so parts read as flat vector-style fills with crisp black edges rather than soft-shaded 3D primitives. Labels use three annotation kits from `lib/procedural_geometry.py` instead of bare floating text:

- `callout()` — a dot on the part, a leader line, and text at the end (most part labels)
- `dimension_line()` — extension lines + a measurement line + centered text (overall length/width)
- `legend()` — a stacked color-swatch key for the figure's subsystem materials

Each figure computes its own camera `cam_y`/`ortho_scale` explicitly in `main()` (via `setup_topdown_camera`) to fit its actual annotation bounds — the legend, dimension lines, and parked roof cover/title text make every composition asymmetric, so the naive symmetric-footprint default undershoots the frame.

`build_fusion_plant_skid_blender.py` additionally imports `constants_model.py` directly (`compute(Params()).values`) for its magnet count/mass and cryocooler count/mass/power, so the rendered figure's callout text can never disagree with `arxiv.md` §9.6 or `assembly.json`'s `mirror_magnets`/`cryocooler` nodes.

The combined-cycle engine skid (scoops/duct/nozzle/water tanks) is **not yet** migrated to this pattern — it needs genuinely new procedural geometry with no library equivalent, and is tracked as a follow-up.

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
