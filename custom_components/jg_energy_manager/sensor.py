"""Diagnostic sensors for JG Energy Manager."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import JGEnergyCoordinator
from .entity import JGEnergyEntity


@dataclass(frozen=True, kw_only=True)
class JGSensorDescription(SensorEntityDescription):
    value_fn: Callable[[JGEnergyCoordinator], Any]


def _decision_value(attribute: str):
    return lambda coordinator: getattr(coordinator.data["decision"], attribute)


SENSORS = (
    JGSensorDescription(key="controller_state", translation_key="controller_state", value_fn=_decision_value("state")),
    JGSensorDescription(key="controller_reason", translation_key="controller_reason", icon="mdi:text-box-outline", value_fn=_decision_value("reason")),
    JGSensorDescription(key="requested_current", translation_key="requested_current", native_unit_of_measurement=UnitOfElectricCurrent.AMPERE, state_class=SensorStateClass.MEASUREMENT, device_class=SensorDeviceClass.CURRENT, suggested_display_precision=1, value_fn=_decision_value("requested_current_a")),
    JGSensorDescription(key="requested_power", translation_key="requested_power", native_unit_of_measurement=UnitOfPower.WATT, state_class=SensorStateClass.MEASUREMENT, device_class=SensorDeviceClass.POWER, suggested_display_precision=0, value_fn=_decision_value("requested_power_w")),
    JGSensorDescription(key="required_average_power", translation_key="required_average_power", native_unit_of_measurement=UnitOfPower.WATT, state_class=SensorStateClass.MEASUREMENT, device_class=SensorDeviceClass.POWER, suggested_display_precision=0, value_fn=_decision_value("required_average_power_w")),
    JGSensorDescription(key="available_solar_power", translation_key="available_solar_power", native_unit_of_measurement=UnitOfPower.WATT, state_class=SensorStateClass.MEASUREMENT, device_class=SensorDeviceClass.POWER, suggested_display_precision=0, value_fn=_decision_value("available_solar_power_w")),
    JGSensorDescription(key="session_energy", translation_key="session_energy", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, state_class=SensorStateClass.TOTAL_INCREASING, device_class=SensorDeviceClass.ENERGY, suggested_display_precision=2, value_fn=lambda c: c.data["session_energy_kwh"]),
    JGSensorDescription(key="energy_remaining", translation_key="energy_remaining", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, state_class=SensorStateClass.MEASUREMENT, device_class=SensorDeviceClass.ENERGY, suggested_display_precision=2, value_fn=_decision_value("energy_remaining_kwh")),
    JGSensorDescription(key="projected_completion", translation_key="projected_completion", device_class=SensorDeviceClass.TIMESTAMP, value_fn=_decision_value("projected_completion")),
    JGSensorDescription(key="deadline", translation_key="deadline", device_class=SensorDeviceClass.TIMESTAMP, value_fn=_decision_value("deadline")),
    JGSensorDescription(key="secondary_charger_state", translation_key="secondary_charger_state", icon="mdi:ev-station", value_fn=lambda c: c.data["secondary"]["control_state"] if c.data["secondary"]["configured"] else "not_configured"),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(JGEnergySensor(coordinator, description) for description in SENSORS)


class JGEnergySensor(JGEnergyEntity, SensorEntity):
    entity_description: JGSensorDescription

    def __init__(self, coordinator: JGEnergyCoordinator, description: JGSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | float | datetime | None:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key != "controller_state":
            return None
        d = self.coordinator.data
        return {
            "observe_only": d["observe_only"],
            "override": d["override"],
            "connected": d["connected"],
            "charger_status": d["charger_status"],
            "charger_power_w": d["charger_power_w"],
            "grid_import_w": d["grid_import_w"],
            "battery_soc": d["battery_soc"],
            "vehicle_satisfied": d["vehicle_satisfied"],
            "inputs_valid": d["inputs_valid"],
        }
