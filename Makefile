# CHARM p-11B SSTO paper — Zenodo / figure build
#
# Vehicle figures: OpenVSP CAD from research/figures/cad/ (stations.json +
# build_ssto_openvsp.py). Mermaid diagrams still render on every TeX build.

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
FIGURES_DIR := $(ROOT)/research/figures
CAD_DIR := $(FIGURES_DIR)/cad
CAD_SCRIPT := $(CAD_DIR)/build_ssto_openvsp.py
CAD_SPEC := $(CAD_DIR)/vehicle_spec.json
CAD_STATIONS := $(CAD_DIR)/stations.json
OPENVSP_LIB := $(ROOT)/third_party/openvsp/sysdeps/usr/lib/x86_64-linux-gnu
POETRY ?= poetry

CAD_STEMS := charm_ssto_interior_floorplan charm_ssto_exterior_profile
CAD_PNGS := $(addprefix $(FIGURES_DIR)/,$(addsuffix .png,$(CAD_STEMS)))

.PHONY: help cad-figures install-openvsp zenodo zenodo-tex zenodo-pdf zenodo-zip arxiv clean-figures

help:
	@echo "Targets:"
	@echo "  make zenodo          - cad-figures + zenodo.pdf + dist/zenodo_submit.zip"
	@echo "  make zenodo-tex      - arxiv.md → zenodo.tex (+ mermaid/assets)"
	@echo "  make cad-figures     - vehicle_spec → OpenVSP (+constraints) → figures"
	@echo "  make cad-validate    - re-check .vsp3 against JSON constraints"
	@echo "  make cad-outliner    - Blender-style assembly hierarchy browser"
	@echo "  make install-openvsp - download Ubuntu .deb + poetry openvsp group"
	@echo "  make arxiv           - optional local arxiv.pdf package"

install-openvsp:
	$(ROOT)/scripts/install_openvsp.sh

CAD_VALIDATE := $(CAD_DIR)/validate_vehicle_constraints.py

cad-figures: $(CAD_PNGS)

cad-validate:
	@test -f $(CAD_DIR)/catskills_ssto.vsp3 || (echo "No .vsp3; run make cad-figures" >&2; exit 1)
	cd $(CAD_DIR) && \
	  LD_LIBRARY_PATH="$(OPENVSP_LIB)$${LD_LIBRARY_PATH:+:$$LD_LIBRARY_PATH}" \
	  $(POETRY) run python $(CAD_VALIDATE)

cad-outliner:
	@echo "Open http://127.0.0.1:8765/hierarchy_app/"
	$(CAD_DIR)/serve_hierarchy_app.sh

$(CAD_PNGS): $(CAD_SCRIPT) $(CAD_SPEC) $(CAD_VALIDATE)
	@test -d $(ROOT)/third_party/openvsp/opt/OpenVSP/python/openvsp || \
	  (echo "OpenVSP not extracted. Run: make install-openvsp" >&2; exit 1)
	cd $(CAD_DIR) && \
	  LD_LIBRARY_PATH="$(OPENVSP_LIB)$${LD_LIBRARY_PATH:+:$$LD_LIBRARY_PATH}" \
	  $(POETRY) run python $(CAD_SCRIPT)

zenodo-tex: cad-figures
	$(ROOT)/scripts/build_zenodo_tex.sh

zenodo-pdf: zenodo-tex
	cd $(ROOT) && latexmk -pdf -interaction=nonstopmode -jobname=zenodo zenodo.tex

zenodo-zip:
	$(ROOT)/scripts/package_zenodo.sh --zip-only

zenodo: cad-figures
	$(ROOT)/scripts/rebuild_zenodo.sh

arxiv:
	bash $(ROOT)/scripts/build_arxiv_pdf.sh

clean-figures:
	rm -rf $(ROOT)/figures/figure-*.pdf $(ROOT)/figures/figure-*.mmd $(ROOT)/figures/figure-*.meta
	rm -rf $(ROOT)/figures/assets
