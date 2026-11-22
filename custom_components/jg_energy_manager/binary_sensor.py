"""Binary sensors for JG Energy Manager."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import JGEnergyEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            JGConnectedSensor(coordinator, "charger_connected"),
            JGChargingSensor(coordinator, "charger_charging"),
            JGLiveControlSensor(coordinator, "live_control"),
            JGInputHealthSensor(coordinator, "input_health"),
            JGActuatorHealthSensor(coordinator, "actuator_health"),
        ]
    )


class JGConnectedSensor(JGEnergyEntity, BinarySensorEntity):
    _attr_translation_key = "charger_connected"
    _attr_device_class = BinarySensorDeviceClass.PLUG

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data["connected"])


class JGChargingSensor(JGEnergyEntity, BinarySensorEntity):
    _attr_translation_key = "charger_charging"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data["charging"])


class JGLiveControlSensor(JGEnergyEntity, BinarySensorEntity):
    _attr_translation_key = "live_control"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def is_on(self) -> bool:
        return bool(
            self.coordinator.data["controller_enabled"]
            and not self.coordinator.data["observe_only"]
        )


class JGInputHealthSensor(JGEnergyEntity, BinarySensorEntity):
    _attr_translation_key = "input_health"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        return not bool(self.coordinator.data["inputs_valid"])


class JGActuatorHealthSensor(JGEnergyEntity, BinarySensorEntity):
    _attr_translation_key = "actuator_health"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        return not bool(self.coordinator.data["actuator"]["healthy"])

    @property
    def extra_state_attributes(self):
        actuator = self.coordinator.data["actuator"]
        return {
            "status": actuator["status"],
            "last_result": actuator["last_command_result"],
            "last_error": actuator["last_command_error"],
            "consecutive_failures": actuator["consecutive_failures"],
            "next_retry_at": actuator["next_retry_at"],
        }
