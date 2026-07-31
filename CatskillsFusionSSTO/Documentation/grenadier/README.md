# CATSKILLS-SSTO-TA-GRENADIER

Shuttle-derived FlightGear **test article**: CHARM + 3-cycle electric engine
inside monorepo `charm_p11b_ssto` (`CatskillsFusionSSTO/` = this aircraft).

## In sim

- `./fs.sh` from repo root
- Menu **CATSKILLS-SSTO-TA-GRENADIER** → CHARM / Engine screens
- Help → Checklist → **Grenadier — CHARM startup** / **Steering / taxi** / **Engine stage**
- Ops: [`Nasal/grenadier/grenadier_ops.nas`](../../Nasal/grenadier/grenadier_ops.nas)

## Docs

| File | Role |
|------|------|
| [ssto_ascent_checklist.md](ssto_ascent_checklist.md) | Scramble / ascent + NWS before taxi |
| [control_map.md](control_map.md) | Engraving → switch → property |
| [reactor_startup.md](reactor_startup.md) | CHARM light-off + steering/hyd (§1a) |
| [reactor_operator_model.md](reactor_operator_model.md) | Property bus |
| [engine_operator_model.md](engine_operator_model.md) | Stage gates |
| [panel_audit.md](panel_audit.md) | Keep / blank / remapped |
| [bay_doors.md](bay_doors.md) | Bay / plant access |

Panel logos: `scripts/stamp_grenadier_apu_labels.py` → **CART/BATT/CRYO**, **MAGNET/FUEL/RF**, **REACTOR POWER** / **CHARM/DEC/VACUUM**; heritage R1 power distribution and R2/R4 surplus paint are blanked (R4 keeps **BRAKE ISOL** only); C3 blanks MAIN ENGINE L/R, SRB/ET SEP, FUEL CELL REAC VLV; OMS arms stamped **STAGE −/+**. Small magenta panel-edge lettering is baked into the original cockpit texture atlases by `Models/Grenadier/build_panel_id_labels.py`.

Crew atmosphere: **L1** controls thermal loops and cabin fans, **L2** controls
the live cabin vent and O₂/N₂ valves, and **O1/O2** carry atmosphere and tank
gauges. The cabin stores are virtual O₂/N₂ tanks 23/24 in `shuttle.xml`;
R1's removed O₂/H₂ switches were dummy heritage hardware.
