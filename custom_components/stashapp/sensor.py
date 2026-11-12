"""Sensors for Stash library statistics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import StashConfigEntry, StashCoordinator
from .entity import StashEntity

BYTES_PER_GB = 1024**3
SECONDS_PER_HOUR = 3600


def _value(key: str) -> Callable[[dict[str, Any]], StateType]:
    return lambda data: data[key]


def _gigabytes(key: str) -> Callable[[dict[str, Any]], StateType]:
    return lambda data: round(data[key] / BYTES_PER_GB, 2)


def _hours(key: str) -> Callable[[dict[str, Any]], StateType]:
    return lambda data: round(data[key] / SECONDS_PER_HOUR, 2)


@dataclass(frozen=True, kw_only=True)
class StashSensorEntityDescription(SensorEntityDescription):
    """Describe a Stash statistics sensor."""

    value_fn: Callable[[dict[str, Any]], StateType]


COUNT_SENSORS: tuple[StashSensorEntityDescription, ...] = (
    StashSensorEntityDescription(
        key="scenes",
        translation_key="scenes",
        icon="mdi:movie-open",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("scenes"),
    ),
    StashSensorEntityDescription(
        key="images",
        translation_key="images",
        icon="mdi:image-multiple",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("images"),
    ),
    StashSensorEntityDescription(
        key="galleries",
        translation_key="galleries",
        icon="mdi:folder-multiple-image",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("galleries"),
    ),
    StashSensorEntityDescription(
        key="performers",
        translation_key="performers",
        icon="mdi:account-group",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("performers"),
    ),
    StashSensorEntityDescription(
        key="studios",
        translation_key="studios",
        icon="mdi:domain",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("studios"),
    ),
    StashSensorEntityDescription(
        key="tags",
        translation_key="tags",
        icon="mdi:tag-multiple",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("tags"),
    ),
    StashSensorEntityDescription(
        key="markers",
        translation_key="markers",
        icon="mdi:bookmark-multiple",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("markers"),
    ),
    StashSensorEntityDescription(
        key="scenes_played",
        translation_key="scenes_played",
        icon="mdi:play-circle",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("scenes_played"),
    ),
    StashSensorEntityDescription(
        key="total_play_count",
        translation_key="total_play_count",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_value("total_play_count"),
    ),
    StashSensorEntityDescription(
        key="total_o_count",
        translation_key="total_o_count",
        icon="mdi:heart",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_value("total_o_count"),
    ),
    StashSensorEntityDescription(
        key="active_jobs",
        translation_key="active_jobs",
        icon="mdi:cog-sync",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("active_jobs"),
    ),
)

SIZE_AND_DURATION_SENSORS: tuple[StashSensorEntityDescription, ...] = (
    StashSensorEntityDescription(
        key="scenes_size",
        translation_key="scenes_size",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_gigabytes("scenes_size"),
    ),
    StashSensorEntityDescription(
        key="images_size",
        translation_key="images_size",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_gigabytes("images_size"),
    ),
    StashSensorEntityDescription(
        key="scenes_duration",
        translation_key="scenes_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_hours("scenes_duration"),
    ),
    StashSensorEntityDescription(
        key="total_play_duration",
        translation_key="total_play_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_hours("total_play_duration"),
    ),
)

DIAGNOSTIC_SENSORS: tuple[StashSensorEntityDescription, ...] = (
    StashSensorEntityDescription(
        key="version",
        translation_key="version",
        icon="mdi:information-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("version"),
    ),
)

SENSORS = COUNT_SENSORS + SIZE_AND_DURATION_SENSORS + DIAGNOSTIC_SENSORS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StashConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Stash statistics sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        StashSensor(coordinator, entry, description) for description in SENSORS
    )


class StashSensor(StashEntity, SensorEntity):
    """A sensor reporting one Stash statistic."""

    entity_description: StashSensorEntityDescription

    def __init__(
        self,
        coordinator: StashCoordinator,
        entry: StashConfigEntry,
        description: StashSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the value computed from the latest statistics."""
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
