#!/usr/bin/env bash
# Launch the OpenMC comprehensive demo in demos/.envs/openmc.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV="${ROOT}/demos/.envs/openmc"
XS="${ROOT}/demos/openmc/nuclear_data/cross_sections.xml"
MAMBA="${MAMBA:-/tmp/bin/micromamba}"

if [[ ! -x "${ENV}/bin/python" ]]; then
  echo "OpenMC env missing at ${ENV}"
  echo "Create with:"
  echo "  micromamba create -y -p demos/.envs/openmc -c conda-forge openmc matplotlib h5py pandas"
  exit 1
fi
if [[ ! -f "$XS" ]]; then
  echo "Nuclear data missing; fetching minimal ENDF/B-VII.1 set ..."
  "$MAMBA" run -p "$ENV" python "${ROOT}/demos/scripts/fetch_openmc_data.py"
fi
export OPENMC_CROSS_SECTIONS="$XS"
exec "$MAMBA" run -p "$ENV" python "${ROOT}/demos/openmc/demo_openmc.py" "$@"
