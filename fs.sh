#!/usr/bin/env bash
# Plan A home field: Edwards AFB — 15,000 ft-class runway + lakebed abort.
# Alternate: --airport=KTTS (Shuttle Landing Facility).
exec fgfs --fg-aircraft=/home/catskills/Desktop/Aircraft --aircraft=CatskillsFusionSSTO --airport=KEDW "$@"
