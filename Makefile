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

BLENDER ?= /snap/bin/blender
CREW_BLEND_SCRIPT := $(CAD_DIR)/build_crew_capsule_blender.py
CREW_BLEND := $(CAD_DIR)/crew_capsule_cutaway.blend
CREW_PNG := $(FIGURES_DIR)/crew_capsule_top.png

AIRLOCK_BLEND_SCRIPT := $(CAD_DIR)/build_airlock_blender.py
AIRLOCK_BLEND := $(CAD_DIR)/airlock_cutaway.blend
AIRLOCK_PNG := $(FIGURES_DIR)/airlock_top.png

CARGO_BLEND_SCRIPT := $(CAD_DIR)/build_cargo_skid_blender.py
CARGO_BLEND := $(CAD_DIR)/cargo_skid_cutaway.blend
CARGO_PNG := $(FIGURES_DIR)/cargo_skid_top.png

FUSION_SKID_BLEND_SCRIPT := $(CAD_DIR)/build_fusion_plant_skid_blender.py
FUSION_SKID_BLEND := $(CAD_DIR)/fusion_plant_skid_cutaway.blend
FUSION_SKID_PNG := $(FIGURES_DIR)/fusion_plant_skid_top.png

CAD_LIB := $(CAD_DIR)/lib/assembly_parser.py $(CAD_DIR)/lib/procedural_geometry.py $(CAD_DIR)/lib/render_utils.py

CONSTANTS_MODEL := $(CAD_DIR)/constants_model.py
CONSTANTS_JSON := $(CAD_DIR)/constants.generated.json
UPDATE_ARXIV_CONSTANTS := $(ROOT)/scripts/update_arxiv_constants.py
APPLY_CONSTANTS_TO_ASSEMBLY := $(ROOT)/scripts/apply_constants_to_assembly.py
UPDATE_ARXIV_MERMAID := $(ROOT)/scripts/update_arxiv_mermaid.py

.PHONY: help cad-figures cad-vspaero smoke-stage1 smoke-stage2 cad-crew-capsule cad-airlock cad-cargo-skid cad-fusion-skid cad-drop-ins paper-constants paper-render install-openvsp zenodo zenodo-tex zenodo-pdf zenodo-zip arxiv clean-figures

help:
	@echo "Targets:"
	@echo "  make zenodo          - cad-figures + zenodo.pdf + dist/zenodo_submit.zip"
	@echo "  make zenodo-tex      - paper-render + arxiv.md → zenodo.tex (+ mermaid/assets)"
	@echo "  make paper-constants - constants_model.py (numpy) → constants.generated.json"
	@echo "  make paper-render    - paper-constants + regenerate arxiv.md <!--gen--> spans + patch assembly.json/vehicle_spec.json + regenerate Figs 7-9 mermaid from assembly.json"
	@echo "  make cad-vspaero     - OpenVSP/VSPAERO Mach×α digital tunnel → cad/vspaero/"
	@echo "  make smoke-stage1    - Stage 1 VSPAERO outline go/no-go (§10.2.1)"
	@echo "  make smoke-stage2    - Stage 2 climb/energy go/no-go (§10.4)"
	@echo "  make cad-figures     - vehicle_spec → OpenVSP (+constraints) → figures"
	@echo "  make cad-drop-ins    - crew capsule + airlock + cargo skid + fusion plant skid (Blender)"
	@echo "  make cad-crew-capsule - assembly.json → Blender crew cutaway PNG + .blend"
	@echo "  make cad-airlock     - assembly.json → Blender airlock cutaway PNG + .blend"
	@echo "  make cad-cargo-skid  - assembly.json → Blender cargo skid cutaway PNG + .blend"
	@echo "  make cad-fusion-skid - assembly.json + constants_model.py → Blender fusion plant skid PNG + .blend"
	@echo "  make cad-validate    - re-check .vsp3 against JSON constraints"
	@echo "  make cad-outliner    - Blender-style assembly hierarchy browser"
	@echo "  make install-openvsp - download Ubuntu .deb + poetry openvsp group"
	@echo "  make arxiv           - optional local arxiv.pdf package"

install-openvsp:
	$(ROOT)/scripts/install_openvsp.sh

CAD_VALIDATE := $(CAD_DIR)/validate_vehicle_constraints.py

cad-vspaero: $(CAD_DIR)/catskills_ssto.vsp3
	@test -d $(ROOT)/third_party/openvsp/opt/OpenVSP || \
	  (echo "OpenVSP not extracted. Run: make install-openvsp" >&2; exit 1)
	cd $(CAD_DIR) && \
	  LD_LIBRARY_PATH="$(OPENVSP_LIB)$${LD_LIBRARY_PATH:+:$$LD_LIBRARY_PATH}" \
	  $(POETRY) run python $(CAD_DIR)/run_vspaero_tunnel.py

