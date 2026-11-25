"""Pure charging-planner logic for JG Energy Manager.

This module deliberately has no Home Assistant imports so the policy and its
safety boundaries can be simulated deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum
import math


class ControllerState(StrEnum):
    DISABLED = "disabled"
    IDLE = "idle"
    COMPLETE = "complete"
    PEAK_PROTECTION = "peak_protection"
    POST_PEAK_BATTERY = "post_peak_battery"
    DAYTIME_RESERVE = "daytime_reserve"
    DAYTIME_OVERFLOW = "daytime_overflow"
    DAYTIME_WAITING_FOR_SURPLUS = "daytime_waiting_for_surplus"
    DAYTIME_SOLAR = "daytime_solar"
    OVERNIGHT_FLOOR = "overnight_floor"
    DEADLINE_RECOVERY = "deadline_recovery"
    IMPOSSIBLE_TARGET = "impossible_target"
    MODE_OFF = "mode_off"
    FORCE_CHARGE = "force_charge"
    SOLAR_ONLY = "solar_only"
    VEHICLE_SATISFIED = "vehicle_satisfied"
    INPUT_ERROR = "input_error"


@dataclass(frozen=True, slots=True)
class PlannerSettings:
    target_energy_kwh: float = 30.0
    ready_by: time = time(6, 0)
    completion_buffer_min: int = 30
    overnight_start: time = time(21, 0)
    peak_start: time = time(15, 0)
    peak_end: time = time(21, 0)
    peak_months: frozenset[int] = frozenset({1, 2, 3, 6, 7, 8, 11, 12})
    overnight_battery_floor: float = 10.0
    daytime_battery_reserve: float = 45.0
    soc_hysteresis: float = 2.0
    min_current_a: float = 6.0
    max_current_a: float = 32.0
    force_charge_current_a: float = 32.0
    max_charger_power_w: float = 7360.0
    battery_max_charge_power_w: float = 5000.0
    battery_discharge_control_ceiling_w: float = 4500.0
    battery_response_grace_s: float = 30.0
    deadline_impossible_enter_margin_kwh: float = 0.20
    deadline_impossible_exit_margin_kwh: float = 0.25
    deadline_max_hold_current_margin_a: float = 2.0
    deadline_max_hold_s: float = 60.0
    grid_tolerance_w: float = 100.0
    current_step_a: float = 0.1
    ramp_up_step_a: float = 1.0
    supply_voltage: float = 230.0
    phases: int = 1
    charging_efficiency: float = 0.90
    solar_start_margin_w: float = 400.0
    solar_run_margin_w: float = 150.0
    control_interval_s: int = 30

    @property
    def watts_per_amp(self) -> float:
        return self.supply_voltage * self.phases

    @property
    def min_power_w(self) -> float:
        return self.min_current_a * self.watts_per_amp

    @property
    def max_power_w(self) -> float:
        return min(self.max_charger_power_w, self.max_current_a * self.watts_per_amp)

    @property
    def effective_max_current_a(self) -> float:
        value = min(self.max_current_a, self.max_power_w / self.watts_per_amp)
        return _round_down(value, self.current_step_a)

    @property
    def effective_force_current_a(self) -> float:
        return min(
            self.effective_max_current_a,
            _round_down(self.force_charge_current_a, self.current_step_a),
        )


@dataclass(frozen=True, slots=True)
class PlannerInputs:
    now: datetime
    controller_enabled: bool
    connected: bool
    battery_soc: float
    battery_power_w: float
    grid_import_w: float
    solar_power_w: float
    charger_power_w: float
    charger_current_a: float
    session_energy_kwh: float
    charger_enabled: bool
    vehicle_satisfied: bool = False
    mode: str = "automatic"
    inputs_valid: bool = True
    increase_allowed: bool = True
    decrease_allowed: bool = True
    battery_power_valid: bool = True
    battery_response_elapsed_s: float = 0.0
    previous_controller_state: ControllerState | None = None
    deadline_max_output_active: bool = False
    deadline_max_release_elapsed_s: float = 0.0


@dataclass(frozen=True, slots=True)
class Decision:
    state: ControllerState
    reason: str
    should_enable: bool
    requested_current_a: float
    requested_power_w: float
    energy_remaining_kwh: float
    required_average_power_w: float
    # Observational solar excess before reserve policy and safety margins.
    available_solar_power_w: float
    # Solar power that policy is presently prepared to allocate to the EV.
    policy_solar_power_w: float
    projected_completion: datetime | None
    deadline: datetime | None
    battery_response_hold: bool = False
    battery_discharge_headroom_w: float = 0.0
    battery_uncovered_import_w: float = 0.0
    deadline_feasibility_margin_kwh: float = 0.0
    deadline_impossible_latched: bool = False
    deadline_max_output_hold: bool = False
    deadline_max_release_candidate: bool = False
    deadline_max_release_elapsed_s: float = 0.0


def _in_window(value: time, start: time, end: time) -> bool:
    if start == end:
        return True
    if start < end:
        return start <= value < end
    return value >= start or value < end


def _at_local_time(now: datetime, day: date, target: time) -> datetime:
    return datetime.combine(day, target, tzinfo=now.tzinfo)


def _next_occurrence(now: datetime, target: time) -> datetime:
    candidate = _at_local_time(now, now.date(), target)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _buffered_deadline(now: datetime, settings: PlannerSettings) -> datetime:
    return _next_occurrence(now, settings.ready_by) - timedelta(
        minutes=settings.completion_buffer_min
    )


def _peak_end_for_current_window(now: datetime, settings: PlannerSettings) -> datetime:
    local_time = now.timetz().replace(tzinfo=None)
    if settings.peak_start < settings.peak_end:
        return _at_local_time(now, now.date(), settings.peak_end)
    if local_time >= settings.peak_start:
        return _at_local_time(now, now.date() + timedelta(days=1), settings.peak_end)
    return _at_local_time(now, now.date(), settings.peak_end)


def _peak_overlap_seconds(start: datetime, end: datetime, settings: PlannerSettings) -> float:
    """Return seasonal peak seconds in [start, end)."""
    if end <= start:
        return 0.0
    total = 0.0
    day = start.date() - timedelta(days=1)
    final_day = end.date()
    while day <= final_day:
        if day.month in settings.peak_months:
            peak_start = _at_local_time(start, day, settings.peak_start)
            peak_end_day = day if settings.peak_start < settings.peak_end else day + timedelta(days=1)
            peak_end = _at_local_time(start, peak_end_day, settings.peak_end)
            overlap_start = max(start, peak_start)
            overlap_end = min(end, peak_end)
            if overlap_end > overlap_start:
                total += (overlap_end - overlap_start).total_seconds()
        day += timedelta(days=1)
    return total


def _round_up(value: float, step: float) -> float:
    return round(math.ceil((value - 1e-9) / step) * step, 3)


def _round_down(value: float, step: float) -> float:
    return round(math.floor((value + 1e-9) / step) * step, 3)


def _completion(
    now: datetime,
    remaining_kwh: float,
    power_w: float,
    efficiency: float,
) -> datetime | None:
    delivered_w = power_w * efficiency
    if remaining_kwh <= 0:
        return now
    if delivered_w <= 0:
        return None
    return now + timedelta(hours=(remaining_kwh * 1000.0) / delivered_w)


def _decision(
    state: ControllerState,
    reason: str,
    enable: bool,
    current_a: float,
    remaining: float,
    settings: PlannerSettings,
    *,
    required_w: float = 0.0,
    available_solar_w: float = 0.0,
    policy_solar_w: float = 0.0,
    deadline: datetime | None = None,
    battery_response_hold: bool = False,
    battery_discharge_headroom_w: float = 0.0,
    battery_uncovered_import_w: float = 0.0,
    deadline_feasibility_margin_kwh: float = 0.0,
    deadline_impossible_latched: bool = False,
    deadline_max_output_hold: bool = False,
    deadline_max_release_candidate: bool = False,
    deadline_max_release_elapsed_s: float = 0.0,
    now: datetime,
) -> Decision:
    current_a = min(settings.effective_max_current_a, max(0.0, current_a))
    power_w = current_a * settings.watts_per_amp if enable else 0.0
    return Decision(
        state=state,
        reason=reason,
        should_enable=enable,
        requested_current_a=current_a if enable else 0.0,
        requested_power_w=power_w,
        energy_remaining_kwh=remaining,
        required_average_power_w=max(0.0, required_w),
        available_solar_power_w=max(0.0, available_solar_w),
        policy_solar_power_w=max(0.0, policy_solar_w),
        projected_completion=_completion(
            now, remaining, power_w, settings.charging_efficiency
        ),
        deadline=deadline,
        battery_response_hold=battery_response_hold,
        battery_discharge_headroom_w=max(0.0, battery_discharge_headroom_w),
        battery_uncovered_import_w=max(0.0, battery_uncovered_import_w),
        deadline_feasibility_margin_kwh=deadline_feasibility_margin_kwh,
        deadline_impossible_latched=deadline_impossible_latched,
        deadline_max_output_hold=deadline_max_output_hold,
        deadline_max_release_candidate=deadline_max_release_candidate,
        deadline_max_release_elapsed_s=max(0.0, deadline_max_release_elapsed_s),
    )


def _requested_current_for_power(power_w: float, settings: PlannerSettings) -> float:
    if power_w <= 0:
        return 0.0
    requested = _round_up(power_w / settings.watts_per_amp, settings.current_step_a)
    return min(settings.effective_max_current_a, max(settings.min_current_a, requested))


def _deadline_current_with_max_hold(
    required_w: float,
    inputs: PlannerInputs,
    settings: PlannerSettings,
) -> tuple[float, bool, bool]:
    """Hold maximum output until a materially lower requirement is sustained.

    This stateful boundary applies only after deadline control was already at
    maximum output. Ordinary feedback current tuning remains unaffected.
    """
    requested = _requested_current_for_power(required_w, settings)
    if not inputs.deadline_max_output_active:
        return requested, False, False

    release_below_a = max(
        settings.min_current_a,
        settings.effective_max_current_a - settings.deadline_max_hold_current_margin_a,
    )
    release_candidate = requested <= release_below_a
    release_sustained = (
        release_candidate
        and inputs.deadline_max_release_elapsed_s >= settings.deadline_max_hold_s
    )
    if release_sustained:
        return requested, False, True
    return settings.effective_max_current_a, True, release_candidate


def _ramped_feedback_current(
    target_power_w: float,
    inputs: PlannerInputs,
    settings: PlannerSettings,
) -> float:
    """Apply slow increases and fast decreases to a feedback-derived power target."""
    target = min(
        settings.effective_max_current_a,
        _round_down(max(0.0, target_power_w) / settings.watts_per_amp, settings.current_step_a),
    )
    actual = (
        max(0.0, inputs.charger_current_a)
        if inputs.charger_enabled
        else max(0.0, inputs.charger_power_w / settings.watts_per_amp)
    )
    if target < settings.min_current_a:
        if actual >= settings.min_current_a and not inputs.decrease_allowed:
            return _round_down(actual, settings.current_step_a)
        return 0.0
    if actual < settings.min_current_a:
        return settings.min_current_a if inputs.increase_allowed else 0.0
    actual = min(settings.effective_max_current_a, _round_down(actual, settings.current_step_a))
    if target > actual:
        if not inputs.increase_allowed:
            return actual
        return min(target, _round_up(actual + settings.ramp_up_step_a, settings.current_step_a))
    if target < actual and not inputs.decrease_allowed:
        return actual
    return target


def _non_peak_recovery_power(
    now: datetime,
    deadline: datetime,
    remaining_kwh: float,
    settings: PlannerSettings,
) -> float:
    """Power required in this interval if waiting would lose non-peak feasibility."""
    interval = min(settings.control_interval_s, max(0.0, (deadline - now).total_seconds()))
    future_start = now + timedelta(seconds=interval)
    future_seconds = max(0.0, (deadline - future_start).total_seconds())
    future_non_peak = max(
        0.0,
        future_seconds - _peak_overlap_seconds(future_start, deadline, settings),
    )
    future_kwh = settings.max_power_w * settings.charging_efficiency * future_non_peak / 3_600_000.0
    deficit_kwh = max(0.0, remaining_kwh - future_kwh)
    if deficit_kwh <= 0 or interval <= 0:
        return 0.0
    return min(
        settings.max_power_w,
        deficit_kwh * 3_600_000.0 / (interval * settings.charging_efficiency),
    )


def _observed_available_solar_power(
    inputs: PlannerInputs, settings: PlannerSettings
) -> float:
    """Return measured solar excess independently of controller policy.

    The power-balance form remains useful while the EV is already consuming
    solar.  It therefore adds current charger load back before removing grid
    import/battery discharge, and is capped by measured PV production.
    """
    grid = 0.0 if abs(inputs.grid_import_w) <= settings.grid_tolerance_w else inputs.grid_import_w
    battery = (
        0.0
        if abs(inputs.battery_power_w) <= settings.grid_tolerance_w
        else inputs.battery_power_w
    )
    headroom = inputs.charger_power_w - grid - battery
    return max(0.0, min(max(0.0, inputs.solar_power_w), headroom))


def _solar_policy_current(
    inputs: PlannerInputs,
    settings: PlannerSettings,
    *,
    below_reserve: bool,
) -> tuple[float, float]:
    """Return a no-grid/no-battery-discharge current and policy headroom."""
    if inputs.solar_power_w <= 0:
        return 0.0, 0.0
    margin = settings.solar_run_margin_w if inputs.charger_enabled else settings.solar_start_margin_w
    grid = 0.0 if abs(inputs.grid_import_w) <= settings.grid_tolerance_w else inputs.grid_import_w
    battery = (
        0.0
        if abs(inputs.battery_power_w) <= settings.grid_tolerance_w
        else inputs.battery_power_w
    )
    if below_reserve:
        # Battery receives its configured maximum charge allowance first. Only
        # genuine export beyond that allowance is offered to the EV.
        available_w = (
            inputs.charger_power_w
            - grid
            - battery
            - settings.battery_max_charge_power_w
            - margin
        )
    else:
        # Once reserve is achieved, current battery charging may be redirected
        # to the EV, but battery discharge and grid import reduce the EV target.
        available_w = inputs.charger_power_w - grid - battery - margin
    current = _ramped_feedback_current(available_w, inputs, settings)
    return current, max(0.0, available_w)


def calculate_decision(inputs: PlannerInputs, settings: PlannerSettings) -> Decision:
    """Calculate one deterministic controller decision."""
    remaining = max(0.0, settings.target_energy_kwh - inputs.session_energy_kwh)
    deadline = _buffered_deadline(inputs.now, settings)
    observed_solar_w = _observed_available_solar_power(inputs, settings)
    off = dict(
        enable=False,
        current_a=0.0,
        remaining=remaining,
        settings=settings,
        deadline=deadline,
        now=inputs.now,
        available_solar_w=observed_solar_w,
    )

    if (
        settings.min_current_a <= 0
        or settings.max_current_a < settings.min_current_a
        or settings.current_step_a <= 0
        or settings.ramp_up_step_a <= 0
        or settings.max_charger_power_w < settings.min_power_w
        or settings.battery_max_charge_power_w < 0
        or settings.battery_discharge_control_ceiling_w < 0
        or settings.battery_response_grace_s < 0
        or settings.deadline_impossible_enter_margin_kwh < 0
        or settings.deadline_impossible_exit_margin_kwh < 0
        or settings.deadline_max_hold_current_margin_a < 0
        or settings.deadline_max_hold_s < 0
        or settings.grid_tolerance_w < 0
        or settings.supply_voltage <= 0
        or settings.phases <= 0
        or not 0 < settings.charging_efficiency <= 1
        or settings.completion_buffer_min < 0
    ):
        return _decision(
            ControllerState.INPUT_ERROR,
            "Controller limits are inconsistent; correct the integration options.",
            **off,
        )

    if not inputs.controller_enabled:
        return _decision(ControllerState.DISABLED, "Controller is disabled.", **off)
    if inputs.mode in {"off", "force_off"}:
        return _decision(ControllerState.MODE_OFF, "Off mode is active.", **off)
    if not inputs.inputs_valid:
        return _decision(
            ControllerState.INPUT_ERROR,
            "Required input unavailable or invalid; fail-safe stop requested.",
            **off,
        )
    if not inputs.connected:
        return _decision(ControllerState.IDLE, "No vehicle is connected.", **off)
    if inputs.vehicle_satisfied:
        return _decision(
            ControllerState.VEHICLE_SATISFIED,
            "The vehicle stopped accepting power; the unused energy allowance is retained.",
            **off,
        )
    if remaining <= 0.001:
        return _decision(
            ControllerState.COMPLETE,
            "The configured maximum session energy allowance has been delivered.",
            **off,
        )
    if inputs.mode in {"force_charge", "force_max"}:
        return _decision(
            ControllerState.FORCE_CHARGE,
            "Force Charge mode is active at the configured current.",
            True,
            settings.effective_force_current_a,
            remaining,
            settings,
            available_solar_w=observed_solar_w,
            deadline=deadline,
            now=inputs.now,
        )

    local_time = inputs.now.timetz().replace(tzinfo=None)
    in_peak = (
        inputs.now.month in settings.peak_months
        and _in_window(local_time, settings.peak_start, settings.peak_end)
    )
    reserve_threshold = (
        settings.daytime_battery_reserve - settings.soc_hysteresis
        if inputs.charger_enabled
        else settings.daytime_battery_reserve + settings.soc_hysteresis
    )
    below_reserve = inputs.battery_soc < reserve_threshold

    if inputs.mode == "solar_only":
        current, policy_solar_w = _solar_policy_current(
            inputs, settings, below_reserve=below_reserve
        )
        if current < settings.min_current_a:
            return _decision(
                ControllerState.SOLAR_ONLY,
                "Solar Only mode is waiting for genuine no-grid, no-battery-discharge headroom.",
                **off,
                policy_solar_w=policy_solar_w,
            )
        return _decision(
            ControllerState.SOLAR_ONLY,
            "Solar Only mode is charging from genuine solar headroom.",
            True,
            current,
            remaining,
            settings,
            available_solar_w=observed_solar_w,
            policy_solar_w=policy_solar_w,
            deadline=deadline,
            now=inputs.now,
        )

    seconds_remaining = max(0.0, (deadline - inputs.now).total_seconds())
    max_deliverable_kwh = (
        settings.max_power_w
        * settings.charging_efficiency
        * seconds_remaining
        / 3_600_000.0
    )
    feasibility_margin_kwh = max_deliverable_kwh - remaining
    feasibility_deficit_kwh = max(0.0, -feasibility_margin_kwh)
    was_impossible = inputs.previous_controller_state is ControllerState.IMPOSSIBLE_TARGET
    impossible_latched = (
        was_impossible
        and feasibility_margin_kwh < settings.deadline_impossible_exit_margin_kwh
    ) or (
        not was_impossible
        and feasibility_deficit_kwh > settings.deadline_impossible_enter_margin_kwh
    )
    if impossible_latched:
        return _decision(
            ControllerState.IMPOSSIBLE_TARGET,
            "The target is meaningfully impossible by the buffered deadline; maximum current remains requested until comfortable feasibility headroom is restored.",
            True,
            settings.effective_max_current_a,
            remaining,
            settings,
            required_w=settings.max_power_w,
            available_solar_w=observed_solar_w,
            deadline=deadline,
            deadline_feasibility_margin_kwh=feasibility_margin_kwh,
            deadline_impossible_latched=True,
            now=inputs.now,
        )

    solar_current, policy_solar_w = _solar_policy_current(
        inputs, settings, below_reserve=below_reserve
    )

    # Confirmed precedence: genuine no-grid solar overflow remains usable during
    # a tariff peak.  Peak protection blocks grid/battery charging, not surplus
    # PV that would otherwise be exported.
    if in_peak and solar_current >= settings.min_current_a:
        state = ControllerState.DAYTIME_OVERFLOW if below_reserve else ControllerState.DAYTIME_SOLAR
        reason = (
            "Peak protection remains active for grid energy; genuine solar overflow is charging the EV."
            if below_reserve
            else "Peak protection remains active for grid energy; solar excess is charging the EV."
        )
        return _decision(
            state,
            reason,
            True,
            solar_current,
            remaining,
            settings,
            available_solar_w=observed_solar_w,
            policy_solar_w=policy_solar_w,
            deadline=deadline,
            now=inputs.now,
        )

    if in_peak:
        peak_end = min(_peak_end_for_current_window(inputs.now, settings), deadline)
        future_non_peak_seconds = max(
            0.0,
            (deadline - peak_end).total_seconds()
            - _peak_overlap_seconds(peak_end, deadline, settings),
        )
        future_non_peak_kwh = (
            settings.max_power_w
            * settings.charging_efficiency
            * future_non_peak_seconds
            / 3_600_000.0
        )
        peak_deficit_kwh = max(0.0, remaining - future_non_peak_kwh)
        if peak_deficit_kwh <= 0:
            return _decision(
                ControllerState.PEAK_PROTECTION,
                "Peak protection is active; charging can wait without risking the buffered deadline.",
                **off,
            )
        peak_seconds = max(1.0, (peak_end - inputs.now).total_seconds())
        required_w = min(
            settings.max_power_w,
            peak_deficit_kwh * 3_600_000.0 / (peak_seconds * settings.charging_efficiency),
        )
        requested, max_hold, release_candidate = _deadline_current_with_max_hold(
            required_w, inputs, settings
        )
        return _decision(
            ControllerState.DEADLINE_RECOVERY,
            (
                "Maximum output is held while peak deadline recovery remains near the feasibility boundary."
                if max_hold
                else "Peak charging is physically required to preserve buffered-deadline feasibility."
            ),
            True,
            requested,
            remaining,
            settings,
            required_w=required_w,
            available_solar_w=observed_solar_w,
            deadline=deadline,
            deadline_feasibility_margin_kwh=feasibility_margin_kwh,
            deadline_max_output_hold=max_hold,
            deadline_max_release_candidate=release_candidate,
            deadline_max_release_elapsed_s=inputs.deadline_max_release_elapsed_s,
            now=inputs.now,
        )

    recovery_w = _non_peak_recovery_power(inputs.now, deadline, remaining, settings)
    in_overnight = _in_window(local_time, settings.overnight_start, settings.ready_by)
    if in_overnight:
        # A maximum deadline request is sticky across the feasibility boundary.
        # Do not hand control straight back to fast battery feedback until the
        # underlying deadline requirement has remained materially lower for the
        # configured dwell.
        requested, max_hold, release_candidate = _deadline_current_with_max_hold(
            recovery_w, inputs, settings
        )
        if max_hold:
            return _decision(
                ControllerState.DEADLINE_RECOVERY,
                "Maximum output is held while the deadline requirement proves it is materially below the feasibility boundary.",
                True,
                requested,
                remaining,
                settings,
                required_w=recovery_w,
                available_solar_w=observed_solar_w,
                deadline=deadline,
                deadline_feasibility_margin_kwh=feasibility_margin_kwh,
                deadline_max_output_hold=True,
                deadline_max_release_candidate=release_candidate,
                deadline_max_release_elapsed_s=inputs.deadline_max_release_elapsed_s,
                now=inputs.now,
            )
        if inputs.battery_soc <= settings.overnight_battery_floor + 0.05:
            hours_remaining = max(seconds_remaining / 3600.0, 1 / 3600)
            required_w = remaining * 1000.0 / (
                hours_remaining * settings.charging_efficiency
            )
            requested, max_hold, release_candidate = _deadline_current_with_max_hold(
                required_w, inputs, settings
            )
            return _decision(
                ControllerState.OVERNIGHT_FLOOR,
                (
                    "Battery floor reached; maximum output is held until the deadline requirement remains materially lower."
                    if max_hold
                    else "Battery floor reached; the remaining allowance is continuously spread to the buffered deadline."
                ),
                True,
                requested,
                remaining,
                settings,
                required_w=required_w,
                available_solar_w=observed_solar_w,
                deadline=deadline,
                deadline_feasibility_margin_kwh=feasibility_margin_kwh,
                deadline_max_output_hold=max_hold,
                deadline_max_release_candidate=release_candidate,
                deadline_max_release_elapsed_s=inputs.deadline_max_release_elapsed_s,
                now=inputs.now,
            )

        # Above the floor, ramp toward the highest rate the battery can support
        # without sustained grid import. Current reductions remain immediate,
        # but disabling the charger is a separate, battery-headroom-aware step.
        excess_import = max(0.0, inputs.grid_import_w - settings.grid_tolerance_w)
        stable_power = (
            settings.max_power_w
            if excess_import <= 0
            else max(0.0, inputs.charger_power_w - excess_import)
        )
        stable_current = _ramped_feedback_current(stable_power, inputs, settings)
        recovery_current = _requested_current_for_power(recovery_w, settings)
        if recovery_current > stable_current:
            requested, max_hold, release_candidate = _deadline_current_with_max_hold(
                recovery_w, inputs, settings
            )
            return _decision(
                ControllerState.DEADLINE_RECOVERY,
                (
                    "Maximum output is held while deadline recovery remains near the feasibility boundary."
                    if max_hold
                    else "Grid support is required now to preserve buffered-deadline feasibility."
                ),
                True,
                requested,
                remaining,
                settings,
                required_w=recovery_w,
                available_solar_w=observed_solar_w,
                deadline=deadline,
                deadline_feasibility_margin_kwh=feasibility_margin_kwh,
                deadline_max_output_hold=max_hold,
                deadline_max_release_candidate=release_candidate,
                deadline_max_release_elapsed_s=inputs.deadline_max_release_elapsed_s,
                now=inputs.now,
            )
        if stable_current < settings.min_current_a:
            actual_current = (
                max(0.0, inputs.charger_current_a)
                if inputs.charger_enabled
                else max(0.0, inputs.charger_power_w / settings.watts_per_amp)
            )
            # Never jump directly from an adjustable rate to off. Reduce to the
            # charger minimum first so ordinary load tuning remains quick without
            # unnecessary contactor cycling.
            if inputs.charger_enabled and actual_current > (
                settings.min_current_a + settings.current_step_a / 2.0
            ):
                return _decision(
                    ControllerState.POST_PEAK_BATTERY,
                    "Post-peak current was reduced to the charger minimum before evaluating a stop.",
                    True,
                    settings.min_current_a,
                    remaining,
                    settings,
                    available_solar_w=observed_solar_w,
                    deadline=deadline,
                    now=inputs.now,
                )

            battery_discharge_w = max(0.0, inputs.battery_power_w)
            battery_headroom_w = max(
                0.0,
                settings.battery_discharge_control_ceiling_w - battery_discharge_w,
            )
            uncovered_import_w = max(0.0, excess_import - battery_headroom_w)
            can_wait_for_battery = (
                inputs.charger_enabled
                and actual_current >= settings.min_current_a - settings.current_step_a / 2.0
                and inputs.battery_power_valid
                and battery_discharge_w < settings.battery_discharge_control_ceiling_w
                and uncovered_import_w <= 0.0
                and inputs.battery_response_elapsed_s < settings.battery_response_grace_s
            )
            if can_wait_for_battery:
                return _decision(
                    ControllerState.POST_PEAK_BATTERY,
                    "Post-peak charging is holding the charger minimum while available battery headroom responds.",
                    True,
                    settings.min_current_a,
                    remaining,
                    settings,
                    available_solar_w=observed_solar_w,
                    deadline=deadline,
                    battery_response_hold=True,
                    battery_discharge_headroom_w=battery_headroom_w,
                    battery_uncovered_import_w=uncovered_import_w,
                    now=inputs.now,
                )
            return _decision(
                ControllerState.POST_PEAK_BATTERY,
                "Post-peak battery-following stopped because minimum-current demand cannot be supported within the battery response limit.",
                **off,
                battery_discharge_headroom_w=battery_headroom_w,
                battery_uncovered_import_w=uncovered_import_w,
            )
        return _decision(
            ControllerState.POST_PEAK_BATTERY,
            "Post-peak charging is following available battery support without sustained grid import.",
            True,
            stable_current,
            remaining,
            settings,
            available_solar_w=observed_solar_w,
            deadline=deadline,
            now=inputs.now,
        )

    recovery_current = _requested_current_for_power(recovery_w, settings)
    if recovery_current > solar_current:
        requested, max_hold, release_candidate = _deadline_current_with_max_hold(
            recovery_w, inputs, settings
        )
        return _decision(
            ControllerState.DEADLINE_RECOVERY,
            (
                "Maximum output is held while non-peak deadline recovery remains near the feasibility boundary."
                if max_hold
                else "Charging now is required to preserve non-peak buffered-deadline feasibility."
            ),
            True,
            requested,
            remaining,
            settings,
            required_w=recovery_w,
            available_solar_w=observed_solar_w,
            policy_solar_w=policy_solar_w,
            deadline=deadline,
            deadline_feasibility_margin_kwh=feasibility_margin_kwh,
            deadline_max_output_hold=max_hold,
            deadline_max_release_candidate=release_candidate,
            deadline_max_release_elapsed_s=inputs.deadline_max_release_elapsed_s,
            now=inputs.now,
        )
    if solar_current < settings.min_current_a:
        state = (
            ControllerState.DAYTIME_RESERVE
            if below_reserve
            else ControllerState.DAYTIME_WAITING_FOR_SURPLUS
        )
        reason = (
            "Battery reserve has priority; no genuine overflow is available for the EV."
            if below_reserve
            else "Battery reserve is achieved, but no-grid solar headroom is below charger minimum."
        )
        return _decision(state, reason, **off, policy_solar_w=policy_solar_w)

    state = ControllerState.DAYTIME_OVERFLOW if below_reserve else ControllerState.DAYTIME_SOLAR
    reason = (
        "Genuine solar overflow is charging the EV while battery reserve retains priority."
        if below_reserve
        else "Battery reserve is achieved; the EV has priority over further battery charging without grid import."
    )
    return _decision(
        state,
        reason,
        True,
        solar_current,
        remaining,
        settings,
        available_solar_w=observed_solar_w,
        policy_solar_w=policy_solar_w,
        deadline=deadline,
        now=inputs.now,
    )
