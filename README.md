# SSTO fusion powered spaceplane using compact CHARM fusion reactor and 3-cycle electric rocket engine

Systems-engineering paper and CAD/mass-closure toolchain for a single-stage-to-orbit (SSTO)
spaceplane that flies Space Shuttle–style operations — including a Shuttle-class cargo bay — from
a municipal airport to International Space Station (ISS) altitude in low Earth orbit (LEO),
powered by a continuous Chambered Aneutronic Rotating Mirror (CHARM) \(p\text{-}^{11}\mathrm{B}\)
plant with direct energy conversion (DEC) driving a three-stage combined-cycle electric engine
(ducted fan → microwave air plasma → carried-water plasma).

This is the **vehicle-integration** paper: it guesstimates the reactor mass hole, constrains water
as a function of dry mass and vacuum \(\Delta v\), imposes a 1 GW plant with space restart and DEC,
and solves a reference all-up mass, station layout, and outer mold line. The reactor and engine
each have their own dedicated, deeper-derivation companion papers (below).

**Read the paper:** [`arxiv.pdf`](arxiv.pdf) (source: [`arxiv.md`](arxiv.md)).

## Companion papers

This vehicle paper is one of three companion papers that together describe the CHARM-powered SSTO
spaceplane:

- **charm_p11b_ssto** (this repo) — the integrated vehicle: mass/energy budget, flight regimes,
  water/shielding sizing equations, station layout, and the solved reference vehicle that the
  reactor and engine below are sized against.
- **[charm_compact_p11b](https://github.com/catskillsresearch/charm_compact_p11b)** — "Compact
  CHARM p-¹¹B fusion reactor for electricity generation for aerospace propulsion": the bottom-up
  reactor engineering chapter (magnet/cryo/shield mass roll-up, fuel/ash, restart, recirculating
  power, safety) in full derivation.
- **[electric_3_stage_ssto_engine](https://github.com/catskillsresearch/electric_3_stage_ssto_engine)**
  — "Three cycle electric SSTO rocket engine": the combined-cycle engine in full derivation (stage
  map, VSPAERO/OpenFOAM/SU2 aero checks, stage 1/2/3 sizing, closed solve, envelope, acoustic
  signature, ascent profile).

This repo's §9 (CHARM power plant) and §10 (combined-cycle engine) are short summaries that cite
the two companion papers for the full derivations; the itemized unobtainium lists for the reactor
and engine live there too.

## Repository layout

- [`arxiv.md`](arxiv.md) — paper source (Markdown with LaTeX math spans and Mermaid diagrams).
- [`research/figures/cad/constants_model.py`](research/figures/cad/constants_model.py) — single
  numeric source of truth (plain NumPy, no fitting) spanning reactor + engine + vehicle math.
- `research/figures/cad/build_*_blender.py` — procedural Blender builds of the vehicle drop-in
  cutaway figures (crew capsule, airlock, cargo skid, fusion-plant skid) from `assembly.json`.
- `research/figures/` — vehicle CAD figures (floorplan, exterior profile, AI concept renders) and
  provenance in [`research/figures/CREDITS.md`](research/figures/CREDITS.md).
- `scripts/` — paper build pipeline (`build_arxiv_pdf.sh`, `update_arxiv_constants.py`,
  `update_arxiv_mermaid.py`, `apply_constants_to_assembly.py`, `ai_model_cards.py`).

## Building the paper

```bash
poetry install
make cad-figures    # OpenVSP/Blender vehicle CAD renders (requires OpenVSP; see make install-openvsp)
make paper-render   # regenerate <!--gen--> numeric spans + mermaid figures
make arxiv          # -> arxiv.pdf
make zenodo         # -> zenodo.pdf + dist/zenodo_submit.zip
```

Requires a local LaTeX toolchain (`latexmk` + LuaLaTeX), Pandoc, and the Mermaid CLI (`mmdc`) for
figure rendering; see [`.latexmkrc`](.latexmkrc).

## License

Apache-2.0 (see [`LICENSE`](LICENSE)). See [`NOTICE`](NOTICE) for AI-assisted development
disclosures.
