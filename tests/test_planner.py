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


def test_post_peak_below_minimum_steps_down_to_six_amps_before_stopping():
    result = calculate_decision(
        inputs(
            "2026-11-21T22:00:00+11:00",
            battery_soc=70,
            charger_enabled=True,
            charger_power_w=1610,
            charger_current_a=7,
            grid_import_w=1200,
            battery_power_w=900,
        ),
        PlannerSettings(),
    )
    assert result.should_enable
    assert result.requested_current_a == 6
    assert not result.battery_response_hold
    assert "minimum" in result.reason.lower()


def test_post_peak_minimum_holds_while_credible_battery_headroom_responds():
    result = calculate_decision(
        inputs(
            "2026-11-21T22:00:00+11:00",
            battery_soc=70,
            charger_enabled=True,
            charger_power_w=1380,
            charger_current_a=6,
            grid_import_w=1097,
            battery_power_w=900,
            battery_response_elapsed_s=10,
        ),
        PlannerSettings(
            battery_discharge_control_ceiling_w=4500,
            battery_response_grace_s=30,
        ),
    )
    assert result.should_enable
    assert result.requested_current_a == 6
    assert result.battery_response_hold
    assert result.battery_discharge_headroom_w == 3600
    assert result.battery_uncovered_import_w == 0


def test_post_peak_minimum_stops_when_battery_grace_expires():
    result = calculate_decision(
        inputs(
            "2026-11-21T22:00:00+11:00",
            battery_soc=70,
            charger_enabled=True,
            charger_power_w=1380,
            charger_current_a=6,
            grid_import_w=1097,
            battery_power_w=900,
            battery_response_elapsed_s=30,
        ),
        PlannerSettings(
            battery_discharge_control_ceiling_w=4500,
            battery_response_grace_s=30,
        ),
    )
    assert not result.should_enable
    assert not result.battery_response_hold


def test_post_peak_minimum_stops_immediately_near_battery_ceiling():
    result = calculate_decision(
        inputs(
            "2026-11-21T22:00:00+11:00",
            battery_soc=70,
            charger_enabled=True,
            charger_power_w=1380,
            charger_current_a=6,
            grid_import_w=800,
            battery_power_w=4600,
        ),
        PlannerSettings(battery_discharge_control_ceiling_w=4500),
    )
    assert not result.should_enable
    assert result.battery_discharge_headroom_w == 0


def test_post_peak_minimum_stops_when_headroom_cannot_cover_import():
    result = calculate_decision(
        inputs(
            "2026-11-21T22:00:00+11:00",
            battery_soc=70,
            charger_enabled=True,
            charger_power_w=1380,
            charger_current_a=6,
            grid_import_w=900,
            battery_power_w=4300,
        ),
        PlannerSettings(battery_discharge_control_ceiling_w=4500),
    )
    assert not result.should_enable
    assert result.battery_discharge_headroom_w == 200
    assert result.battery_uncovered_import_w == 600


def test_post_peak_minimum_does_not_wait_without_valid_battery_power():
    result = calculate_decision(
        inputs(
            "2026-11-21T22:00:00+11:00",
            battery_soc=70,
            charger_enabled=True,
            charger_power_w=1380,
            charger_current_a=6,
            grid_import_w=800,
            battery_power_w=0,
            battery_power_valid=False,
        ),
        PlannerSettings(),
    )
    assert not result.should_enable


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


def test_impossible_target_requires_a_meaningful_feasibility_deficit():
    marginal = calculate_decision(
        inputs(
            "2026-11-22T05:00:00+11:00",
            battery_soc=20,
            charger_enabled=True,
            charger_power_w=6200,
            charger_current_a=27,
            grid_import_w=1500,
        ),
        PlannerSettings(target_energy_kwh=3.40),
    )
    assert marginal.state is not ControllerState.IMPOSSIBLE_TARGET

    meaningful = calculate_decision(
        inputs("2026-11-22T05:00:00+11:00", battery_soc=20),
        PlannerSettings(target_energy_kwh=3.60),
    )
    assert meaningful.state is ControllerState.IMPOSSIBLE_TARGET
    assert meaningful.deadline_impossible_latched


def test_impossible_target_remains_latched_until_comfortable_headroom_returns():
    still_latched = calculate_decision(
        inputs(
            "2026-11-22T05:00:00+11:00",
            battery_soc=20,
            previous_controller_state=ControllerState.IMPOSSIBLE_TARGET,
        ),
        PlannerSettings(target_energy_kwh=3.20),
    )
    assert still_latched.state is ControllerState.IMPOSSIBLE_TARGET

    released = calculate_decision(
        inputs(
            "2026-11-22T05:00:00+11:00",
            battery_soc=20,
            charger_enabled=True,
            charger_power_w=7360,
            charger_current_a=32,
            grid_import_w=2000,
            previous_controller_state=ControllerState.IMPOSSIBLE_TARGET,
            deadline_max_output_active=True,
        ),
        PlannerSettings(target_energy_kwh=3.00),
    )
    assert released.state is ControllerState.DEADLINE_RECOVERY
    assert released.requested_current_a == 32
    assert released.deadline_max_output_hold
    assert released.deadline_max_release_candidate


