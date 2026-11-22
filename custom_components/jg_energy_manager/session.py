"""Deterministic charging-session lifecycle and energy accounting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .runtime import RuntimeState


@dataclass(frozen=True, slots=True)
class SessionSettings:
    """Session-accounting controls."""

    target_energy_kwh: float
    control_interval_s: float
    idle_power_w: float
    no_demand_timeout_s: float


@dataclass(frozen=True, slots=True)
class SessionSample:
    """One normalised charger sample."""

    now: datetime
    connected: bool
    charging: bool
    charger_power_w: float
    energy_total_kwh: float | None
    charger_enabled: bool
    requesting_charge: bool


def _finish_session(rt: RuntimeState, sample: SessionSample, settings: SessionSettings) -> None:
    """Capture the completed session before clearing active-session state."""
    if rt.session_started_at is not None:
        rt.last_session_energy_kwh = rt.session_energy_kwh
        rt.last_session_unused_allowance_kwh = max(
            0.0, settings.target_energy_kwh - rt.session_energy_kwh
        )
        rt.last_session_started_at = rt.session_started_at
        rt.last_session_ended_at = sample.now.isoformat()
        rt.last_session_satisfied_at = rt.session_satisfied_at
        rt.last_session_end_reason = (
            "vehicle_satisfied" if rt.vehicle_satisfied else "disconnected"
        )


def _clear_active_session(rt: RuntimeState) -> None:
    rt.energy_baseline_kwh = None
    rt.integrated_energy_kwh = 0.0
    rt.counter_delta_kwh = None
    rt.session_energy_kwh = 0.0
    rt.session_energy_source = "inactive"
    rt.energy_meter_available = False
    rt.vehicle_satisfied = False
    rt.session_started_at = None
    rt.session_satisfied_at = None
    rt.satisfied_energy_kwh = None
    rt.low_demand_since = None
    rt.session_had_charging = False
    rt.was_charging = False


def update_session(
    rt: RuntimeState,
    sample: SessionSample,
    settings: SessionSettings,
) -> None:
    """Update persistent session state without attributing unobserved energy.

    Meter deltas are authoritative while the cumulative meter is available.
    Power integration is a bounded fallback only.  A rising connection edge and
    a stale/restart interval never retrospectively apply the latest power sample.
    """
    previous_sample = RuntimeState.parse_dt(rt.last_sample_at)
    rising_edge = sample.connected and not rt.was_connected
    falling_edge = not sample.connected and rt.was_connected

    if rising_edge:
        rt.energy_baseline_kwh = sample.energy_total_kwh
        rt.integrated_energy_kwh = 0.0
        rt.counter_delta_kwh = 0.0 if sample.energy_total_kwh is not None else None
        rt.session_energy_kwh = 0.0
        rt.session_energy_source = (
            "meter" if sample.energy_total_kwh is not None else "integrated_fallback"
        )
        rt.energy_meter_available = sample.energy_total_kwh is not None
        rt.vehicle_satisfied = False
        rt.session_started_at = sample.now.isoformat()
        rt.session_satisfied_at = None
        rt.satisfied_energy_kwh = None
        rt.low_demand_since = None
        rt.session_had_charging = False
        rt.was_charging = sample.charging
    elif falling_edge:
        _finish_session(rt, sample, settings)
        _clear_active_session(rt)
    elif sample.connected:
        elapsed_s = None
        if previous_sample is not None:
            elapsed_s = max(0.0, (sample.now - previous_sample).total_seconds())
        fresh_limit_s = max(
            settings.control_interval_s * 2.5,
            settings.control_interval_s + 5.0,
        )

        if not rt.vehicle_satisfied:
            if (
                elapsed_s is not None
                and elapsed_s <= fresh_limit_s
                and sample.charging
                and sample.charger_power_w > 0
            ):
                rt.integrated_energy_kwh += (
                    sample.charger_power_w * elapsed_s / 3_600_000.0
                )

            meter_available = sample.energy_total_kwh is not None
            if meter_available:
                # On first availability/recovery/rebase, preserve energy already
                # measured by the bounded integration fallback.
                if (
                    rt.energy_baseline_kwh is None
                    or not rt.energy_meter_available
                    or sample.energy_total_kwh < rt.energy_baseline_kwh - 0.001
                ):
                    preserved_energy = max(
                        rt.session_energy_kwh, rt.integrated_energy_kwh
                    )
                    rt.energy_baseline_kwh = (
                        sample.energy_total_kwh - preserved_energy
                    )
                delta = max(0.0, sample.energy_total_kwh - rt.energy_baseline_kwh)
                rt.counter_delta_kwh = delta
                rt.session_energy_kwh = delta
                rt.integrated_energy_kwh = delta
                rt.session_energy_source = "meter"
            else:
                rt.counter_delta_kwh = None
                rt.session_energy_kwh = rt.integrated_energy_kwh
                rt.session_energy_source = "integrated_fallback"
            rt.energy_meter_available = meter_available

        if sample.charging and sample.charger_power_w >= settings.idle_power_w:
            rt.session_had_charging = True

        credible_no_demand = bool(
            sample.charger_enabled
            and sample.requesting_charge
            and rt.session_had_charging
            and not sample.charging
            and sample.charger_power_w < settings.idle_power_w
        )
        if not rt.vehicle_satisfied and credible_no_demand:
            if rt.low_demand_since is None:
                rt.low_demand_since = sample.now.isoformat()
            since = RuntimeState.parse_dt(rt.low_demand_since)
            if (
                since is not None
                and (sample.now - since).total_seconds()
                >= settings.no_demand_timeout_s
            ):
                rt.vehicle_satisfied = True
                rt.session_satisfied_at = sample.now.isoformat()
                rt.satisfied_energy_kwh = rt.session_energy_kwh
                rt.session_energy_source = "frozen_at_satisfaction"
        elif not rt.vehicle_satisfied:
            rt.low_demand_since = None

        rt.was_charging = sample.charging

    rt.was_connected = sample.connected
    rt.last_sample_at = sample.now.isoformat()
    rt.last_energy_total_kwh = sample.energy_total_kwh
