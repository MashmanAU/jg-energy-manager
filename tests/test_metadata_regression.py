"""Static metadata and migration regressions without Home Assistant imports."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]


def _sensor_call(key: str):
    source = ROOT / "custom_components" / "jg_energy_manager" / "sensor.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    sensors = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "SENSORS" for target in node.targets)
    )
    return next(
        call
        for call in ast.walk(sensors.value)
        if isinstance(call, ast.Call)
        and any(
            keyword.arg == "key"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == key
            for keyword in call.keywords
        )
    )


def test_remaining_allowance_is_a_migration_safe_measurement_gauge():
    energy_remaining = _sensor_call("energy_remaining")
    keywords = {keyword.arg: keyword.value for keyword in energy_remaining.keywords}
    assert "state_class" in keywords
    assert isinstance(keywords["state_class"], ast.Attribute)
    assert keywords["state_class"].attr == "MEASUREMENT"
    # Energy device class does not accept measurement state class; the unit still
    # communicates kWh while preserving the v0.1.x statistics state class.
    assert "device_class" not in keywords


def test_stable_existing_entity_keys_preserve_unique_ids():
    for key in (
        "controller_state",
        "requested_current",
        "requested_power",
        "available_solar_power",
        "session_energy",
        "energy_remaining",
    ):
        assert _sensor_call(key)


def test_runtime_migrates_legacy_override_values_to_operating_modes():
    source = ROOT / "custom_components" / "jg_energy_manager" / "runtime.py"
    text = source.read_text(encoding="utf-8")
    assert '"force_max": "force_charge"' in text
    assert '"force_off": "off"' in text


def test_config_entry_migration_adds_charging_states_without_replacing_ids():
    source = (ROOT / "custom_components" / "jg_energy_manager" / "__init__.py").read_text()
    assert "async_migrate_entry" in source
    assert "CONF_CHARGING_STATES" in source
    entity_source = (ROOT / "custom_components" / "jg_energy_manager" / "entity.py").read_text()
    assert 'f"{coordinator.config_entry.entry_id}_{key}"' in entity_source


def test_live_reconciliation_tracks_all_control_relevant_input_entities():
    source = (ROOT / "custom_components" / "jg_energy_manager" / "coordinator.py").read_text()
    assert "async_track_state_change_event" in source
    for constant in (
        "CONF_CHARGER_STATUS_ENTITY",
        "CONF_CHARGER_POWER_ENTITY",
        "CONF_CHARGER_CURRENT_ENTITY",
        "CONF_CHARGER_ENABLE_ENTITY",
        "CONF_CHARGER_ENERGY_ENTITY",
        "CONF_BATTERY_SOC_ENTITY",
        "CONF_GRID_POWER_ENTITY",
        "CONF_SOLAR_POWER_ENTITY",
    ):
        assert constant in source
    init_source = (ROOT / "custom_components" / "jg_energy_manager" / "__init__.py").read_text()
    assert "async_start_reconciliation" in init_source
