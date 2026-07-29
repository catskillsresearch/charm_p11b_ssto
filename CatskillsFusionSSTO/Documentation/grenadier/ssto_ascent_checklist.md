# SSTO ascent checklist (Grenadier TA)

Beginner path: **sit PLT (right seat)** for plant switches; **center** for Stage ± / SCRAM / throttle.

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
| Stage − / + | Center console | Stage −/+ · `oms-eng-left` / `oms-eng-right` |
| SCRAM | Center | Main Eng Limit → Enable · `main-eng-limit-shut-dn` |
| Throttle | Center | Engine throttle |

**Landing only (panel R4):** **BRAKE ISOL VLV** stays labeled (leave OPEN). All other R4 paint is blanked — leave those switches alone.

## CRT pages

On an MDU: **MAIN → SUBSYS STATUS**

| Softkey | Page | Use for |
|---------|------|---------|
| **CHARM** | plant | mode, BATT/CRYO/MAGNET/FUEL/RF/DEC, bus |
| **STAGE** | engine | Stage 1/2/3, throttle, seal, water, thrust |
| SPI | leave | not required for scramble |

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

### 2. Engine (center)
1. Stage = 1 (OMS L/R = Stage − / +).
2. Throttle up for takeoff roll.
3. Climb: Stage 2 when schedule allows (inlets open).
4. Before Stage 3: seal inlets; need water. Then Stage 3.
5. MECO / circularize on bus; RCS for attitude only.

### 3. If something breaks
- **SCRAM**: Main Eng Limit → **Enable** (center).

## CDR vs PLT

| Function | CDR | PLT | Center |
|----------|-----|-----|--------|
| Stick | yes | yes | — |
| Plant row (BATT…DEC) | look right | **yes** | — |
| Stage ±, SCRAM, throttle | yes | yes | **yes** |
| MEDS CHARM/STAGE | yes | yes | — |

**Single-pilot scramble:** PLT (or CDR with view slewed to the right wall).

## Related

- [control_map.md](control_map.md) — remap + engraving table  
- [panel_audit.md](panel_audit.md) — keep / blank / remapped  
- Cue cards: CHARM startup → Engine Stage → Ascent (Plan A)  
- Repo root: `charm_p11b_ssto` (aircraft under `CatskillsFusionSSTO/`)
