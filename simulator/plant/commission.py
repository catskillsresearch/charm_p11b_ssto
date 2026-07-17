"""0-order cold-start / shot-cycle commission sequences.

Stages are survey- and publication-sourced where possible; long facility steps
use time warps (instant clock jump + ledger debit) so wall-clock stays usable.
Starter-battery debit applies only when batt_powered=True — vacuum halls are
usually on facility AC, not the islanded pack.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from simulator.plant.site_io import SiteIOState
from simulator.plant.streams import StreamBus


@dataclass(frozen=True)
class CommissionStage:
    id: str
    label: str
    duration_s: float
    aux_MW: float = 0.0
    energy_kWh: float = 0.0
    time_warp: bool = False
    batt_powered: bool = True
    plasma: bool = False
    source: str = ""


@dataclass
class CommissionState:
    stages: list[CommissionStage] = field(default_factory=list)
    index: int = 0
    stage_elapsed_s: float = 0.0
    done: bool = False
    shot_complete: bool = False

    @property
    def current(self) -> CommissionStage | None:
        if self.done or self.index >= len(self.stages):
            return None
        return self.stages[self.index]

    @property
    def plasma_allowed(self) -> bool:
        cur = self.current
        return bool(cur and cur.plasma)


def sequences_for_slug(slug: str) -> list[CommissionStage]:
    from simulator.plant.operation_mode import mode_for_slug

    # Continuous plant architectures use APU/operator loop — no single-shot commission
    if mode_for_slug(slug) == "continuous_plant":
        return []
    return dict(_SEQUENCES).get(slug, [])


def fresh_commission(slug: str) -> CommissionState:
    stages = list(sequences_for_slug(slug))
    return CommissionState(stages=stages, done=not stages)


def stage_power_MW(stage: CommissionStage) -> float:
    one = 0.0
    if stage.duration_s > 0 and stage.energy_kWh > 0:
        one = stage.energy_kWh * 3.6 / stage.duration_s
    return max(0.0, stage.aux_MW) + one


def _debit_batt(site: SiteIOState, bus: StreamBus, need_MW: float, dt_s: float) -> None:
    kWh = need_MW * dt_s / 3.6
    site.batt_kWh = max(0.0, site.batt_kWh - kWh)
    site.energy_from_batt_kWh += kWh
    if site.batt_kWh <= 0:
        site.batt_kWh = 0.0
        bus.alarm(bus.get("t"), "trip", "BATT", "Starter battery depleted — islanded plant offline")


def _advance_index(comm: CommissionState) -> None:
    comm.index += 1
    comm.stage_elapsed_s = 0.0
    if comm.index >= len(comm.stages):
        comm.done = True


def apply_commission_tick(
    comm: CommissionState,
    site: SiteIOState,
    bus: StreamBus,
    dt: float,
    clock_t: float,
) -> tuple[float, bool, float]:
    """Returns (clock_t', plasma_allowed, step_dt).

    Prep battery debit happens here. Plasma electrical uses site_io / P_import.
    """
    if comm.done or not comm.stages:
        return clock_t, True, dt

    def _warp_stage(stage: CommissionStage, t0: float) -> float:
        """Apply one prep stage instantly; return new clock time. Updates site/bus."""
        p_mw = stage_power_MW(stage)
        bus.set("t", t0)
        # Endpoint samples so stripcharts show the jump (battery step, flat powers)
        soc0 = site.batt_kWh / max(site.batt_kWh_cap, 1e-9)
        bus.set("batt_SOC", soc0)
        bus.set("batt_kWh", site.batt_kWh)
        bus.set("batt_draw_kW", p_mw * 1000.0 if stage.batt_powered else 0.0)
        bus.commit_sample(t0)

        bus.alarm(
            t0,
            "info",
            "TIMEWARP",
            f"{stage.label}: +{stage.duration_s:g}s · {stage.source}",
        )
        kWh = p_mw * stage.duration_s / 3.6
        if stage.batt_powered:
            _debit_batt(site, bus, p_mw, stage.duration_s)
        else:
            bus.alarm(
                t0,
                "info",
                "FACILITY",
                f"{stage.label}: {kWh:.2f} kWh @ {p_mw:g} MW on facility bus (not starter batt)",
            )
        t1 = t0 + stage.duration_s
        site.t_run += stage.duration_s
        soc1 = site.batt_kWh / max(site.batt_kWh_cap, 1e-9)
        bus.set("t", t1)
        bus.set("batt_SOC", soc1)
        bus.set("batt_kWh", site.batt_kWh)
        bus.set("batt_used_kWh", site.energy_from_batt_kWh)
        bus.set("batt_draw_kW", 0.0)
        bus.set("preprod_remaining_s", 0.0)
        bus.set("apu_bootstrap_s", stage.duration_s)
        bus.set("apu_ramp", 1.0)
        bus.commit_sample(t1)
        bus.alarm(t1, "info", "STAGE", f"Completed: {stage.label}")
        return t1

    # Warp *all* non-plasma prep — no sitting through static arm/bank graphs
    while True:
        stage = comm.current
        if stage is None:
            return clock_t, False, dt
        if stage.plasma:
            break
        clock_t = _warp_stage(stage, clock_t)
        _advance_index(comm)
        if comm.done:
            comm.shot_complete = True
            return clock_t, False, dt

    stage = comm.current
    if stage is None:
        return clock_t, False, dt

    # Plasma / shot window: honest sim duration (e.g. 40 ms) but play back over
    # several wall-clock seconds so the operator can see powers/Q before Shot end.
    playback_wall_s = max(stage.duration_s, 8.0)  # ≥8 s wall for short research shots
    remaining = max(0.0, stage.duration_s - comm.stage_elapsed_s)
    if comm.stage_elapsed_s <= 0:
        bus.set("chart_zoom_t0", 0.0)  # shot charts use shot_t_ms, not wall t
        bus.set("shot_duration_s", stage.duration_s)
        bus.alarm(
            clock_t,
            "info",
            "SHOT",
            f"{stage.label}: {stage.duration_s*1000:g} ms sim · "
            f"~{playback_wall_s:g}s slow-mo playback · {stage.source}",
        )

    # Each UI tick (~dt wall) advances this much plant time
    sim_per_wall = stage.duration_s / playback_wall_s
    step = min(remaining, max(sim_per_wall * dt, 1e-9))

    bus.set("t", clock_t)
    comm.stage_elapsed_s += step
    site.t_run += step
    clock_t += step

    rem = max(0.0, stage.duration_s - comm.stage_elapsed_s)
    bus.set("preprod_remaining_s", rem)
    bus.set("apu_bootstrap_s", stage.duration_s)
    bus.set("apu_ramp", min(1.0, comm.stage_elapsed_s / max(stage.duration_s, 1e-12)))
    bus.set("plasma_playback", 1.0)

    if comm.stage_elapsed_s + 1e-12 >= stage.duration_s:
        bus.alarm(clock_t, "info", "STAGE", f"Completed: {stage.label}")
        src = stage.source
        _advance_index(comm)
        bus.alarm(clock_t, "info", "SHOT", f"Plasma/NBI window ended. {src}")
        comm.shot_complete = True
        comm.done = True
        bus.set("plasma_playback", 0.0)

    return clock_t, True, step


_SEQUENCES: dict[str, list[CommissionStage]] = {
    "tae": [
        CommissionStage(
            id="vacuum_cold",
            label="Cold vacuum / pump-down (facility)",
            duration_s=3 * 3600,
            aux_MW=0.08,
            time_warp=True,
            batt_powered=False,
            source=(
                "Editorial facility cue (not TAE-published). Norman/C-2W is a copper-coil "
                "FRC hall, not a superconducting cryo plant — tokamak-style multi-day cryo "
                "does not apply. Atm→UHV pump-down is hours-class on large vessels."
            ),
        ),
        CommissionStage(
            id="shot_recovery",
            label="Between-shot recovery / wall prep",
            duration_s=8 * 60,
            aux_MW=0.25,
            time_warp=True,
            batt_powered=False,
            source="Google Research blog on Norman: ~one experiment every eight minutes.",
        ),
        CommissionStage(
            id="arm_nbi",
            label="Arm magnets + NBI power supplies",
            duration_s=120.0,
            aux_MW=1.0,
            energy_kWh=12.0,
            time_warp=True,
            batt_powered=False,  # lab: facility / grid interconnect
            source=(
                "Editorial ready-hall arm (~2 min, time-warped). Lab mode assumes Duke-style "
                "grid power — kWh logged on facility bus only. Copper/pulsed coils (Gota et al.)."
            ),
        ),
        CommissionStage(
            id="plasma_nbi",
            label="NBI-sustained FRC flattop",
            duration_s=0.040,
            plasma=True,
            batt_powered=False,
            source=(
                "Gota et al. C-2W/Norman: sustainment up to ~40 ms, NB-pulse-limited; "
                "NBI electrical ~13–20 MW from facility. Not continuous plant power. "
                "No published plant Q>1."
            ),
        ),
    ],
    "enn": [
        CommissionStage(
            id="vacuum_cold",
            label="Cold vacuum / hall prep (facility)",
            duration_s=4 * 3600,
            aux_MW=0.12,
            time_warp=True,
            batt_powered=False,
            source="Editorial ST-hall cue; not a published ENN cooldown procedure.",
        ),
        CommissionStage(
            id="tf_pf_ramp",
            label="TF/PF + aux ramp (facility)",
            duration_s=600.0,
            aux_MW=2.0,
            energy_kWh=50.0,
            time_warp=True,
            batt_powered=False,
            source=(
                "Editorial: ST coil energization longer than FRC copper pulse systems. "
                "Research-hall coil energy on facility bus — not the islanded starter pack."
            ),
        ),
        CommissionStage(
            id="plasma",
            label="Plasma / NBI–ICRF window",
            duration_s=5.0,
            plasma=True,
            batt_powered=True,
            source="Editorial flattop — ENN has not published plant Q>1 for p–11B.",
        ),
    ],
    "thea": [
        CommissionStage(
            id="cryo_cold",
            label="SC coil cryo cooldown (facility)",
            duration_s=72 * 3600,
            aux_MW=0.5,
            time_warp=True,
            batt_powered=False,
            source=(
                "Editorial stellarator/SC cue: multi-day cryo from warm is normal for large "
                "SC magnets. Applies to Thea-class, not TAE Norman copper FRC."
            ),
        ),
        CommissionStage(
            id="magnet_energize",
            label="Coil energization",
            duration_s=1800.0,
            aux_MW=3.0,
            energy_kWh=100.0,
            time_warp=True,
            batt_powered=True,
            source="Editorial coil ramp after cryo.",
        ),
        CommissionStage(
            id="plasma",
            label="Plasma window",
            duration_s=10.0,
            plasma=True,
            batt_powered=True,
            source="Editorial; D–T sister path — not p11B-clean.",
        ),
    ],
    "hb11": [
        CommissionStage(
            id="bank_charge",
            label="Capacitor / laser bank charge to first shot",
            duration_s=8.0,
            aux_MW=4.0,
            energy_kWh=12.0,
            batt_powered=True,
            source="Plant-scale bank fill editorial. Published HB11 sketch ~30 kJ + ~3 kJ coil (lab).",
        ),
        CommissionStage(
            id="shot",
            label="Shot / catcher window",
            duration_s=0.5,
            plasma=True,
            batt_powered=True,
            source="Pulsed; survey: current path ~4 orders below driver breakeven.",
        ),
    ],
    "avalanche": [
        CommissionStage(
            id="hv_enable",
            label="HV / orbit enable",
            duration_s=3.0,
            aux_MW=0.02,
            energy_kWh=0.05,
            batt_powered=True,
            source="Desk-scale Orbitron editorial.",
        ),
        CommissionStage(
            id="orbit",
            label="Orbitron run window",
            duration_s=30.0,
            plasma=True,
            batt_powered=True,
            source="No published plant Q>1.",
        ),
    ],
}
