# CHARM p-11B SSTO paper — Zenodo / figure build
#
# AI figures: prompts are source of truth under research/figures/prompts/.
# PNGs are cached; regenerated only when prompt hash changes AND AI_IMAGE_CMD
# is set (or FORCE_AI_FIGURES=1). Prototyping in Cursor: GenerateImage →
# update .prompt.txt → `make ai-stamp`.

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PROMPTS_DIR := $(ROOT)/research/figures/prompts
FIGURES_DIR := $(ROOT)/research/figures

AI_STEMS := charm_ssto_interior_floorplan charm_ssto_exterior_profile
AI_PROMPTS := $(addprefix $(PROMPTS_DIR)/,$(addsuffix .prompt.txt,$(AI_STEMS)))
AI_PNGS := $(addprefix $(FIGURES_DIR)/,$(addsuffix .png,$(AI_STEMS)))

.PHONY: help ai-figures ai-stamp zenodo zenodo-tex zenodo-pdf zenodo-zip arxiv clean-figures

help:
	@echo "Targets:"
	@echo "  make zenodo       - ai-figures (cached) + zenodo.pdf + dist/zenodo_submit.zip"
	@echo "  make zenodo-tex   - arxiv.md → zenodo.tex (+ mermaid/assets)"
	@echo "  make ai-figures   - refresh PNGs from prompts if stale (needs AI_IMAGE_CMD to regen)"
	@echo "  make ai-stamp     - stamp .ai.meta for committed PNGs after Cursor GenerateImage"
	@echo "  make arxiv        - optional local arxiv.pdf package"
	@echo "  FORCE_AI_FIGURES=1 make ai-figures  - force remote regen when AI_IMAGE_CMD is set"

ai-figures: $(AI_PNGS)

$(FIGURES_DIR)/%.png: $(PROMPTS_DIR)/%.prompt.txt
	python3 $(ROOT)/scripts/render_ai_figure.py $<

ai-stamp:
	@for p in $(AI_PROMPTS); do \
	  python3 $(ROOT)/scripts/render_ai_figure.py --stamp $$p; \
	done

zenodo-tex: ai-figures
	$(ROOT)/scripts/build_zenodo_tex.sh

zenodo-pdf: zenodo-tex
	cd $(ROOT) && latexmk -pdf -interaction=nonstopmode -jobname=zenodo zenodo.tex

zenodo-zip:
	$(ROOT)/scripts/package_zenodo.sh --zip-only

zenodo: ai-figures
	$(ROOT)/scripts/rebuild_zenodo.sh

arxiv:
	bash $(ROOT)/scripts/build_arxiv_pdf.sh

clean-figures:
	rm -rf $(ROOT)/figures/figure-*.pdf $(ROOT)/figures/figure-*.mmd $(ROOT)/figures/figure-*.meta
	rm -rf $(ROOT)/figures/assets
