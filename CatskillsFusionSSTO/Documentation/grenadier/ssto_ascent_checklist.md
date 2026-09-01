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
| 6 | F8 | Below inboard PLT MDU (R1) | **FLT CNTLR POWER** → **ON** | Guarded toggle, right of **RDR ALTM** (not the HUD brow). Auto-ON with BATT — confirm ON |
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
| 32 | Display R2 | PLT outboard MDU / PFD | Observe PFD / HUD → **~85–90 KEAS** | Not sheet panel R2; HUD airspeed is **KEAS** |
| 33 | Keypad | — | `KP 2` → gentle nose-up | At **~80–90 KEAS** (slow-path loft). Num Lock ON |
| 34 | Keypad | — | `KP 5`, then small `KP 2` / `KP 8` | Trim a **shallow** climb at **~110–125 KEAS** — do not haul into stall. Num Lock ON |
| 35 | Keypad | — | `g` → gear **UP** | Grenadier retracts in flight (`Shift+G` down). STAGE + to σ2 from **~12,000 ft** when MAX/GO allow |

**Control-surface check (steps 8–12) is mandatory before taxi.** If a surface does not move with BATT and Flight Controller Power ON, stop — do not release the parking brake.

**HUD units (use these in the cockpit):** airspeed **KEAS**, altitude **ft**. Provisional targets: rotate **~80–90 KEAS**, σ1 shallow climb **~110–125 KEAS** at ~**2°** path (900 m² / **60 m** wing, AR≈4, paper σ1 T/W≈0.28) — not certified V-speeds.

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

There is no power-up button for the single nozzle. After CHARM is in **POWER**, open the **STAGE** CRT (`CMD` / `MAX` / `GO` / `SEAL` / `THR`) and fly the four slow-path segments below. Stage command is manual: left/right black **STG** pushbuttons (former SRB/ET SEP) for Stage −/+. Throttle is `KP 9` / `KP 3` only — the heritage center throttle is not the Grenadier command source.

Ignore blanked **MAIN ENGINE LEFT/RIGHT** shutdown and FUEL CELL REAC VLV labels.

## Ascent stages (slow path)

Plan A TA profile: **900 m² / 60 m** wing (AR≈4), paper thrust freeze (σ1 T/W≈0.28 at GLOW — wing-borne climb, not a vertical rocket). Pad to ISS ≈ **5 h** total.

**Units match the HUD / cockpit:** airspeed **KEAS** (HUD tape / readout from equivalent airspeed), altitude **ft**, climb **fpm**, along-track **nmi**. At high altitude KEAS falls toward zero even as true speed rises — σ2/σ3 energy targets are therefore also given as **fps** (relative / inertial scale). Speeds and times are provisional; σ2/σ3 durations follow the paper energy freeze. Along-track is path length while thrusting, not great-circle distance from Edwards.

**σ2 is not Shuttle main engines.** In dense air (teens of kft) nose-down acceleration tops out near **Mach ~0.85 / ~400+ KEAS** where drag rise meets density-derated thrust. That wall is expected. Later, true speed rises while HUD KEAS falls — fly energy / STAGE cues, not “more KEAS forever.”

### Takeoff roll (σ1)

| | |
|--|--|
| Stage | σ1 (EDF) — confirm `CMD 1` `MAX≥1` `GO 1` `PLANT 1` on STAGE CRT |
| Speed | 0 → **~85–90 KEAS** |
| Climb rate | 0 (on runway) |
| Time | ≈ **18 s** |
| Heading | KEDW **Rwy 22** (~224°) |
| Altitude | **0 ft** |
| Along-track | ≈ **0.2 nmi** |

Release the parking brake (`Shift+B`), hold `KP 9` to `THR 100`, and verify `CPL 1` with thrust / `DRAW` rising. Keep the nosewheel on centerline with small `KP 0` / `KP Enter` taps. Rotate with a gentle `KP 2` at **~80–90 KEAS** — do **not** wait for a high KEAS that puts you on the stall edge. Gear stays **DOWN** until you are cleanly airborne and trimmed.

### Stage 1 → Stage 2 (σ1)

| | |
|--|--|
| Stage | σ1 until handoff; then **STAGE +** → σ2 |
| Speed | Shallow climb at **~110–125 KEAS** |
| Climb rate | ≈ **1,000–1,500 fpm** (path ~**2°** — not a zoom) |
| Time | ≈ **13 min** |
| Heading | Runway / departure heading |
| Altitude | **0 → 12,000 ft** |
| Along-track | ≈ **24 nmi** |

