"""Image entities: one per feed, each showing a random image filtered by tags."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .api import StashClient, StashError
from .const import (
    CONF_AUTO_REFRESH_INTERVAL,
    CONF_TAGS,
    SERVICE_REFRESH_FEED,
    SUBENTRY_TYPE_FEED,
)
from .coordinator import StashConfigEntry
from .entity import device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StashConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one image entity per feed."""
    client = entry.runtime_data.client
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_FEED:
            continue
        async_add_entities(
            [StashFeedImage(hass, entry, subentry, client)],
            config_subentry_id=subentry.subentry_id,
        )
    entity_platform.async_get_current_platform().async_register_entity_service(
        SERVICE_REFRESH_FEED, None, "async_refresh_feed"
    )


class StashFeedImage(ImageEntity):
    """A random image picked from Stash using the tags of one feed."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: StashConfigEntry,
        subentry: ConfigSubentry,
        client: StashClient,
    ) -> None:
        """Initialize the feed image entity."""
        super().__init__(hass)
        self._entry = entry
        self._client = client
        self._tags: list[str] | None = subentry.data.get(CONF_TAGS) or None
        self._auto_refresh_interval: int = subentry.data.get(
            CONF_AUTO_REFRESH_INTERVAL, 0
        )
        self._content: bytes | None = None
        self._attr_name = subentry.title
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = device_info(entry, client)

    async def async_added_to_hass(self) -> None:
        """Schedule periodic refreshes and pick an initial image."""
        await super().async_added_to_hass()
        if self._auto_refresh_interval > 0:
            self.async_on_remove(
                async_track_time_interval(
                    self.hass,
                    self._async_refresh_logged,
                    timedelta(seconds=self._auto_refresh_interval),
                )
            )
        self._entry.async_create_background_task(
            self.hass,
            self._async_refresh_logged(),
            f"stashapp_feed_{self._attr_unique_id}",
        )

    async def async_refresh_feed(self) -> None:
        """Pick a new random image matching this feed's tags."""
        try:
            found = await self._client.async_get_random_image(self._tags)
            if found is None:
                raise ServiceValidationError(
                    f"No images matched the tags of feed {self.name}"
                )
            content, content_type = await self._client.async_fetch_image(
                found["image_url"]
            )
        except StashError as err:
            raise HomeAssistantError(str(err)) from err

        self._content = content
        self._attr_content_type = content_type
        self._attr_image_last_updated = dt_util.utcnow()
        self._attr_extra_state_attributes = {
            "title": found["title"],
            "stash_id": found["id"],
        }
        self.async_write_ha_state()

    async def _async_refresh_logged(self, _now: datetime | None = None) -> None:
        """Refresh from a timer or startup, logging instead of raising."""
        try:
            await self.async_refresh_feed()
        except HomeAssistantError as err:
            _LOGGER.warning("Could not refresh Stash feed %s: %s", self.name, err)

    async def async_image(self) -> bytes | None:
        """Return the bytes of the current image."""
        return self._content
