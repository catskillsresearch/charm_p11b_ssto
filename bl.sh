#!/usr/bin/env bash
# Open the crew-capsule cutaway (assembly.json → Blender). Rebuild first if needed:
#   make cad-crew-capsule
exec /snap/bin/blender "$(dirname "$0")/research/figures/cad/crew_capsule_cutaway.blend" "$@"
