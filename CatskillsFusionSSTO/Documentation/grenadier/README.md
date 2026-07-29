# CATSKILLS-SSTO-TA-GRENADIER

Shuttle-derived FlightGear **test article**: CHARM + 3-cycle electric engine
inside monorepo `charm_p11b_ssto` (`CatskillsFusionSSTO/` = this aircraft).

## In sim

- `./fs.sh` from repo root
- Menu **CATSKILLS-SSTO-TA-GRENADIER** → CHARM / Engine screens
- Help → Checklist → **Grenadier — CHARM startup** / **Grenadier — Engine stage**
- Ops: [`Nasal/grenadier/grenadier_ops.nas`](../../Nasal/grenadier/grenadier_ops.nas)

## Docs

| File | Role |
|------|------|
| [ssto_ascent_checklist.md](ssto_ascent_checklist.md) | Scramble / ascent (current engravings) |
| [control_map.md](control_map.md) | Engraving → switch → property |
| [reactor_startup.md](reactor_startup.md) | CHARM light-off checklist |
| [reactor_operator_model.md](reactor_operator_model.md) | Property bus |
| [engine_operator_model.md](engine_operator_model.md) | Stage gates |
| [panel_audit.md](panel_audit.md) | Keep / blank / remapped |
| [bay_doors.md](bay_doors.md) | Bay / plant access |

Panel logos: `scripts/stamp_grenadier_apu_labels.py` → **CART/BATT/CRYO**, **MAGNET/FUEL/RF**, **REACTOR POWER** / **CHARM/DEC/VACUUM**; R4 MPS blanked.
