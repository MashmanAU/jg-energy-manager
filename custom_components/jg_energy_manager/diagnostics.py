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


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    coordinator = entry.runtime_data
    decision = coordinator.data["decision"]
    return {
        "config": async_redact_data(dict(entry.data), TO_REDACT),
        "options": async_redact_data(dict(entry.options), TO_REDACT),
        "runtime": {
            **coordinator.runtime.as_dict(),
            "energy_baseline_kwh": "redacted",
            "last_energy_total_kwh": "redacted",
        },
        "decision": {
            "state": decision.state,
            "reason": decision.reason,
            "should_enable": decision.should_enable,
            "requested_current_a": decision.requested_current_a,
            "requested_power_w": decision.requested_power_w,
            "energy_remaining_kwh": decision.energy_remaining_kwh,
            "required_average_power_w": decision.required_average_power_w,
            "available_solar_power_w": decision.available_solar_power_w,
            "projected_completion": decision.projected_completion,
            "deadline": decision.deadline,
        },
        "input_health": coordinator.data["inputs_valid"],
        "secondary": coordinator.data["secondary"],
    }
