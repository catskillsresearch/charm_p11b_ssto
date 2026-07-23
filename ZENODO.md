# Zenodo deposit (p11b CHARM SSTO note)

## Metadata: `.zenodo.json` is authoritative

| File | Role |
|------|------|
| **`.zenodo.json`** | Resource type, LOC subjects, keywords, creators, license, GitHub link, version |
| `CITATION.cff` | GitHub “Cite this repository” only |

## Build

```bash
make zenodo                 # AI figures (cached) + zenodo.pdf + dist/zenodo_submit.zip
make ai-stamp               # after Cursor GenerateImage tweaks: stamp prompt↔PNG hashes
FORCE_AI_FIGURES=1 AI_IMAGE_CMD='...' make ai-figures   # optional remote regen
```

### AI figures (self-documenting)

| Artifact | Role |
|----------|------|
| `research/figures/prompts/<stem>.prompt.txt` | Full generation prompt (= PDF caption via `![@prompt](...)`) |
| `research/figures/<stem>.png` | Cached raster (committed) |
| `research/figures/<stem>.ai.meta` | SHA-256 of prompt that produced the PNG |

Mermaid diagrams still render on every TeX build (with their own `.meta` cache under `figures/`). AI PNGs regenerate **only** when the prompt hash is stale **and** `AI_IMAGE_CMD` is set—so paper builds stay fast while you iterate prompts in Cursor.

## Upload

1. `make zenodo`
2. https://zenodo.org/deposit/new
3. Upload `dist/zenodo_submit.zip` (`zenodo.pdf` + `.zenodo.json`)

Source: https://github.com/catskillsresearch/p11b
