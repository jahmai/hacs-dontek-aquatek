"""Number entities for pump speed control in the Dontek Aquatek integration."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PUMP_COUNT, REG_PUMP_SPEED_BASE
from .coordinator import AquatekCoordinator
from .entity_base import AquatekEntity

# Speed levels 0–3 (confirmed from app register defaults; exact RPM mapping
# depends on pump model — to be validated with hardware)
_SPEED_MIN = 0
_SPEED_MAX = 3
_SPEED_STEP = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AquatekCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        AquatekPumpSpeed(coordinator, i)
        for i in range(PUMP_COUNT - 1)  # pumps 0–11; spa (index 12) has no speed
    ]
    async_add_entities(entities)


class AquatekPumpSpeed(AquatekEntity, NumberEntity):
    """Speed level control for a variable-speed pump."""

    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = _SPEED_MIN
    _attr_native_max_value = _SPEED_MAX
    _attr_native_step = _SPEED_STEP
    _attr_icon = "mdi:pump"

    def __init__(self, coordinator: AquatekCoordinator, pump_index: int) -> None:
        super().__init__(coordinator, f"pump_speed_{pump_index}")
        self._pump_index = pump_index
        self._register = REG_PUMP_SPEED_BASE + pump_index
        self._attr_name = f"Pump {pump_index + 1} Speed"
        # Disabled by default for pumps beyond index 0 — user enables installed pumps
        self._attr_entity_registry_enabled_default = pump_index == 0

    @property
    def native_value(self) -> float | None:
        val = self._reg(self._register)
        return float(val) if val is not None else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write_register(
            self._register, [int(value)]
        )
