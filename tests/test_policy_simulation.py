"""Deterministic ten-minute simulations for the agreed charging scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import random

from conftest import planner

PlannerInputs = planner.PlannerInputs
PlannerSettings = planner.PlannerSettings
calculate_decision = planner.calculate_decision


@dataclass(frozen=True)
class Scenario:
    name: str
    configured_target_kwh: float
    actual_need_kwh: float
    starting_soc: float
    house_min_kw: float
    house_max_kw: float
    seed: int


@dataclass
class SimulationResult:
    delivered_kwh: float
    peak_grid_kwh: float
    ev_grid_kwh: float
    finished_at: datetime | None
    soc_at_finish: float | None
    final_soc: float
    states: list[str]


def simulate(scenario: Scenario) -> SimulationResult:
    step = timedelta(minutes=10)
    step_hours = step.total_seconds() / 3600
    now = datetime.fromisoformat("2026-11-21T15:00:00+11:00")
    end = datetime.fromisoformat("2026-11-22T06:00:00+11:00")
    buffered_deadline = datetime.fromisoformat("2026-11-22T05:30:00+11:00")
    rng = random.Random(scenario.seed)

    settings = PlannerSettings(
        target_energy_kwh=scenario.configured_target_kwh,
        completion_buffer_min=30,
        control_interval_s=600,
    )
    battery_capacity_kwh = 30.0
    battery_max_discharge_kw = 10.0
    soc = scenario.starting_soc
    delivered = 0.0
    requested_current = 0.0
    vehicle_satisfied = False
    finished_at = None
    soc_at_finish = None
    peak_grid = 0.0
    ev_grid = 0.0
    states: list[str] = []

    while now < end:
        house_kw = rng.uniform(scenario.house_min_kw, scenario.house_max_kw)
        requested_ev_kw = requested_current * settings.watts_per_amp / 1000.0
        remaining_actual = max(0.0, scenario.actual_need_kwh - delivered)
        accepted_ev_kw = min(requested_ev_kw, remaining_actual / step_hours)
        charger_enabled = requested_current >= settings.min_current_a and remaining_actual > 0

        floor_energy = battery_capacity_kwh * settings.overnight_battery_floor / 100.0
        battery_energy = battery_capacity_kwh * soc / 100.0
        available_battery_kwh = max(0.0, battery_energy - floor_energy)
        required_kw = house_kw + accepted_ev_kw
        battery_discharge_kw = min(
            required_kw,
            battery_max_discharge_kw,
            available_battery_kwh / step_hours,
        )
        grid_kw = max(0.0, required_kw - battery_discharge_kw)
        battery_energy -= battery_discharge_kw * step_hours
        soc = max(settings.overnight_battery_floor, 100.0 * battery_energy / battery_capacity_kwh)

        delivered_this_step = accepted_ev_kw * step_hours
        delivered += delivered_this_step
        if 15 <= now.hour < 21:
            peak_grid += grid_kw * step_hours
        # Grid is allocated to house first; this gives a conservative EV-grid measure.
        ev_grid += max(0.0, grid_kw - house_kw) * step_hours

        if delivered >= scenario.actual_need_kwh - 1e-6:
            delivered = scenario.actual_need_kwh
            vehicle_satisfied = scenario.actual_need_kwh < scenario.configured_target_kwh
            if finished_at is None:
                finished_at = now
                soc_at_finish = soc

        decision = calculate_decision(
            PlannerInputs(
                now=now,
                controller_enabled=True,
                connected=True,
                battery_soc=soc,
                battery_power_w=battery_discharge_kw * 1000.0,
                grid_import_w=grid_kw * 1000.0,
                solar_power_w=0.0,
                charger_power_w=accepted_ev_kw * 1000.0,
                charger_current_a=requested_current,
                session_energy_kwh=delivered,
                charger_enabled=charger_enabled,
                vehicle_satisfied=vehicle_satisfied,
                mode="automatic",
                inputs_valid=True,
                increase_allowed=True,
                decrease_allowed=True,
            ),
            settings,
        )
        states.append(decision.state)
        requested_current = decision.requested_current_a if decision.should_enable else 0.0
        now += step

    # Full-need scenarios must finish by the configured buffered deadline.
    if scenario.actual_need_kwh == scenario.configured_target_kwh and finished_at:
        assert finished_at <= buffered_deadline

    return SimulationResult(
        delivered_kwh=delivered,
        peak_grid_kwh=peak_grid,
        ev_grid_kwh=ev_grid,
        finished_at=finished_at,
        soc_at_finish=soc_at_finish,
        final_soc=soc,
        states=states,
    )


def test_scenario_a_high_soc_full_30_kwh_need():
    result = simulate(
        Scenario("A", 30.0, 30.0, 90.0, 0.3, 1.0, seed=101)
    )
    assert result.peak_grid_kwh < 1e-6
    assert result.delivered_kwh >= 29.99
    assert result.finished_at is not None
    assert "overnight_floor" in result.states


def test_scenario_b_low_soc_full_30_kwh_need():
    result = simulate(
        Scenario("B", 30.0, 30.0, 30.0, 0.3, 0.5, seed=202)
    )
    assert result.peak_grid_kwh < 1e-6
    assert result.delivered_kwh >= 29.99
    assert result.finished_at is not None
    assert "overnight_floor" in result.states


def test_scenario_c_vehicle_full_at_10_kwh_retains_battery_and_uses_no_ev_grid():
    result = simulate(
        Scenario("C", 30.0, 10.0, 70.0, 0.4, 1.0, seed=303)
    )
    assert result.peak_grid_kwh < 1e-6
    assert result.delivered_kwh == 10.0
    assert result.finished_at is not None
    assert result.finished_at < datetime.fromisoformat("2026-11-22T05:30:00+11:00")
    assert result.ev_grid_kwh < 1e-6
    assert result.soc_at_finish is not None and result.soc_at_finish > 10.0
    assert "vehicle_satisfied" in result.states
