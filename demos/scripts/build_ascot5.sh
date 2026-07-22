#!/usr/bin/env bash
# Create demos/.envs/ascot5 and compile ASCOT5 (libascot + ascot5_main + a5py).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV="${ROOT}/demos/.envs/ascot5"
VENDOR="${ROOT}/demos/vendor/ascot5"
MAMBA="${MAMBA:-/tmp/bin/micromamba}"

if [[ ! -x "$MAMBA" ]]; then
  echo "micromamba not found at $MAMBA — set MAMBA=..."
  exit 1
fi

if [[ ! -d "$VENDOR/.git" && ! -f "$VENDOR/Makefile" ]]; then
  mkdir -p "${ROOT}/demos/vendor"
  git clone --depth 1 https://github.com/ascot4fusion/ascot5.git "$VENDOR"
fi

if [[ ! -x "${ENV}/bin/python" ]]; then
  "$MAMBA" create -y -p "$ENV" -c conda-forge \
    python=3.12 c-compiler make llvm-openmp hdf5 zlib setuptools pip \
    'numpy<2' scipy h5py xmlschema 'unyt<3.1' wurlitzer matplotlib freeqdsk ipython
fi

# Conda h5cc injects -shlib which gcc rejects — build with CC=gcc.
"$MAMBA" run -p "$ENV" bash -lc "
set -euo pipefail
cd '$VENDOR'
unset CFLAGS CXXFLAGS LDFLAGS CPPFLAGS || true
export CONDA_PREFIX='$ENV'
make -C src clean >/dev/null 2>&1 || true
make libascot -j\$(nproc) CC=gcc
make ascot5_main -j\$(nproc) CC=gcc
export LD_LIBRARY_PATH='$VENDOR/build:$ENV/lib:\${LD_LIBRARY_PATH:-}'
pip install -e . --no-deps -q
python -c 'from a5py import Ascot; print(\"a5py OK\")'
"
echo "ASCOT5 ready: $VENDOR/build/ascot5_main"
