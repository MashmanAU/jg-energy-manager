"""Actuator acknowledgement, timeout and retry regression tests."""

from __future__ import annotations

from datetime import datetime, timedelta
import importlib.util
from pathlib import Path
import sys

MODULE = Path(__file__).parents[1] / "custom_components/jg_energy_manager/actuator.py"
spec = importlib.util.spec_from_file_location("jg_energy_actuator_test", MODULE)
actuator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = actuator
assert spec.loader is not None
spec.loader.exec_module(actuator)
ActuatorState = actuator.ActuatorState


def now():
    return datetime.fromisoformat("2026-11-23T10:00:00+11:00")


def test_issued_current_is_not_successful_until_observed_acknowledgement():
    state = ActuatorState()
    state.begin(now(), requested_current_a=12.0)
    assert state.status == "awaiting_acknowledgement"
    assert state.last_success_at is None
    state.observe(
        now() + timedelta(seconds=30),
        current_a=12.0,
        enabled=True,
        deadband_a=0.2,
        acknowledgement_timeout_s=90,
    )
    assert state.healthy
    assert state.status == "acknowledged"
    assert state.last_acknowledged_current_a == 12.0


def test_missing_acknowledgement_marks_failure_and_backs_off():
    state = ActuatorState()
    state.begin(now(), requested_current_a=16.0)
    state.observe(
        now() + timedelta(seconds=91),
        current_a=6.0,
        enabled=True,
        deadband_a=0.2,
        acknowledgement_timeout_s=90,
    )
    assert not state.healthy
    assert state.consecutive_failures == 1
    assert not state.can_attempt(now() + timedelta(seconds=100))
    assert state.can_attempt(now() + timedelta(seconds=107))


def test_service_failure_has_bounded_exponential_retry_including_safety_stop():
    state = ActuatorState()
    state.record_failure(now(), "Dashboard connection failed")
    first_retry = state._parse(state.next_retry_at)
    assert (first_retry - now()).total_seconds() == 15
    state.record_failure(now() + timedelta(seconds=15), "still down")
    second_retry = state._parse(state.next_retry_at)
    assert (second_retry - (now() + timedelta(seconds=15))).total_seconds() == 30
    assert not state.can_attempt(now(), safety_stop=True)
    assert state.can_attempt(second_retry, safety_stop=True)


def test_safer_current_reduction_supersedes_pending_higher_command():
    state = ActuatorState()
    state.begin(now(), requested_current_a=20.0)
    state.cancel_pending_for_reduction(12.0)
    assert state.pending_since is None
    assert state.can_attempt(now())
