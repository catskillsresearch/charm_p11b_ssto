# CHARM reactor startup — CATSKILLS-SSTO-TA-GRENADIER

Operator checklist for **Earth first light** / scramble of the bay CHARM plant.

FG property root: `/fdm/jsbsim/systems/grenadier/charm/`  
FG checklist: `CatskillsGrenadier-reactor-checklists.xml`  
Panel map: [control_map.md](control_map.md) · ascent: [ssto_ascent_checklist.md](ssto_ascent_checklist.md)

Legend: **INPUT** = crew action (use **engraved** name). **√** = go/no-go.

---

## 0. Preconditions

| Step | Action / measurement | INPUT / √ | Property / note |
|------|----------------------|-----------|-----------------|
| 0.1 | Plant mode OFF | √ | `mode` = `OFF` |
| 0.2 | Bay doors as required | INPUT | ops choice |
| 0.3 | √ Water (shield + σ3) | √ | `../engine/water-kg` |
| 0.4 | √ p-¹¹B / proton inventory | √ | `fuel-b11-kg`, `fuel-proton-kg` |
| 0.5 | √ Flight battery ≥ min | √ | `battery-kwh` ≥ `battery-min-kwh` |
| 0.6 | √ No SCRAM latch | √ | `scram` = 0 |

**Scramble:** skip **CART** — stage 7 battery is enough. **CART** only for long pad-tied holds.

---

## 1. Power path

| Step | Engraving | INPUT / √ | Property |
|------|-----------|-----------|----------|
| 1.1 | **BATT** → On | INPUT | `battery-online` = 1 |
| 1.2 | √ Aux bus live | √ | `aux-bus-v` in band |
| 1.3 | **CART** (optional pad GSE) | INPUT | `ground-cart` = 1, `cart-tied` = 1 |

*(Space restart: battery only; budget ≤ ~300–500 kWh.)*

---

## 2. Cryo and magnets

| Step | Engraving | INPUT / √ | Property |
|------|-----------|-----------|----------|
| 2.1 | **CRYO** → On | INPUT | `cryo-enable` = 1 |
| 2.2 | √ Cryo / magnet thermal | √ | `go-cryo`, `magnet-t-k` |
| 2.3 | **MAGNET** → Arm | INPUT | `magnet-arm` = 1 |
| 2.4 | √ Magnet current | √ | `magnet-i-frac` ≥ 0.95 |
| 2.5 | Mode → CRYO | auto / √ | `mode` = `CRYO` |

---

## 3. Fuel and vacuum

| Step | Engraving | INPUT / √ | Property |
|------|-----------|-----------|----------|
| 3.1 | **FUEL** → On | INPUT | `fuel-enable` = 1 |
| 3.2 | √ Fuel ready | √ | `fuel-ready` = 1 |
| 3.3 | **VACUUM** → Ready | INPUT | `vacuum-ready` = 1 |
| 3.4 | Mode → ARM | auto / √ | `mode` = `ARM` |

---

## 4. RF / light-off / DEC

| Step | Engraving | INPUT / √ | Property |
|------|-----------|-----------|----------|
| 4.1 | **RF** → On | INPUT | `rf-enable` = 1 |
| 4.2 | **CHARM** (REACTOR POWER) → On | INPUT | `light-cmd` = 1 |
| 4.3 | √ Plasma proxy | √ | `plasma-proxy` rising |
| 4.4 | Mode → LIGHT | auto | `mode` = `LIGHT` |
| 4.5 | **DEC** → On | INPUT | `dec-online` = 1 |
| 4.6 | √ Bus climbing | √ | `bus-mw` > 0 |
| 4.7 | Mode → POWER | auto | `mode` = `POWER` |
| 4.8 | Detie **CART** if used | INPUT | `cart-tied` = 0 |

---

## 5. Aborts / safing

| Condition | Action |
|-----------|--------|
| Hard trip | SCRAM (Main Eng Limit → Enable) → RF/magnets/fuel inhibit |
| Bus undervolt in POWER | Derate engine; CWS |
| Water empty (σ3) | Engine inhibit; plant may stay POWER |
| Planned shutdown | POWER → ARM → CRYO → OFF |

---

## Panel cheat sheet (right wall)

```
APU OPERATE:     CART | BATT | CRYO
APU CNTLR:       MAGNET | FUEL | RF
REACTOR POWER:   CHARM | DEC | VACUUM
```
