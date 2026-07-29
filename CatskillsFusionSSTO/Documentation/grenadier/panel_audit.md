# Shuttle panel audit — Grenadier keep / blank / repurpose

Source inventory: 542 `set-tooltip` bindings in `Models/cockpit.xml`
([panel_tooltips_raw.csv](panel_tooltips_raw.csv)).

## Locked decisions

1. **APU OPERATE row** engraved **CART / BATT / CRYO** = ground cart / flight battery / cryo.
2. **APU CNTLR row** engraved **MAGNET / FUEL / RF**.
3. **REACTOR POWER** trio engraved **CHARM / DEC / VACUUM** (light-off / DEC / vacuum).
4. **SCRAM** = Main Engine Limit Shutdown → Enable (center).
5. **Fuel cells / Sys B / R2 surplus / R4 MPS** = inert; paint blanked; hover empty where cleared.
6. **R4 BRAKE ISOL VLV** label kept for landing; heater / LG / NWS paint blanked (unwired).

## Keep

- Flight controls, gear, brakes, NWS, RHC/THC, DAP/RCS, HUD/ADI/HSI, GPC/IDP/MDU
- Cabin fans, lighting, radios/Ku as available, abort CWS
- Remapped plant row (above)

## Blank / obsolete

| Family | Status |
|--------|--------|
| SSME / MPS fill–drain / prevalve / TVC / manf | R4 paint blanked; hover empty |
| Sys B ENGINE CNTLR | Hover empty |
| ET / SRB | Unused |
| OMS engines (except Stage ± arms) | Deleted / unused |
| Fuel cells | Inert |
| APU hydrazine / hyd pumps | Inert (operate/ctrl rows remapped only) |

## Repurpose (v1)

See [control_map.md](control_map.md) for engraving + object + property table.

Stamp script: `scripts/stamp_grenadier_apu_labels.py`.
