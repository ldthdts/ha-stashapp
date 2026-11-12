"""Shared entity helpers for the Stash integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import StashClient
from .const import DOMAIN
from .coordinator import StashConfigEntry, StashCoordinator


def device_info(entry: StashConfigEntry, client: StashClient) -> DeviceInfo:
    """Return the device shared by all entities of one Stash server."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Stash",
        manufacturer="Stash",
        model="Stash server",
        configuration_url=client.base_url,
    )


class StashEntity(CoordinatorEntity[StashCoordinator]):
    """Base class for Stash entities that read coordinator data."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: StashCoordinator, entry: StashConfigEntry, key: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = device_info(entry, coordinator.client)
