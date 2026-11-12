"""The Stash integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import StashClient
from .const import CONF_API_KEY, CONF_URL
from .coordinator import StashConfigEntry, StashCoordinator
from .services import async_register_services

PLATFORMS = [Platform.IMAGE, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register integration services."""
    async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: StashConfigEntry) -> bool:
    """Set up a Stash server from a config entry."""
    client = StashClient(
        entry.data[CONF_URL],
        async_get_clientsession(hass),
        entry.data.get(CONF_API_KEY),
    )
    coordinator = StashCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: StashConfigEntry) -> None:
    """Reload the entry so feed entities match the current subentries."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: StashConfigEntry) -> bool:
    """Unload a Stash config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
