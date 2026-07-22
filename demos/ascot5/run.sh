#!/usr/bin/env bash
# Launch the ASCOT5 comprehensive demo in demos/.envs/ascot5.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV="${ROOT}/demos/.envs/ascot5"
VENDOR="${ROOT}/demos/vendor/ascot5"
MAMBA="${MAMBA:-/tmp/bin/micromamba}"

if [[ ! -x "${ENV}/bin/python" ]]; then
  echo "ASCOT5 env missing at ${ENV}. Run demos/scripts/build_ascot5.sh"
  exit 1
fi
if [[ ! -x "${VENDOR}/build/ascot5_main" ]]; then
  echo "ascot5_main missing. Run demos/scripts/build_ascot5.sh"
  exit 1
fi
export LD_LIBRARY_PATH="${VENDOR}/build:${ENV}/lib:${LD_LIBRARY_PATH:-}"
export PATH="${VENDOR}/build:${PATH:-}"
cd "${ROOT}"
exec "$MAMBA" run -p "$ENV" python "${ROOT}/demos/ascot5/demo_ascot5.py" "$@"
