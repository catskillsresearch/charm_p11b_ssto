# CATSKILLS-SSTO CAD

## Sources of truth

| File | Role |
|------|------|
| [`assembly.json`](assembly.json) | **Geometry / topology** — hierarchy, ports, joints, sizes, station labels |
| [`assembly_hierarchy.mmd`](assembly_hierarchy.mmd) | Mermaid of that tree (`python emit_assembly_mermaid.py`) |
| [`lib/mermaid_builder.py`](lib/mermaid_builder.py) | Shared visible-set/nearest-ancestor Mermaid renderer — one algorithm behind `assembly_hierarchy.mmd`, the interactive outliner, and arxiv.md Figs. 7–9 |
| [`vehicle_spec.json`](vehicle_spec.json) | Temporary OpenVSP *implementation* binding (builders); not the product tree |
| [`constants_model.py`](constants_model.py) | **Numeric sizing constraints** — numpy/dataclass model for the CHARM bottom-up mass roll-up (magnets, cryo) and the full `m_dry`/`mu`/`m_w`/`m0` chain; writes `constants.generated.json`, consumed by `arxiv.md`'s `<!--gen-->` spans, `assembly.json`, `vehicle_spec.json`, and `build_fusion_plant_skid_blender.py` |

```text
assembly.json  →  OpenVSP exterior  →  .stl shell
               →  VSPAERO digital tunnel (`make cad-vspaero` → `vspaero/`)
               →  SU2 coarse Euler (`make su2-ssto`) / OpenFOAM snappy (`make cad-snappy`)
               →  Blender cutaway / interior placement along the same tree
constants_model.py (numpy)  →  constants.generated.json  →  arxiv.md <!--gen--> spans
                                                          →  assembly.json / vehicle_spec.json size blocks
                                                          →  build_fusion_plant_skid_blender.py magnet/cryo counts
                                                          →  stage2_climb_check.png
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

The combined-cycle engine skid (scoops/duct/nozzle) is **not yet** migrated to this pattern — it needs genuinely new procedural geometry with no library equivalent, and is tracked as a follow-up. Its water reaction-mass tanks were relocated to the CHARM skid (§9.9 radiation-shield buffer), so this figure no longer carries bulk tankage.

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

### Mermaid figures in arxiv.md (Figs. 7–9)

`arxiv.md`'s three embedded diagrams — the fusion-plant schematic (Fig. 7), the
profile-station tree (Fig. 8), and the top-down floorplan (Fig. 9) — are no
longer hand-authored text. Each is generated straight from `assembly.json` by
[`lib/mermaid_builder.py`](lib/mermaid_builder.py) (a Python port of the
interactive outliner's `buildMermaid()`/`nearestVisible()` in
[`hierarchy_app/app.js`](hierarchy_app/app.js)), so the same visible-set
algorithm draws all three: `assembly_hierarchy.mmd`, the interactive outliner,
and the paper figures.

```text
assembly.json + emit_paper_mermaid.py's FIGURES specs
  → lib/mermaid_builder.build_mermaid()
  → scripts/update_arxiv_mermaid.py regenerates the
    <!--mermaid-gen KEY-->...<!--/mermaid-gen--> blocks in arxiv.md in place
```

Two things the paper figures use that the other two consumers don't:

- **Hard scope + boundary stubs** (`scope_root=` in `emit_paper_mermaid.FigureSpec`) — Fig. 7 is scoped to `charm_power_plant`'s own subtree; any real joint that leaves it (e.g. the water duct and power cable to the combined-cycle engine) is drawn as a small dashed `"→ Combined-cycle engine"` stub instead of pulling the external assembly's parts into the figure.
- **Functional-joint filtering** (`FUNCTIONAL_JOINT_TYPES` in `lib/mermaid_builder.py`) — paper figures only draw joints that carry a real resource/signal flow (fuel, power, coolant, RF, crew passage, …), dropping the ~80 purely mechanical "bolted to" mounts that `assembly_hierarchy.mmd` and the interactive outliner still show in full.

Each figure's `(scope_root, expand_ids, direction)` is an explicit spec in
[`emit_paper_mermaid.py`](emit_paper_mermaid.py) — the non-interactive
equivalent of clicking through the outliner's expand/collapse twisties.
Preview all three on stdout:

```bash
poetry run python research/figures/cad/emit_paper_mermaid.py
```

`make paper-render` runs `scripts/update_arxiv_mermaid.py` as its last step
(after `assembly.json` has been patched with the latest magnet/cryo counts),
so every paper build re-derives Figs. 7–9 from the live JSON tree — they can
no longer silently drift the way the old hand-written blocks did.

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
make cad-vspaero       # VSPAERO Mach×α polar → vspaero/{summary.json,polar.csv,polar.png}
```

`run_vspaero_tunnel.py` deletes landing-gear pods from a working copy, builds thin-surface DegenGeom, and sweeps \(\alpha\in\{0,4,8\}^\circ\) at \(M\in\{0.3,0.6,0.8,0.95\}\). Raw solver files stay under `vspaero/run/` (gitignored); the committed artifacts are the summary/CSV/plot used by §10.2.1.
