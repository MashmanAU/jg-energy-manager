"""Operating-mode select for JG Energy Manager."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MODE_OPTIONS
from .entity import JGEnergyEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([JGOverrideSelect(entry.runtime_data, "override")])


class JGOverrideSelect(JGEnergyEntity, SelectEntity):
    _attr_translation_key = "override"
    _attr_icon = "mdi:tune-variant"
    _attr_options = MODE_OPTIONS

    @property
    def current_option(self) -> str:
        return self.coordinator.runtime.override

    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            raise ValueError(f"Unsupported operating mode: {option}")
        await self.coordinator.async_set_override(option)
