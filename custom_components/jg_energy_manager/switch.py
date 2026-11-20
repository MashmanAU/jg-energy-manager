"""Runtime control switches for JG Energy Manager."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import JGEnergyEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            JGControllerEnabledSwitch(coordinator, "controller_enabled"),
            JGObserveOnlySwitch(coordinator, "observe_only"),
        ]
    )


class JGControllerEnabledSwitch(JGEnergyEntity, SwitchEntity):
    _attr_translation_key = "controller_enabled"
    _attr_icon = "mdi:ev-station"

    @property
    def is_on(self) -> bool:
        return self.coordinator.runtime.controller_enabled

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_controller_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_controller_enabled(False)


class JGObserveOnlySwitch(JGEnergyEntity, SwitchEntity):
    _attr_translation_key = "observe_only"
    _attr_icon = "mdi:eye-outline"

    @property
    def is_on(self) -> bool:
        return self.coordinator.runtime.observe_only

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_observe_only(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_observe_only(False)
