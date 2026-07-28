# Plan A ops (no-cargo TA)

Locked in `arxiv.md` §1.2b.

- **No cargo** — bay is plant + water only (`m_pl = 0`).
- **1 GW retained** @ 15 kW/kg → dry ≈ 172 t, GLOW ≈ 211 t.
- **Lander sized to plant** — design land ≈ 190 t; wing ≈ 480 m²; span ≈ 33 m.
- **Structure** — carbon sandwich primary; reusable-only zoned TPS (no ablatives).
- **Home airport** — **KEDW** Edwards AFB runway **22** (FG id for the long paved strip; real-world name is 22L). Alternate **KTTS** SLF.
- **Spawn** — level on gear, parking brake, CHARM **OFF**, throttle 0; onboard battery charged for cold start (no ground cart required).
- **No drag chute** — brakes + long runway only.
- Launch: `./fs.sh` from the charm repo.

Unmodified OV ~104 t landing remains FAIL; Plan A PASS by raising gear/wing/runway, not by shrinking the reactor.

Note: FG **visual** mesh is still heritage-sized; **JSBSim** metrics/mass/gear are Plan A (`Models/Grenadier/PLAN_A_FDM.md`) so flyability uses the stretched numbers.
