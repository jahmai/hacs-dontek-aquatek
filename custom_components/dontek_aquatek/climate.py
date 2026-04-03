"""Climate entities for the Dontek Aquatek heaters.

Each heater has independent Pool and Spa setpoint registers:
  - Heater 1: ctrl=65348, pool setpoint=65447, spa setpoint=65441
  - Heater 2: ctrl=57517, pool setpoint=57575, spa setpoint=57576

The active setpoint shown/written by the climate entity depends on the heater's
heating mode (65450 for H1, 57566 for H2):
  - Pool only (3)  → pool setpoint
  - Spa only  (4)  → spa setpoint
  - Pool & Spa (2) → show whichever matches the current controller Pool/Spa mode
                     (65313=0 → pool, 65313=1 → spa); write both on set_temperature
  - Off (0)        → show pool setpoint; write both on set_temperature

Setpoints are encoded as °C × 2 (e.g. 32°C is stored as 64).

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
    REG_H1_POOL_SETPOINT,
    REG_H1_SPA_SETPOINT,
    REG_H2_POOL_SETPOINT,
    REG_H2_SPA_SETPOINT,
    REG_HEATER1_CTRL,
    REG_HEATER2_CTRL,
    REG_POOL_SPA_MODE,
    REG_SENSOR_READING_BASE,
    REG_SENSOR_TYPE_BASE,
    REG_VF1_HEAT_MODE,
    REG_VF2_HEAT_MODE,
    SENSOR_COUNT,
    SENSOR_TYPE_POOL,
)
from .coordinator import AquatekCoordinator
from .entity_base import AquatekEntity

_TEMP_SCALE = 2.0

# Heating mode values (same for both heaters)
_HEAT_MODE_POOL_AND_SPA = 2
_HEAT_MODE_POOL_ONLY = 3
_HEAT_MODE_SPA_ONLY = 4

# Raw register value used by the firmware to mean "Off" for a setpoint circuit.
# Confirmed: device factory-resets H1 Pool setpoint to 255; app shows "Off" at 127.5°C.
_SETPOINT_OFF = 255


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
    """Shared base for Heater 1 and Heater 2 climate entities."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 10.0
    _attr_max_temp = 45.0
    _attr_target_temperature_step = 0.5

    _ctrl_register: int
    _heat_mode_register: int
    _pool_setpoint_register: int
    _spa_setpoint_register: int

    _HVAC_MODE_TO_VAL = {HVACMode.OFF: 0, HVACMode.HEAT: 1, HVACMode.AUTO: 2}
    _VAL_TO_HVAC_MODE = {0: HVACMode.OFF, 1: HVACMode.HEAT, 2: HVACMode.AUTO}

    @property
    def _heat_mode(self) -> int | None:
        return self._reg(self._heat_mode_register)

    @property
    def _active_setpoint_register(self) -> int:
        """Return the setpoint register appropriate for the current heating mode."""
        mode = self._heat_mode
        if mode == _HEAT_MODE_SPA_ONLY:
            return self._spa_setpoint_register
        if mode == _HEAT_MODE_POOL_AND_SPA:
            controller_in_spa = self._reg(REG_POOL_SPA_MODE) == 1
            if controller_in_spa:
                # Show pool as fallback if spa circuit is Off
                if self._reg(self._spa_setpoint_register) != _SETPOINT_OFF:
                    return self._spa_setpoint_register
            else:
                # Show spa as fallback if pool circuit is Off
                if self._reg(self._pool_setpoint_register) == _SETPOINT_OFF:
                    return self._spa_setpoint_register
        return self._pool_setpoint_register

    @property
    def hvac_mode(self) -> HVACMode | None:
        val = self._reg(self._ctrl_register)
        if val is None:
            return None
        return self._VAL_TO_HVAC_MODE.get(val, HVACMode.AUTO)

    @property
    def target_temperature(self) -> float | None:
        val = self._reg(self._active_setpoint_register)
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
        val = self._HVAC_MODE_TO_VAL.get(hvac_mode, 2)
        await self.coordinator.async_write_register(self._ctrl_register, [val])

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        raw = int(temp * _TEMP_SCALE)
        mode = self._heat_mode
        if mode == _HEAT_MODE_POOL_ONLY:
            await self.coordinator.async_write_register(self._pool_setpoint_register, [raw])
        elif mode == _HEAT_MODE_SPA_ONLY:
            await self.coordinator.async_write_register(self._spa_setpoint_register, [raw])
        else:
            # Pool & Spa (2), Off (0), or unknown — write each circuit only if not Off (255)
            if self._reg(self._pool_setpoint_register) != _SETPOINT_OFF:
                await self.coordinator.async_write_register(self._pool_setpoint_register, [raw])
            if self._reg(self._spa_setpoint_register) != _SETPOINT_OFF:
                await self.coordinator.async_write_register(self._spa_setpoint_register, [raw])


class AquatekHeater1(_AquatekHeaterBase):
    """Heater 1 (VF1) — ctrl=65348, pool setpoint=65447, spa setpoint=65441."""

    _attr_name = "Heater 1"
    _attr_icon = "mdi:radiator"
    _ctrl_register = REG_HEATER1_CTRL
    _heat_mode_register = REG_VF1_HEAT_MODE
    _pool_setpoint_register = REG_H1_POOL_SETPOINT
    _spa_setpoint_register = REG_H1_SPA_SETPOINT

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_1")


class AquatekHeater2(_AquatekHeaterBase):
    """Heater 2 (VF2) — ctrl=57517, pool setpoint=57575, spa setpoint=57576."""

    _attr_name = "Heater 2"
    _attr_icon = "mdi:radiator"
    _ctrl_register = REG_HEATER2_CTRL
    _heat_mode_register = REG_VF2_HEAT_MODE
    _pool_setpoint_register = REG_H2_POOL_SETPOINT
    _spa_setpoint_register = REG_H2_SPA_SETPOINT

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_2")
