"""Base entity for JG Energy Manager."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import JGEnergyCoordinator


class JGEnergyEntity(CoordinatorEntity[JGEnergyCoordinator]):
    """Base coordinator-backed entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: JGEnergyCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=coordinator.name,
            manufacturer="JG Energy Manager",
            model="Home Energy Controller",
            sw_version="0.1.0",
            configuration_url="https://github.com/MashmanAU/jg-energy-manager",
        )
