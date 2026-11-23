"""Diagnostics support for JG Energy Manager."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

TO_REDACT = {
    "battery_soc_entity",
    "battery_power_entity",
    "grid_power_entity",
    "solar_power_entity",
    "charger_status_entity",
    "charger_power_entity",
    "charger_energy_entity",
    "charger_enable_entity",
    "charger_current_entity",
    "secondary_switch_entity",
    "secondary_status_entity",
    "secondary_power_entity",
}


def _rounded(value, digits=3):
    return None if value is None else round(float(value), digits)


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    coordinator = entry.runtime_data
    decision = coordinator.data["decision"]
    runtime = coordinator.runtime
    # Effective config includes defaults, entry data and options. Entity IDs stay
    # redacted; non-identifying calculated energy deltas remain available.
    effective = async_redact_data(dict(coordinator.settings), TO_REDACT)
    runtime_data = runtime.as_dict()
    runtime_data["energy_baseline_kwh"] = "redacted"
    runtime_data["last_energy_total_kwh"] = "redacted"
    for key in (
        "integrated_energy_kwh",
        "counter_delta_kwh",
        "session_energy_kwh",
        "satisfied_energy_kwh",
        "last_session_energy_kwh",
        "last_session_unused_allowance_kwh",
    ):
        runtime_data[key] = _rounded(runtime_data.get(key))

    return {
        "effective_config": effective,
        "stored_config": async_redact_data(dict(entry.data), TO_REDACT),
        "options": async_redact_data(dict(entry.options), TO_REDACT),
        "runtime": runtime_data,
        "decision": {
            "state": decision.state,
            "reason": decision.reason,
            "should_enable": decision.should_enable,
            "requested_current_a": round(decision.requested_current_a, 1),
            "requested_power_w": round(decision.requested_power_w),
            "energy_remaining_kwh": round(decision.energy_remaining_kwh, 3),
            "required_average_power_w": round(decision.required_average_power_w),
            "available_solar_power_w": round(decision.available_solar_power_w),
            "policy_solar_power_w": round(decision.policy_solar_power_w),
            "projected_completion": decision.projected_completion,
            "deadline": decision.deadline,
        },
        "inputs": {
            "input_health": coordinator.data["inputs_valid"],
            "connected": coordinator.data["connected"],
            "charging": coordinator.data["charging"],
            "charger_status": coordinator.data["charger_status"],
            "charger_enable_switch_state": coordinator.data["charger_enabled"],
            "physical_charging": coordinator.data["physical_charging"],
            "charger_power_w": _rounded(coordinator.data["charger_power_w"], 0),
            "charger_current_a": _rounded(coordinator.data["charger_current_a"], 1),
            "grid_import_w": _rounded(coordinator.data["grid_import_w"], 0),
            "battery_discharge_w": _rounded(coordinator.data["battery_discharge_w"], 0),
            "battery_soc": _rounded(coordinator.data["battery_soc"], 1),
            "solar_power_w": _rounded(coordinator.data["solar_power_w"], 0),
        },
        "actuator": coordinator.actuator.as_dict(),
        "secondary": coordinator.data["secondary"],
    }
