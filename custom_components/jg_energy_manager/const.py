"""Constants for JG Energy Manager."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "jg_energy_manager"
NAME: Final = "JG Energy Manager"
VERSION: Final = "0.1.3"
PLATFORMS: Final = ["binary_sensor", "button", "select", "sensor", "switch"]

CONF_NAME: Final = "name"
CONF_BATTERY_SOC_ENTITY: Final = "battery_soc_entity"
CONF_BATTERY_POWER_ENTITY: Final = "battery_power_entity"
CONF_BATTERY_POWER_SIGN: Final = "battery_power_sign"
CONF_GRID_POWER_ENTITY: Final = "grid_power_entity"
CONF_GRID_POWER_SIGN: Final = "grid_power_sign"
CONF_SOLAR_POWER_ENTITY: Final = "solar_power_entity"
CONF_CHARGER_STATUS_ENTITY: Final = "charger_status_entity"
CONF_CHARGER_POWER_ENTITY: Final = "charger_power_entity"
CONF_CHARGER_ENERGY_ENTITY: Final = "charger_energy_entity"
CONF_CHARGER_ENABLE_ENTITY: Final = "charger_enable_entity"
CONF_CHARGER_CURRENT_ENTITY: Final = "charger_current_entity"
CONF_CONNECTED_STATES: Final = "connected_states"
CONF_CHARGING_STATES: Final = "charging_states"

CONF_TARGET_ENERGY_KWH: Final = "target_energy_kwh"
CONF_READY_BY: Final = "ready_by"
CONF_OVERNIGHT_START: Final = "overnight_start"
CONF_PEAK_START: Final = "peak_start"
CONF_PEAK_END: Final = "peak_end"
CONF_PEAK_MONTHS: Final = "peak_months"
CONF_OVERNIGHT_BATTERY_FLOOR: Final = "overnight_battery_floor"
CONF_DAYTIME_BATTERY_RESERVE: Final = "daytime_battery_reserve"
CONF_SOC_HYSTERESIS: Final = "soc_hysteresis"
CONF_MIN_CURRENT_A: Final = "min_current_a"
CONF_MAX_CURRENT_A: Final = "max_current_a"
CONF_MAX_CHARGER_POWER_W: Final = "max_charger_power_w"
CONF_CURRENT_STEP_A: Final = "current_step_a"
CONF_SUPPLY_VOLTAGE: Final = "supply_voltage"
CONF_PHASES: Final = "phases"
CONF_CHARGING_EFFICIENCY: Final = "charging_efficiency"
CONF_SOLAR_START_MARGIN_W: Final = "solar_start_margin_w"
CONF_SOLAR_RUN_MARGIN_W: Final = "solar_run_margin_w"
CONF_IDLE_POWER_W: Final = "idle_power_w"
CONF_NO_DEMAND_TIMEOUT_S: Final = "no_demand_timeout_s"
CONF_CONTROL_INTERVAL_S: Final = "control_interval_s"
CONF_COMMAND_DEADBAND_A: Final = "command_deadband_a"
CONF_MIN_COMMAND_INTERVAL_S: Final = "min_command_interval_s"
CONF_STOP_WHEN_DISABLED: Final = "stop_when_disabled"
CONF_FAIL_SAFE_STOP: Final = "fail_safe_stop"
CONF_INITIAL_OBSERVE_ONLY: Final = "initial_observe_only"

CONF_SECONDARY_ENABLED: Final = "secondary_enabled"
CONF_SECONDARY_NAME: Final = "secondary_name"
CONF_SECONDARY_SWITCH_ENTITY: Final = "secondary_switch_entity"
CONF_SECONDARY_STATUS_ENTITY: Final = "secondary_status_entity"
CONF_SECONDARY_POWER_ENTITY: Final = "secondary_power_entity"

GRID_POSITIVE_IMPORT: Final = "positive_import"
GRID_NEGATIVE_IMPORT: Final = "negative_import"
BATTERY_POSITIVE_DISCHARGE: Final = "positive_discharge"
BATTERY_POSITIVE_CHARGE: Final = "positive_charge"

OVERRIDE_AUTOMATIC: Final = "automatic"
OVERRIDE_FORCE_OFF: Final = "force_off"
OVERRIDE_FORCE_MAX: Final = "force_max"
OVERRIDE_OPTIONS: Final = [OVERRIDE_AUTOMATIC, OVERRIDE_FORCE_OFF, OVERRIDE_FORCE_MAX]

DEFAULTS: Final = {
    CONF_NAME: NAME,
    CONF_CONNECTED_STATES: "B,C",
    CONF_CHARGING_STATES: "C,charging",
    CONF_GRID_POWER_SIGN: GRID_POSITIVE_IMPORT,
    CONF_BATTERY_POWER_SIGN: BATTERY_POSITIVE_DISCHARGE,
    CONF_TARGET_ENERGY_KWH: 30.0,
    CONF_READY_BY: "06:00:00",
    CONF_OVERNIGHT_START: "21:00:00",
    CONF_PEAK_START: "15:00:00",
    CONF_PEAK_END: "21:00:00",
    CONF_PEAK_MONTHS: "1,2,3,6,7,8,11,12",
    CONF_OVERNIGHT_BATTERY_FLOOR: 10.0,
    CONF_DAYTIME_BATTERY_RESERVE: 45.0,
    CONF_SOC_HYSTERESIS: 2.0,
    CONF_MIN_CURRENT_A: 6.0,
    CONF_MAX_CURRENT_A: 32.0,
    CONF_MAX_CHARGER_POWER_W: 7360.0,
    CONF_CURRENT_STEP_A: 0.1,
    CONF_SUPPLY_VOLTAGE: 230.0,
    CONF_PHASES: "1",
    CONF_CHARGING_EFFICIENCY: 0.90,
    CONF_SOLAR_START_MARGIN_W: 400.0,
    CONF_SOLAR_RUN_MARGIN_W: 150.0,
    CONF_IDLE_POWER_W: 250.0,
    CONF_NO_DEMAND_TIMEOUT_S: 180,
    CONF_CONTROL_INTERVAL_S: 30,
    CONF_COMMAND_DEADBAND_A: 0.2,
    CONF_MIN_COMMAND_INTERVAL_S: 30,
    CONF_STOP_WHEN_DISABLED: True,
    CONF_FAIL_SAFE_STOP: True,
    CONF_INITIAL_OBSERVE_ONLY: True,
    CONF_SECONDARY_ENABLED: False,
    CONF_SECONDARY_NAME: "Charger 2",
}

STORAGE_VERSION: Final = 1
STORAGE_KEY_PREFIX: Final = f"{DOMAIN}.runtime"
