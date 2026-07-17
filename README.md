# p11b

An open-source, general-purpose simulation framework for proton–boron-11
(`p–¹¹B`) fusion architectures.

The long-term goal is an application that provides useful, transparent
**digital twins** of the major reactor architectures cataloged in
[`pb11.md`](pb11.md). A model should reproduce the defining geometry,
controls, operating sequence, plasma assumptions, diagnostics, losses, and
energy-conversion path of its source architecture as accurately as public data
allows.

This repository is currently a **documentation-first scaffold**. It contains
the state-of-the-art survey and its research archive, but no simulator
implementation yet.

## Why this project

The headline reaction is:

```text
p + ¹¹B → 3 α + 8.7 MeV
```

The fuel is abundant and non-radioactive, and the principal products are
charged alpha particles. That creates a potential path to direct electrical
conversion without a tritium-breeding blanket or the intense 14.1 MeV neutron
flux of deuterium–tritium fusion.

It is also an exceptionally difficult fuel. Any credible model must confront:

- the high energy required for useful reaction rates;
- Bremsstrahlung and other radiation losses;
- ion–electron energy transfer and the Rider limit;
- non-Maxwellian, beam-target, or otherwise structured kinetics;
- confinement, ash removal, impurities, and material loading;
- driver and recirculating power;
- direct and thermal energy conversion; and
- the distinction between plasma gain, engineering gain, and net electricity.

`p11b` is intended to make those tradeoffs comparable across architectures
rather than hide them behind unrelated one-off demonstrations.

## Architecture scope

The initial scope follows the catalog in [`pb11.md`](pb11.md):

- **Magnetic confinement**
  - spherical torus and related closed magnetic systems;
  - beam-driven field-reversed configurations (FRCs);
  - rotating mirrors and multi-chamber open-field concepts;
  - relevant helical and stellarator experiments.
- **Laser and inertial systems**
  - laser block ignition;
  - beam-target and high-energy-density-physics targets;
  - nanostructured and compressed-target concepts.
- **Magneto-inertial and pinch systems**
  - dense plasma focus (DPF);
  - pulsed plasmoid and related compression systems.
- **Magneto-electrostatic and electrostatic systems**
  - Orbitron-class magneto-electrostatic confinement (MEC);
  - inertial electrostatic confinement (IEC);
  - nanosecond vacuum-discharge virtual-cathode systems.
- **Cross-cutting physics**
  - thermal and nonthermal reaction kinetics;
  - alpha spectra, transport, channeling, and ash;
  - Bremsstrahlung, synchrotron, conduction, and end losses;
  - direct energy conversion and thermal recovery;
  - materials, controls, diagnostics, and plant power balance.

Sister-fuel machines may be modeled when they illuminate a relevant
architecture, but the project’s target fuel and comparison basis remain
`p–¹¹B`.

## What “digital twin” means here

The term is used in levels. Not every public architecture has enough data for a
high-fidelity twin.

1. **Concept model** — documented geometry, reaction model, controls, phases,
   and zeroth-order power balance.
2. **Reduced-order twin** — calibrated 0D/1D dynamics with uncertainty bounds
   and reproducible operating points.
3. **Spatial twin** — 2D/3D fields, particles or fluids, boundary interactions,
   and synthetic diagnostics.
4. **Validated twin** — parameters calibrated against published measurements,
   with explicit validation cases and residuals.
5. **Operational twin** — synchronized with live hardware telemetry. This level
   is only possible with cooperation and data from a device operator.

Every model should identify its level and clearly separate measured inputs,
literature assumptions, fitted parameters, and speculative extrapolations.

## Modeling principles

- **Evidence before appearance.** A visually convincing animation is not
  validation.
- **Common accounting.** Architectures should report comparable quantities:
  fusion power, radiation, transport, driver power, recovered power,
  `Q_plasma`, engineering `Q`, and net electric output.
- **Traceable assumptions.** Equations and constants should cite primary
  sources where possible.
- **Uncertainty is an output.** Sparse or disputed nuclear and machine data
  should produce ranges, not false precision.
- **Architecture-specific physics.** A common interface must not flatten
  fundamentally different devices into the same toy model.
- **Reproducibility.** Published scenarios should include configuration,
  random seeds, software version, and validation artifacts.
- **Honest limitations.** No model should imply demonstrated reactor
  performance where only component experiments or conceptual studies exist.

The feasibility gates in [`pb11.md`](pb11.md)—fuel data, kinetics, radiation,
ash, Lawson/engineering gain, confinement, materials, breeding where relevant,
technology maturity, in-silico iteration, and hardware iteration—provide the
initial comparison rubric.

## Planned application

The intended application will eventually support:

- selection of a reactor architecture;
- architecture-specific geometry and control inputs;
- steady-state and pulsed operating sequences;
- optimization with physically bounded parameters;
- coupled reduced-order and spatial solvers;
- time-resolved particle, field, plasma, and power diagnostics;
- side-by-side scenario and architecture comparison;
- uncertainty and sensitivity analysis;
- validation against published experiments; and
- reproducible plots, data exports, and narrated visualizations.

No implementation architecture or GUI toolkit is fixed at this stage. The
Poetry scaffold supplies the numerical and visualization foundation without
committing the project to a particular solver design.

## Repository contents

```text
.
├── pb11.md          State-of-the-art survey and architecture catalog
├── research/        Survey research materials and figure provenance
├── pyproject.toml   Python/Poetry project definition
├── poetry.lock      Reproducible dependency resolution
├── LICENSE          Apache License 2.0
└── NOTICE           Attribution and third-party-material notice
```

The files under `research/` were copied verbatim from the survey repository.
They may include third-party material. Their inclusion documents sources and
does **not** grant rights beyond the original authors’ or publishers’ terms.
See [`research/figures/CREDITS.md`](research/figures/CREDITS.md) and
[`NOTICE`](NOTICE).

## Installation

Python 3.12–3.14 and [Poetry](https://python-poetry.org/) are expected.

```bash
poetry install
```

There is not yet an executable simulator.

## Project status

Pre-implementation. The immediate work is to turn the survey taxonomy into:

1. a common model and diagnostics interface;
2. explicit fidelity and validation requirements;
3. architecture-specific specifications; and
4. the first reference implementation.

## License, safety, and limitations

Original project software and documentation are licensed under the
[Apache License 2.0](LICENSE), subject to the third-party exceptions described
in [`NOTICE`](NOTICE).

This project is for theoretical research, education, and software development.
It is **not** an engineering specification, operational procedure, safety
analysis, investment recommendation, or claim of reactor feasibility. Models
may be incomplete, unvalidated, AI-assisted, or wrong. Users are responsible
for independent verification and for determining whether any use is
appropriate.

The software is provided **“AS IS,” without warranties or conditions of any
kind**. See Sections 7 and 8 of the Apache License 2.0 for the warranty
disclaimer and limitation of liability.

Copyright 2026 Catskills Research Company.
