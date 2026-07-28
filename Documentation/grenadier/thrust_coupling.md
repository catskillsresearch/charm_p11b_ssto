# Dual-control thrust coupling — CATSKILLS-SSTO-TA-GRENADIER

Thrust is the product of **two independent control sets**. Either alone yields zero force on the FDM.

```
CHARM plant (power)          Engine (cycle + throttle)
─────────────────────        ─────────────────────────
mode → POWER                 sigma ∈ {1,2,3}
scram = 0                    stage-go (gates + seal/water for σ3)
bus-mw > 1                   throttle 0…1 (pilot lever)
        \                   /
         \                 /
          v               v
           coupled-ok = 1
                |
                v
     thrust-lbf → JSBSim external_reactions
                  (grenadier_thrust, body −X)
```

## Property outputs

| Property | Meaning |
|----------|---------|
| `engine/plant-ok` | CHARM is POWER and not scrammed |
| `engine/stage-go` | Selected cycle is allowed |
| `engine/coupled-ok` | Plant **and** engine ready with throttle |
| `engine/bus-frac` | Fraction after CHARM cable limit (0…1) |
| `engine/thrust-kn` | Surrogate thrust (display) |
| `engine/thrust-lbf` | Force applied to JSBSim |

## Control map

| Crew action | System |
|-------------|--------|
| Reactor canvas / APU aliases → POWER | Power plant |
| Engine canvas σ1/σ2/σ3, SEAL | Engine cycle |
| Pilot throttle lever (or engine THR±) | Engine throttle demand |

Heritage SSME/OMS `run-cmd` stay off; chemical rockets do not produce Grenadier thrust.

## Exhaust VFX

`vfx/plume-norm` = thrust / peak for the selected σ. Nasal drives:

| Thrust | Visual |
|--------|--------|
| ~idle (`plume-norm` ≳ 0.01) | Small thruster flame (`vfx/flame-scale`) |
| Mid (`≳ 0.12`) | Cyan plasma core trail |
| High (`≳ 0.18`) | Large outer plasma plume (σ3 denser) |

Cold until `coupled-ok` produces thrust (`vfx/show-flame`).

## Files

- Nasal: `Nasal/grenadier/grenadier_ops.nas`
- JSBSim force: `shuttle.xml` → `grenadier_thrust`
- System stub: `Systems/grenadier_propulsion.xml`
- Exhaust: `Models/Effects/Grenadier/grenadier_exhaust.xml`
