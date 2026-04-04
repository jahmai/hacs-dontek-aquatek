"""Number entities for the Dontek Aquatek integration.

Covers:
- Heater 1/2 Pool/Spa setpoints in °C
- VF1/VF2 cool down time in minutes
- VF2 setback temperature offset in °C
- Per-socket Run Once duration in minutes (all 5 sockets, always created)
- Filter pump Run Once duration in minutes
- Heater 1/2 Run Once duration in minutes
"""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    REG_FILTER_DUTY_CYCLE,
    REG_FILTER_RUNONCE_END,
    REG_FILTER_RUNONCE_START,
    REG_H1_POOL_SETPOINT,
    REG_H1_RUNONCE_END,
    REG_H1_RUNONCE_START,
    REG_H1_SPA_SETPOINT,
    REG_H2_POOL_SETPOINT,
    REG_H2_RUNONCE_END,
    REG_H2_RUNONCE_START,
    REG_H2_SPA_SETPOINT,
    REG_JET_PUMP_RUNONCE_END,
    REG_JET_PUMP_RUNONCE_START,
    REG_SOCKET_RUNONCE_END_BASE,
    REG_SOCKET_RUNONCE_START_BASE,
    REG_SOCKET_TYPE_BASE,
    REG_VF1_COOLDOWN,
    REG_VF2_COOLDOWN,
    REG_VF2_SETBACK_TEMP,
    SOCKET_COUNT,
    SOCKET_TYPE_JET_PUMP,
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
    ]

    # Per-socket RunOnce duration — all 5 sockets, always created.
    # Jet Pump sockets use dedicated registers (57652/57672) instead of the sequential bases.
    data = coordinator.data or {}
    for n in range(1, SOCKET_COUNT + 1):
        socket_type = data.get(REG_SOCKET_TYPE_BASE + (n - 1), 0)
        if socket_type == SOCKET_TYPE_JET_PUMP:
            start_reg, end_reg = REG_JET_PUMP_RUNONCE_START, REG_JET_PUMP_RUNONCE_END
        else:
            start_reg = REG_SOCKET_RUNONCE_START_BASE + (n - 1)
            end_reg = REG_SOCKET_RUNONCE_END_BASE + (n - 1)
        entities.append(AquatekRunOnceDuration(
            coordinator,
            unique_key=f"socket_{n}_runonce_duration",
            name=f"Socket {n} Run Once Duration",
            start_reg=start_reg,
            end_reg=end_reg,
        ))

    entities.append(AquatekRunOnceDuration(
        coordinator,
        unique_key="filter_runonce_duration",
        name="Filter Run Once Duration",
        start_reg=REG_FILTER_RUNONCE_START,
        end_reg=REG_FILTER_RUNONCE_END,
    ))
    entities.append(AquatekRunOnceDuration(
        coordinator,
        unique_key="heater_1_runonce_duration",
        name="Heater 1 Run Once Duration",
        start_reg=REG_H1_RUNONCE_START,
        end_reg=REG_H1_RUNONCE_END,
    ))
    entities.append(AquatekRunOnceDuration(
        coordinator,
        unique_key="heater_2_runonce_duration",
        name="Heater 2 Run Once Duration",
        start_reg=REG_H2_RUNONCE_START,
        end_reg=REG_H2_RUNONCE_END,
    ))

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


class AquatekRunOnceDuration(AquatekEntity, NumberEntity):
    """Run Once duration in minutes for any timer (socket, filter, heater).

    Reads the current duration from (end - start) registers with midnight rollover.
    Writing sets start=now and end=now+duration so the device runs from this moment.
    Max duration: 23 hours 59 minutes (1439 minutes).
    """

    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 1.0
    _attr_native_max_value = 1439.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:timer"

    def __init__(
        self,
        coordinator: AquatekCoordinator,
        unique_key: str,
        name: str,
        start_reg: int,
        end_reg: int,
    ) -> None:
        super().__init__(coordinator, unique_key)
        self._attr_name = name
        self._start_reg = start_reg
        self._end_reg = end_reg

    @property
    def native_value(self) -> float | None:
        start_raw = self._reg(self._start_reg)
        end_raw = self._reg(self._end_reg)
        if start_raw is None or end_raw is None or end_raw == TIME_REG_UNSET:
            return None
        start_mins = ((start_raw >> 8) & 0xFF) * 60 + (start_raw & 0xFF)
        end_mins = ((end_raw >> 8) & 0xFF) * 60 + (end_raw & 0xFF)
        delta = (end_mins - start_mins) % 1440
        return float(delta) if delta > 0 else None

    async def async_set_native_value(self, value: float) -> None:
        now = dt_util.now()
        start_encoded = (now.hour << 8) | now.minute
        end_dt = now + timedelta(minutes=int(value))
        end_encoded = (end_dt.hour << 8) | end_dt.minute
        await self.coordinator.async_write_register(self._start_reg, [start_encoded])
        await self.coordinator.async_write_register(self._end_reg, [end_encoded])


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
