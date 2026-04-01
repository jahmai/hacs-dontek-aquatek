"""Climate entities for the Dontek Aquatek heaters.

Two independent heaters, each with their own setpoint register:
  - Gas Heater (Heater 1): on/off via 65348, setpoint via 65441 (labeled "Spa" in app)
  - Heat Pump  (Heater 2): on/off via 57517, setpoint via 57575 (labeled "Pool" in app)

Setpoints are encoded as °C × 2 (e.g. 32°C is stored as 64).
The setpoints are independent of Pool/Spa mode — they are per-heater controls.

Current water temperature is read from whichever physical sensor (1-3) is
configured as Pool type (sensor type config regs 65314-65316; type=1 means Pool).
"""

from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    REG_GAS_HEATER_CTRL,
    REG_HEAT_PUMP_CTRL,
    REG_HEAT_SETPOINT,
    REG_SENSOR_READING_BASE,
    REG_SENSOR_TYPE_BASE,
    REG_SPA_SETPOINT,
    SENSOR_COUNT,
    SENSOR_TYPE_POOL,
)
from .coordinator import AquatekCoordinator
from .entity_base import AquatekEntity

# Setpoint is stored as °C × 2 (confirmed on hardware: 32°C = 64, 33°C = 66)
_TEMP_SCALE = 2.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AquatekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        AquatekHeater1(coordinator),
        AquatekHeater2(coordinator),
    ])


class _AquatekHeaterBase(AquatekEntity, ClimateEntity):
    """Shared base for gas heater and heat pump climate entities."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 15.0
    _attr_max_temp = 40.0
    _attr_target_temperature_step = 0.5

    _ctrl_register: int
    _setpoint_register: int

    @property
    def hvac_mode(self) -> HVACMode | None:
        val = self._reg(self._ctrl_register)
        if val is None:
            return None
        return HVACMode.OFF if val == 0 else HVACMode.HEAT

    @property
    def target_temperature(self) -> float | None:
        val = self._reg(self._setpoint_register)
        return None if val is None else val / _TEMP_SCALE

    @property
    def current_temperature(self) -> float | None:
        """Return temp from whichever sensor is configured as Pool type."""
        for n in range(SENSOR_COUNT):
            if self._reg(REG_SENSOR_TYPE_BASE + n) == SENSOR_TYPE_POOL:
                val = self._reg(REG_SENSOR_READING_BASE + n)
                return None if val is None else val / _TEMP_SCALE
        return None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        val = 0 if hvac_mode == HVACMode.OFF else 2
        await self.coordinator.async_write_register(self._ctrl_register, [val])

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        await self.coordinator.async_write_register(
            self._setpoint_register, [int(temp * _TEMP_SCALE)]
        )


class AquatekHeater1(_AquatekHeaterBase):
    """Heater 1 (VF1) — on/off via socket output (65348), setpoint at 65441."""

    _attr_name = "Heater 1"
    _attr_icon = "mdi:radiator"
    _ctrl_register = REG_GAS_HEATER_CTRL
    _setpoint_register = REG_SPA_SETPOINT

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_1")


class AquatekHeater2(_AquatekHeaterBase):
    """Heater 2 (VF2) — on/off via serial (57517), setpoint at 57575."""

    _attr_name = "Heater 2"
    _attr_icon = "mdi:radiator"
    _ctrl_register = REG_HEAT_PUMP_CTRL
    _setpoint_register = REG_HEAT_SETPOINT

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_2")
