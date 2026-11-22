"""Config and options flows for JG Energy Manager."""

from __future__ import annotations

import json
import logging
from typing import Any

import probatio
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_validation as cv, selector

from .const import *  # noqa: F403

_LOGGER = logging.getLogger(__name__)


def _checked_schema(step_id: str, schema: vol.Schema) -> vol.Schema:
    """Fail and log before Home Assistant prepares an unserialisable form result."""
    try:
        probatio.to_field_list(schema, custom_serializer=cv.custom_serializer)
    except Exception:
        validators = {
            str(getattr(marker, "schema", marker)): getattr(value, "__qualname__", type(value).__name__)
            for marker, value in schema.schema.items()
        }
        _LOGGER.exception(
            "JG Energy Manager %s schema is not serialisable; validators=%s",
            step_id,
            validators,
        )
        raise
    return schema


def _entity(domain: str | list[str] | None = None) -> selector.EntitySelector:
    config = (
        selector.EntitySelectorConfig()
        if domain is None
        else selector.EntitySelectorConfig(domain=domain)
    )
    return selector.EntitySelector(config)


def _time() -> selector.TimeSelector:
    return selector.TimeSelector()


def _text() -> selector.TextSelector:
    return selector.TextSelector()


def _boolean() -> selector.BooleanSelector:
    return selector.BooleanSelector()


def _normalise_month_list(value: Any) -> str:
    text = cv.string(value)
    try:
        months = {int(item.strip()) for item in text.split(",") if item.strip()}
    except ValueError as err:
        raise vol.Invalid("Use comma-separated month numbers from 1 to 12") from err
    if not months or any(month < 1 or month > 12 for month in months):
        raise vol.Invalid("Use comma-separated month numbers from 1 to 12")
    return ",".join(str(month) for month in sorted(months))


def _connected_states(value: Any) -> str:
    """Normalise a text value, or a selector list, to comma-separated states."""
    values = value if isinstance(value, (list, tuple, set)) else cv.string(value).split(",")
    states: list[str] = []
    seen: set[str] = set()
    for item in values:
        state = cv.string(item).strip()
        folded = state.casefold()
        if state and folded not in seen:
            states.append(state)
            seen.add(folded)
    if not states:
        raise vol.Invalid("Enter at least one connected state")
    return ",".join(states)


def _charging_states(value: Any) -> str:
    """Normalise charger states that positively confirm active charging."""
    try:
        return _connected_states(value)
    except vol.Invalid as err:
        raise vol.Invalid("Enter at least one charging state") from err


def _number(minimum: float, maximum: float, step: float, unit: str | None = None):
    config: dict[str, Any] = {
        "min": minimum,
        "max": maximum,
        "step": step,
        "mode": selector.NumberSelectorMode.BOX,
    }
    if unit is not None:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(
        selector.NumberSelectorConfig(**config)
    )


def _limits_form_values(defaults: dict[str, Any]) -> dict[str, Any]:
    """Return Limits defaults in the types expected by Home Assistant selectors."""
    stored = defaults[CONF_PHASES]  # noqa: F405
    if stored in (PHASE_OPTION_SINGLE, PHASE_OPTION_THREE):  # noqa: F405
        selected = stored
    else:
        selected = PHASE_OPTION_THREE if int(stored) == 3 else PHASE_OPTION_SINGLE  # noqa: F405
    return {
        **defaults,
        CONF_PHASES: selected,  # noqa: F405
    }


