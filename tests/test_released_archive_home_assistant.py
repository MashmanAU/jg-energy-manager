"""Run the built HACS archive through real Home Assistant and Probatio libraries.

This test is mandatory in GitHub validation/release jobs, which install the pinned
Home Assistant runtime. It is skipped only in the lightweight local unit-test
runtime where Home Assistant is intentionally unavailable.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import ModuleType
import zipfile

import pytest

if os.environ.get("JG_REAL_HA_TEST") != "1":
    pytest.skip(
        "real Home Assistant archive test runs in its dedicated pinned-runtime job",
        allow_module_level=True,
    )

homeassistant = pytest.importorskip("homeassistant")
probatio = pytest.importorskip("probatio")
from homeassistant.helpers import config_validation as cv  # noqa: E402

ROOT = Path(__file__).parents[1]
ARCHIVE = ROOT / "dist" / "jg_energy_manager.zip"


def _load_release(tmp_path: Path):
    assert ARCHIVE.is_file(), "Build dist/jg_energy_manager.zip before this test"
    release = tmp_path / "jg_energy_manager"
    release.mkdir()
    with zipfile.ZipFile(ARCHIVE) as archive:
        archive.extractall(release)

    source = (release / "config_flow.py").read_text(encoding="utf-8")
    tree = __import__("ast").parse(source)
    assert not any(
        isinstance(node, __import__("ast").FunctionDef) and node.name == "_peak_months"
        for node in tree.body
    )

    package_name = "jg_energy_manager_release_test"
    package = ModuleType(package_name)
    package.__path__ = [str(release)]
    sys.modules[package_name] = package

    for module_name in ("const", "config_flow"):
        full_name = f"{package_name}.{module_name}"
        spec = importlib.util.spec_from_file_location(
            full_name, release / f"{module_name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
    return sys.modules[f"{package_name}.config_flow"]


def _run(coroutine):
    return asyncio.run(coroutine)


def _serialise(result):
    if result["type"] == "form":
        fields = probatio.to_field_list(
            result["data_schema"], custom_serializer=cv.custom_serializer
        )
        json.dumps(fields)
    return result


def _assert_number_units_are_valid(result):
    """Real selector configs must omit unit_of_measurement or contain a string."""
    if result["type"] != "form":
        return
    for validator in result["data_schema"].schema.values():
        config = getattr(validator, "config", None)
        if not isinstance(config, dict) or "unit_of_measurement" not in config:
            continue
        assert isinstance(config["unit_of_measurement"], str)


def _submit(flow, result, values):
    validated = result["data_schema"](values)
    next_result = _serialise(
        _run(getattr(flow, f"async_step_{result['step_id']}")(validated))
    )
    _assert_number_units_are_valid(next_result)
    return next_result


def test_built_hacs_archive_completes_real_home_assistant_config_flow(tmp_path):
    """Every released form serialises with Probatio and reaches entry creation."""
    module = _load_release(tmp_path)
    flow = module.JGEnergyConfigFlow()

    result = _serialise(_run(flow.async_step_user()))
    _assert_number_units_are_valid(result)
    result = _submit(
        flow, result, {"name": "JG Energy Manager", "initial_observe_only": True}
    )
    assert result["step_id"] == "energy"

    result = _submit(
        flow,
        result,
        {
            "battery_soc_entity": "sensor.alphaess_battery_soc",
            "battery_power_sign": "positive_discharge",
            "grid_power_entity": "sensor.home_charger_grid_power",
            "grid_power_sign": "positive_import",
            "solar_power_entity": "sensor.home_charger_pv_power",
        },
    )
    assert result["step_id"] == "charger"

    result = _submit(
        flow,
        result,
        {
            "charger_status_entity": "sensor.home_charger_evcc_state",
            "charger_power_entity": "sensor.home_charger_power",
            "charger_energy_entity": "sensor.home_charger_energy_import",
            "charger_enable_entity": "switch.home_charger_evcc_charging",
            "charger_current_entity": "number.home_charger_charging_current_limit",
            "connected_states": "B,C",
        },
    )
    assert result["step_id"] == "schedule"

    result = _submit(
        flow,
        result,
        {
            "target_energy_kwh": 30.0,
            "ready_by": "06:00:00",
            "overnight_start": "21:00:00",
            "peak_start": "15:00:00",
            "peak_end": "21:00:00",
            "peak_months": "1,2,3,6,7,8,11,12",
            "overnight_battery_floor": 10.0,
            "daytime_battery_reserve": 45.0,
            "soc_hysteresis": 2.0,
        },
    )
    assert result["step_id"] == "limits"
    efficiency = next(
        validator
        for marker, validator in result["data_schema"].schema.items()
        if marker.schema == "charging_efficiency"
    )
    assert "unit_of_measurement" not in efficiency.config

    result = _submit(
        flow,
        result,
        {
            "min_current_a": 6.0,
            "max_current_a": 32.0,
            "max_charger_power_w": 7360.0,
            "current_step_a": 0.1,
            "supply_voltage": 230.0,
            "phases": "single_phase",
            "charging_efficiency": 0.90,
            "solar_start_margin_w": 400.0,
            "solar_run_margin_w": 150.0,
            "idle_power_w": 250.0,
        },
    )
    assert result["step_id"] == "control"

    result = _submit(
        flow,
        result,
        {
            "control_interval_s": 30,
            "no_demand_timeout_s": 180,
            "command_deadband_a": 0.2,
            "min_command_interval_s": 30,
            "stop_when_disabled": True,
            "fail_safe_stop": True,
            "initial_observe_only": True,
        },
    )
    assert result["step_id"] == "secondary"

    result = _submit(
        flow,
        result,
        {"secondary_enabled": False, "secondary_name": "Charger 2"},
    )
    assert result["type"] == "create_entry"
    assert result["data"]["phases"] == 1
