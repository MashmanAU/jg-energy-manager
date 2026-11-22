from datetime import datetime

from conftest import planner

ControllerState = planner.ControllerState
PlannerInputs = planner.PlannerInputs
PlannerSettings = planner.PlannerSettings
calculate_decision = planner.calculate_decision


def inputs(at: str, **changes):
    values = dict(
        now=datetime.fromisoformat(at),
        controller_enabled=True,
        connected=True,
        battery_soc=60.0,
        battery_power_w=0.0,
        grid_import_w=0.0,
        solar_power_w=0.0,
        charger_power_w=0.0,
        charger_current_a=0.0,
        session_energy_kwh=0.0,
        charger_enabled=False,
        vehicle_satisfied=False,
        mode="automatic",
        inputs_valid=True,
        increase_allowed=True,
        decrease_allowed=True,
    )
    values.update(changes)
    return PlannerInputs(**values)


def test_post_peak_above_floor_starts_low_and_ramps_without_grid_import():
    settings = PlannerSettings()
    start = calculate_decision(inputs("2026-11-21T21:00:00+11:00", battery_soc=90), settings)
    assert start.state is ControllerState.POST_PEAK_BATTERY
    assert start.requested_current_a == 6

    ramp = calculate_decision(
        inputs(
            "2026-11-21T21:10:00+11:00",
            battery_soc=88,
            charger_enabled=True,
            charger_power_w=1380,
            charger_current_a=6,
            grid_import_w=0,
            battery_power_w=1800,
        ),
        settings,
    )
    assert ramp.state is ControllerState.POST_PEAK_BATTERY
    assert ramp.requested_current_a == 7


def test_post_peak_fast_decrease_responds_to_grid_import():
    result = calculate_decision(
        inputs(
            "2026-11-21T22:00:00+11:00",
            battery_soc=70,
            charger_enabled=True,
            charger_power_w=4600,
            charger_current_a=20,
            grid_import_w=1200,
            battery_power_w=4000,
        ),
        PlannerSettings(),
    )
    assert result.requested_current_a < 20
    assert result.requested_current_a == 15.2


def test_floor_spreads_remaining_energy_to_buffered_deadline():
    result = calculate_decision(
        inputs(
            "2026-11-21T23:00:00+11:00",
            battery_soc=10,
            session_energy_kwh=10,
        ),
        PlannerSettings(completion_buffer_min=30),
    )
    assert result.state is ControllerState.OVERNIGHT_FLOOR
    assert result.deadline.isoformat() == "2026-11-22T05:30:00+11:00"
    assert result.required_average_power_w > 0
    assert result.requested_current_a >= 6
    assert result.projected_completion <= result.deadline


def test_impossible_target_is_explicit_and_requests_maximum():
    result = calculate_decision(
        inputs("2026-11-22T05:20:00+11:00", battery_soc=10),
        PlannerSettings(target_energy_kwh=30, completion_buffer_min=30),
    )
    assert result.state is ControllerState.IMPOSSIBLE_TARGET
    assert result.requested_current_a == 32
    assert "impossible" in result.reason.lower()


def test_peak_import_is_avoided_when_deadline_remains_feasible():
    result = calculate_decision(
        inputs("2026-11-21T17:00:00+11:00", battery_soc=60),
        PlannerSettings(),
    )
    assert result.state is ControllerState.PEAK_PROTECTION
    assert not result.should_enable


def test_peak_grid_use_occurs_only_when_physically_required():
    result = calculate_decision(
        inputs("2026-11-21T20:00:00+11:00", battery_soc=90),
        PlannerSettings(target_energy_kwh=60),
    )
    assert result.state is ControllerState.DEADLINE_RECOVERY
    assert result.should_enable
    assert "physically required" in result.reason.lower()


def test_force_charge_uses_configured_current_and_respects_power_cap():
    result = calculate_decision(
        inputs("2026-11-21T17:00:00+11:00", mode="force_charge"),
        PlannerSettings(force_charge_current_a=28, max_charger_power_w=5000),
    )
    assert result.state is ControllerState.FORCE_CHARGE
    assert result.requested_current_a == 21.7


