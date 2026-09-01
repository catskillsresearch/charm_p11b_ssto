# Grenadier to orbit (buttons only)

PLT (right seat). **Ctrl** = clickable. **Num Lock ON** for keypad.

Three engines, one nozzle — you switch them: **σ1 EDF → σ2 air plasma → σ3 water**. Center console right **STG** = STAGE **+**. STAGE CRT: `CMD` / `MAX` / `GO`. Throttle is always `KP 9` / `KP 3`.

## 0. Cold pad → scramble

1. `v` / `Shift+V` → **Pilot**
2. **R1 display POWER** → **ON**
3. **R2 display POWER** → **ON**
4. **BATT** → **ON**
5. **HUD Power** → **ON**, mode **NORM**
6. **FLT CNTLR POWER** → **ON** (below inboard PLT MDU / R1, right of **RDR ALTM**; may auto-ON with BATT)
7. **Num Lock** → **ON**
8. `v` → external (wing TE)
9. Hold `KP 2`, then `KP 8` — elevons
10. Hold `KP 4`, then `KP 6` — roll
11. Hold `KP 0`, then `KP Enter` — rudder / NWS (`[` / `]` also work)
12. `KP 5` — center
13. `v` / `Shift+V` → **Pilot**
14. R1 softkeys → **CHARM**
15. **CRYO** → **ON** (wait `T·K < 35`, green `CRYO`)
16. **MAGNET** → **ARM/ON** (wait green `MAG`)
17. **FUEL** → **ON**
18. **VACUUM** → **ON/READY**
19. **RF** → **ON**
20. **CHARM** → **ON** (mode `LIGHT`)
21. **DEC** → **ON**
22. Confirm CHARM `MODE POWER`, green `BUS`
23. R1 softkey → **STAGE** (`CMD 1` `MAX 1` `GO 1` `PLANT 1` `THR 000`)
24. `KP 5` — center
25. Hold `KP 3` → idle / `THR 000`
26. **CART** — leave **OFF**
27. Gear **DOWN**, speedbrake **IN**, `SEAL 0`

## 1. Takeoff / σ1 EDF (0 → 12,000 ft)

28. `Shift+B` — release parking brake
29. Hold `KP 9` → `THR 100` (`CPL 1`, thrust / `DRAW` rising)
30. Tap `KP 0` / `KP Enter` — centerline
31. **~80–90 KEAS**: `KP 2` — rotate
32. `g` — gear **UP**
33. `KP 5`, then small `KP 2` / `KP 8` — shallow climb **~110–125 KEAS**, ~**2°** / **1,000–1,500 fpm**
34. **~12,000 ft**, `MAX` / `GO` allow σ2: right **STG** (STAGE **+**) → `CMD 2`

## 2. σ2 air plasma (12,000 → 130,000 ft)

35. Confirm STAGE `CMD 2`, σ2 `THR% 100`, inlets **open** (`SEAL 0`)
36. Keep `KP 9` at `THR 100`
37. Early: **~150–200 KEAS**, still ~**2°** / **1,000–1,500 fpm** — do not zoom
38. Dense-air wall **~400+ KEAS / M0.85** is normal; then KEAS falls while true speed rises
39. Before elevons go soft (late σ2): **`Ctrl+m`** until HUD **`RCS ROT DAP-A`**
40. Near **~130,000 ft**: **SEAL** → `SEAL 1`; confirm water; `MAX` / `GO` allow σ3
41. Right **STG** (STAGE **+**) → `CMD 3`

## 3. RCS (thin air — nozzle does not steer)

42. HUD must show **`RCS ROT DAP-A`** (or **`Ctrl+m`** again). Panel **A6** Orbital DAP if needed
43. Keypad / stick = **rotation** jets, not elevons
44. **`m`** → THC (`RCS TRANS …`) if you need translate
    - `KP 0` −X aft · `KP Enter` +X · `KP 4/6` ±Y · `KP 2/8` ±Z · `KP 5` stop
    - `KP 9` / `KP 3` still **CHARM throttle**, not RCS

## 4. σ3 water → ISS (130,000 → ~1,310,000 ft)

45. Confirm `CMD 3`, `SEAL 1`, water &gt; ~10 kg, `THR 100`
46. Fly energy, not KEAS: **~11,500 → 25,200 fps**
47. Long shallow burn (~**4.3 h**). RCS for attitude only
48. Circularize when velocity / apoapsis match ISS
49. MECO: hold `KP 3` → `THR 000`

**SCRAM:** center **Main Eng Limit** → **Enable**. STAGE **−** (left **STG**) steps back if you jumped early.
