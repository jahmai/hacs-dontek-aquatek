"""Climate entity for the Dontek Aquatek heater control."""

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

from .const import DOMAIN, REG_HEAT_SETPOINT, REG_HEATER_MODE
from .coordinator import AquatekCoordinator
from .entity_base import AquatekEntity

# Temperature is stored as tenths of a degree (e.g. 285 = 28.5°C).
# TODO: confirm scaling with hardware — could be whole degrees on some firmware.
_TEMP_SCALE = 10.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AquatekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AquatekClimate(coordinator)])


class AquatekClimate(AquatekEntity, ClimateEntity):
    """Heater control — on/off mode and target temperature setpoint."""

    _attr_name = "Heater"
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 15.0
    _attr_max_temp = 40.0
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater")

    @property
    def hvac_mode(self) -> HVACMode | None:
        val = self._reg(REG_HEATER_MODE)
        if val is None:
            return None
        return HVACMode.OFF if val == 0 else HVACMode.HEAT

    @property
    def target_temperature(self) -> float | None:
        val = self._reg(REG_HEAT_SETPOINT)
        if val is None:
            return None
        return val / _TEMP_SCALE

    @property
    def current_temperature(self) -> float | None:
        # No current temp register identified yet — return None until confirmed
        return None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        mode_val = 0 if hvac_mode == HVACMode.OFF else 1
        await self.coordinator.async_write_register(REG_HEATER_MODE, [mode_val])

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        await self.coordinator.async_write_register(
            REG_HEAT_SETPOINT, [int(temp * _TEMP_SCALE)]
        )
