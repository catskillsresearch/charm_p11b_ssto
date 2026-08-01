# Plan A FDM pack (JSBSim) + visual wing — high-AR loft

Makes the **simulator** see a wing that can hold a shallow climb on paper
σ1/σ2 thrust (T/W ≈ 0.3–0.5 at SL, less aloft), without pretending this is a
vertical rocket. Exterior mesh matches the planform.

Source: `arxiv.md` §1.2b + high-AR climb loft. Files: `shuttle.xml`,
`Models/shuttle_o2_plan_a.ac`, `Nasal/grenadier/grenadier_ops.nas`.

## Scaled metrics (FDM) — high-AR loft

| Quantity | Heritage | Fat delta (prior) | **High-AR (current)** |
|----------|----------|-------------------|------------------------|
| Wing area | 2691 ft² (250 m²) | 9688 ft² (900 m²) | **9688 ft² (900 m²)** |
| Span | 78.1 ft (23.8 m) | 147.6 ft (45 m) | **196.9 ft (60 m)** |
| Aspect ratio | ~2.3 | ~2.25 | **~4.0** |
| Chord | 34.5 ft | 65.6 ft | **49.2 ft** |
| Wing incidence | 2.0° | 4.0° | **4.0°** |
| Empty weight | 180 000 lb | 378 534 lb | **378 534 lb (~171.7 t dry)** |
| Wing loading (GLOW≈216 t) | — | ~49 psf | **~49 psf** |
| Stall @ CLmax 1.65 (GLOW) | — | ~94 KEAS | **~94 KEAS** |
| CG / AERORP x | 2.70 m | 3.77 m | **3.77 m** |

## Why span 60 m (not more area)

Paper σ1 is **589 kN** on ~216 t GLOW → T/W ≈ **0.28**. Area sets the stall
floor; **aspect ratio** sets how hard induced drag punishes climb α. The fat
delta (45 m / AR≈2.25) could accelerate, then bled to ~90 KEAS and porpoised on
any small pitch-up. Holding S at 900 m² and stretching to **60 m (AR≈4)** cuts
the α² drag term so a **~2° / ~1,000–1,500 fpm** shallow climb stays on the
right side of thrust−drag. (Cockpit HUD: airspeed **KEAS**, altitude **ft**.)

Thrust peaks are **unchanged** (paper freeze). Loft comes from planform + AR-
consistent polar, not fake T/W > 1.

## Aero coeff tuning

| Lever | Value | Why |
|-------|--------|-----|
| \(C_{L\alpha}\) poly | **4.30**; quadratic **−1.15** | Slightly steeper for higher AR |
| CD α² term | **1.00** (was 1.79) | Scaled ≈ AR_old/AR_new for induced drag |
| Clp / Clb / Clda | same as prior loft pack | Roll damping vs scaled inertia |
| Cmq / Cmadot | −100 / −10 | Damp climb↔dive phugoid |

## Stage ops (slow path)

| Gate | Value | Role |
|------|--------|------|
| σ2 open | **12 000 ft** | Cut over before σ1 fades in the teens |
| σ1 air-exp | **0.65** | Softer than linear-ρ so climb continues |
| σ1 stall floor | **0.12** air-frac | ~still dies near mid-stratosphere |
| σ2 air-exp | **0.70** | Holds thinner air better on the way to seal |
| σ3 seal gate | **130 000 ft** | Paper \(h_{\mathrm{seal}}\); then long water burn |

## σ2 speed wall (not a missing engine)

σ2 is **air-breathing plasma**, not SSME-class rockets. At ~17 000 ft with
nose down you will hit roughly **Mach ~0.85 / ~400+ KEAS** where drag rise meets
density-derated thrust (~500–600 kN). That is a thrust=drag ceiling in dense
air — expected on this bus. Energy to orbit is gained later as true speed rises
while **KEAS falls** toward seal, then σ3 water burn. Do not expect Shuttle-ascent
KEAS schedules from σ2.

## Visual wing (`shuttle_o2_plan_a.ac`)

Built by `Models/Grenadier/build_plan_a_wings.py` → `build_delta_wing.py`:

- Flat-bottomed monowing shells, root buried inboard of the hull chine
- Span **60 m**, S ≈ **900 m²**, hinge at x = **17.20 m**
- Main gear bays recessed under `GearDoorL/R`; track ±**10.57 m**
- Aft body / nozzle stretched to the elevon TE

Rebuild: `python3 Models/Grenadier/build_plan_a_wings.py`

## How to fly it (provisional)

1. `./fs.sh` → KEDW 22, CHARM → POWER, σ1, throttle up
2. Rotate ~**80–90 KEAS** — do **not** haul the nose into stall
3. Shallow climb ~**110–125 KEAS**; σ2 early climb often ~**150–200 KEAS**
4. Hold **~2° path / ~1,000–1,500 fpm** — not zoom climbs
5. By ~**12,000 ft** STAGE + to σ2 when MAX/GO allow
6. Before aero dies: **Ctrl+m** → RCS ROT DAP (see checklist RCS notes)
7. σ3 only after seal + water at ~**130,000 ft**

Check: `/fdm/jsbsim/metrics/Sw-sqft` ≈ 9688, `bw-ft` ≈ 197.
