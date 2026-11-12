"""Data coordinator for the Stash integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import StashAuthenticationError, StashClient, StashError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


type StashConfigEntry = ConfigEntry[StashCoordinator]


class StashCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll Stash statistics."""

    config_entry: StashConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: StashConfigEntry, client: StashClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.async_get_stats()
        except StashAuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except StashError as err:
            raise UpdateFailed(str(err)) from err
