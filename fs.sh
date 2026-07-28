#!/usr/bin/env bash
# Plan A home field: Edwards AFB long paved runway.
# In this FG apt.dat the 15k-class paved strip is "04"/"22" (not real-world "22L").
# Alternate: --airport=KTTS (Shuttle Landing Facility).
exec fgfs \
  --fg-aircraft=/home/catskills/Desktop/Aircraft \
  --aircraft=CatskillsFusionSSTO \
  --airport=KEDW \
  --runway=22 \
  --on-ground \
  --altitude=0 \
  --vc=0 \
  "$@"
