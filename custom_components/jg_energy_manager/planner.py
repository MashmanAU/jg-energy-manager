"""Pure charging-planner logic for JG Energy Manager.

This module deliberately has no Home Assistant imports so the safety-critical
calculation can be unit tested in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import StrEnum
import math


class ControllerState(StrEnum):
    DISABLED = "disabled"
    IDLE = "idle"
    COMPLETE = "complete"
    PEAK_PROTECTION = "peak_protection"
    DAYTIME_RESERVE = "daytime_reserve"
    DAYTIME_WAITING_FOR_SURPLUS = "daytime_waiting_for_surplus"
    DAYTIME_SOLAR = "daytime_solar"
    OVERNIGHT_SLOW = "overnight_slow"
    OVERNIGHT_FLOOR = "overnight_floor"
    DEADLINE_RECOVERY = "deadline_recovery"
    OVERRIDE_OFF = "override_off"
    OVERRIDE_MAX = "override_max"
    VEHICLE_SATISFIED = "vehicle_satisfied"
    INPUT_ERROR = "input_error"


@dataclass(frozen=True, slots=True)
class PlannerSettings:
    target_energy_kwh: float = 30.0
    ready_by: time = time(6, 0)
    overnight_start: time = time(21, 0)
    peak_start: time = time(15, 0)
    peak_end: time = time(21, 0)
    peak_months: frozenset[int] = frozenset({1, 2, 3, 6, 7, 8, 11, 12})
    overnight_battery_floor: float = 10.0
    daytime_battery_reserve: float = 45.0
    soc_hysteresis: float = 2.0
    min_current_a: float = 6.0
    max_current_a: float = 32.0
    max_charger_power_w: float = 7360.0
    current_step_a: float = 0.1
    supply_voltage: float = 230.0
    phases: int = 1
    charging_efficiency: float = 0.90
    solar_start_margin_w: float = 400.0
    solar_run_margin_w: float = 150.0

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
        return round(
            math.floor((value + 1e-9) / self.current_step_a) * self.current_step_a,
            3,
        )


@dataclass(frozen=True, slots=True)
class PlannerInputs:
    now: datetime
    controller_enabled: bool
    connected: bool
    battery_soc: float
    grid_import_w: float
    solar_power_w: float
    charger_power_w: float
    session_energy_kwh: float
    charger_enabled: bool
    vehicle_satisfied: bool = False
    override: str = "automatic"
    inputs_valid: bool = True


@dataclass(frozen=True, slots=True)
class Decision:
    state: ControllerState
    reason: str
    should_enable: bool
    requested_current_a: float
    requested_power_w: float
    energy_remaining_kwh: float
    required_average_power_w: float
    available_solar_power_w: float
    projected_completion: datetime | None
    deadline: datetime | None


def _in_window(value: time, start: time, end: time) -> bool:
    """Return whether a local time is in [start, end), including midnight wrap."""
    if start == end:
        return True
    if start < end:
        return start <= value < end
    return value >= start or value < end


def _next_occurrence(now: datetime, target: time) -> datetime:
    candidate = now.replace(
        hour=target.hour,
        minute=target.minute,
        second=target.second,
        microsecond=0,
    )
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


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
    deadline: datetime | None = None,
    now: datetime,
) -> Decision:
    power_w = current_a * settings.watts_per_amp if enable else 0.0
    return Decision(
        state=state,
        reason=reason,
        should_enable=enable,
        requested_current_a=current_a if enable else 0.0,
        requested_power_w=power_w,
        energy_remaining_kwh=remaining,
        required_average_power_w=required_w,
        available_solar_power_w=max(0.0, available_solar_w),
        projected_completion=_completion(
            now, remaining, power_w, settings.charging_efficiency
        ),
        deadline=deadline,
    )


def calculate_decision(inputs: PlannerInputs, settings: PlannerSettings) -> Decision:
    """Calculate one deterministic controller decision."""
    remaining = max(0.0, settings.target_energy_kwh - inputs.session_energy_kwh)
    off = dict(
        enable=False,
        current_a=0.0,
        remaining=remaining,
        settings=settings,
        now=inputs.now,
    )

    if (
        settings.min_current_a <= 0
        or settings.max_current_a < settings.min_current_a
        or settings.current_step_a <= 0
        or settings.max_charger_power_w < settings.min_power_w
        or settings.supply_voltage <= 0
        or settings.phases <= 0
        or not 0 < settings.charging_efficiency <= 1
    ):
        return _decision(
            ControllerState.INPUT_ERROR,
            "Controller limits are inconsistent; correct the integration options.",
            **off,
        )

    if not inputs.inputs_valid:
        return _decision(
            ControllerState.INPUT_ERROR,
            "Required input unavailable or invalid; fail-safe stop requested.",
            **off,
        )
    if not inputs.controller_enabled:
        return _decision(
            ControllerState.DISABLED,
            "Controller is disabled.",
            **off,
        )
    if inputs.override == "force_off":
        return _decision(
            ControllerState.OVERRIDE_OFF,
            "Manual Force Off override is active.",
            **off,
        )
    if not inputs.connected:
        return _decision(
            ControllerState.IDLE,
            "No vehicle is connected.",
            **off,
        )
    if inputs.vehicle_satisfied:
        return _decision(
            ControllerState.VEHICLE_SATISFIED,
            "The vehicle stopped accepting power; session maximum is no longer forced.",
            **off,
        )
    if remaining <= 0.001:
        return _decision(
            ControllerState.COMPLETE,
            "The configured maximum session energy has been delivered.",
            **off,
        )
    if inputs.override == "force_max":
        return _decision(
            ControllerState.OVERRIDE_MAX,
            "Manual Force Max override is active.",
            True,
            settings.effective_max_current_a,
            remaining,
            settings,
            now=inputs.now,
        )

    local_time = inputs.now.timetz().replace(tzinfo=None)

    # Peak protection is intentionally the highest automatic priority.
    if (
        inputs.now.month in settings.peak_months
        and _in_window(local_time, settings.peak_start, settings.peak_end)
    ):
        return _decision(
            ControllerState.PEAK_PROTECTION,
            "Peak protection window is active; EV charging is stopped.",
            **off,
        )

    if _in_window(local_time, settings.overnight_start, settings.ready_by):
        deadline = _next_occurrence(inputs.now, settings.ready_by)
        hours_remaining = max((deadline - inputs.now).total_seconds() / 3600.0, 1 / 60)
        required_w = remaining * 1000.0 / (
            hours_remaining * settings.charging_efficiency
        )
        raw_current = required_w / settings.watts_per_amp
        requested = max(settings.min_current_a, _round_up(raw_current, settings.current_step_a))
        state = ControllerState.OVERNIGHT_SLOW
        reason = (
            "Overnight slow charging is pacing the remaining session energy to the ready-by time."
        )
        if requested > settings.effective_max_current_a:
            requested = settings.effective_max_current_a
            state = ControllerState.DEADLINE_RECOVERY
            reason = (
                "The target cannot be met at the calculated rate; maximum current is requested."
            )
        elif inputs.battery_soc <= settings.overnight_battery_floor:
            state = ControllerState.OVERNIGHT_FLOOR
            reason = (
                "The overnight battery floor has been reached; charging continues at the "
                "deadline rate and the inverter may draw the shortfall from the grid."
            )
        return _decision(
            state,
            reason,
            True,
            requested,
            remaining,
            settings,
            required_w=required_w,
            deadline=deadline,
            now=inputs.now,
        )

    # Daytime logic starts only with export headroom. Including current charger
    # load makes the feedback stable after charging begins:
    # available = present charger load - present grid import - margin.
    reserve_threshold = (
        settings.daytime_battery_reserve - settings.soc_hysteresis
        if inputs.charger_enabled
        else settings.daytime_battery_reserve + settings.soc_hysteresis
    )
    if inputs.battery_soc < reserve_threshold:
        return _decision(
            ControllerState.DAYTIME_RESERVE,
            "Battery SOC is below the daytime reserve; solar is retained for the home battery.",
            **off,
        )

    margin = (
        settings.solar_run_margin_w
        if inputs.charger_enabled
        else settings.solar_start_margin_w
    )
    available_w = max(0.0, inputs.charger_power_w - inputs.grid_import_w - margin)
    raw_current = available_w / settings.watts_per_amp
    requested = min(
        settings.effective_max_current_a,
        _round_down(raw_current, settings.current_step_a),
    )
    if requested < settings.min_current_a:
        return _decision(
            ControllerState.DAYTIME_WAITING_FOR_SURPLUS,
            "Battery reserve is protected, but export headroom is below the minimum charger power.",
            **off,
            available_solar_w=available_w,
        )

    return _decision(
        ControllerState.DAYTIME_SOLAR,
        "Daytime solar-surplus charging is active while the battery reserve is protected.",
        True,
        requested,
        remaining,
        settings,
        available_solar_w=available_w,
        now=inputs.now,
    )
