"""Climate entity for the Dontek Aquatek heat pump heater.

The heat pump is connected via serial cable to the controller.
Register 57517 controls on/off/auto; setpoint register depends on Pool/Spa mode:
  - Pool mode (65313=0): setpoint at 57575
  - Spa mode  (65313=1): setpoint at 65441
Both setpoints are encoded as °C × 2 (e.g. 32°C is stored as 64).
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
    REG_HEAT_PUMP_CTRL,
    REG_HEAT_SETPOINT,
    REG_POOL_SPA_MODE,
    REG_SPA_SETPOINT,
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
    async_add_entities([AquatekHeatPump(coordinator)])


class AquatekHeatPump(AquatekEntity, ClimateEntity):
    """Heat pump heater — on/off mode and target temperature setpoint.

    The active setpoint register depends on Pool/Spa mode (65313):
    pool mode uses 57575, spa mode uses 65441.
    """

    _attr_name = "Heat Pump"
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 15.0
    _attr_max_temp = 40.0
    _attr_target_temperature_step = 0.5
    _attr_icon = "mdi:heat-pump"

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heat_pump")

    @property
    def _setpoint_register(self) -> int:
        """Return the active setpoint register based on Pool/Spa mode."""
        spa_mode = self._reg(REG_POOL_SPA_MODE)
        return REG_SPA_SETPOINT if spa_mode == 1 else REG_HEAT_SETPOINT

    @property
    def hvac_mode(self) -> HVACMode | None:
        val = self._reg(REG_HEAT_PUMP_CTRL)
        if val is None:
            return None
        # 0 = off, 2 = auto (heat); treat any non-zero value as HEAT
        return HVACMode.OFF if val == 0 else HVACMode.HEAT

    @property
    def target_temperature(self) -> float | None:
        val = self._reg(self._setpoint_register)
        if val is None:
            return None
        return val / _TEMP_SCALE

    @property
    def current_temperature(self) -> float | None:
        # No confirmed current-temperature register yet
        return None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        # 0 = off, 2 = auto (the normal operating mode)
        val = 0 if hvac_mode == HVACMode.OFF else 2
        await self.coordinator.async_write_register(REG_HEAT_PUMP_CTRL, [val])

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        await self.coordinator.async_write_register(
            self._setpoint_register, [int(temp * _TEMP_SCALE)]
        )
