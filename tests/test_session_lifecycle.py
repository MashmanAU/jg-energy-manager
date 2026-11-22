"""Session accounting at connect, restart, recovery, satisfaction and disconnect."""

from __future__ import annotations

from datetime import datetime, timedelta
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

ROOT = Path(__file__).parents[1] / "custom_components" / "jg_energy_manager"
PACKAGE = "jg_energy_session_test"
package = ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules.setdefault(PACKAGE, package)


def _load(name):
    full = f"{PACKAGE}.{name}"
    spec = importlib.util.spec_from_file_location(full, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


runtime = _load("runtime")
session = _load("session")
RuntimeState = runtime.RuntimeState
SessionSample = session.SessionSample
SessionSettings = session.SessionSettings
update_session = session.update_session
SETTINGS = SessionSettings(30, 30, 250, 180)


def at(text):
    return datetime.fromisoformat(text)


def sample(when, **changes):
    values = dict(
        now=at(when),
        connected=True,
        charging=True,
        charger_power_w=6900,
        energy_total_kwh=100.0,
        charger_enabled=True,
        requesting_charge=True,
    )
    values.update(changes)
    return SessionSample(**values)


def test_connect_edge_sets_baseline_without_backdating_one_poll_of_energy():
    rt = RuntimeState(last_sample_at="2026-11-23T09:59:30+11:00")
    update_session(rt, sample("2026-11-23T10:00:00+11:00"), SETTINGS)
    assert rt.session_energy_kwh == 0
    assert rt.integrated_energy_kwh == 0
    assert rt.energy_baseline_kwh == 100


def test_meter_is_authoritative_during_normal_session():
    rt = RuntimeState()
    update_session(rt, sample("2026-11-23T10:00:00+11:00"), SETTINGS)
    update_session(
        rt,
        sample("2026-11-23T10:00:30+11:00", energy_total_kwh=100.05),
        SETTINGS,
    )
    assert abs(rt.session_energy_kwh - 0.05) < 1e-9
    assert rt.session_energy_source == "meter"


def test_restart_gap_does_not_integrate_latest_power_backwards():
    rt = RuntimeState(
        was_connected=True,
        energy_baseline_kwh=100,
        session_energy_kwh=5,
        integrated_energy_kwh=5,
        energy_meter_available=True,
        session_started_at="2026-11-23T01:00:00+11:00",
        last_sample_at="2026-11-23T02:00:00+11:00",
    )
    update_session(
        rt,
        sample("2026-11-23T02:20:00+11:00", energy_total_kwh=105.0),
        SETTINGS,
    )
    assert rt.session_energy_kwh == 5


def test_meter_recovery_rebases_without_jump_after_integrated_fallback():
    rt = RuntimeState()
    update_session(
        rt,
        sample("2026-11-23T10:00:00+11:00", energy_total_kwh=None),
        SETTINGS,
    )
    update_session(
        rt,
        sample("2026-11-23T10:00:30+11:00", energy_total_kwh=None, charger_power_w=3600),
        SETTINGS,
    )
    assert abs(rt.session_energy_kwh - 0.03) < 1e-9
    update_session(
        rt,
        sample("2026-11-23T10:01:00+11:00", energy_total_kwh=200.0, charger_power_w=3600),
        SETTINGS,
    )
    assert abs(rt.session_energy_kwh - 0.06) < 1e-9
    assert rt.session_energy_source == "meter"


def test_satisfaction_requires_confirmed_prior_charging_and_freezes_energy():
    rt = RuntimeState()
    update_session(rt, sample("2026-11-23T01:00:00+11:00"), SETTINGS)
    update_session(
        rt,
        sample("2026-11-23T01:00:30+11:00", energy_total_kwh=100.05),
        SETTINGS,
    )
    # Connected-but-not-charging status and low demand must persist for timeout.
    update_session(
        rt,
        sample("2026-11-23T01:01:00+11:00", charging=False, charger_power_w=0, energy_total_kwh=100.05),
        SETTINGS,
    )
    update_session(
        rt,
        sample("2026-11-23T01:04:00+11:00", charging=False, charger_power_w=0, energy_total_kwh=100.05),
        SETTINGS,
    )
    assert rt.vehicle_satisfied
    frozen = rt.session_energy_kwh
    update_session(
        rt,
        sample("2026-11-23T02:00:00+11:00", charging=False, charger_power_w=40, energy_total_kwh=100.2),
        SETTINGS,
    )
    assert rt.session_energy_kwh == frozen
    assert rt.session_energy_source == "frozen_at_satisfaction"


def test_disconnect_captures_last_session_before_active_values_clear():
    rt = RuntimeState(
        was_connected=True,
        session_started_at="2026-11-23T01:00:00+11:00",
        session_energy_kwh=19.808,
        vehicle_satisfied=True,
        session_satisfied_at="2026-11-23T02:13:12+11:00",
        last_sample_at="2026-11-23T07:59:42+11:00",
    )
    update_session(
        rt,
        sample(
            "2026-11-23T08:00:12+11:00",
            connected=False,
            charging=False,
            charger_power_w=0,
            energy_total_kwh=120,
            charger_enabled=False,
            requesting_charge=False,
        ),
        SETTINGS,
    )
    assert rt.session_energy_kwh == 0
    assert rt.last_session_energy_kwh == 19.808
    assert rt.last_session_unused_allowance_kwh == 10.192
    assert rt.last_session_end_reason == "vehicle_satisfied"
