"""Maintenance buttons for JG Energy Manager."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import JGEnergyEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([JGResetSessionButton(entry.runtime_data, "reset_session")])


class JGResetSessionButton(JGEnergyEntity, ButtonEntity):
    _attr_translation_key = "reset_session"
    _attr_icon = "mdi:restart"

    async def async_press(self) -> None:
        await self.coordinator.async_reset_session()