def _limits_storage_values(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return submitted Limits values in their canonical storage types."""
    selected = user_input[CONF_PHASES]  # noqa: F405
    phase_map = {
        PHASE_OPTION_SINGLE: 1,  # noqa: F405
        PHASE_OPTION_THREE: 3,  # noqa: F405
        "1": 1,
        "3": 3,
        1: 1,
        3: 3,
    }
    if selected not in phase_map:
        raise vol.Invalid("Select either single-phase or three-phase charging")
    return {**user_input, CONF_PHASES: phase_map[selected]}  # noqa: F405


def _secondary_storage_values(user_input: dict[str, Any]) -> dict[str, Any]:
    """Clear dormant second-charger mappings whenever the feature is disabled."""
    values = dict(user_input)
    if not values.get(CONF_SECONDARY_ENABLED):  # noqa: F405
        values[CONF_SECONDARY_SWITCH_ENTITY] = None  # noqa: F405
        values[CONF_SECONDARY_STATUS_ENTITY] = None  # noqa: F405
        values[CONF_SECONDARY_POWER_ENTITY] = None  # noqa: F405
    return values


def _energy_schema(defaults: dict[str, Any]) -> vol.Schema:
    return _checked_schema("energy", vol.Schema(
        {
            vol.Required(CONF_BATTERY_SOC_ENTITY): _entity("sensor"),  # noqa: F405
            vol.Optional(CONF_BATTERY_POWER_ENTITY): _entity("sensor"),  # noqa: F405
            vol.Required(  # noqa: F405
                CONF_BATTERY_POWER_SIGN,
                default=defaults[CONF_BATTERY_POWER_SIGN],  # noqa: F405
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[BATTERY_POSITIVE_DISCHARGE, BATTERY_POSITIVE_CHARGE],  # noqa: F405
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="battery_power_sign",
                )
            ),
            vol.Required(CONF_GRID_POWER_ENTITY): _entity("sensor"),  # noqa: F405
            vol.Required(  # noqa: F405
                CONF_GRID_POWER_SIGN, default=defaults[CONF_GRID_POWER_SIGN]  # noqa: F405
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[GRID_POSITIVE_IMPORT, GRID_NEGATIVE_IMPORT],  # noqa: F405
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="grid_power_sign",
                )
            ),
            vol.Required(CONF_SOLAR_POWER_ENTITY): _entity("sensor"),  # noqa: F405
        }
    ))


def _charger_schema(defaults: dict[str, Any]) -> vol.Schema:
    return _checked_schema("charger", vol.Schema(
        {
            # Some third-party charger integrations expose otherwise compatible
            # controls through non-standard entity platforms.  Restricting the
            # entity selector by domain makes Home Assistant 2026.11 reject those
            # selections in the browser before this flow receives the values.
            # Keep these pickers intentionally unfiltered and validate behaviour
            # at runtime from the selected entities' states and services.
            vol.Required(CONF_CHARGER_STATUS_ENTITY): _entity(),  # noqa: F405
            vol.Required(CONF_CHARGER_POWER_ENTITY): _entity(),  # noqa: F405
            vol.Required(CONF_CHARGER_ENERGY_ENTITY): _entity(),  # noqa: F405
            vol.Required(CONF_CHARGER_ENABLE_ENTITY): _entity(),  # noqa: F405
            vol.Required(CONF_CHARGER_CURRENT_ENTITY): _entity(),  # noqa: F405
            vol.Required(  # noqa: F405
                CONF_CONNECTED_STATES, default=defaults[CONF_CONNECTED_STATES]  # noqa: F405
            ): selector.TextSelector(),
            vol.Required(  # noqa: F405
                CONF_CHARGING_STATES, default=defaults[CONF_CHARGING_STATES]  # noqa: F405
            ): selector.TextSelector(),
        }
    ))


def _schedule_schema(defaults: dict[str, Any]) -> vol.Schema:
    return _checked_schema("schedule", vol.Schema(
        {
            vol.Required(CONF_TARGET_ENERGY_KWH, default=defaults[CONF_TARGET_ENERGY_KWH]): _number(0.5, 100, 0.5, "kWh"),  # noqa: E501,F405
            vol.Required(CONF_READY_BY, default=defaults[CONF_READY_BY]): _time(),  # noqa: F405
            vol.Required(CONF_COMPLETION_BUFFER_MIN, default=defaults[CONF_COMPLETION_BUFFER_MIN]): _number(0, 180, 5, "min"),  # noqa: E501,F405
            vol.Required(CONF_OVERNIGHT_START, default=defaults[CONF_OVERNIGHT_START]): _time(),  # noqa: E501,F405
            vol.Required(CONF_PEAK_START, default=defaults[CONF_PEAK_START]): _time(),  # noqa: F405
            vol.Required(CONF_PEAK_END, default=defaults[CONF_PEAK_END]): _time(),  # noqa: F405
            # Custom callables cannot be serialised as Home Assistant form
            # selectors. Normalise and validate this text in the step handler.
            vol.Required(CONF_PEAK_MONTHS, default=defaults[CONF_PEAK_MONTHS]): selector.TextSelector(),  # noqa: E501,F405
            vol.Required(CONF_OVERNIGHT_BATTERY_FLOOR, default=defaults[CONF_OVERNIGHT_BATTERY_FLOOR]): _number(0, 100, 1, "%"),  # noqa: E501,F405
            vol.Required(CONF_DAYTIME_BATTERY_RESERVE, default=defaults[CONF_DAYTIME_BATTERY_RESERVE]): _number(0, 100, 1, "%"),  # noqa: E501,F405
            vol.Required(CONF_SOC_HYSTERESIS, default=defaults[CONF_SOC_HYSTERESIS]): _number(0, 20, 0.5, "%"),  # noqa: E501,F405
        }
    ))


def _limits_schema(defaults: dict[str, Any]) -> vol.Schema:
    try:
        required_defaults = (
            CONF_MIN_CURRENT_A,  # noqa: F405
            CONF_MAX_CURRENT_A,  # noqa: F405
            CONF_MAX_CHARGER_POWER_W,  # noqa: F405
            CONF_BATTERY_MAX_CHARGE_POWER_W,  # noqa: F405
            CONF_GRID_TOLERANCE_W,  # noqa: F405
            CONF_CURRENT_STEP_A,  # noqa: F405
            CONF_RAMP_UP_STEP_A,  # noqa: F405
            CONF_FORCE_CHARGE_CURRENT_A,  # noqa: F405
            CONF_SUPPLY_VOLTAGE,  # noqa: F405
            CONF_PHASES,  # noqa: F405
            CONF_CHARGING_EFFICIENCY,  # noqa: F405
            CONF_SOLAR_START_MARGIN_W,  # noqa: F405
            CONF_SOLAR_RUN_MARGIN_W,  # noqa: F405
            CONF_IDLE_POWER_W,  # noqa: F405
        )
        missing = [key for key in required_defaults if key not in defaults]
        if missing:
            raise KeyError(f"Missing Limits defaults: {', '.join(missing)}")
        json.dumps({key: defaults[key] for key in required_defaults})
        defaults = _limits_form_values(defaults)
        return _checked_schema("limits", vol.Schema({
            vol.Required(CONF_MIN_CURRENT_A, default=defaults[CONF_MIN_CURRENT_A]): _number(1, 32, 0.1, "A"),  # noqa: E501,F405
            vol.Required(CONF_MAX_CURRENT_A, default=defaults[CONF_MAX_CURRENT_A]): _number(1, 80, 0.1, "A"),  # noqa: E501,F405
            vol.Required(CONF_MAX_CHARGER_POWER_W, default=defaults[CONF_MAX_CHARGER_POWER_W]): _number(500, 22000, 100, "W"),  # noqa: E501,F405
            vol.Required(CONF_BATTERY_MAX_CHARGE_POWER_W, default=defaults[CONF_BATTERY_MAX_CHARGE_POWER_W]): _number(0, 20000, 100, "W"),  # noqa: E501,F405
            vol.Required(CONF_GRID_TOLERANCE_W, default=defaults[CONF_GRID_TOLERANCE_W]): _number(0, 2000, 10, "W"),  # noqa: E501,F405
            vol.Required(CONF_CURRENT_STEP_A, default=defaults[CONF_CURRENT_STEP_A]): _number(0.1, 5, 0.1, "A"),  # noqa: E501,F405
            vol.Required(CONF_RAMP_UP_STEP_A, default=defaults[CONF_RAMP_UP_STEP_A]): _number(0.1, 10, 0.1, "A"),  # noqa: E501,F405
            vol.Required(CONF_FORCE_CHARGE_CURRENT_A, default=defaults[CONF_FORCE_CHARGE_CURRENT_A]): _number(1, 80, 0.1, "A"),  # noqa: E501,F405
            vol.Required(CONF_SUPPLY_VOLTAGE, default=defaults[CONF_SUPPLY_VOLTAGE]): _number(100, 260, 1, "V"),  # noqa: E501,F405
            vol.Required(CONF_PHASES, default=defaults[CONF_PHASES]): selector.SelectSelector(  # noqa: F405
                selector.SelectSelectorConfig(
                    options=[PHASE_OPTION_SINGLE, PHASE_OPTION_THREE],  # noqa: F405
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="charging_phases",
                )
            ),
            vol.Required(CONF_CHARGING_EFFICIENCY, default=defaults[CONF_CHARGING_EFFICIENCY]): _number(0.5, 1.0, 0.01),  # noqa: E501,F405
            vol.Required(CONF_SOLAR_START_MARGIN_W, default=defaults[CONF_SOLAR_START_MARGIN_W]): _number(0, 5000, 50, "W"),  # noqa: E501,F405
            vol.Required(CONF_SOLAR_RUN_MARGIN_W, default=defaults[CONF_SOLAR_RUN_MARGIN_W]): _number(0, 5000, 50, "W"),  # noqa: E501,F405
            vol.Required(CONF_IDLE_POWER_W, default=defaults[CONF_IDLE_POWER_W]): _number(0, 2000, 50, "W"),  # noqa: E501,F405
        }))
    except Exception:
        _LOGGER.exception(
            "Failed to build JG Energy Manager Limits schema; keys=%s",
            sorted(defaults),
        )
        raise


def _control_schema(defaults: dict[str, Any]) -> vol.Schema:
    return _checked_schema("control", vol.Schema(
        {
            vol.Required(CONF_CONTROL_INTERVAL_S, default=defaults[CONF_CONTROL_INTERVAL_S]): _number(10, 300, 5, "s"),  # noqa: E501,F405
            vol.Required(CONF_NO_DEMAND_TIMEOUT_S, default=defaults[CONF_NO_DEMAND_TIMEOUT_S]): _number(30, 1800, 30, "s"),  # noqa: E501,F405
            vol.Required(CONF_COMMAND_DEADBAND_A, default=defaults[CONF_COMMAND_DEADBAND_A]): _number(0, 5, 0.1, "A"),  # noqa: E501,F405
            vol.Required(CONF_MIN_COMMAND_INTERVAL_S, default=defaults[CONF_MIN_COMMAND_INTERVAL_S]): _number(5, 300, 5, "s"),  # noqa: E501,F405
            vol.Required(CONF_INCREASE_DWELL_S, default=defaults[CONF_INCREASE_DWELL_S]): _number(0, 900, 5, "s"),  # noqa: E501,F405
            vol.Required(CONF_DECREASE_DWELL_S, default=defaults[CONF_DECREASE_DWELL_S]): _number(0, 300, 5, "s"),  # noqa: E501,F405
            vol.Required(CONF_STOP_WHEN_DISABLED, default=defaults[CONF_STOP_WHEN_DISABLED]): _boolean(),  # noqa: F405
            vol.Required(CONF_FAIL_SAFE_STOP, default=defaults[CONF_FAIL_SAFE_STOP]): _boolean(),  # noqa: F405
            vol.Required(CONF_INITIAL_OBSERVE_ONLY, default=defaults[CONF_INITIAL_OBSERVE_ONLY]): _boolean(),  # noqa: F405
        }
    ))


def _secondary_schema(defaults: dict[str, Any]) -> vol.Schema:
    return _checked_schema("secondary", vol.Schema(
        {
            vol.Required(CONF_SECONDARY_ENABLED, default=defaults.get(CONF_SECONDARY_ENABLED, False)): _boolean(),  # noqa: E501,F405
            vol.Required(CONF_SECONDARY_NAME, default=defaults.get(CONF_SECONDARY_NAME, "Charger 2")): _text(),  # noqa: E501,F405
            vol.Optional(CONF_SECONDARY_SWITCH_ENTITY): _entity(["switch", "input_boolean"]),  # noqa: E501,F405
            vol.Optional(CONF_SECONDARY_STATUS_ENTITY): _entity(["sensor", "binary_sensor"]),  # noqa: E501,F405
            vol.Optional(CONF_SECONDARY_POWER_ENTITY): _entity("sensor"),  # noqa: F405
        }
    ))


class JGEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # noqa: F405
    """Configure a JG Energy Manager instance."""

    VERSION = 2

    def __init__(self) -> None:
        self._data: dict[str, Any] = dict(DEFAULTS)  # noqa: F405
        _LOGGER.warning(
            "Loaded JG Energy Manager config flow %s from %s",
            VERSION,  # noqa: F405
            __file__,
        )

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_energy()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULTS[CONF_NAME]): _text(),  # noqa: F405
                    vol.Required(CONF_INITIAL_OBSERVE_ONLY, default=True): _boolean(),  # noqa: F405
                }
            ),
        )

    async def async_step_energy(self, user_input=None) -> ConfigFlowResult:
        return await self._next("energy", user_input, _energy_schema(self._data), self.async_step_charger)

    async def async_step_charger(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            user_input = dict(user_input)
            try:
                user_input[CONF_CONNECTED_STATES] = _connected_states(  # noqa: F405
                    user_input[CONF_CONNECTED_STATES]  # noqa: F405
                )
                user_input[CONF_CHARGING_STATES] = _charging_states(  # noqa: F405
                    user_input[CONF_CHARGING_STATES]  # noqa: F405
                )
            except vol.Invalid:
                values = {**self._data, **user_input}
                return self.async_show_form(
                    step_id="charger",
                    data_schema=_charger_schema(values),
                    errors={"base": "invalid_charger_states"},
                )
        return await self._next("charger", user_input, _charger_schema(self._data), self.async_step_schedule)

    async def async_step_schedule(self, user_input=None) -> ConfigFlowResult:
        try:
            if user_input is not None:
                user_input = dict(user_input)
                try:
                    user_input[CONF_PEAK_MONTHS] = _normalise_month_list(  # noqa: F405
                        user_input[CONF_PEAK_MONTHS]  # noqa: F405
                    )
                except vol.Invalid:
                    values = {**self._data, **user_input}
                    return self.async_show_form(
                        step_id="schedule",
                        data_schema=_schedule_schema(values),
                        errors={CONF_PEAK_MONTHS: "invalid_month_list"},  # noqa: F405
                    )
            return await self._next("schedule", user_input, _schedule_schema(self._data), self.async_step_limits)
        except Exception:
            _LOGGER.exception("JG Energy Manager failed in async_step_schedule")
            raise

    async def async_step_limits(self, user_input=None) -> ConfigFlowResult:
        try:
            if user_input is not None:
                try:
                    user_input = _limits_storage_values(user_input)
                except vol.Invalid:
                    return self.async_show_form(
                        step_id="limits",
                        data_schema=_limits_schema(self._data),
                        errors={CONF_PHASES: "invalid_phases"},  # noqa: F405
                    )
            return await self._next("limits", user_input, _limits_schema(self._data), self.async_step_control)
        except Exception:
            _LOGGER.exception("JG Energy Manager failed in async_step_limits")
            raise

    async def async_step_control(self, user_input=None) -> ConfigFlowResult:
        return await self._next("control", user_input, _control_schema(self._data), self.async_step_secondary)

    async def async_step_secondary(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            user_input = _secondary_storage_values(user_input)
            self._data.update(user_input)
            if self._data[CONF_SECONDARY_ENABLED] and not self._data.get(CONF_SECONDARY_SWITCH_ENTITY):  # noqa: E501,F405
                return self.async_show_form(
                    step_id="secondary",
                    data_schema=_secondary_schema(self._data),
                    errors={"base": "secondary_switch_required"},
                )
            return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)  # noqa: F405
        return self.async_show_form(step_id="secondary", data_schema=_secondary_schema(self._data))

    async def _next(self, step_id, user_input, schema, next_step):
        try:
            if user_input is not None:
                self._data.update(user_input)
                _LOGGER.debug(
                    "JG Energy Manager advancing from %s to %s",
                    step_id,
                    next_step.__name__,
                )
                return await next_step()
            return self.async_show_form(step_id=step_id, data_schema=schema)
        except Exception:
            _LOGGER.exception(
                "JG Energy Manager failed while handling transition from %s to %s",
                step_id,
                next_step.__name__,
            )
            raise

    @staticmethod
    def async_get_options_flow(config_entry):
        return JGEnergyOptionsFlow()


class JGEnergyOptionsFlow(config_entries.OptionsFlow):
    """Edit every mapping and logic parameter from the Home Assistant UI."""

    @property
    def current(self) -> dict[str, Any]:
        current = {
            **DEFAULTS,  # noqa: F405
            **self.config_entry.data,
            **self.config_entry.options,
        }
        if not current.get(CONF_SECONDARY_ENABLED):  # noqa: F405
            current.pop(CONF_SECONDARY_SWITCH_ENTITY, None)  # noqa: F405
            current.pop(CONF_SECONDARY_STATUS_ENTITY, None)  # noqa: F405
            current.pop(CONF_SECONDARY_POWER_ENTITY, None)  # noqa: F405
        return current

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["energy", "charger", "schedule", "limits", "control", "secondary"],
        )

    async def _save_step(self, step_id: str, user_input, schema) -> ConfigFlowResult:
        if user_input is not None:
            updated = dict(self.config_entry.options)
            updated.update(user_input)
            return self.async_create_entry(title="", data=updated)
        suggested = self.add_suggested_values_to_schema(schema, self.current)
        return self.async_show_form(step_id=step_id, data_schema=suggested)

    async def async_step_energy(self, user_input=None) -> ConfigFlowResult:
        return await self._save_step("energy", user_input, _energy_schema(self.current))

    async def async_step_charger(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            user_input = dict(user_input)
            try:
                user_input[CONF_CONNECTED_STATES] = _connected_states(  # noqa: F405
                    user_input[CONF_CONNECTED_STATES]  # noqa: F405
                )
                user_input[CONF_CHARGING_STATES] = _charging_states(  # noqa: F405
                    user_input[CONF_CHARGING_STATES]  # noqa: F405
                )
            except vol.Invalid:
                values = {**self.current, **user_input}
                return self.async_show_form(
                    step_id="charger",
                    data_schema=self.add_suggested_values_to_schema(
                        _charger_schema(values), values
                    ),
                    errors={"base": "invalid_charger_states"},
                )
        return await self._save_step("charger", user_input, _charger_schema(self.current))

    async def async_step_schedule(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            user_input = dict(user_input)
            try:
                user_input[CONF_PEAK_MONTHS] = _normalise_month_list(  # noqa: F405
                    user_input[CONF_PEAK_MONTHS]  # noqa: F405
                )
            except vol.Invalid:
                values = {**self.current, **user_input}
                return self.async_show_form(
                    step_id="schedule",
                    data_schema=self.add_suggested_values_to_schema(
                        _schedule_schema(values), values
                    ),
                    errors={CONF_PEAK_MONTHS: "invalid_month_list"},  # noqa: F405
                )
        return await self._save_step("schedule", user_input, _schedule_schema(self.current))

    async def async_step_limits(self, user_input=None) -> ConfigFlowResult:
        current = _limits_form_values(self.current)
        if user_input is not None:
            try:
                user_input = _limits_storage_values(user_input)
            except vol.Invalid:
                return self.async_show_form(
                    step_id="limits",
                    data_schema=self.add_suggested_values_to_schema(
                        _limits_schema(current), current
                    ),
                    errors={CONF_PHASES: "invalid_phases"},  # noqa: F405
                )
            return await self._save_step("limits", user_input, _limits_schema(current))
        suggested = self.add_suggested_values_to_schema(
            _limits_schema(current), current
        )
        return self.async_show_form(step_id="limits", data_schema=suggested)

    async def async_step_control(self, user_input=None) -> ConfigFlowResult:
        return await self._save_step("control", user_input, _control_schema(self.current))

    async def async_step_secondary(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None and user_input.get(CONF_SECONDARY_ENABLED) and not user_input.get(CONF_SECONDARY_SWITCH_ENTITY):  # noqa: E501,F405
            return self.async_show_form(
                step_id="secondary",
                data_schema=self.add_suggested_values_to_schema(_secondary_schema(self.current), user_input),
                errors={"base": "secondary_switch_required"},
            )
        if user_input is not None:
            user_input = _secondary_storage_values(user_input)
        return await self._save_step("secondary", user_input, _secondary_schema(self.current))
