"""Sensor entities for the Dontek Aquatek integration.

Covers: connection status, device name, temperature sensors.
"""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    REG_SENSOR_READING_BASE,
    REG_SENSOR_TYPE_BASE,
    SENSOR_COUNT,
    SENSOR_TYPE_NAMES,
)
from .coordinator import AquatekCoordinator
from .entity_base import AquatekEntity
from .mqtt_client import ConnectionState

_TEMP_SCALE = 2.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AquatekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        AquatekConnectionSensor(coordinator),
        AquatekDeviceNameSensor(coordinator),
        *[AquatekTemperatureSensor(coordinator, n) for n in range(1, SENSOR_COUNT + 1)],
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


class AquatekTemperatureSensor(AquatekEntity, SensorEntity):
    """One of three physical temperature sensors on the controller.

    The sensor role (Pool/Roof/Water/None) is configurable in the app and stored
    in the device config register for that sensor number.
    """

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:thermometer"

    def __init__(self, coordinator: AquatekCoordinator, sensor_n: int) -> None:
        super().__init__(coordinator, f"temperature_{sensor_n}")
        self._sensor_n = sensor_n
        self._attr_name = f"Temperature Sensor {sensor_n}"

    @property
    def native_value(self) -> float | None:
        val = self._reg(REG_SENSOR_READING_BASE + self._sensor_n - 1)
        return None if val is None else val / _TEMP_SCALE

    @property
    def extra_state_attributes(self) -> dict:
        type_val = self._reg(REG_SENSOR_TYPE_BASE + self._sensor_n - 1)
        if type_val is None:
            return {}
        return {"configured_type": SENSOR_TYPE_NAMES.get(type_val, f"unknown ({type_val})")}
