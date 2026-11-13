"""Binary sensors for WebUntis."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WebUntisCoordinator


@dataclass(frozen=True, kw_only=True)
class WebUntisBinarySensorDescription(BinarySensorEntityDescription):
    """Description for a WebUntis binary sensor."""

    value_key: str


BINARY_SENSORS: tuple[WebUntisBinarySensorDescription, ...] = (
    WebUntisBinarySensorDescription(
        key="is_holiday",
        name="Is Holiday",
        icon="mdi:beach",
        value_key="is_holiday",
    ),
    WebUntisBinarySensorDescription(
        key="is_weekend",
        name="Is Weekend",
        icon="mdi:calendar-weekend",
        value_key="is_weekend",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WebUntis binary sensors from a config entry."""
    coordinator: WebUntisCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        WebUntisBinarySensor(coordinator, entry, description)
        for description in BINARY_SENSORS
    )


class WebUntisBinarySensor(
    CoordinatorEntity[WebUntisCoordinator], BinarySensorEntity
):
    """Representation of a WebUntis binary sensor."""

    entity_description: WebUntisBinarySensorDescription

    def __init__(
        self,
        coordinator: WebUntisCoordinator,
        entry: ConfigEntry,
        description: WebUntisBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_has_entity_name = True

    @property
    def is_on(self) -> bool:
        """Return the binary sensor state."""
        return bool(self.coordinator.data.get(self.entity_description.value_key, False))
