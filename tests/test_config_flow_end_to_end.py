"""End-to-end regression tests for every JG Energy Manager config-flow form.

The production module is imported against a compact Home Assistant compatibility
runtime. Unlike the earlier AST-only tests, this runtime serialises every form,
validates selector defaults and submitted values, and advances the real flow
methods through config-entry creation.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum
import importlib.util
import json
from pathlib import Path
import re
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

ROOT = Path(__file__).parents[1]
DOMAIN_DIR = ROOT / "custom_components" / "jg_energy_manager"


class Invalid(ValueError):
    """Voluptuous-compatible validation error."""


_UNDEFINED = object()


class _Marker:
    def __init__(self, schema: str, default: Any = _UNDEFINED) -> None:
        self.schema = schema
        self.default = default

    def __hash__(self) -> int:
        return id(self)


class Required(_Marker):
    """Required schema key."""


class Optional(_Marker):
    """Optional schema key."""


class Schema:
    """Small subset of voluptuous used by this integration."""

    def __init__(self, schema: dict[_Marker, Any]) -> None:
        self.schema = schema

    def __call__(self, data: dict[str, Any]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for marker, validator in self.schema.items():
            key = marker.schema
            if key in data:
                value = data[key]
            elif marker.default is not _UNDEFINED:
                value = marker.default() if callable(marker.default) else marker.default
            elif isinstance(marker, Required):
                raise Invalid(f"required key not provided: {key}")
            else:
                continue
            output[key] = validator(value) if callable(validator) else value
        return output


class _Config:
    def __init__(self, **values: Any) -> None:
        self.__dict__.update(values)

    def as_dict(self) -> dict[str, Any]:
        return {
            key: value.value if isinstance(value, StrEnum) else value
            for key, value in self.__dict__.items()
            if value is not None
        }


class EntitySelectorConfig(_Config):
    pass


class NumberSelectorConfig(_Config):
    pass


class SelectSelectorConfig(_Config):
    pass


class NumberSelectorMode(StrEnum):
    BOX = "box"


class SelectSelectorMode(StrEnum):
    DROPDOWN = "dropdown"


class _Selector:
    selector_type = "unknown"

    def __init__(self, config: _Config | None = None) -> None:
        self.config = config or _Config()

    def serialize(self) -> dict[str, Any]:
        return {"selector": {self.selector_type: self.config.as_dict()}}


class EntitySelector(_Selector):
    selector_type = "entity"

    def __call__(self, value: Any) -> str:
        if not isinstance(value, str) or "." not in value:
            raise Invalid("invalid entity ID")
        domains = getattr(self.config, "domain", None)
        if domains:
            domains = [domains] if isinstance(domains, str) else domains
            if value.split(".", 1)[0] not in domains:
                raise Invalid("entity domain not allowed")
        return value


class TimeSelector(_Selector):
    selector_type = "time"

    def __call__(self, value: Any) -> str:
        if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}:\d{2}", value):
            raise Invalid("invalid time")
        return value


class TextSelector(_Selector):
    selector_type = "text"

    def __call__(self, value: Any) -> str:
        if not isinstance(value, str):
            raise Invalid("expected text")
        return value


class BooleanSelector(_Selector):
    selector_type = "boolean"

    def __call__(self, value: Any) -> bool:
        if not isinstance(value, bool):
            raise Invalid("expected boolean")
        return value


class NumberSelector(_Selector):
    selector_type = "number"

    def __call__(self, value: Any) -> int | float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise Invalid("expected number")
        minimum = getattr(self.config, "min", None)
        maximum = getattr(self.config, "max", None)
        if minimum is not None and value < minimum:
            raise Invalid("number below minimum")
        if maximum is not None and value > maximum:
            raise Invalid("number above maximum")
        return value


class SelectSelector(_Selector):
    selector_type = "select"

    def __call__(self, value: Any) -> str:
        if not isinstance(value, str):
            raise Invalid("select values must be strings")
        options = getattr(self.config, "options", [])
        allowed = [item["value"] if isinstance(item, dict) else item for item in options]
        if value not in allowed:
            raise Invalid(f"not a valid option: {value}")
        return value


def _string(value: Any) -> str:
    if not isinstance(value, str):
        raise Invalid("expected string")
    return value


def _copy_schema_with_suggestions(schema: Schema, suggested: dict[str, Any]) -> Schema:
    fields: dict[_Marker, Any] = {}
    for marker, validator in schema.schema.items():
        default = suggested.get(marker.schema, marker.default)
        fields[type(marker)(marker.schema, default=default)] = validator
    return Schema(fields)


def _serialise_schema(schema: Schema) -> list[dict[str, Any]]:
    """Exercise the same compatibility boundary that failed in Home Assistant."""
    rendered: list[dict[str, Any]] = []
    for marker, validator in schema.schema.items():
        field: dict[str, Any] = {
            "name": marker.schema,
            "required": isinstance(marker, Required),
        }
        if marker.default is not _UNDEFINED:
            default = marker.default() if callable(marker.default) else marker.default
            field["default"] = validator(default) if callable(validator) else default
        if isinstance(validator, _Selector):
            field.update(validator.serialize())
        elif validator is bool:
            field["type"] = "boolean"
        elif validator is _string:
            field["type"] = "string"
        else:
            raise TypeError(
                f"Form field {marker.schema!r} uses a non-serialisable validator: "
                f"{validator!r}"
            )
        rendered.append(field)
    json.dumps(rendered)
    return rendered


class ConfigFlow:
    """Home Assistant ConfigFlow surface used by the integration."""

    def __init_subclass__(cls, *, domain: str | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.DOMAIN = domain

    def async_show_form(
        self,
        *,
        step_id: str,
        data_schema: Schema,
        errors: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        rendered = _serialise_schema(data_schema)
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "rendered": rendered,
            "errors": errors or {},
        }

    def async_create_entry(self, *, title: str, data: dict[str, Any]) -> dict[str, Any]:
        json.dumps(data)
        return {"type": "create_entry", "title": title, "data": data}


class OptionsFlow(ConfigFlow):
    def add_suggested_values_to_schema(
        self, schema: Schema, suggested_values: dict[str, Any]
    ) -> Schema:
        return _copy_schema_with_suggestions(schema, suggested_values)

    def async_show_menu(self, *, step_id: str, menu_options: list[str]) -> dict[str, Any]:
        return {"type": "menu", "step_id": step_id, "menu_options": menu_options}


@dataclass
class ConfigEntry:
    data: dict[str, Any]
    options: dict[str, Any]


def _install_compatibility_modules() -> None:
    vol = ModuleType("voluptuous")
    vol.Invalid = Invalid
    vol.Required = Required
    vol.Optional = Optional
    vol.Schema = Schema
    sys.modules["voluptuous"] = vol

    homeassistant = ModuleType("homeassistant")
    config_entries = ModuleType("homeassistant.config_entries")
    config_entries.ConfigFlow = ConfigFlow
    config_entries.OptionsFlow = OptionsFlow
    config_entries.ConfigEntry = ConfigEntry
    config_entries.ConfigFlowResult = dict[str, Any]

    helpers = ModuleType("homeassistant.helpers")
    config_validation = ModuleType("homeassistant.helpers.config_validation")
    config_validation.string = _string
    selector = ModuleType("homeassistant.helpers.selector")
    for name, value in {
        "EntitySelectorConfig": EntitySelectorConfig,
        "NumberSelectorConfig": NumberSelectorConfig,
        "SelectSelectorConfig": SelectSelectorConfig,
        "NumberSelectorMode": NumberSelectorMode,
        "SelectSelectorMode": SelectSelectorMode,
        "EntitySelector": EntitySelector,
        "TimeSelector": TimeSelector,
        "TextSelector": TextSelector,
        "BooleanSelector": BooleanSelector,
        "NumberSelector": NumberSelector,
        "SelectSelector": SelectSelector,
    }.items():
        setattr(selector, name, value)

    helpers.config_validation = config_validation
    helpers.selector = selector
    homeassistant.config_entries = config_entries
    homeassistant.helpers = helpers
    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.config_validation"] = config_validation
    sys.modules["homeassistant.helpers.selector"] = selector


def _load_flow_module():
    _install_compatibility_modules()
    package = ModuleType("jg_energy_manager")
    package.__path__ = [str(DOMAIN_DIR)]
    sys.modules["jg_energy_manager"] = package

    for module_name in ("const", "config_flow"):
        full_name = f"jg_energy_manager.{module_name}"
        spec = importlib.util.spec_from_file_location(
            full_name, DOMAIN_DIR / f"{module_name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
    return sys.modules["jg_energy_manager.config_flow"]


FLOW = _load_flow_module()


def _run(coroutine):
    return asyncio.run(coroutine)


def _submit(flow: Any, result: dict[str, Any], values: dict[str, Any]):
    assert result["type"] == "form"
    validated = result["data_schema"](values)
    return _run(getattr(flow, f"async_step_{result['step_id']}")(validated))


def _full_setup_entry() -> dict[str, Any]:
    flow = FLOW.JGEnergyConfigFlow()

    result = _run(flow.async_step_user())
    assert result["step_id"] == "user"
    result = _submit(
        flow,
        result,
        {"name": "JG Energy Manager", "initial_observe_only": True},
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
    phase_field = next(item for item in result["rendered"] if item["name"] == "phases")
    assert phase_field["default"] == "single_phase"
    assert phase_field["selector"]["select"]["options"] == [
        "single_phase",
        "three_phase",
    ]
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
    return result


def test_first_time_setup_renders_and_advances_through_every_form():
    """Energy through Secondary completes and creates a JSON-safe config entry."""
    result = _full_setup_entry()
    assert result["title"] == "JG Energy Manager"
    assert result["data"]["phases"] == 1
    assert isinstance(result["data"]["phases"], int)
    assert result["data"]["connected_states"] == "B,C"
    assert result["data"]["peak_months"] == "1,2,3,6,7,8,11,12"


def test_limits_options_flow_renders_and_stores_integer_phase_value():
    """Options Flow renders current phase safely and stores a canonical integer."""
    entry_result = _full_setup_entry()
    options_flow = FLOW.JGEnergyOptionsFlow()
    options_flow.config_entry = ConfigEntry(data=entry_result["data"], options={})

    menu = _run(options_flow.async_step_init())
    assert menu["menu_options"] == [
        "energy",
        "charger",
        "schedule",
        "limits",
        "control",
        "secondary",
    ]

    result = _run(options_flow.async_step_limits())
    phase_field = next(item for item in result["rendered"] if item["name"] == "phases")
    assert phase_field["default"] == "single_phase"

    values = result["data_schema"]({"phases": "three_phase"})
    # Required fields receive their suggested defaults, matching Home Assistant's form post.
    saved = _run(options_flow.async_step_limits(values))
    assert saved["type"] == "create_entry"
    assert saved["data"]["phases"] == 3
    assert isinstance(saved["data"]["phases"], int)


def test_every_options_form_serialises_with_current_entry_values():
    """All Options Flow destinations render without unsupported validators."""
    entry_result = _full_setup_entry()
    options_flow = FLOW.JGEnergyOptionsFlow()
    options_flow.config_entry = ConfigEntry(data=entry_result["data"], options={})

    for step in ("energy", "charger", "schedule", "limits", "control", "secondary"):
        result = _run(getattr(options_flow, f"async_step_{step}")())
        assert result["type"] == "form"
        assert result["step_id"] == step
        json.dumps(result["rendered"])
