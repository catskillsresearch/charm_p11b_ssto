# SSTO ascent checklist (Grenadier TA)

## Quick Start — cold runway to initial climb (PLT)

Use the **Pilot** view (`v` cycles forward, `Shift+V` backward). Turn **Num Lock on**. Cockpit switches and MDU softkeys require the mouse; use the keypad for throttle and flight control.

| Step | Panel / view | Switch or key | Setting / action |
|------|--------------|---------------|------------------|
| 1 | View | `v` / `Shift+V` | Select **Pilot** (right-seat) view |
| 2 | PLT forward displays | **R1 Power** (inner PLT MDU) | **ON**; screen remains dark until BATT |
| 3 | PLT forward displays | **R2 Power** (outer PLT MDU) | **ON**; screen remains dark until BATT |
| 4 | Right wall — **APU OPERATE** | **BATT** | **ON**; R1 opens on **CHARM**, R2 on **FLT INST / PFD**, and CHARM `V` shows about 260 V |
| 5 | Pilot HUD panel | **HUD Power** | **ON**; mode **NORM**, brightness **AUTO** or **DAY** |
| 6 | Pilot F8 | **Flight Controller Power** | **ON** |
| 7 | R1 MDU | Page | If not already there: **MAIN → SUBSYS STATUS → CHARM** |
| 8 | Right wall — **APU OPERATE** | **CRYO** | **ON**; wait for `T·K < 35` and green `CRYO 0001` |
| 9 | Right wall — **APU CNTLR PWR** | **MAGNET** | **ARM/ON**; wait for green `MAG` / `MAGI` near 100 |
| 10 | Right wall — **APU CNTLR PWR** | **FUEL** | **ON** |
| 11 | Right wall — **REACTOR POWER** | **VACUUM** | **ON/READY**; confirm `VAC 0001` and green `FUEL` |
| 12 | Right wall — **APU CNTLR PWR** | **RF** | **ON** |
| 13 | Right wall — **REACTOR POWER** | **CHARM** | **ON**; mode advances to `LIGHT` |
| 14 | Right wall — **REACTOR POWER** | **DEC** | **ON** |
| 15 | R1 — CHARM | Status | Wait for `MODE POWER`, green `BUS`, and bus MW rising |
| 16 | R1 MDU | **STAGE** softkey | Select STAGE; confirm `CMD 1`, `MAX 1`, `GO 1`, `PLANT 1`, `THR 000` |
| 17 | Keypad | `KP 5` | Center elevator, aileron, and rudder |
| 18 | Keypad | `KP 3` | Hold until throttle is at idle / `THR 000` |
| 19 | Brakes | `Shift+B` | **Do not press yet**; parking brake starts SET |
| 20 | Right wall — **APU OPERATE** | **CART** | Leave **OFF** |
| 21 | Takeoff configuration | Gear / speedbrake / inlet | Gear **DOWN**, speedbrake **IN**, `SEAL 0`, controls neutral |
| 22 | Brakes | `Shift+B` | Release parking brake |
| 23 | Keypad | `KP 9` | Hold to advance throttle smoothly to `THR 100`; verify `CPL 1`, thrust and `DRAW` rising |
| 24 | Runway steering | `KP 0` / `KP Enter` | Rudder left/right; use small taps to hold centerline |
| 25 | Takeoff roll | R2 PFD / HUD | Accelerate through **225 KIAS** |
| 26 | Keypad | `KP 2` | At 225 KIAS, pitch up to about **10–12° nose-up** |
| 27 | Keypad | `KP 5`, then `KP 2` / `KP 8` | Center the initial input, then make small pitch corrections |
| 28 | Positive climb | `g` | Gear **UP**; remain in Stage 1 until the STAGE page recommends Stage 2 |

**225 KIAS is the current provisional rotation target for the enlarged Plan-A FDM, not a flight-tested certified V-speed.** If the nose will not lift cleanly, continue accelerating rather than commanding excessive pitch.

Keypad summary: `2/8` nose up/down, `4/6` roll left/right, `0/Enter` rudder left/right, `5` center controls, `9/3` throttle up/down. `Page Up/Page Down` duplicate throttle up/down.

Beginner path: **sit PLT (right seat)** for plant switches and displays; use the center console for Stage ± / SCRAM and the keypad for throttle.

Panel paint uses Grenadier logos (surplus Shuttle hull). Use the **engraved names** below — not Shuttle heritage lettering. If hover shows **nothing**, ignore that switch (blanked / unused).

CHARM mode `OFF → CRYO → ARM → LIGHT → POWER` is **derived** (CHARM MEDS page). There is no five-position mode rotary.

## Where the live keys are

