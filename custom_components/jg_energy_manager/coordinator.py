"""Home Assistant coordinator and actuator boundary."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    BATTERY_POSITIVE_CHARGE,
    CONF_BATTERY_POWER_ENTITY,
    CONF_BATTERY_MAX_CHARGE_POWER_W,
    CONF_BATTERY_POWER_SIGN,
    CONF_BATTERY_SOC_ENTITY,
    CONF_CHARGER_CURRENT_ENTITY,
    CONF_CHARGER_ENABLE_ENTITY,
    CONF_CHARGER_ENERGY_ENTITY,
    CONF_CHARGER_POWER_ENTITY,
    CONF_CHARGER_STATUS_ENTITY,
    CONF_CHARGING_EFFICIENCY,
    CONF_COMPLETION_BUFFER_MIN,
    CONF_COMMAND_DEADBAND_A,
    CONF_CONNECTED_STATES,
    CONF_CONTROL_INTERVAL_S,
    CONF_CURRENT_STEP_A,
    CONF_DECREASE_DWELL_S,
    CONF_DAYTIME_BATTERY_RESERVE,
    CONF_FAIL_SAFE_STOP,
    CONF_FORCE_CHARGE_CURRENT_A,
    CONF_GRID_POWER_ENTITY,
    CONF_GRID_POWER_SIGN,
    CONF_GRID_TOLERANCE_W,
    CONF_IDLE_POWER_W,
    CONF_INITIAL_OBSERVE_ONLY,
    CONF_INCREASE_DWELL_S,
    CONF_MAX_CURRENT_A,
    CONF_MAX_CHARGER_POWER_W,
    CONF_MIN_COMMAND_INTERVAL_S,
    CONF_MIN_CURRENT_A,
    CONF_NAME,
    CONF_NO_DEMAND_TIMEOUT_S,
    CONF_OVERNIGHT_BATTERY_FLOOR,
    CONF_OVERNIGHT_START,
    CONF_PEAK_END,
    CONF_PEAK_MONTHS,
    CONF_PEAK_START,
    CONF_PHASES,
    CONF_RAMP_UP_STEP_A,
    CONF_READY_BY,
    CONF_SECONDARY_ENABLED,
    CONF_SECONDARY_NAME,
    CONF_SECONDARY_POWER_ENTITY,
    CONF_SECONDARY_STATUS_ENTITY,
    CONF_SECONDARY_SWITCH_ENTITY,
    CONF_SOC_HYSTERESIS,
    CONF_SOLAR_POWER_ENTITY,
    CONF_SOLAR_RUN_MARGIN_W,
    CONF_SOLAR_START_MARGIN_W,
    CONF_STOP_WHEN_DISABLED,
    CONF_SUPPLY_VOLTAGE,
    CONF_TARGET_ENERGY_KWH,
    DEFAULTS,
    DOMAIN,
    GRID_NEGATIVE_IMPORT,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
)
from .planner import (
    ControllerState,
    Decision,
    PlannerInputs,
    PlannerSettings,
    calculate_decision,
)
from .runtime import RuntimeState

_LOGGER = logging.getLogger(__name__)


def _parse_time(value: str):
    return datetime.strptime(value[:8], "%H:%M:%S").time()


def _csv_states(value: str) -> set[str]:
    return {item.strip().casefold() for item in value.split(",") if item.strip()}


def _float_state(state: State | None) -> float | None:
    if state is None or state.state in {"unknown", "unavailable", "none", ""}:
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


class JGEnergyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Read input entities, run the planner and apply bounded commands."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.config_entry = entry
        self.settings = {**DEFAULTS, **entry.data, **entry.options}
        self.name = self.settings[CONF_NAME]
        interval = int(self.settings[CONF_CONTROL_INTERVAL_S])
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=interval),
            always_update=True,
        )
        self.store = Store[dict[str, Any]](
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{entry.entry_id}"
        )
        self.runtime = RuntimeState(
            observe_only=bool(self.settings[CONF_INITIAL_OBSERVE_ONLY])
        )
        self._last_decision: Decision | None = None
        self._last_command_at: datetime | None = None
        self._last_saved_at: datetime | None = None
        self._last_written_current: float | None = None
        self._last_increase_at: datetime | None = None
        self._last_decrease_at: datetime | None = None

    async def async_load_runtime(self) -> None:
        stored = await self.store.async_load()
        self.runtime = RuntimeState.from_dict(
            stored, observe_only=bool(self.settings[CONF_INITIAL_OBSERVE_ONLY])
        )

    async def async_shutdown(self) -> None:
        await self.store.async_save(self.runtime.as_dict())

    def planner_settings(self) -> PlannerSettings:
        s = self.settings
        return PlannerSettings(
            target_energy_kwh=float(s[CONF_TARGET_ENERGY_KWH]),
            ready_by=_parse_time(s[CONF_READY_BY]),
            completion_buffer_min=int(s[CONF_COMPLETION_BUFFER_MIN]),
            overnight_start=_parse_time(s[CONF_OVERNIGHT_START]),
            peak_start=_parse_time(s[CONF_PEAK_START]),
            peak_end=_parse_time(s[CONF_PEAK_END]),
            peak_months=frozenset(
                int(month.strip())
                for month in str(s[CONF_PEAK_MONTHS]).split(",")
                if month.strip()
            ),
            overnight_battery_floor=float(s[CONF_OVERNIGHT_BATTERY_FLOOR]),
            daytime_battery_reserve=float(s[CONF_DAYTIME_BATTERY_RESERVE]),
            soc_hysteresis=float(s[CONF_SOC_HYSTERESIS]),
            min_current_a=float(s[CONF_MIN_CURRENT_A]),
            max_current_a=float(s[CONF_MAX_CURRENT_A]),
            max_charger_power_w=float(s[CONF_MAX_CHARGER_POWER_W]),
            battery_max_charge_power_w=float(s[CONF_BATTERY_MAX_CHARGE_POWER_W]),
            grid_tolerance_w=float(s[CONF_GRID_TOLERANCE_W]),
            current_step_a=float(s[CONF_CURRENT_STEP_A]),
            ramp_up_step_a=float(s[CONF_RAMP_UP_STEP_A]),
            force_charge_current_a=float(s[CONF_FORCE_CHARGE_CURRENT_A]),
            supply_voltage=float(s[CONF_SUPPLY_VOLTAGE]),
            phases=int(s[CONF_PHASES]),
            charging_efficiency=float(s[CONF_CHARGING_EFFICIENCY]),
            solar_start_margin_w=float(s[CONF_SOLAR_START_MARGIN_W]),
            solar_run_margin_w=float(s[CONF_SOLAR_RUN_MARGIN_W]),
            control_interval_s=int(s[CONF_CONTROL_INTERVAL_S]),
        )

    def _state(self, key: str) -> State | None:
        entity_id = self.settings.get(key)
        return self.hass.states.get(entity_id) if entity_id else None

    async def _async_update_data(self) -> dict[str, Any]:
        now = dt_util.now()
        battery_soc = _float_state(self._state(CONF_BATTERY_SOC_ENTITY))
        grid_raw = _float_state(self._state(CONF_GRID_POWER_ENTITY))
        solar_power = _float_state(self._state(CONF_SOLAR_POWER_ENTITY))
        battery_power_raw = _float_state(self._state(CONF_BATTERY_POWER_ENTITY))
        charger_power = _float_state(self._state(CONF_CHARGER_POWER_ENTITY))
        energy_total = _float_state(self._state(CONF_CHARGER_ENERGY_ENTITY))
        status_state = self._state(CONF_CHARGER_STATUS_ENTITY)
        enable_state = self._state(CONF_CHARGER_ENABLE_ENTITY)
        current_state = _float_state(self._state(CONF_CHARGER_CURRENT_ENTITY))

        status = status_state.state if status_state else None
        status_valid = bool(
            status is not None
            and status.casefold() not in {"unknown", "unavailable", "none", ""}
        )
        connected = (
            bool(
                status_valid
                and status.casefold()
                in _csv_states(self.settings[CONF_CONNECTED_STATES])
            )
            if status_valid
            else self.runtime.was_connected
        )
        charger_enabled = bool(enable_state and enable_state.state == STATE_ON)
        grid_import = (
            -grid_raw
            if grid_raw is not None
            and self.settings[CONF_GRID_POWER_SIGN] == GRID_NEGATIVE_IMPORT
            else grid_raw
        )
        battery_discharge = (
            -battery_power_raw
            if battery_power_raw is not None
            and self.settings[CONF_BATTERY_POWER_SIGN] == BATTERY_POSITIVE_CHARGE
            else battery_power_raw
        )

        self._update_session(
            now=now,
            connected=connected,
            charger_power_w=charger_power or 0.0,
            energy_total_kwh=energy_total,
            charger_enabled=charger_enabled,
        )

        required_values = (
            battery_soc,
            grid_import,
            solar_power,
            charger_power,
            current_state,
        )
        inputs_valid = all(value is not None for value in required_values) and status_valid and bool(
            enable_state
            and enable_state.state not in {"unknown", "unavailable", "none", ""}
        )
        decision = calculate_decision(
            PlannerInputs(
                now=now,
                controller_enabled=self.runtime.controller_enabled,
                connected=connected,
                battery_soc=battery_soc or 0.0,
                battery_power_w=battery_discharge or 0.0,
                grid_import_w=grid_import or 0.0,
                solar_power_w=solar_power or 0.0,
                charger_power_w=charger_power or 0.0,
                charger_current_a=current_state or 0.0,
                session_energy_kwh=self.runtime.session_energy_kwh,
                charger_enabled=charger_enabled,
                vehicle_satisfied=self.runtime.vehicle_satisfied,
                mode=self.runtime.override,
                inputs_valid=inputs_valid,
                increase_allowed=(
                    self._last_increase_at is None
                    or (now - self._last_increase_at).total_seconds()
                    >= float(self.settings[CONF_INCREASE_DWELL_S])
                ),
                decrease_allowed=(
                    self._last_decrease_at is None
                    or (now - self._last_decrease_at).total_seconds()
                    >= float(self.settings[CONF_DECREASE_DWELL_S])
                ),
            ),
            self.planner_settings(),
        )
        self._last_decision = decision
        await self._async_apply_decision(
            decision,
            now=now,
            charger_enabled=charger_enabled,
            current_state=current_state,
        )
        await self._async_maybe_save(now)

        secondary_configured = bool(self.settings.get(CONF_SECONDARY_ENABLED))
        secondary = {
            "configured": secondary_configured,
            "name": self.settings.get(CONF_SECONDARY_NAME),
            "switch_entity": self.settings.get(CONF_SECONDARY_SWITCH_ENTITY)
            if secondary_configured
            else None,
            "status": self._state(CONF_SECONDARY_STATUS_ENTITY).state
            if secondary_configured and self._state(CONF_SECONDARY_STATUS_ENTITY)
            else None,
            "power_w": _float_state(self._state(CONF_SECONDARY_POWER_ENTITY))
            if secondary_configured
            else None,
            "control_state": "reserved_for_future_logic",
        }
        return {
            "decision": decision,
            "battery_soc": battery_soc,
            "battery_discharge_w": battery_discharge,
            "grid_import_w": grid_import,
            "solar_power_w": solar_power,
            "charger_power_w": charger_power,
            "charger_energy_total_kwh": energy_total,
            "charger_current_a": current_state,
            "charger_status": status,
            "charger_enabled": charger_enabled,
            "connected": connected,
            "session_energy_kwh": self.runtime.session_energy_kwh,
            "observe_only": self.runtime.observe_only,
            "controller_enabled": self.runtime.controller_enabled,
            "override": self.runtime.override,
            "vehicle_satisfied": self.runtime.vehicle_satisfied,
            "inputs_valid": inputs_valid,
            "secondary": secondary,
        }

    def _update_session(
        self,
        *,
        now: datetime,
        connected: bool,
        charger_power_w: float,
        energy_total_kwh: float | None,
        charger_enabled: bool,
    ) -> None:
        rt = self.runtime
        previous_sample = RuntimeState.parse_dt(rt.last_sample_at)
        if connected and not rt.was_connected:
            rt.energy_baseline_kwh = energy_total_kwh
            rt.integrated_energy_kwh = 0.0
            rt.session_energy_kwh = 0.0
            rt.vehicle_satisfied = False
            rt.low_demand_since = None
        elif not connected and rt.was_connected:
            rt.energy_baseline_kwh = None
            rt.integrated_energy_kwh = 0.0
            rt.session_energy_kwh = 0.0
            rt.vehicle_satisfied = False
            rt.low_demand_since = None

        if connected and previous_sample is not None:
            seconds = max(0.0, min((now - previous_sample).total_seconds(), 300.0))
            rt.integrated_energy_kwh += max(0.0, charger_power_w) * seconds / 3_600_000.0

        counter_delta = None
        if (
            connected
            and energy_total_kwh is not None
            and rt.energy_baseline_kwh is not None
            and energy_total_kwh >= rt.energy_baseline_kwh
        ):
            counter_delta = energy_total_kwh - rt.energy_baseline_kwh
        rt.session_energy_kwh = max(
            rt.integrated_energy_kwh,
            counter_delta if counter_delta is not None else 0.0,
        )

        requesting_charge = bool(
            self._last_decision and self._last_decision.should_enable
        )
        idle_threshold = float(self.settings[CONF_IDLE_POWER_W])
        if (
            connected
            and charger_enabled
            and requesting_charge
            and charger_power_w < idle_threshold
        ):
            if rt.low_demand_since is None:
                rt.low_demand_since = now.isoformat()
            since = RuntimeState.parse_dt(rt.low_demand_since)
            if since and (now - since).total_seconds() >= int(
                self.settings[CONF_NO_DEMAND_TIMEOUT_S]
            ):
                rt.vehicle_satisfied = True
        else:
            rt.low_demand_since = None

        rt.was_connected = connected
        rt.last_sample_at = now.isoformat()
        rt.last_energy_total_kwh = energy_total_kwh

    async def _async_apply_decision(
        self,
        decision: Decision,
        *,
        now: datetime,
        charger_enabled: bool,
        current_state: float | None,
    ) -> None:
        if self.runtime.observe_only:
            return
        if not self.runtime.controller_enabled and not self.settings[CONF_STOP_WHEN_DISABLED]:
            return
        if decision.state is ControllerState.INPUT_ERROR and not self.settings[CONF_FAIL_SAFE_STOP]:
            return

        # Stop commands are never delayed by command-rate limiting. This keeps
        # peak entry, fail-safe input loss and Off mode fail-safe by default.
        if not decision.should_enable:
            if charger_enabled:
                await self._async_turn(self.settings[CONF_CHARGER_ENABLE_ENTITY], False)
                self._last_command_at = now
            return

        decreasing = bool(
            current_state is not None
            and decision.requested_current_a < current_state
        )
        if (
            not decreasing
            and self._last_command_at is not None
            and (now - self._last_command_at).total_seconds()
            < float(self.settings[CONF_MIN_COMMAND_INTERVAL_S])
        ):
            return

        command_sent = False
        if decision.should_enable:
            deadband = float(self.settings[CONF_COMMAND_DEADBAND_A])
            if current_state is None or abs(current_state - decision.requested_current_a) >= deadband:
                await self._async_set_number(
                    self.settings[CONF_CHARGER_CURRENT_ENTITY],
                    decision.requested_current_a,
                )
                self._last_written_current = decision.requested_current_a
                if current_state is not None and decision.requested_current_a < current_state:
                    self._last_decrease_at = now
                else:
                    self._last_increase_at = now
                command_sent = True
            if not charger_enabled:
                await self._async_turn(self.settings[CONF_CHARGER_ENABLE_ENTITY], True)
                command_sent = True
        if command_sent:
            self._last_command_at = now

    async def _async_turn(self, entity_id: str, on: bool) -> None:
        domain = entity_id.split(".", 1)[0]
        await self.hass.services.async_call(
            domain,
            "turn_on" if on else "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )

    async def _async_set_number(self, entity_id: str, value: float) -> None:
        domain = entity_id.split(".", 1)[0]
        service = "set_value"
        await self.hass.services.async_call(
            domain,
            service,
            {"entity_id": entity_id, "value": value},
            blocking=True,
        )

    async def _async_maybe_save(self, now: datetime) -> None:
        if self._last_saved_at is None or (now - self._last_saved_at).total_seconds() >= 300:
            await self.store.async_save(self.runtime.as_dict())
            self._last_saved_at = now

    async def async_set_controller_enabled(self, value: bool) -> None:
        self.runtime.controller_enabled = value
        await self.store.async_save(self.runtime.as_dict())
        await self.async_request_refresh()

    async def async_set_observe_only(self, value: bool) -> None:
        self.runtime.observe_only = value
        await self.store.async_save(self.runtime.as_dict())
        await self.async_request_refresh()

    async def async_set_override(self, value: str) -> None:
        self.runtime.override = value
        await self.store.async_save(self.runtime.as_dict())
        await self.async_request_refresh()

    async def async_reset_session(self) -> None:
        total = _float_state(self._state(CONF_CHARGER_ENERGY_ENTITY))
        self.runtime.energy_baseline_kwh = total
        self.runtime.integrated_energy_kwh = 0.0
        self.runtime.session_energy_kwh = 0.0
        self.runtime.vehicle_satisfied = False
        self.runtime.low_demand_since = None
        await self.store.async_save(self.runtime.as_dict())
        await self.async_request_refresh()
