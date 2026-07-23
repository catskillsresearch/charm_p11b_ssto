#!/usr/bin/env bash
# Fetch OpenVSP 3.51.0 (Ubuntu 24.04 amd64) and wire it into Poetry.
#
# OpenVSP is not on PyPI. The Python API is bundled in the official .deb from:
#   https://openvsp.org/download.php
#   https://openvsp.org/download.php?file=zips/current/linux/OpenVSP-3.51.0-Ubuntu-24.04_amd64.deb
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VER=3.51.0
DEB_NAME="OpenVSP-${VER}-Ubuntu-24.04_amd64.deb"
DEB_URL="https://openvsp.org/download.php?file=zips/current/linux/${DEB_NAME}"
TP="$ROOT/third_party/openvsp"
DEB="$TP/$DEB_NAME"
CMINPACK_DEB_DIR="$TP"

mkdir -p "$TP"

if [[ ! -f "$DEB" ]]; then
  echo "Downloading $DEB_NAME ..."
  curl -fL --retry 3 -o "$DEB" "$DEB_URL"
else
  echo "Using existing $DEB"
fi

echo "Extracting OpenVSP tree under $TP ..."
dpkg-deb -x "$DEB" "$TP"

# Runtime lib required by _vsp.so (no sudo): vendor libcminpack1 from Ubuntu.
if [[ ! -f "$TP/sysdeps/usr/lib/x86_64-linux-gnu/libcminpack.so.1" ]]; then
  echo "Vendoring libcminpack1 ..."
  tmp="$(mktemp -d)"
  (
    cd "$tmp"
    apt-get download libcminpack1
    dpkg-deb -x libcminpack1_*.deb "$TP/sysdeps"
  )
  rm -rf "$tmp"
fi

# Optional system install of the GUI + libs when sudo is available.
if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
  echo "Installing OpenVSP system package (sudo) ..."
  sudo apt-get install -y libcminpack1 libglew2.2 libgl1 libglu1-mesa libxml2
  sudo dpkg -i "$DEB" || sudo apt-get install -f -y
else
  echo "No passwordless sudo — using extracted tree + vendored libcminpack."
  echo "For the GUI binary, later run: sudo dpkg -i $DEB"
fi

echo "Installing Poetry openvsp group ..."
poetry install --with openvsp

echo "Verifying import ..."
# shellcheck disable=SC2016
poetry run env \
  LD_LIBRARY_PATH="$TP/sysdeps/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
  python -c 'import openvsp as vsp; print("openvsp", getattr(vsp, "__file__", vsp))'

echo "Done. Use: make cad-figures   (or poetry run with LD_LIBRARY_PATH as above)"