smoke-stage1:
	$(POETRY) run python $(CAD_DIR)/smoke_stage1.py

smoke-stage2:
	$(POETRY) run python $(CAD_DIR)/smoke_stage2.py

cad-figures: $(CAD_PNGS)

cad-validate:
	@test -f $(CAD_DIR)/catskills_ssto.vsp3 || (echo "No .vsp3; run make cad-figures" >&2; exit 1)
	cd $(CAD_DIR) && \
	  LD_LIBRARY_PATH="$(OPENVSP_LIB)$${LD_LIBRARY_PATH:+:$$LD_LIBRARY_PATH}" \
	  $(POETRY) run python $(CAD_VALIDATE)

cad-outliner:
	@echo "Open http://127.0.0.1:8765/hierarchy_app/"
	$(CAD_DIR)/serve_hierarchy_app.sh

cad-crew-capsule: $(CREW_PNG)
cad-airlock: $(AIRLOCK_PNG)
cad-cargo-skid: $(CARGO_PNG)
cad-fusion-skid: $(FUSION_SKID_PNG)
cad-drop-ins: cad-crew-capsule cad-airlock cad-cargo-skid cad-fusion-skid

$(CREW_PNG) $(CREW_BLEND): $(CREW_BLEND_SCRIPT) $(CAD_DIR)/assembly.json $(CAD_LIB)
	@test -x "$(BLENDER)" || (echo "Blender not found at $(BLENDER)" >&2; exit 1)
	$(BLENDER) -b -P $(CREW_BLEND_SCRIPT)

$(AIRLOCK_PNG) $(AIRLOCK_BLEND): $(AIRLOCK_BLEND_SCRIPT) $(CAD_DIR)/assembly.json $(CAD_LIB)
	@test -x "$(BLENDER)" || (echo "Blender not found at $(BLENDER)" >&2; exit 1)
	$(BLENDER) -b -P $(AIRLOCK_BLEND_SCRIPT)

$(CARGO_PNG) $(CARGO_BLEND): $(CARGO_BLEND_SCRIPT) $(CAD_DIR)/assembly.json $(CAD_LIB)
	@test -x "$(BLENDER)" || (echo "Blender not found at $(BLENDER)" >&2; exit 1)
	$(BLENDER) -b -P $(CARGO_BLEND_SCRIPT)

$(FUSION_SKID_PNG) $(FUSION_SKID_BLEND): $(FUSION_SKID_BLEND_SCRIPT) $(CAD_DIR)/assembly.json $(CAD_LIB) $(CONSTANTS_MODEL)
	@test -x "$(BLENDER)" || (echo "Blender not found at $(BLENDER)" >&2; exit 1)
	$(BLENDER) -b -P $(FUSION_SKID_BLEND_SCRIPT)

$(CAD_PNGS): $(CAD_SCRIPT) $(CAD_SPEC) $(CAD_VALIDATE)
	@test -d $(ROOT)/third_party/openvsp/opt/OpenVSP/python/openvsp || \
	  (echo "OpenVSP not extracted. Run: make install-openvsp" >&2; exit 1)
	cd $(CAD_DIR) && \
	  LD_LIBRARY_PATH="$(OPENVSP_LIB)$${LD_LIBRARY_PATH:+:$$LD_LIBRARY_PATH}" \
	  $(POETRY) run python $(CAD_SCRIPT)

# --- Generated numeric constants (magnets/cryo bottom-up mass, full m_dry/
# mu/m_w/m0 chain): single numpy source of truth for arxiv.md §6-§9 and the
# assembly.json/vehicle_spec.json SSOT. See research/figures/cad/constants_model.py.
$(CONSTANTS_JSON): $(CONSTANTS_MODEL)
	$(POETRY) run python $(CONSTANTS_MODEL)

paper-constants: $(CONSTANTS_JSON)

paper-render: paper-constants
	$(POETRY) run python $(UPDATE_ARXIV_CONSTANTS)
	$(POETRY) run python $(APPLY_CONSTANTS_TO_ASSEMBLY)
	$(POETRY) run python $(UPDATE_ARXIV_MERMAID)

zenodo-tex: paper-render cad-figures
	$(ROOT)/scripts/build_zenodo_tex.sh

zenodo-pdf: zenodo-tex
	cd $(ROOT) && latexmk -pdf -interaction=nonstopmode -jobname=zenodo zenodo.tex

zenodo-zip:
	$(ROOT)/scripts/package_zenodo.sh --zip-only

zenodo: paper-render cad-figures
	$(ROOT)/scripts/rebuild_zenodo.sh

arxiv: paper-render
	bash $(ROOT)/scripts/build_arxiv_pdf.sh

clean-figures:
	rm -rf $(ROOT)/figures/figure-*.pdf $(ROOT)/figures/figure-*.mmd $(ROOT)/figures/figure-*.meta
	rm -rf $(ROOT)/figures/assets
