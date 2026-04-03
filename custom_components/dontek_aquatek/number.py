"""Number entities for the Dontek Aquatek integration.

Covers:
- Heater 1 Pool setpoint in °C (65447): value = °C × 2
- Heater 1 Spa setpoint in °C (65441): value = °C × 2
- Heater 2 Pool setpoint in °C (57575): value = °C × 2
- Heater 2 Spa setpoint in °C (57576): value = °C × 2
- VF1 cool down time in minutes (65451)
- VF2 cool down time in minutes (57568)
- VF2 setback temperature offset in °C (57579): 0 to -15 in 0.5°C steps
- Per-socket Run Once duration in minutes (all 5 sockets, always created)
- Filter pump Run Once duration in minutes (derived from 57650/57670 delta)
"""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    REG_FILTER_DUTY_CYCLE,
    REG_FILTER_RUNONCE_END,
    REG_FILTER_RUNONCE_START,
    REG_H1_POOL_SETPOINT,
    REG_H1_SPA_SETPOINT,
    REG_H2_POOL_SETPOINT,
    REG_H2_SPA_SETPOINT,
    REG_SOCKET_RUNONCE_END_BASE,
    REG_SOCKET_RUNONCE_START_BASE,
    REG_VF1_COOLDOWN,
    REG_VF2_COOLDOWN,
    REG_VF2_SETBACK_TEMP,
    SOCKET_COUNT,
    TIME_REG_UNSET,
)
from .coordinator import AquatekCoordinator
from .entity_base import AquatekEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AquatekCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list = [
        AquatekFilterDutyCycleNumber(coordinator),
        AquatekHeaterSetpointNumber(coordinator, "heater_1_pool_setpoint", "Heater 1 Pool Setpoint", REG_H1_POOL_SETPOINT),
        AquatekHeaterSetpointNumber(coordinator, "heater_1_spa_setpoint",  "Heater 1 Spa Setpoint",  REG_H1_SPA_SETPOINT),
        AquatekHeaterSetpointNumber(coordinator, "heater_2_pool_setpoint", "Heater 2 Pool Setpoint", REG_H2_POOL_SETPOINT),
        AquatekHeaterSetpointNumber(coordinator, "heater_2_spa_setpoint",  "Heater 2 Spa Setpoint",  REG_H2_SPA_SETPOINT),
        AquatekCoolDownNumber(coordinator, "heater_1_cooldown", "Heater 1 Cool Down", REG_VF1_COOLDOWN),
        AquatekCoolDownNumber(coordinator, "heater_2_cooldown", "Heater 2 Cool Down", REG_VF2_COOLDOWN),
        AquatekSetbackTempNumber(coordinator),
        AquatekFilterRunOnceDuration(coordinator),
    ]

    # Per-socket RunOnce duration — all 5 sockets, always created
    for n in range(1, SOCKET_COUNT + 1):
        entities.append(AquatekSocketRunOnceDuration(coordinator, n))

    async_add_entities(entities)


class AquatekHeaterSetpointNumber(AquatekEntity, NumberEntity):
    """Individual Pool or Spa setpoint for a heater (°C × 2 encoding)."""

    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 18.0
    _attr_native_max_value = 40.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:thermometer"

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

    _SETPOINT_OFF = 255  # firmware sentinel — "Off" circuit; managed by companion switch

    @property
    def native_value(self) -> float | None:
        val = self._reg(self._register)
        if val is None or val == self._SETPOINT_OFF:
            return None
        return val / 2.0

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write_register(self._register, [int(value * 2)])


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


class AquatekSocketRunOnceDuration(AquatekEntity, NumberEntity):
    """Run Once duration for a socket, in minutes.

    The device uses (end - start) as the duration delta when RunOnce is activated.
    We always store start=0x0000 and end=(h<<8)|m so the duration reads back cleanly.
    Max duration: 23 hours 59 minutes (1439 minutes).
    """

    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 1.0
    _attr_native_max_value = 1439.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:timer"

    def __init__(self, coordinator: AquatekCoordinator, socket_n: int) -> None:
        super().__init__(coordinator, f"socket_{socket_n}_runonce_duration")
        self._attr_name = f"Socket {socket_n} Run Once Duration"
        self._start_reg = REG_SOCKET_RUNONCE_START_BASE + (socket_n - 1)
        self._end_reg = REG_SOCKET_RUNONCE_END_BASE + (socket_n - 1)

    @property
    def native_value(self) -> float | None:
        start_raw = self._reg(self._start_reg)
        end_raw = self._reg(self._end_reg)
        if start_raw is None or end_raw is None or end_raw == TIME_REG_UNSET:
            return None
        start_mins = ((start_raw >> 8) & 0xFF) * 60 + (start_raw & 0xFF)
        end_mins = ((end_raw >> 8) & 0xFF) * 60 + (end_raw & 0xFF)
        delta = end_mins - start_mins
        return float(delta) if delta > 0 else None

    async def async_set_native_value(self, value: float) -> None:
        minutes = int(value)
        end_encoded = ((minutes // 60) << 8) | (minutes % 60)
        await self.coordinator.async_write_register(self._start_reg, [0x0000])
        await self.coordinator.async_write_register(self._end_reg, [end_encoded])


class AquatekFilterRunOnceDuration(AquatekEntity, NumberEntity):
    """Filter pump Run Once duration in minutes.

    Reads (end - start) delta from 57670/57650 and writes start=0x0000, end=(h<<8)|m.
    """

    _attr_name = "Filter Run Once Duration"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 1.0
    _attr_native_max_value = 1439.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:timer"

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "filter_runonce_duration")

    @property
    def native_value(self) -> float | None:
        start_raw = self._reg(REG_FILTER_RUNONCE_START)
        end_raw = self._reg(REG_FILTER_RUNONCE_END)
        if start_raw is None or end_raw is None or end_raw == TIME_REG_UNSET:
            return None
        start_mins = ((start_raw >> 8) & 0xFF) * 60 + (start_raw & 0xFF)
        end_mins = ((end_raw >> 8) & 0xFF) * 60 + (end_raw & 0xFF)
        delta = end_mins - start_mins
        return float(delta) if delta > 0 else None

    async def async_set_native_value(self, value: float) -> None:
        minutes = int(value)
        end_encoded = ((minutes // 60) << 8) | (minutes % 60)
        await self.coordinator.async_write_register(REG_FILTER_RUNONCE_START, [0x0000])
        await self.coordinator.async_write_register(REG_FILTER_RUNONCE_END, [end_encoded])


class AquatekFilterDutyCycleNumber(AquatekEntity, NumberEntity):
    """Filter pump duty cycle — percentage of each cycle the pump runs (reg 57681).

    App UI steps in 5% increments but the register accepts any integer 0-100.
    """

    _attr_name = "Filter Duty Cycle"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 0.0
    _attr_native_max_value = 100.0
    _attr_native_step = 5.0
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:chart-donut"

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "filter_duty_cycle")

    @property
    def native_value(self) -> float | None:
        val = self._reg(REG_FILTER_DUTY_CYCLE)
        return float(val) if val is not None else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write_register(REG_FILTER_DUTY_CYCLE, [int(value)])
