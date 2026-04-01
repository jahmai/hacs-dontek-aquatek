"""Number entities for the Dontek Aquatek integration.

Covers:
- VF1 cool down time in minutes (65451)
- VF2 cool down time in minutes (57568)
- VF2 setback temperature offset in °C (57579): 0 to -15 in 0.5°C steps
"""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    REG_VF1_COOLDOWN,
    REG_VF2_COOLDOWN,
    REG_VF2_SETBACK_TEMP,
)
from .coordinator import AquatekCoordinator
from .entity_base import AquatekEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AquatekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        AquatekCoolDownNumber(coordinator, "heater_1_cooldown", "Heater 1 Cool Down", REG_VF1_COOLDOWN),
        AquatekCoolDownNumber(coordinator, "heater_2_cooldown", "Heater 2 Cool Down", REG_VF2_COOLDOWN),
        AquatekSetbackTempNumber(coordinator),
    ])


class AquatekCoolDownNumber(AquatekEntity, NumberEntity):
    """Cool down time in minutes for a heater VF port."""

    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 60
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:timer"

    def __init__(
        self,
        coordinator: AquatekCoordinator,
        unique_key: str,
        name: str,
        register: int,
    ) -> None:
        super().__init__(coordinator, unique_key)
        self._attr_name = name
        self._register = register

    @property
    def native_value(self) -> float | None:
        val = self._reg(self._register)
        return float(val) if val is not None else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write_register(self._register, [int(value)])


class AquatekSetbackTempNumber(AquatekEntity, NumberEntity):
    """Heater 2 setback temperature offset (reg 57579): 0 to -15°C in 0.5°C steps."""

    _attr_name = "Heater 2 Setback Temperature"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = -15.0
    _attr_native_max_value = 0.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:thermometer-minus"

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_2_setback_temp")

    @property
    def native_value(self) -> float | None:
        val = self._reg(REG_VF2_SETBACK_TEMP)
        if val is None:
            return None
        # Stored as positive integer in 0.5°C steps (e.g. 6 = -3°C)
        return -(val * 0.5)

    async def async_set_native_value(self, value: float) -> None:
        # value is negative (e.g. -3.0); store as positive integer steps of 0.5°C
        await self.coordinator.async_write_register(REG_VF2_SETBACK_TEMP, [int(-value * 2)])
