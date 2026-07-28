#!/usr/bin/env bash
# Plan A home field: Edwards AFB paved 15,000 ft runway (22L), not the lakebed.
# Alternate: --airport=KTTS (Shuttle Landing Facility).
exec fgfs \
  --fg-aircraft=/home/catskills/Desktop/Aircraft \
  --aircraft=CatskillsFusionSSTO \
  --airport=KEDW \
  --runway=22L \
  --on-ground \
  --altitude=0 \
  --vc=0 \
  "$@"
