# Grenadier control map (assembly → cockpit)

Operator-facing systems vs flightdeck switches. CHARM mode string
`OFF/CRYO/ARM/LIGHT/POWER/SCRAM` is **derived** — not a physical rotary.

Prefixes: `C=/fdm/jsbsim/systems/grenadier/charm/` · `E=.../engine/`

**Repo:** everything lives in `charm_p11b_ssto` (`CatskillsFusionSSTO/` = FG aircraft).

## REMAP (wired in `Nasal/grenadier/grenadier_ops.nas`)

| Function | Engraving | Switch object | Hover | Property |
|----------|-----------|---------------|-------|----------|
| Ground cart | **CART** | `apu-operate-1` | Ground cart | `C/ground-cart` |
| Flight battery | **BATT** | `apu-operate-2` | Flight battery | `C/battery-online` |
| Cryo plant | **CRYO** | `apu-operate-3` | Cryo enable | `C/cryo-enable` |
| Magnets | **MAGNET** | `apu-ctrl-pwr-1` | Magnet arm | `C/magnet-arm` |
| Fuel services | **FUEL** | `apu-ctrl-pwr-2` | Fuel enable | `C/fuel-enable` |
| RF | **RF** | `apu-ctrl-pwr-3` | RF enable | `C/rf-enable` |
| CHARM light-off | **CHARM** | `ctrl-pwr-sys-a-ac2-left` | CHARM LIGHT | `C/light-cmd` |
| DEC | **DEC** | `ctrl-pwr-sys-a-ac1-ctr` | DEC online | `C/dec-online` |
| Vacuum | **VACUUM** | `ctrl-pwr-sys-a-ac3-right` | Vacuum ready | `C/vacuum-ready` |
| SCRAM | *(center)* | `main-eng-limit-shut-dn` Enable | CHARM SCRAM | `C/scram` |
| Stage − | **STAGE −** *(center)* | left black `STG` pushbutton (former SRB SEP) | Stage - | `E/sigma` |
| Stage + | **STAGE +** *(center)* | right black `STG` pushbutton (former ET SEP) | Stage + | `E/sigma` |
| Throttle | **KP 9 / KP 3** | FlightGear engine[0] keyboard command | Increase / decrease | `E/throttle` |

Header over CHARM/DEC/VACUUM: **REACTOR POWER** (was ENGINE POWER).

Scramble progression: **BATT → CRYO → MAGNET → FUEL → VACUUM → RF → CHARM → DEC** → POWER. **CART** optional (pad GSE).

## KEEP (airframe / avionics)

Flight controls, gear, **brake isol** (R4), RHC/THC, DAP/RCS, HUD/ADI/HSI,
GPC/IDP/MDU, lighting, cabin fans, abort CWS.

**Steering / hyd:** **BATT** (not APU START) → `systems/grenadier/hyd/available` → NWS + aero. See [reactor_startup.md](reactor_startup.md) §1a and [ssto_ascent_checklist.md](ssto_ascent_checklist.md) Quick Start.

**Panel ID labels:** bright yellow letters baked into blank panel-edge regions of
the original forward/aft cockpit texture atlases (same regular Sans engraving
size as stock white legends; no plaque geometry). Placement uses only large
plate UV islands and their outer rim — never the featureless interior UV holes
that host 3D switches. Tiny MDU doors (C4/C5) are UV-remapped onto larger blank
atlas patches so the lettering stays sharp. Rebuild with
`python3 Models/Grenadier/build_panel_id_labels.py` after
`scripts/stamp_grenadier_apu_labels.py`.

