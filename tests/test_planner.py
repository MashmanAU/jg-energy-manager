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
        grid_import_w=0.0,
        solar_power_w=0.0,
        charger_power_w=0.0,
        session_energy_kwh=0.0,
        charger_enabled=False,
        vehicle_satisfied=False,
        override="automatic",
        inputs_valid=True,
    )
    values.update(changes)
    return PlannerInputs(**values)


def test_overnight_paces_maximum_target_from_start():
    result = calculate_decision(inputs("2026-11-21T21:00:00+11:00"), PlannerSettings())
    assert result.state is ControllerState.OVERNIGHT_SLOW
    assert result.should_enable
    assert result.deadline.isoformat() == "2026-11-22T06:00:00+11:00"
    assert result.requested_current_a == 16.2
    assert result.requested_current_a < 32


def test_overnight_floor_continues_at_deadline_rate():
    result = calculate_decision(
        inputs("2026-11-21T23:00:00+11:00", battery_soc=10), PlannerSettings()
    )
    assert result.state is ControllerState.OVERNIGHT_FLOOR
    assert result.should_enable
    assert result.requested_current_a >= 6


def test_deadline_recovery_caps_at_maximum():
    result = calculate_decision(
        inputs("2026-11-22T05:30:00+11:00", session_energy_kwh=0),
        PlannerSettings(),
    )
    assert result.state is ControllerState.DEADLINE_RECOVERY
    assert result.requested_current_a == 32


def test_peak_protection_stops_before_other_automatic_logic():
    result = calculate_decision(
        inputs("2026-11-21T17:00:00+11:00", charger_enabled=True),
        PlannerSettings(),
    )
    assert result.state is ControllerState.PEAK_PROTECTION
    assert not result.should_enable


def test_peak_protection_is_seasonal_from_configured_months():
    result = calculate_decision(
        inputs("2026-04-21T17:00:00+10:00", battery_soc=60, grid_import_w=-4000),
        PlannerSettings(),
    )
    assert result.state is ControllerState.DAYTIME_SOLAR


def test_force_max_is_explicit_peak_override():
    result = calculate_decision(
        inputs("2026-11-21T17:00:00+11:00", override="force_max"),
        PlannerSettings(),
    )
    assert result.state is ControllerState.OVERRIDE_MAX
    assert result.requested_current_a == 32


def test_maximum_power_also_caps_force_max_current():
    result = calculate_decision(
        inputs("2026-11-21T17:00:00+11:00", override="force_max"),
        PlannerSettings(max_charger_power_w=5000),
    )
    assert result.requested_current_a == 21.7
    assert result.requested_power_w == 4991


def test_daytime_reserve_has_start_hysteresis():
    result = calculate_decision(
        inputs("2026-11-21T12:00:00+11:00", battery_soc=46.9, grid_import_w=-4000),
        PlannerSettings(daytime_battery_reserve=45, soc_hysteresis=2),
    )
    assert result.state is ControllerState.DAYTIME_RESERVE


def test_daytime_export_starts_solar_charging_above_reserve():
    result = calculate_decision(
        inputs("2026-11-21T12:00:00+11:00", battery_soc=55, grid_import_w=-4000),
        PlannerSettings(),
    )
    assert result.state is ControllerState.DAYTIME_SOLAR
    assert result.requested_current_a == 15.6
    assert result.available_solar_power_w == 3600


def test_daytime_feedback_holds_existing_load_without_import():
    result = calculate_decision(
        inputs(
            "2026-11-21T12:00:00+11:00",
            battery_soc=55,
            charger_enabled=True,
            charger_power_w=2300,
            grid_import_w=0,
        ),
        PlannerSettings(),
    )
    assert result.state is ControllerState.DAYTIME_SOLAR
    assert result.requested_current_a == 9.3


def test_session_target_is_an_upper_bound():
    result = calculate_decision(
        inputs("2026-11-21T23:00:00+11:00", session_energy_kwh=30),
        PlannerSettings(),
    )
    assert result.state is ControllerState.COMPLETE
    assert not result.should_enable


def test_vehicle_satisfied_stops_for_less_than_maximum_target():
    result = calculate_decision(
        inputs(
            "2026-11-21T23:00:00+11:00",
            session_energy_kwh=11,
            vehicle_satisfied=True,
        ),
        PlannerSettings(),
    )
    assert result.state is ControllerState.VEHICLE_SATISFIED
    assert result.energy_remaining_kwh == 19
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
