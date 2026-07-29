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
| Stage − | *(center)* | `oms-eng-left` | Stage - | `E/sigma` |
| Stage + | *(center)* | `oms-eng-right` | Stage + | `E/sigma` |
| Throttle | *(center)* | engine[0] lever | Engine throttle | `E/throttle` |

Header over CHARM/DEC/VACUUM: **REACTOR POWER** (was ENGINE POWER).

Scramble progression: **BATT → CRYO → MAGNET → FUEL → VACUUM → RF → CHARM → DEC** → POWER. **CART** optional (pad GSE).

## KEEP (airframe / avionics)

Flight controls, gear, **brakes / NWS** (R4 labels kept), RHC/THC, DAP/RCS, HUD/ADI/HSI,
GPC/IDP/MDU, lighting, cabin fans, abort CWS.

## BLANK / INERT (mesh may remain; no Grenadier function)

| Family | What you see | Why |
|--------|--------------|-----|
| R4 MPS / ET | Paint blanked | No LO2/LH2/SSME |
| Sys B controller row | Hover blank | Duplicate SSME ctrl |
| Fuel cells | Hover blank | CHARM bus + BATT |
| ET / SRB / OMS engines | Unused | No stack; Stage ± only on OMS arm switches |
| APU hydrazine / hyd pumps | Ignore | No hyd TVC story |

## CRT map

| Softkey | Page | Content |
|---------|------|---------|
| STAGE | `p_meds_oms_mps` | Stage, throttle, seal, water, thrust, bus |
| CHARM | `p_meds_apu` | Mode, BATT/CRYO/MAGNET/FUEL/RF/DEC, bus MW |
| SPI | `p_meds_spi` | Keep |

## Physical engraving

`Models/fwd-cockpit-text-map-x.png` via `scripts/stamp_grenadier_apu_labels.py`:

- APU OPERATE → **CART / BATT / CRYO**
- APU CNTLR PWR → **MAGNET / FUEL / RF**
- ENGINE POWER → **REACTOR POWER** + **CHARM / DEC / VACUUM**
- R4 plate → blank except brake heater/isol and LG extend/NWS
