"""Coordinator-level command failure containment without a Home Assistant install."""

from __future__ import annotations

import asyncio
from datetime import datetime
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

ROOT = Path(__file__).parents[1] / "custom_components" / "jg_energy_manager"


def _module(name, **values):
    module = ModuleType(name)
    for key, value in values.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


class GenericStub:
    @classmethod
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, *args, **kwargs):
        pass


# Minimal imports required to execute the real coordinator actuator methods.
_module("homeassistant")
_module("homeassistant.config_entries", ConfigEntry=GenericStub)
_module("homeassistant.const", STATE_ON="on")
_module("homeassistant.core", HomeAssistant=object, State=object)
_module("homeassistant.helpers")
_module("homeassistant.helpers.storage", Store=GenericStub)
_module("homeassistant.helpers.update_coordinator", DataUpdateCoordinator=GenericStub)
util = _module("homeassistant.util")
util.dt = _module("homeassistant.util.dt", now=lambda: datetime.now().astimezone())

PACKAGE = "jg_energy_coordinator_test"
package = ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE] = package


def _load(name):
    full = f"{PACKAGE}.{name}"
    spec = importlib.util.spec_from_file_location(full, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


for dependency in ("const", "runtime", "actuator", "session", "planner"):
    _load(dependency)
coordinator = _load("coordinator")
runtime = sys.modules[f"{PACKAGE}.runtime"]
actuator = sys.modules[f"{PACKAGE}.actuator"]
planner = sys.modules[f"{PACKAGE}.planner"]
const = sys.modules[f"{PACKAGE}.const"]


def _coordinator():
    value = object.__new__(coordinator.JGEnergyCoordinator)
    value.runtime = runtime.RuntimeState(observe_only=False)
    value.actuator = actuator.ActuatorState()
    value.settings = {
        const.CONF_STOP_WHEN_DISABLED: True,
        const.CONF_FAIL_SAFE_STOP: True,
        const.CONF_COMMAND_DEADBAND_A: 0.2,
        const.CONF_MIN_COMMAND_INTERVAL_S: 30,
        const.CONF_CHARGER_CURRENT_ENTITY: "number.charger_current",
        const.CONF_CHARGER_ENABLE_ENTITY: "switch.charger_enable",
    }
    value._last_increase_at = None
    value._last_decrease_at = None
    return value


def _decision(current=12.0):
    return planner.Decision(
        state=planner.ControllerState.DAYTIME_SOLAR,
        reason="test",
        should_enable=True,
        requested_current_a=current,
        requested_power_w=current * 230,
        energy_remaining_kwh=10,
        required_average_power_w=0,
        available_solar_power_w=4000,
        policy_solar_power_w=3000,
        projected_completion=None,
        deadline=None,
    )


def test_failed_current_service_is_contained_and_charger_is_not_enabled():
    value = _coordinator()
    value._async_command_current = AsyncMock(return_value=False)
    value._async_command_turn = AsyncMock(return_value=True)
    asyncio.run(
        coordinator.JGEnergyCoordinator._async_apply_decision(
            value,
            _decision(),
            now=datetime.fromisoformat("2026-11-23T10:00:00+11:00"),
            charger_enabled=False,
            current_state=6.0,
        )
    )
    value._async_command_turn.assert_not_awaited()


def test_service_exception_sets_actuator_failure_instead_of_escaping():
    value = _coordinator()
    value.hass = SimpleNamespace(
        services=SimpleNamespace(async_call=AsyncMock(side_effect=RuntimeError("Dashboard connection failed")))
    )
    result = asyncio.run(
        coordinator.JGEnergyCoordinator._async_command_current(
            value, 12.0, datetime.fromisoformat("2026-11-23T10:00:00+11:00")
        )
    )
    assert result is False
    assert not value.actuator.healthy
    assert "Dashboard connection failed" in value.actuator.last_command_error