def test_deadline_maximum_holds_until_lower_requirement_is_material_and_sustained():
    settings = PlannerSettings(target_energy_kwh=3.303375)
    common = dict(
        battery_soc=20,
        charger_enabled=True,
        charger_power_w=7360,
        charger_current_a=32,
        grid_import_w=2000,
        previous_controller_state=ControllerState.DEADLINE_RECOVERY,
        deadline_max_output_active=True,
    )
    before_dwell = calculate_decision(
        inputs(
            "2026-11-22T05:00:00+11:00",
            deadline_max_release_elapsed_s=59,
            **common,
        ),
        settings,
    )
    assert before_dwell.requested_current_a == 32
    assert before_dwell.deadline_max_output_hold
    assert before_dwell.deadline_max_release_candidate

    after_dwell = calculate_decision(
        inputs(
            "2026-11-22T05:00:00+11:00",
            deadline_max_release_elapsed_s=60,
            **common,
        ),
        settings,
    )
    assert after_dwell.state is ControllerState.DEADLINE_RECOVERY
    assert after_dwell.requested_current_a == 27
    assert not after_dwell.deadline_max_output_hold


def test_deadline_maximum_does_not_release_for_near_maximum_requirement():
    result = calculate_decision(
        inputs(
            "2026-11-22T05:00:00+11:00",
            battery_soc=20,
            charger_enabled=True,
            charger_power_w=7360,
            charger_current_a=32,
            grid_import_w=2000,
            previous_controller_state=ControllerState.DEADLINE_RECOVERY,
            deadline_max_output_active=True,
            deadline_max_release_elapsed_s=300,
        ),
        PlannerSettings(target_energy_kwh=3.310275),
    )
    assert result.requested_current_a == 32
    assert result.deadline_max_output_hold
    assert not result.deadline_max_release_candidate


def test_deadline_maximum_release_margin_includes_exact_threshold():
    result = calculate_decision(
        inputs(
            "2026-11-22T05:00:00+11:00",
            battery_soc=20,
            charger_enabled=True,
            charger_power_w=7360,
            charger_current_a=32,
            grid_import_w=2000,
            previous_controller_state=ControllerState.DEADLINE_RECOVERY,
            deadline_max_output_active=True,
            deadline_max_release_elapsed_s=59,
        ),
        PlannerSettings(target_energy_kwh=3.30855),
    )
    assert result.requested_current_a == 32
    assert result.deadline_max_release_candidate


def test_history_2_boundary_pattern_no_longer_flips_to_impossible_target():
    """Regression for the supplied 10-second deadline-boundary oscillation."""
    samples = (
        ("2026-11-26T04:19:12.922+11:00", 7.834),
        ("2026-11-26T04:19:23.895+11:00", 7.796),
        ("2026-11-26T04:19:33.898+11:00", 7.779),
        ("2026-11-26T04:19:44.875+11:00", 7.779),
        ("2026-11-26T04:19:54.879+11:00", 7.757),
        ("2026-11-26T04:20:04.884+11:00", 7.739),
    )
    previous = ControllerState.DEADLINE_RECOVERY
    for at, remaining in samples:
        result = calculate_decision(
            inputs(
                at,
                battery_soc=20,
                charger_enabled=True,
                charger_power_w=7360,
                charger_current_a=32,
                grid_import_w=2000,
                session_energy_kwh=30 - remaining,
                previous_controller_state=previous,
                deadline_max_output_active=True,
            ),
            PlannerSettings(),
        )
        assert result.state is not ControllerState.IMPOSSIBLE_TARGET
        assert result.requested_current_a == 32
        previous = result.state


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
    assert result.available_solar_power_w == 7000
    assert result.policy_solar_power_w == 1600


def test_peak_solar_overflow_precedes_peak_grid_protection():
    result = calculate_decision(
        inputs(
            "2026-11-21T16:00:00+11:00",
            battery_soc=30,
            solar_power_w=7000,
            grid_import_w=-2000,
            battery_power_w=-5000,
        ),
        PlannerSettings(),
    )
    assert result.state is ControllerState.DAYTIME_OVERFLOW
    assert result.should_enable
    assert result.available_solar_power_w == 7000
    assert result.requested_power_w == 1380


def test_available_solar_is_observational_while_calculated_power_remains_policy_controlled():
    result = calculate_decision(
        inputs(
            "2026-11-21T12:00:00+11:00",
            battery_soc=30,
            solar_power_w=6000,
            grid_import_w=-1000,
            battery_power_w=-5000,
        ),
        PlannerSettings(),
    )
    assert result.available_solar_power_w == 6000
    assert result.policy_solar_power_w == 600
    assert result.requested_power_w == 0


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
