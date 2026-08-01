# SSTO ascent checklist (Grenadier TA)

## Quick Start — cold runway to initial climb (PLT)

Magenta cockpit labels show **Panel ID** + purpose on each live plate. MDU
display positions also use names such as `R1`/`R2`, but those are **not** the
same thing as sheet panels R1/R2. Non-panel inputs use **Keypad** or **Mouse**.
For cockpit clicks: press **Ctrl** so the mouse is in pick/clickable mode (not
view-drag); **Esc** releases pointer capture if the view has grabbed the mouse.

| Step | Panel ID | Panel Purpose | Switch / Setting | Notes |
|------|----------|---------------|------------------|-------|
| 1 | Keypad | — | `v` / `Shift+V` → **Pilot** (right seat) | Cycle views until Pilot |
| 2 | Mouse | PLT inboard MDU bezel | **R1 display POWER** rotary → **ON** | Small rotary immediately inboard of the R1 screen; hover says `R1 Power`. Do **not** use sheet panel R1 (POWER DISTRIBUTION). Ctrl = clickable; screen dark until BATT |
| 3 | Mouse | PLT outboard MDU bezel | **R2 display POWER** rotary → **ON** | Small rotary immediately inboard of the R2 screen; hover says `R2 Power`. This is separate from sheet panel R2. Ctrl = clickable; screen dark until BATT |
| 4 | R2 | CHARM plant / propulsion controls | **BATT** (APU OPERATE) → **ON** | Mouse; electric hyd live (NWS / brakes / aero). CHARM `V` ~260 |
| 5 | F8 | PLT HUD | **HUD Power** → **ON**; mode **NORM** | Mouse; brightness AUTO or DAY |
| 6 | F8 | PLT HUD | **Flight Controller Power** → **ON** | Mouse; auto-ON with BATT — confirm ON |
| 7 | Keypad | — | **Num Lock** → **ON** | Required for all KP flight / throttle keys below |
| 8 | Keypad | — | `v` → external view (wing TE + vertical tail) | Num Lock stays ON; Chase/Helicopter OK |
| 9 | Keypad | — | Hold `KP 2`, then hold `KP 8` | Elevons TE down then up; watch both wings. Num Lock ON |
| 10 | Keypad | — | Hold `KP 4`, then hold `KP 6` | Roll: opposite wing motion. Num Lock ON |
| 11 | Keypad | — | Hold `KP 0`, then hold `KP Enter` | Rudder L/R; nosewheel steers on gear. Num Lock ON |
| 12 | Keypad | — | `KP 5` | Center elevator / aileron / rudder. Num Lock ON |
| 13 | Keypad | — | `v` / `Shift+V` → **Pilot** | Back to right seat before plant scramble |
| 14 | Mouse | PLT inboard MDU (display position R1) | Softkeys → **CHARM** page | Ctrl = clickable. MAIN → SUBSYS STATUS → CHARM if needed |
| 15 | R2 | CHARM plant / propulsion controls | **CRYO** → **ON** | Mouse; wait `T·K < 35`, green `CRYO 0001` |
| 16 | R2 | CHARM plant / propulsion controls | **MAGNET** → **ARM/ON** | Mouse; wait green `MAG` / `MAGI` ~100 |
| 17 | R2 | CHARM plant / propulsion controls | **FUEL** → **ON** | Mouse |
| 18 | R2 | CHARM plant / propulsion controls | **VACUUM** → **ON/READY** | Mouse; `VAC 0001`, green `FUEL` |
| 19 | R2 | CHARM plant / propulsion controls | **RF** → **ON** | Mouse |
| 20 | R2 | CHARM plant / propulsion controls | **CHARM** → **ON** | Mouse; mode → `LIGHT` |
| 21 | R2 | CHARM plant / propulsion controls | **DEC** → **ON** | Mouse |
| 22 | Display R1 | PLT inboard MDU | Confirm `MODE POWER`, green `BUS` | Observe CHARM page; bus MW rising. Not sheet panel R1 |
| 23 | Mouse | PLT inboard MDU (display position R1) | Softkey **STAGE**; `CMD 1` `MAX 1` `GO 1` `PLANT 1` `THR 000` | Ctrl = clickable |
| 24 | Keypad | — | `KP 5` | Re-center controls. Num Lock ON |
| 25 | Keypad | — | Hold `KP 3` → idle / `THR 000` | Num Lock ON |
| 26 | Keypad | — | Leave parking brake **SET** | Do not press `Shift+B` yet |
| 27 | R2 | CHARM plant / propulsion controls | **CART** → leave **OFF** | Scramble does not need cart |
| 28 | C6 / C7 | Gear / NWS / brakes · Speedbrake / body flap | Gear **DOWN**, speedbrake **IN**, `SEAL 0` | Confirm config; controls neutral |
| 29 | Keypad | — | `Shift+B` → release parking brake | — |
| 30 | Keypad | — | Hold `KP 9` → `THR 100` | Num Lock ON; verify `CPL 1`, thrust / `DRAW` rising |
| 31 | Keypad | — | Tap `KP 0` / `KP Enter` | Small NWS taps for centerline. Num Lock ON |
| 32 | Display R2 | PLT outboard MDU / PFD | Observe PFD / HUD → **~210 KIAS** | Not sheet panel R2 |
| 33 | Keypad | — | `KP 2` → gentle nose-up | At ~200–220 KIAS (Plan A loft). Num Lock ON |
| 34 | Keypad | — | `KP 5`, then small `KP 2` / `KP 8` | Trim a **shallow** climb at ~240–280 KIAS — avoid chasing pitch into stall/dive. Num Lock ON |
| 35 | Keypad | — | `g` → gear **UP** | Grenadier retracts in flight (`Shift+G` down). Stay Stage 1 until STAGE page recommends Stage 2 |

**Control-surface check (steps 8–12) is mandatory before taxi.** If a surface does not move with BATT and Flight Controller Power ON, stop — do not release the parking brake.

**~200–220 KIAS** rotate / **240–280 KIAS** shallow climb are provisional Plan A loft targets (600 m² / 38 m wing), not certified V-speeds.

Keypad: `2/8` elevon, `4/6` roll, `0/Enter` rudder/NWS, `5` center, `9/3` throttle. Hold to drive a surface; tap for runway corrections.

Beginner path: **PLT** (right seat) for plant row; center console **C3** for Stage ± / SCRAM; keypad for flight/throttle. Use engraved names on yellow panel-ID labels / plant row — not heritage Shuttle lettering. Hover empty = blanked / ignore.

CHARM mode `OFF → CRYO → ARM → LIGHT → POWER` is **derived** (CHARM MEDS page).

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

## Steering before taxi (replaces Shuttle APU–hyd)

Same as Quick Start steps 1–13. Cold pad = no hyd until **BATT**; no heritage APU start. Surface check works as soon as BATT is on; thrust still needs CRYO…DEC → POWER.

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

Do **not** start heritage APUs. **BATT** powers electric hyd packs so nosewheel steering (`KP 0` / `Enter`) and aero surfaces work. Stay in **Pilot** view so the stick/keypad are live.

1. **BATT** → On (hyd + flight-controller power arm).
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
3. Climb on σ1 while air is dense; thrust falls with density and stalls near ~50 kft — Stage + to σ2 when MAX/GO allow (inlets open).
4. σ2 also fades in thin air; before it stalls: seal inlets, confirm water, Stage + to σ3.
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