**AFT LEFT/RIGHT RCS** paint (aft text map): green monoprop **LMP-103S** —
`He (OXID)/(FUEL)` → **He (A)/(B)**; tank `OXID`/`FUEL` → **PROP**/**PROP**.
Switches/manifold banks unchanged (A/B press + isolation).

## REMOVED / INERT (no Grenadier function)

| Family | What you see | Why |
|--------|--------------|-----|
| Drag chute ARM / DPY / JETTISON (both seats) | Hardware hidden | No drag chute — rollout uses gear brakes on a long runway |
| R1 power distribution | Hardware hidden; smooth blank plate | Heritage fuel-cell, inverter, and bus controls; Grenadier uses BATT + CHARM bus. R1 O₂/H₂ controls were dummy and did not operate ECLSS |
| R2 surplus (isol / He / hyd / boiler / ET door / …) | Hardware hidden; smooth blank plate | Not aliased into Grenadier ops |
| R4 surplus (heater / LG / MPS / TVC / …) | Hardware hidden; brake isol retained | Only brake isol is live |
| Sys B controller row | Hardware hidden | Duplicate SSME ctrl |
| Fuel cells | Hover blank | CHARM bus + BATT |
| ET / SRB selector levers and heritage paint | Hardware hidden | No stack; adjacent pushbuttons are repurposed below |
| MAIN ENGINE LEFT/RIGHT SD | Hardware hidden | Single nozzle; CTR label kept |
| FUEL CELL REAC VLV (C3) | Hardware hidden | No fuel cells — CHARM bus + BATT |
| SRB/ET SEP pushbuttons | Relabeled **STAGE − / +** with `STG` button faces | Stack separation removed; left decrements, right increments Stage |
| OMS ENG arms | Legacy secondary mapping | Not needed in normal operation; use the labeled `STG` pushbuttons |
| APU hydrazine / hyd pumps | Hardware hidden on R2; A12 aft plate stripped of all switchgear | No hydrazine APUs; **BATT** (or CART / CHARM bus) drives electric hyd packs for NWS, brakes, and aero (`systems/grenadier/hyd/available`) |
| A14 OMS/RCS heat + RMS pyro | Hardware hidden (plate + fasteners only) | No OMS engines; not used in scramble |

## CRT map

| Softkey | Page | Content |
|---------|------|---------|
| CHARM (first) | `p_meds_apu` | see table below |
| STAGE | `p_meds_oms_mps` | Stage CMD/MAX, REC/SEAL, THR%/PLANT; **BRAKES** PARK/TOE L/TOE R; engine DELIV%, H2O%, BUS MW, thrust kN, mode, GO/CPL/DRAW, feed kg/s, σ1–3 output |
| SPI | `p_meds_spi` | Keep |

### CHARM page labels (what each tape means)

| Block | Label | Meaning |
|-------|-------|---------|
| CHARM | **SOC** | Battery state of charge % |
| CHARM | **MAGI** | Magnet current fraction % |
| CHARM | **PLAS** | Plasma proxy % |
| CHARM | **V** | Aux bus volts |
| CHARM | **MW** | Plant bus megawatts (/10 on tape) |
| CHARM | **MODE** | Mode index (OFF…POWER) |
| CHARM | **CART** | Ground cart enable |
| CHARM | **BATT** | Flight battery online |
| CHARM | **CRYO** | Cryo plant enable (wall switch) |
| CHARM | **T·K** | Magnet temperature (K) |
| CHARM | **CRYO** (go) | `go-cryo` — magnet cold enough (&lt;35 K) |
| CHARM | **VAC** | Vacuum ready (VACUUM wall switch) |
| PLANT | **H+** | Proton / H₂ feed inventory % |
| PLANT | **B11** | Solid ¹¹B inventory % |
| PLANT | **H2O** | Engine water inventory % |
| PLANT | **MAG** | `go-magnet` |
| PLANT | **FUEL** | `go-fuel` (needs VACUUM + FUEL) |
| PLANT | **BUS** | `go-bus` |

**FREON LOOP** on the top-center caution light is ATCS coolant (avionics / heat rejection) — not part of the CHARM scramble. Freon pumps are heritage ECLSS; leave alone unless you are doing a full thermal startup.

## Cabin atmosphere / life support

| Panel | Function |
|-------|----------|
| **L1** | Thermal-control pumps, cabin/avionics-bay fans, humidity separation, and fire suppression |
| **L2** | Cabin vent/isolation valves and the live O₂/N₂ supply, crossover, and regulator controls |
| **O1** | Cabin pressure, O₂ partial pressure, atmosphere flow, and thermal gauges |
| **O2** | Cryogenic O₂/H₂ tank pressure, quantity, and temperature gauges |
| **F7** | Caution/warning lights for cabin atmosphere and O₂ pressure |

Cabin atmosphere is represented by virtual JSBSim tanks in `shuttle.xml`:
O₂ tank 23 starts with **40 lb** (45 lb capacity), and N₂ tank 24 starts with
**130 lb** (147 lb capacity). `Systems/eclss.xml` meters those stores through
the **L2** valves and computes cabin pressure and O₂ fraction. Normal startup
defaults leave ECLSS system 1 supplied and the cabin at 14.7 psi; do not close
the L2 O₂/N₂ supply or regulator valves for crewed operation.

## Physical engraving

`Models/fwd-cockpit-text-map-x.png` via `scripts/stamp_grenadier_apu_labels.py`:

- APU OPERATE → **CART / BATT / CRYO**
- APU CNTLR PWR → **MAGNET / FUEL / RF**
- ENGINE POWER → **REACTOR POWER** + **CHARM / DEC / VACUUM**
- R1 plate → blank (heritage fuel-cell power distribution)
- R2 plate → blank except those three plant groups
- R4 plate → blank except **BRAKE ISOL VLV**