def test_off_mode_stops_charging():
    result = calculate_decision(
        inputs("2026-11-21T22:00:00+11:00", mode="off", charger_enabled=True),
        PlannerSettings(),
    )
    assert result.state is ControllerState.MODE_OFF
    assert not result.should_enable


def test_below_reserve_only_genuine_battery_overflow_charges_ev():
    result = calculate_decision(
        inputs(
            "2026-11-21T12:00:00+11:00",
            battery_soc=30,
            solar_power_w=7000,
            grid_import_w=-2000,
            battery_power_w=-5000,
        ),
        PlannerSettings(),
    )
    assert result.state is ControllerState.DAYTIME_OVERFLOW
    assert result.requested_current_a == 6
    assert result.available_solar_power_w == 1600


def test_below_reserve_does_not_bridge_from_grid_or_battery():
    result = calculate_decision(
        inputs(
            "2026-11-21T12:00:00+11:00",
            battery_soc=30,
            solar_power_w=4000,
            grid_import_w=-1000,
            battery_power_w=-3000,
        ),
        PlannerSettings(),
    )
    assert result.state is ControllerState.DAYTIME_RESERVE
    assert not result.should_enable


def test_above_reserve_ev_takes_priority_over_further_battery_charging():
    result = calculate_decision(
        inputs(
            "2026-11-21T12:00:00+11:00",
            battery_soc=55,
            solar_power_w=6000,
            grid_import_w=0,
            battery_power_w=-5000,
        ),
        PlannerSettings(),
    )
    assert result.state is ControllerState.DAYTIME_SOLAR
    assert result.requested_current_a == 6


def test_solar_only_never_uses_battery_discharge():
    result = calculate_decision(
        inputs(
            "2026-11-21T12:00:00+11:00",
            mode="solar_only",
            battery_soc=80,
            solar_power_w=3000,
            grid_import_w=0,
            battery_power_w=500,
            charger_enabled=True,
            charger_power_w=1380,
            charger_current_a=6,
        ),
        PlannerSettings(),
    )
    assert result.state is ControllerState.SOLAR_ONLY
    assert not result.should_enable


def test_session_target_is_a_maximum_allowance():
    result = calculate_decision(
        inputs("2026-11-21T23:00:00+11:00", session_energy_kwh=30),
        PlannerSettings(),
    )
    assert result.state is ControllerState.COMPLETE
    assert not result.should_enable


def test_vehicle_satisfied_stops_recovery_and_retains_allowance():
    result = calculate_decision(
        inputs(
            "2026-11-21T23:00:00+11:00",
            session_energy_kwh=10,
            vehicle_satisfied=True,
        ),
        PlannerSettings(),
    )
    assert result.state is ControllerState.VEHICLE_SATISFIED
    assert result.energy_remaining_kwh == 20
    assert not result.should_enable


def test_input_failure_requests_safe_stop():
    result = calculate_decision(
        inputs("2026-11-21T12:00:00+11:00", inputs_valid=False),
        PlannerSettings(),
    )
    assert result.state is ControllerState.INPUT_ERROR
    assert not result.should_enable


def test_inconsistent_electrical_limits_request_safe_stop():
    result = calculate_decision(
        inputs("2026-11-21T22:00:00+11:00"),
        PlannerSettings(min_current_a=10, max_charger_power_w=1000),
    )
    assert result.state is ControllerState.INPUT_ERROR
    assert "inconsistent" in result.reason


def test_solar_only_never_enters_deadline_recovery_even_when_target_is_impossible():
    result = calculate_decision(
        inputs(
            "2026-11-22T05:20:00+11:00",
            mode="solar_only",
            solar_power_w=0,
            battery_power_w=0,
            grid_import_w=0,
        ),
        PlannerSettings(target_energy_kwh=30),
    )
    assert result.state is ControllerState.SOLAR_ONLY
    assert not result.should_enable
