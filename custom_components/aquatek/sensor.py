"""Sensor entities for the Dontek Aquatek integration.

Covers: connection status, device name.
"""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AquatekCoordinator
from .entity_base import AquatekEntity
from .mqtt_client import ConnectionState


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AquatekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        AquatekConnectionSensor(coordinator),
        AquatekDeviceNameSensor(coordinator),
    ])


class AquatekConnectionSensor(AquatekEntity, SensorEntity):
    """Reports the MQTT connection state."""

    _attr_name = "Connection"
    _attr_icon = "mdi:cloud-check"

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "connection")

    @property
    def available(self) -> bool:
        # Always available so users can see "Disconnected" state
        return True

    @property
    def native_value(self) -> str:
        return self.coordinator.connection_state.value


class AquatekDeviceNameSensor(AquatekEntity, SensorEntity):
    """Reports the device name read from registers 65488–65495."""

    _attr_name = "Device Name"
    _attr_icon = "mdi:tag"

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "device_name")

    @property
    def native_value(self) -> str | None:
        return self.coordinator.get_device_name()
