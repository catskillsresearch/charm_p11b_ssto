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

## Property bus

Prefix: `/fdm/jsbsim/systems/grenadier/engine/`

| Property | Type | Meaning |
|----------|------|---------|
| `sigma` | int | Commanded stage 1/2/3 |
| `sigma-recommended` | int | From altitude (and optional Q) |
| `sigma-allowed` | int | Max stage permitted by sensors + plant |
| `inlet-sealed` | bool | Intakes sealed (required for σ3) |
| `throttle` | double | 0–1 thrust demand |
| `thrust-kn` | double | Delivered thrust (peak × throttle × bus-frac) |
| `thrust-peak-kn-sigma{1,2,3}` | double | Paper freeze peaks |
| `power-draw-mw` | double | Bus demand |
| `power-peak-mw-sigma{1,2,3}` | double | Paper freeze bus peaks |
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
| σ1 | Always when plant-ok | Inlet open |
| σ2 | `alt-ft` ≥ `sigma2-alt-ft` (default 25000) | Inlet open |
| σ3 | `alt-ft` ≥ `sigma3-alt-ft` (default 130000) **or** operator override with inhibit warn | `inlet-sealed` = 1; water > 0 |

Altitude thresholds are editable props for tuning. Crew may command a higher stage;
UI shows INHIBIT if sensors say no; hard block only when water empty (σ3) or plant not POWER.

## Screens

`Nasal/canvas/cdlg_grenadier_engine.nas`:

- Stage commanded / recommended / allowed
- Altimeter (primary sensor strip)
- Inlet sealed, water kg, thrust, power draw, plant-ok
- Buttons: σ1 / σ2 / σ3, SEAL, throttle ±
