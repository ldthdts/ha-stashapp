"""Services for the Stash integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .api import StashError
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_TAGS,
    DOMAIN,
    SERVICE_RANDOM_IMAGE,
    SERVICE_RANDOM_SCENE,
    SERVICE_SCAN_LIBRARY,
)
from .coordinator import StashCoordinator

ENTRY_SCHEMA = {vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string}
TAG_SCHEMA = vol.Schema(
    {
        **ENTRY_SCHEMA,
        vol.Optional(ATTR_TAGS): vol.All(cv.ensure_list, [cv.string]),
    }
)
SCAN_SCHEMA = vol.Schema(ENTRY_SCHEMA)


def _get_coordinator(hass: HomeAssistant, entry_id: str | None) -> StashCoordinator:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if entry_id:
        for entry in entries:
            if entry.entry_id == entry_id:
                return entry.runtime_data
        raise ServiceValidationError(f"No loaded Stash server with id {entry_id}")
    if len(entries) == 1:
        return entries[0].runtime_data
    if not entries:
        raise ServiceValidationError("No Stash server is configured")
    raise ServiceValidationError(
        "Set config_entry_id when more than one Stash server is configured"
    )


async def _async_random_image(call: ServiceCall) -> ServiceResponse:
    coordinator = _get_coordinator(call.hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
    try:
        found = await coordinator.client.async_get_random_image(
            call.data.get(ATTR_TAGS)
        )
    except StashError as err:
        raise HomeAssistantError(str(err)) from err
    if found is None:
        raise ServiceValidationError("No images matched the request")
    return {
        "id": found["id"],
        "title": found["title"],
        "image_url": found["image_url"],
    }


async def _async_random_scene(call: ServiceCall) -> ServiceResponse:
    coordinator = _get_coordinator(call.hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
    try:
        found = await coordinator.client.async_get_random_scene(
            call.data.get(ATTR_TAGS)
        )
    except StashError as err:
        raise HomeAssistantError(str(err)) from err
    if found is None:
        raise ServiceValidationError("No scenes matched the request")
    return found


async def _async_scan_library(call: ServiceCall) -> ServiceResponse:
    coordinator = _get_coordinator(call.hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
    try:
        job_id = await coordinator.client.async_metadata_scan()
    except StashError as err:
        raise HomeAssistantError(str(err)) from err
    return {"job_id": job_id}


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register the Stash services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_RANDOM_IMAGE,
        _async_random_image,
        schema=TAG_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RANDOM_SCENE,
        _async_random_scene,
        schema=TAG_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SCAN_LIBRARY,
        _async_scan_library,
        schema=SCAN_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
