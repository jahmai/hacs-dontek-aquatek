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
    FILTER_PUMP_STATUS_NAMES,
    HEATER_STATUS_NAMES,
    REG_FILTER_PUMP_LAST_RAN,
    REG_FILTER_PUMP_STATUS,
    REG_HEATER1_CTRL,
    REG_HEATER1_STATUS,
    REG_HEATER2_CTRL,
    REG_HEATER2_STATUS,
    REG_POOL_SPA_MODE,
    REG_SENSOR_READING_BASE,
    REG_SENSOR_TYPE_BASE,
    REG_VF1_HEAT_MODE,
    REG_VF2_HEAT_MODE,
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
        AquatekLastMessageSensor(coordinator),
        AquatekDeviceNameSensor(coordinator),
        AquatekFilterPumpStatusSensor(coordinator),
        AquatekHeater1StatusSensor(coordinator),
        AquatekHeater2StatusSensor(coordinator),
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


class AquatekLastMessageSensor(AquatekEntity, SensorEntity):
    """Timestamp of the last MQTT message received from the device."""

    _attr_name = "Last Message"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check"

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "last_message")

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self):
        return self.coordinator.last_message_time


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


def _decode_last_ran(val: int | None) -> str | None:
    """Decode a packed (hours<<8)|minutes register into 'HH:MM' or None."""
    if val is None or val == 65535:
        return None
    hours = (val & 0xFF00) >> 8
    minutes = val & 0xFF
    if hours > 23 or minutes > 59:
        return None
    return f"{hours:02d}:{minutes:02d}"


# States where speed is meaningful (pump is actually running).
# Off (0, 1) and Fault (17) retain a stale speed byte — don't display it.
_FILTER_PUMP_RUNNING_STATES = {5, 6, 7, 8, 9, 10, 11, 12, 13}


class AquatekFilterPumpStatusSensor(AquatekEntity, SensorEntity):
    """Status of the variable-speed filter pump (register 92).

    High byte = state (0-1=Off, 5=Priming, 9-11=On, 12=Running, 13=Run On, 17=Fault).
    Low byte  = speed, 0-indexed (0=Speed 1, 1=Speed 2, 2=Speed 3, 3=Speed 4).
    Speed byte is stale when pump is off — only show it for running states.
    Register 94 holds the time the pump last stopped, packed as (hours<<8)|minutes.
    """

    _attr_name = "Filter Pump Status"
    _attr_icon = "mdi:pump"

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "filter_pump_status")

    @property
    def native_value(self) -> str | None:
        val = self._reg(REG_FILTER_PUMP_STATUS)
        if val is None:
            return None
        state_byte = (val & 0xFF00) >> 8
        name = FILTER_PUMP_STATUS_NAMES.get(state_byte, f"Unknown ({state_byte})")
        if state_byte in _FILTER_PUMP_RUNNING_STATES:
            speed = (val & 0xFF) + 1  # 0-indexed raw → 1-indexed display
            return f"{name} (Speed {speed})"
        return name

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {}
        val = self._reg(REG_FILTER_PUMP_STATUS)
        if val is not None and (val >> 8) in _FILTER_PUMP_RUNNING_STATES:
            attrs["speed"] = (val & 0xFF) + 1
        last_ran = _decode_last_ran(self._reg(REG_FILTER_PUMP_LAST_RAN))
        if last_ran is not None:
            attrs["last_ran_at"] = last_ran
        return attrs


class _AquatekHeaterStatusSensor(AquatekEntity, SensorEntity):
    """Base for heater status sensors — both heaters share the same status code table.

    Status code 0 is "Off" when the ctrl register is 0, otherwise "Waiting".
    Code 1 is always "Waiting". Mode context (e.g. "Waiting (Pool Mode)") is
    only appended when the heater's heating mode conflicts with the current
    controller mode — i.e. the heater is armed but blocked by mode mismatch.
    """

    _register: int
    _ctrl_register: int
    _heat_mode_register: int
    _status_names = HEATER_STATUS_NAMES

    @property
    def native_value(self) -> str | None:
        val = self._reg(self._register)
        if val is None:
            return None
        if val in (0, 11, 12):
            ctrl = self._reg(self._ctrl_register)
            if ctrl == 0:
                return "Off"
            # ctrl ≠ 0: heater is armed but blocked — treat as waiting
            val = 1
        if val == 1:
            mode = self._reg(REG_POOL_SPA_MODE)
            heat_mode = self._reg(self._heat_mode_register)
            # Only label the blocking mode when there's an actual mismatch.
            # heat_mode 2 = Pool & Spa (never blocked); None = not yet received.
            if heat_mode not in (None, 0, 2):
                if heat_mode == 4 and mode == 0:  # Spa-only heater, Pool mode active
                    return "Waiting (Pool Mode)"
                if heat_mode == 3 and mode == 1:  # Pool-only heater, Spa mode active
                    return "Waiting (Spa Mode)"
            return "Waiting"
        return self._status_names.get(val, f"Unknown ({val})")


class AquatekHeater1StatusSensor(_AquatekHeaterStatusSensor):
    """Heater 1 status (register 81)."""

    _attr_name = "Heater 1 Status"
    _attr_icon = "mdi:fire"
    _register = REG_HEATER1_STATUS
    _ctrl_register = REG_HEATER1_CTRL
    _heat_mode_register = REG_VF1_HEAT_MODE

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_1_status")


class AquatekHeater2StatusSensor(_AquatekHeaterStatusSensor):
    """Heater 2 status (register 184)."""

    _attr_name = "Heater 2 Status"
    _attr_icon = "mdi:heat-pump"
    _register = REG_HEATER2_STATUS
    _ctrl_register = REG_HEATER2_CTRL
    _heat_mode_register = REG_VF2_HEAT_MODE

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_2_status")
