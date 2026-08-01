# Plan A FDM pack (JSBSim) + visual wing stretch

Makes the **simulator** see Plan A size/weight, and the **exterior mesh** show Plan A wings.

Source: `arxiv.md` §1.2b + loft tuning for steady dense-air climb. Files: `shuttle.xml`, `Models/shuttle_o2_plan_a.ac`.

## Scaled metrics (FDM) — loft pack

| Quantity | Heritage | First Plan A | Loft pack (current) |
|----------|----------|--------------|---------------------|
| Wing area | 2691 ft² (250 m²) | 5167 ft² (480 m²) | **6458 ft² (600 m²)** |
| Span | 78.1 ft (23.8 m) | 108.3 ft (33 m) | **124.7 ft (38 m)** |
| Chord | 34.5 ft | 47.7 ft | **51.8 ft** |
| Aspect ratio | ≈2.27 | ≈2.27 | **≈2.41** |
| Wing incidence | 2.0° | 2.0° | **3.5°** |
| Empty weight | 180 000 lb | 378 534 lb | **378 534 lb (~171.7 t dry)** |
| Wing loading (dry) | ~67 lb/ft² | ~73 lb/ft² | **~59 lb/ft²** |
| Ixx / Iyy / Izz | stock | × ~4.07 | unchanged (mass pack) |
| CG / AERORP x | 2.70 m | 3.77 m | **3.77 m** |
| H / V tail area | stock | scaled | **×1.25 vs first Plan A** |

## Aero coeff tuning (still Shuttle-family tables)

Honest envelope levers for steady climb above ~225 KIAS (not fake thrust):

| Lever | Change | Why |
|-------|--------|-----|
| \(C_{L\alpha}\) poly | 2.73 → **3.50**; quadratic −1.55 → **−1.40** | Lift at moderate α; margin vs mush |
| Clp scale | ×**1.90** | Roll damping vs scaled inertia |
| Clb scale | ×**1.65** | Lateral / spiral stability |
| Clda scale | ×**1.20** | Roll authority under stronger Clp |
| Cmq / Cmadot | −70→**−100**, −6→**−10** | Damp climb↔dive phugoid |

## Visual wing (`shuttle_o2_plan_a.ac`)

Built by `Models/Grenadier/build_plan_a_wings.py` from `shuttle_o2_heritage.ac`.

Warping the OV planform never worked: its cranked glove turned into SR-71 chines
that suddenly widened, with see-through notches at the elevons. The wing is now
**generated** by `Models/Grenadier/build_delta_wing.py` instead:

- OV glove / strake skins **deleted** from `fuselage` + `heatshield` (189 surfaces)
- New closed shells `plan-a-wing-left` / `plan-a-wing-right`: straight LE from
  root x **−2.00 m** to tip x **+10.20 m**, root rib at |z| = 2.10 m so it sits
  inboard of the hull chine (the side wall is only |z| ≈ 2.66 m at wing level)
- **Flat-bottomed monowing**: the underside is level with the tiled boat
  (y ≈ −5.23 m) and all thickness is carried on the upper surface, so wing and
  belly read as one continuous surface instead of meeting at a step
- Trailing edge on a **straight hinge line at x = 15.05 m**; the four elevon
  objects are regenerated flush to it (no ground between wing and flap), hinge
  axis in `SpaceShuttle.xml` at z = −4.84 m
- Span **38.1 m**, S ≈ **598 m²** (FDM reference 600 m²), root chord 17.1 m, tip 4.9 m
- Underside + LE wrap sample the black HRSI patch of `spstob_1.png`, upper
  surface the white LRSI patch, matching the heritage `heatshield`
- **Main gear bay** boxed out at x 0.38–5.42 m, |z| 2.55–4.52 m, roof at
  y = −4.80 m, cut a little larger than the doors so `GearDoorL/R` hang in the
  opening with a tile gap and the wells are visible from below
- Body glove / gear doors still ride the old span-chord warp (Plan A gear track)
- Fuselage length / bay width **not** stretched

Rebuild: `python3 Models/Grenadier/build_plan_a_wings.py`

## Gear

- Nose x **−20.94 m**, mains x **5.03 m**, track y **±6.70 m**
- z kept **−7.97 m** (level park)
- Spring/damping × ~2.10 (mass ratio)

## What is *not* changed

- Fuselage packaging length (heritage visual length; FDM CG uses Plan A length scale)
- Grenadier thrust model — same peak force; loft comes from wing/aero, not thrust cheats
- Water mass still Nasal-only (not yet in JSBSim weight)

## How to sniff-test

1. `./fs.sh` → KEDW 22, cold level park
2. Top-down: wings ≈ **38 m** tip-to-tip
3. Check `/fdm/jsbsim/metrics/Sw-sqft` ≈ 6458, `bw-ft` ≈ 125, emptywt ≈ 378534
4. Plant up → rotate ~**200–220 KIAS** → trim a shallow climb at **240–280 KIAS** with small pitch inputs; roll should feel damped
