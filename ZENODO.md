# Zenodo deposit (p11b CHARM SSTO note)

## Metadata: `.zenodo.json` is authoritative

| File | Role |
|------|------|
| **`.zenodo.json`** | Resource type, LOC subjects, keywords, creators, license, GitHub link, version |
| `CITATION.cff` | GitHub “Cite this repository” only |

## Build

```bash
make zenodo                 # CAD figures + zenodo.pdf + dist/zenodo_submit.zip
make install-openvsp        # once: official OpenVSP .deb + Poetry API
make cad-figures            # rebuild floorplan/profile via OpenVSP
```

### Vehicle figures (CAD)

| Artifact | Role |
|----------|------|
| `research/figures/cad/stations.json` | Shared station map (length / bay extents) |
| `research/figures/cad/build_ssto_openvsp.py` | OpenVSP driver (`.vsp3` + top/side orthographics) |
| `research/figures/cad/stations.json` | Shared station / OML truth |
| `research/figures/charm_ssto_*.png` | Paper assets (committed; rebuild with `make cad-figures`) |

Mermaid diagrams still render on every TeX build (with their own `.meta` cache under `figures/`).

## Upload

1. `make zenodo`
2. https://zenodo.org/deposit/new
3. Upload `dist/zenodo_submit.zip` (`zenodo.pdf` + `.zenodo.json`)

Source: https://github.com/catskillsresearch/p11b