| What you need | Engraving (right wall) | Hover / object |
|---------------|------------------------|----------------|
| Flight battery | **BATT** (APU OPERATE row) | Flight battery · `apu-operate-2` |
| Cryo | **CRYO** | Cryo enable · `apu-operate-3` |
| Ground cart (optional) | **CART** | Ground cart · `apu-operate-1` — pad GSE only; not required for scramble |
| Magnet | **MAGNET** (APU CNTLR row) | Magnet arm · `apu-ctrl-pwr-1` |
| Fuel | **FUEL** | Fuel enable · `apu-ctrl-pwr-2` |
| RF | **RF** | RF enable · `apu-ctrl-pwr-3` |
| CHARM light-off | **CHARM** under **REACTOR POWER** | CHARM LIGHT · `ctrl-pwr-sys-a-ac2-left` |
| DEC | **DEC** | DEC online · `ctrl-pwr-sys-a-ac1-ctr` |
| Vacuum | **VACUUM** | Vacuum ready · `ctrl-pwr-sys-a-ac3-right` |
| Stage − / + | Center console | Left/right black **STG** pushbuttons (former SRB/ET SEP) |
| SCRAM | Center | Main Eng Limit → Enable · `main-eng-limit-shut-dn` |
| Throttle | Keyboard | `KP 9` increase / `KP 3` decrease (`Page Up/Down` also work) |

**Landing only (panel R4):** **BRAKE ISOL VLV** stays labeled (leave OPEN). All other R4 paint is blanked — leave those switches alone.

## CRT pages

On an MDU: **MAIN → SUBSYS STATUS**

| Softkey | Page | Use for |
|---------|------|---------|
| **CHARM** (first) | plant | scramble plant to POWER |
| **STAGE** | engine | Stage 1/2/3, throttle, seal, water, thrust — after CHARM |
| SPI | leave | not required for scramble |

After power-up, PLT **R1** defaults to **CHARM** and PLT **R2** defaults to the takeoff **PFD**. Stage 7 pads are **dead cold** (all enables, displays, HUD, and PLT flight controller OFF; charged battery + propellant inventories only). The center IDP CRTs are not required for this quick start.

Ignore Fuel Cells / APU–HYD DISP pages (blanked titles).

## Scramble order

### 0. Seats / view
1. Prefer **PLT** so the right-wall plant row faces you.
2. Cue cards → **CHARM startup** if you want the same steps as a popup.

### 1. Plant to POWER (right wall + CHARM CRT)

Stage 7 pads with a **charged flight battery**. Scramble on **BATT** alone — **CART** off.

1. **BATT** → On.
2. **CRYO** → On. Wait CHARM page **MAG T K** &lt; 35 and **CRYO** col = `0001` (green) — that is `go-cryo`.
3. **MAGNET** → Arm. Wait go-magnet.
4. **FUEL** → On.
5. **VACUUM** → Ready.
6. **RF** → On.
7. **CHARM** (REACTOR POWER) → On.
8. **DEC** → On.
9. Confirm CHARM CRT **mode = POWER** and bus MW rising.

### 2. Engine (center console — not a “MAIN ENGINE” button)
There is no power-up button for the single nozzle. After CHARM is in **POWER**:

1. Confirm **CMD 1** on the STAGE CRT. Use the left/right black **STG** pushbuttons for Stage −/+.
2. Hold `KP 9` to throttle up for the takeoff roll. The visible heritage center throttle is not the Grenadier command source.
3. Climb: Stage 2 when schedule allows (inlets open).
4. Before Stage 3: seal inlets; need water. Then Stage 3.
5. MECO / circularize on bus; RCS for attitude only.

Ignore blanked **MAIN ENGINE LEFT/RIGHT** shutdown and FUEL CELL REAC VLV labels. The former SRB/ET SEP pushbuttons are now explicitly relabeled **STAGE − / +**; their stack-separation behavior is removed.

### 3. If something breaks
- **SCRAM**: Main Eng Limit → **Enable** (center console; keep that switch).

## CDR vs PLT

| Function | CDR | PLT | Center |
|----------|-----|-----|--------|
| Stick | yes | yes | — |
| Plant row (BATT…DEC) | look right | **yes** | — |
| Stage ± and SCRAM | yes | yes | **yes** |
| Throttle (`KP 9/3`) | yes | yes | — |
| MEDS CHARM/STAGE | yes | yes | — |

**Single-pilot scramble:** PLT (or CDR with view slewed to the right wall).

## Related

- [control_map.md](control_map.md) — remap + engraving table  
- [panel_audit.md](panel_audit.md) — keep / blank / remapped  
- Cue cards: CHARM startup → Engine Stage → Ascent (Plan A)  
- Repo root: `charm_p11b_ssto` (aircraft under `CatskillsFusionSSTO/`)
