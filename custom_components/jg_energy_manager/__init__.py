"""JG Energy Manager integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_CHARGING_STATES, DEFAULTS, DOMAIN, PLATFORMS
from .coordinator import JGEnergyCoordinator


JGEnergyConfigEntry = ConfigEntry[JGEnergyCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: JGEnergyConfigEntry) -> bool:
    """Set up JG Energy Manager from a config entry."""
    coordinator = JGEnergyCoordinator(hass, entry)
    await coordinator.async_load_runtime()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate existing entries without replacing stable entity unique IDs."""
    if entry.version < 2:
        data = dict(entry.data)
        data.setdefault(CONF_CHARGING_STATES, DEFAULTS[CONF_CHARGING_STATES])
        hass.config_entries.async_update_entry(entry, data=data, version=2)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: JGEnergyConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_shutdown()
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: JGEnergyConfigEntry) -> None:
    """Reload when UI options change."""
    await hass.config_entries.async_reload(entry.entry_id)
