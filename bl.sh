#!/usr/bin/env bash
# Open the current Grenadier FlightGear mesh assembly in Blender.
# Blend is built from live CatskillsFusionSSTO/Models/ via:
#   "${BLENDER:-/snap/bin/blender}" -b -P assets/flightgear_space_shuttle/build_grenadier_fg_blend.py
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
BLEND="${ROOT}/assets/flightgear_space_shuttle/grenadier_fg_now.blend"
BLENDER="${BLENDER:-/snap/bin/blender}"
if [[ ! -f "${BLEND}" ]]; then
  echo "error: missing ${BLEND}" >&2
  echo "Rebuild: ${BLENDER} -b -P ${ROOT}/assets/flightgear_space_shuttle/build_grenadier_fg_blend.py" >&2
  exit 1
fi
exec "${BLENDER}" "${BLEND}" "$@"
