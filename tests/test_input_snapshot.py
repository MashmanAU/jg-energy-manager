"""Startup/reload snapshots and input-health recovery regressions."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

MODULE = Path(__file__).parents[1] / "custom_components/jg_energy_manager/input_snapshot.py"
spec = importlib.util.spec_from_file_location("jg_energy_input_snapshot_test", MODULE)
inputs = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = inputs
assert spec.loader is not None
spec.loader.exec_module(inputs)

InputRole = inputs.InputRole
snapshot_inputs = inputs.snapshot_inputs

ROLES = (
    InputRole("battery_soc", "battery_soc_entity", "numeric"),
    InputRole("battery_power", "battery_power_entity", "numeric", required=False),
    InputRole("grid_power", "grid_power_entity", "numeric"),
    InputRole("solar_power", "solar_power_entity", "numeric"),
    InputRole("charger_status", "charger_status_entity", "text"),
    InputRole("charger_power", "charger_power_entity", "numeric"),
    InputRole("charger_energy", "charger_energy_entity", "numeric", required=False),
    InputRole("charger_enable", "charger_enable_entity", "text"),
    InputRole("charger_current", "charger_current_entity", "numeric"),
)

SETTINGS = {
    "battery_soc_entity": "sensor.battery_soc",
    "battery_power_entity": "sensor.battery_power",
    "grid_power_entity": "sensor.grid_power",
    "solar_power_entity": "sensor.solar_power",
    "charger_status_entity": "sensor.charger_status",
    "charger_power_entity": "sensor.charger_power",
    "charger_energy_entity": "sensor.charger_energy",
    "charger_enable_entity": "switch.charger_enable",
    "charger_current_entity": "number.charger_current",
}


def state(value):
    return SimpleNamespace(state=str(value))


def valid_preexisting_states():
    return {
        "sensor.battery_soc": state("62.5"),
        "sensor.battery_power": state("0"),
        "sensor.grid_power": state("0"),
        "sensor.solar_power": state("0.0"),
        "sensor.charger_status": state("A"),
        "sensor.charger_power": state("0"),
        "sensor.charger_energy": state("123.456"),
        "switch.charger_enable": state("off"),
        "number.charger_current": state("6"),
    }


def test_startup_snapshot_reads_valid_preexisting_states_including_zero_and_a():
    states = valid_preexisting_states()
    snapshot = snapshot_inputs(SETTINGS, ROLES, states.get)
    assert snapshot.valid
    assert snapshot.numeric("charger_power") == 0.0
    assert snapshot.numeric("grid_power") == 0.0
    assert snapshot.numeric("battery_power") == 0.0
    assert snapshot.numeric("solar_power") == 0.0
    assert snapshot.text("charger_status") == "A"
    assert snapshot.text("charger_enable") == "off"
    assert snapshot.missing_roles == []
    assert snapshot.invalid_roles == []


def test_reload_and_regular_cycle_do_not_require_any_state_change_callback():
    states = valid_preexisting_states()
    calls = []

    def get_state(entity_id):
        calls.append(entity_id)
        return states.get(entity_id)

    first_refresh = snapshot_inputs(SETTINGS, ROLES, get_state)
    reload_refresh = snapshot_inputs(SETTINGS, ROLES, get_state)
    regular_cycle = snapshot_inputs(SETTINGS, ROLES, get_state)
    assert first_refresh.valid and reload_refresh.valid and regular_cycle.valid
    # Every invocation unconditionally reads every configured role.
    assert len(calls) == len(ROLES) * 3
    assert calls.count("sensor.charger_power") == 3
    assert calls.count("sensor.battery_soc") == 3


def test_unavailable_required_inputs_report_exact_roles_and_recover_when_valid():
    states = valid_preexisting_states()
    states["sensor.grid_power"] = state("unavailable")
    states["sensor.battery_soc"] = None
    failed = snapshot_inputs(SETTINGS, ROLES, states.get)
    assert not failed.valid
    assert failed.missing_roles == ["battery_soc"]
    assert failed.invalid_roles == ["grid_power"]
    health = failed.redacted_health()
    assert set(health) == {role.name for role in ROLES}
    assert all("entity_id" not in detail for detail in health.values())

    states["sensor.grid_power"] = state("0")
    states["sensor.battery_soc"] = state("50")
    recovered = snapshot_inputs(SETTINGS, ROLES, states.get)
    assert recovered.valid
    assert recovered.numeric("grid_power") == 0.0
    assert recovered.missing_roles == []
    assert recovered.invalid_roles == []


def test_optional_meter_or_battery_power_degrades_without_false_input_problem():
    settings = {**SETTINGS, "battery_power_entity": None}
    states = valid_preexisting_states()
    states["sensor.charger_energy"] = state("unavailable")
    snapshot = snapshot_inputs(settings, ROLES, states.get)
    assert snapshot.valid
    assert snapshot.degraded_optional_roles == ["battery_power", "charger_energy"]
