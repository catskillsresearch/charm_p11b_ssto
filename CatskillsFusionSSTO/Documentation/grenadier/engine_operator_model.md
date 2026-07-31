# Engine operator model — CATSKILLS-SSTO-TA-GRENADIER

Three-cycle electric rocket: σ1 EDF (air), σ2 air-plasma, σ3 water-plasma (intakes sealed).
Plant couples **only** by power cable (`charm/bus-mw`).

## Performance freeze (matches paper)

Throttle=1 peaks come from arxiv §10 / `research/figures/cad/constants.generated.json`
(same solve as companion engine paper [17]). JSBSim force is `thrust-kn × 224.808943` lbf.

| σ | Name | Peak thrust | Peak bus draw | σ3 \(\dot m_w\) |
|---|------|-------------|---------------|-----------------|
| 1 | EDF | 589.4 kN | 92.5 MW | — |
| 2 | Air plasma | 820.9 kN | 995 MW | — |
| 3 | Water plasma | 55.8 kN | 995 MW | 2.845 kg/s |

Water inventory default: 44 356 kg. σ3 seal gate default: 130 000 ft (≈ paper \(h_{\mathrm{seal}}\)).

Sea-level peaks apply in dense air. **σ1 / σ2 thrust and bus draw scale with
ambient density** (`atmosphere/rho-slugs_ft3` / `rho-sl-slugft3`), then hard-stall
below a floor so the EDF and air-plasma cycles die as the air runs out. σ3 is
water-propelled (no air scale) and still depletes `water-kg`.

## Property bus

Prefix: `/fdm/jsbsim/systems/grenadier/engine/`

| Property | Type | Meaning |
|----------|------|---------|
| `sigma` | int | Commanded stage 1/2/3 |
| `sigma-recommended` | int | From altitude + air-frac (and optional Q) |
| `sigma-allowed` | int | Max stage permitted by sensors + plant |
| `inlet-sealed` | bool | Intakes sealed (required for σ3) |
| `throttle` | double | 0–1 thrust demand |
| `thrust-kn` | double | Delivered thrust (peak × throttle × air-scale × bus-frac) |
| `thrust-peak-kn-sigma{1,2,3}` | double | Paper freeze peaks (sea-level / dense-air) |
| `power-draw-mw` | double | Bus demand (also air-scaled on σ1/σ2) |
| `power-peak-mw-sigma{1,2,3}` | double | Paper freeze bus peaks |
| `air-frac` | double | `rho / rho-sl` (clipped ≤ 1) |
| `air-scale` | double | Applied density scale for current σ (0 if stalled) |
| `rho-slugft3` | double | Ambient density mirror |
| `rho-sl-slugft3` | double | Sea-level reference (default 0.0023769) |
| `sigma1-stall-frac` | double | σ1 hard stall below this air-frac (default 0.15 ≈ 50 kft) |
| `sigma2-stall-frac` | double | σ2 hard stall below this air-frac (default 0.025) |
| `sigma1-air-exp` | double | σ1 thrust ∝ air-frac^exp (default 1.0) |
| `sigma2-air-exp` | double | σ2 thrust ∝ air-frac^exp (default 0.9) |
| `water-kg` | double | Carried water |
| `water-flow-kgps` | double | σ3 mass flow |
| `water-flow-peak-kgps` | double | σ3 \(\dot m\) at throttle=1 |
| `alt-ft` | double | Mirror of `/position/altitude-ft` |
| `q-psf` | double | Dynamic pressure (optional gate) |
| `stage-go` | bool | Commanded stage is allowed |
| `plant-ok` | bool | CHARM mode POWER and not scrammed |

## Stage gates (v1)

| Stage | Sensor gate (default) | Other |
|-------|----------------------|-------|
| σ1 | `air-frac` ≥ `sigma1-stall-frac` (0.15) | Inlet open; thrust ∝ air-frac |
| σ2 | `alt-ft` ≥ `sigma2-alt-ft` (25000) **and** `air-frac` ≥ `sigma2-stall-frac` (0.025) | Inlet open; thrust ∝ air-frac^0.9 |
| σ3 | `alt-ft` ≥ `sigma3-alt-ft` (130000) | `inlet-sealed` = 1; water > 10 kg; no air scale |

Altitude / stall floors are editable props for tuning. Stage command stays **manual**
(STAGE ±); density only derates thrust and clears `stage-go` when stalled. σ3 still
runs dry if water is not managed.

## Screens

`Nasal/canvas/cdlg_grenadier_engine.nas`:

- Stage commanded / recommended / allowed
- Altimeter (primary sensor strip)
- Inlet sealed, water kg, thrust, power draw, plant-ok
- Buttons: σ1 / σ2 / σ3, SEAL, throttle ±
