"""Diagnostic and commissioning sensors for JG Energy Manager."""

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


def _rounded_decision(attribute: str, digits: int):
    return lambda c: round(float(getattr(c.data["decision"], attribute)), digits)


def _rounded_data(attribute: str, digits: int):
    return lambda c: (
        None if c.data.get(attribute) is None else round(float(c.data[attribute]), digits)
    )


def _active_session(c: JGEnergyCoordinator) -> float | None:
    return round(c.data["session_energy_kwh"], 3) if c.data["connected"] else None


def _remaining(c: JGEnergyCoordinator) -> float | None:
    return (
        round(c.data["decision"].energy_remaining_kwh, 3)
        if c.data["connected"]
        else None
    )


def _minute(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(second=0, microsecond=0)


SENSORS = (
    JGSensorDescription(key="controller_state", translation_key="controller_state", value_fn=_decision_value("state")),
    JGSensorDescription(key="controller_reason", translation_key="controller_reason", icon="mdi:text-box-outline", value_fn=_decision_value("reason")),
    JGSensorDescription(key="requested_current", translation_key="requested_current", native_unit_of_measurement=UnitOfElectricCurrent.AMPERE, state_class=SensorStateClass.MEASUREMENT, device_class=SensorDeviceClass.CURRENT, suggested_display_precision=1, value_fn=_rounded_decision("requested_current_a", 1)),
    JGSensorDescription(key="requested_power", translation_key="requested_power", native_unit_of_measurement=UnitOfPower.WATT, state_class=SensorStateClass.MEASUREMENT, device_class=SensorDeviceClass.POWER, suggested_display_precision=0, value_fn=_rounded_decision("requested_power_w", 0)),
    JGSensorDescription(key="required_average_power", translation_key="required_average_power", native_unit_of_measurement=UnitOfPower.WATT, state_class=SensorStateClass.MEASUREMENT, device_class=SensorDeviceClass.POWER, suggested_display_precision=0, value_fn=_rounded_decision("required_average_power_w", 0)),
    # Pure observation: policy margins and battery-reserve allocation only affect Calculated Power.
    JGSensorDescription(key="available_solar_power", translation_key="available_solar_power", native_unit_of_measurement=UnitOfPower.WATT, state_class=SensorStateClass.MEASUREMENT, device_class=SensorDeviceClass.POWER, suggested_display_precision=0, value_fn=_rounded_decision("available_solar_power_w", 0)),
    JGSensorDescription(key="session_energy", translation_key="session_energy", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, state_class=SensorStateClass.TOTAL_INCREASING, device_class=SensorDeviceClass.ENERGY, suggested_display_precision=3, value_fn=_active_session),
    # Migration-safe gauge: MEASUREMENT is valid because no energy device class is attached.
    JGSensorDescription(key="energy_remaining", translation_key="energy_remaining", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=3, value_fn=_remaining),
    JGSensorDescription(key="projected_completion", translation_key="projected_completion", device_class=SensorDeviceClass.TIMESTAMP, value_fn=lambda c: _minute(c.data["decision"].projected_completion)),
    JGSensorDescription(key="deadline", translation_key="deadline", device_class=SensorDeviceClass.TIMESTAMP, value_fn=lambda c: _minute(c.data["decision"].deadline)),
    JGSensorDescription(key="last_session_energy", translation_key="last_session_energy", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=3, value_fn=lambda c: None if c.runtime.last_session_energy_kwh is None else round(c.runtime.last_session_energy_kwh, 3)),
    JGSensorDescription(key="last_session_unused_allowance", translation_key="last_session_unused_allowance", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=3, value_fn=lambda c: None if c.runtime.last_session_unused_allowance_kwh is None else round(c.runtime.last_session_unused_allowance_kwh, 3)),
    JGSensorDescription(key="last_session_started", translation_key="last_session_started", device_class=SensorDeviceClass.TIMESTAMP, value_fn=lambda c: c.runtime.parse_dt(c.runtime.last_session_started_at)),
    JGSensorDescription(key="last_session_ended", translation_key="last_session_ended", device_class=SensorDeviceClass.TIMESTAMP, value_fn=lambda c: c.runtime.parse_dt(c.runtime.last_session_ended_at)),
    JGSensorDescription(key="last_session_end_reason", translation_key="last_session_end_reason", icon="mdi:flag-checkered", value_fn=lambda c: c.runtime.last_session_end_reason),
    JGSensorDescription(key="last_acknowledged_current", translation_key="last_acknowledged_current", native_unit_of_measurement=UnitOfElectricCurrent.AMPERE, state_class=SensorStateClass.MEASUREMENT, device_class=SensorDeviceClass.CURRENT, suggested_display_precision=1, value_fn=lambda c: c.data["actuator"]["last_acknowledged_current_a"]),
    JGSensorDescription(key="last_command_result", translation_key="last_command_result", icon="mdi:message-check-outline", value_fn=lambda c: c.data["actuator"]["last_command_result"]),
    JGSensorDescription(key="secondary_charger_state", translation_key="secondary_charger_state", icon="mdi:ev-station", value_fn=lambda c: c.data["secondary"]["control_state"]),
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
            "charging": d["charging"],
            "charger_status": d["charger_status"],
            "vehicle_satisfied": d["vehicle_satisfied"],
            "session_energy_source": self.coordinator.runtime.session_energy_source,
            "inputs_valid": d["inputs_valid"],
            "input_missing_roles": d["input_missing_roles"],
            "input_invalid_roles": d["input_invalid_roles"],
            "actuator_status": d["actuator"]["status"],
        }