Trim a **shallow** climb — small `KP 2` / `KP 8` after `KP 5` center. Hauling the nose bleeds energy and puts you back on the stall. Retract gear (`g`) once climbing. Watch STAGE CRT: when HUD altitude approaches **~12,000 ft** and `MAX` / `GO` allow σ2, press the right black **STG** (**STAGE +**). Do not wait until the EDF is gasping in thinner air; the slow-path gate opens σ2 here on purpose.

### Stage 2 → Stage 3 (σ2)

| | |
|--|--|
| Stage | σ2 (air plasma); inlets **open** |
| Speed | Early climb **~150–200 KEAS**; dense-air wall ~**400+ KEAS / M0.85**. Then KEAS falls as true speed rises. Energy target ≈ **11,500 fps** at seal (Mach_seal ≈ 11) |
| Climb rate | Hold **~1,000–1,500 fpm** / ~**2°** path early; segment average ≈ **4,100 fpm** is mostly later energy into speed |
| Time | **28.7 min** (paper \(t_2\)) |
| Heading | Mission azimuth toward the **ISS plane** (51.6° class) |
| Altitude | **12,000 → 130,000 ft** (seal) |
| Along-track | ≈ **1,670 nmi** |

Do **not** chase zoom climbs or a fixed high KEAS. On the STAGE CRT watch thrust, `DRAW`, and `REC` / seal cues. Before aero authority dies, engage RCS (below). Before σ2 stalls in rarefied air: set **SEAL** (inlets sealed), confirm water inventory, and when `MAX` / `GO` allow, **STAGE +** to σ3.

### RCS when the air runs out

The single nozzle is **axial thrust only** — it does not steer. Direction/attitude in thin air is **heritage Shuttle RCS / DAP** (OMS pods are RCS-only on Grenadier).

| | |
|--|--|
| Engage | **`Ctrl+m`** cycles control mode → look for HUD string **`RCS ROT DAP-A`** (or similar). Or Panel **A6** Orbital DAP (AUTO / INRTL / LVLH / FREE, DAP A/B). |
| Stick (RHC) | Same axes command **rotation** jets, not elevons. |
| Translate (THC) | Press **`m`** to toggle RHC ↔ THC. HUD string becomes **`RCS TRANS …`**. Keypad then maps to **body translate**, including reverse. |
| Automatic? | **Not by altitude.** Heritage auto-launch arms RCS after MECO/ET-sep events; Grenadier ascent does **not** auto-hand over when qbar falls — you switch. |
| HUD | Control-mode string (`/controls/shuttle/control-system-string`) — e.g. `RCS ROT DAP-A` vs `RCS TRANS DAP-A`. HUD still shows body-flap / gear / speedbrake; it does **not** paint per-jet RCS pulses. |
| MDU | DPS **SPEC 20** (DAP config), **SPEC 23** (RCS jet status). Thruster flames are external VFX when jets fire. |
| Propellant | FWD / aft RCS tanks (OMS/RCS gauges) — keep inventory for attitude through σ3 / insertion. |

**THC keypad map** (Num Lock ON; only after `m` → TRANS — not the main-engine throttle):

| Key | THC translate |
|-----|----------------|
| `KP 0` | **−X aft** (backwards) |
| `KP Enter` | **+X forward** |
| `KP 4` / `KP 6` | **±Y** left / right |
| `KP 2` / `KP 8` | **±Z** up / down (elevator sense) |
| `KP 5` | center / stop pulse |
| `KP 9` / `KP 3` | still **CHARM throttle** — not RCS ±X |

`KP 9` only opens the big nozzle; it cannot fire RCS aft. For reverse Δv use **`m` → THC → `KP 0`**.

Switch to RCS **before** elevons go soft (late σ2 / seal). Use RHC for attitude, THC when you need translate (including backwards); the engine still provides the long axial Δv in σ3.

### Stage 3 → ISS (σ3)

| | |
|--|--|
| Stage | σ3 (water plasma); `SEAL 1`, water &gt; ~10 kg |
| Speed | ≈ **11,500 → 25,200 fps** (ISS circular ~1,310,000 ft — not Earth escape). HUD **KEAS** is not the useful cue here |
| Climb rate | ≈ **4,500 fpm** geometric average over the segment |
| Time | **4.33 h** (paper \(t_3\)) |
| Heading | Orbital / plane-change margin |
| Altitude | **130,000 → ~1,310,000 ft** |
| Along-track | ≈ **47,000 nmi** |

This is a long, mostly horizontal insertion burn at T/W≈0.03 — not standing on the tail. The ~47,000 nmi figure is **path length** at orbital speeds over 4.3 h (multiple Earth revolutions of arc), not “Edwards to ISS in a straight line.” Circularize on the bus when apoapsis / velocity match the ISS target; use RCS for attitude only. MECO when insertion is complete.

### If something breaks

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
