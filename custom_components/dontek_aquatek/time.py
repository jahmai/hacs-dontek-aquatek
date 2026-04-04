"""Time entities for schedule start/end times.

All schedule times are encoded as (hours << 8) | minutes.
0xFFFF = unset ("--:--" in app) → entity returns None.

Entities:
  - Socket 1–5 Schedule 1/2 Start/End   (always all 5 sockets)
  - Filter Pump Schedule 1–4 Start/End  (4 slots)
  - Heater 1 Schedule Start/End
  - Heater 2 Schedule Start/End
"""

from __future__ import annotations

from datetime import time as dt_time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    FILTER_SCHED_COUNT,
    FILTER_SCHED_END_REGS,
    FILTER_SCHED_START_REGS,
    REG_H1_SCHEDULE_END,
    REG_H1_SCHEDULE_START,
    REG_H1_SCHEDULE2_END,
    REG_H1_SCHEDULE2_START,
    REG_H2_SCHEDULE_END,
    REG_H2_SCHEDULE_START,
    REG_H2_SCHEDULE2_END,
    REG_H2_SCHEDULE2_START,
    REG_JET_PUMP_SCHED1_END,
    REG_JET_PUMP_SCHED1_START,
    REG_JET_PUMP_SCHED2_END,
    REG_JET_PUMP_SCHED2_START,
    REG_SOCKET_SCHED1_END_BASE,
    REG_SOCKET_SCHED1_START_BASE,
    REG_SOCKET_SCHED2_END_BASE,
    REG_SOCKET_SCHED2_START_BASE,
    REG_SOCKET_TYPE_BASE,
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
    entities: list[AquatekScheduleTime] = []

    # Socket schedule times — always all 5 sockets.
    # Jet Pump (type 12) uses dedicated registers instead of the sequential base+offset pattern.
    data = coordinator.data or {}
    for n in range(1, SOCKET_COUNT + 1):
        socket_type = data.get(REG_SOCKET_TYPE_BASE + (n - 1), 0)
        for sched_idx in range(2):
            sched_num = sched_idx + 1
            if socket_type == SOCKET_TYPE_JET_PUMP:
                start_reg = REG_JET_PUMP_SCHED1_START if sched_idx == 0 else REG_JET_PUMP_SCHED2_START
                end_reg   = REG_JET_PUMP_SCHED1_END   if sched_idx == 0 else REG_JET_PUMP_SCHED2_END
            else:
                start_base = REG_SOCKET_SCHED1_START_BASE if sched_idx == 0 else REG_SOCKET_SCHED2_START_BASE
                end_base   = REG_SOCKET_SCHED1_END_BASE   if sched_idx == 0 else REG_SOCKET_SCHED2_END_BASE
                start_reg  = start_base + (n - 1)
                end_reg    = end_base   + (n - 1)
            entities.append(AquatekScheduleTime(
                coordinator,
                unique_key=f"socket_{n}_schedule_{sched_num}_start",
                name=f"Socket {n} Schedule {sched_num} Start",
                register=start_reg,
            ))
            entities.append(AquatekScheduleTime(
                coordinator,
                unique_key=f"socket_{n}_schedule_{sched_num}_end",
                name=f"Socket {n} Schedule {sched_num} End",
                register=end_reg,
            ))

    # Filter pump schedule times — 4 slots
    for slot in range(FILTER_SCHED_COUNT):
        entities.append(AquatekScheduleTime(
            coordinator,
            unique_key=f"filter_schedule_{slot + 1}_start",
            name=f"Filter Schedule {slot + 1} Start",
            register=FILTER_SCHED_START_REGS[slot],
        ))
        entities.append(AquatekScheduleTime(
            coordinator,
            unique_key=f"filter_schedule_{slot + 1}_end",
            name=f"Filter Schedule {slot + 1} End",
            register=FILTER_SCHED_END_REGS[slot],
        ))

    # Heater schedule times
    entities += [
        AquatekScheduleTime(coordinator, "heater_1_schedule_start",  "Heater 1 Schedule 1 Start", REG_H1_SCHEDULE_START),
        AquatekScheduleTime(coordinator, "heater_1_schedule_end",    "Heater 1 Schedule 1 End",   REG_H1_SCHEDULE_END),
        AquatekScheduleTime(coordinator, "heater_1_schedule2_start", "Heater 1 Schedule 2 Start", REG_H1_SCHEDULE2_START),
        AquatekScheduleTime(coordinator, "heater_1_schedule2_end",   "Heater 1 Schedule 2 End",   REG_H1_SCHEDULE2_END),
        AquatekScheduleTime(coordinator, "heater_2_schedule_start",  "Heater 2 Schedule 1 Start", REG_H2_SCHEDULE_START),
        AquatekScheduleTime(coordinator, "heater_2_schedule_end",    "Heater 2 Schedule 1 End",   REG_H2_SCHEDULE_END),
        AquatekScheduleTime(coordinator, "heater_2_schedule2_start", "Heater 2 Schedule 2 Start", REG_H2_SCHEDULE2_START),
        AquatekScheduleTime(coordinator, "heater_2_schedule2_end",   "Heater 2 Schedule 2 End",   REG_H2_SCHEDULE2_END),
    ]

    async_add_entities(entities)


class AquatekScheduleTime(AquatekEntity, TimeEntity):
    """Schedule start or end time for a socket, filter slot, or heater."""

    _attr_icon = "mdi:clock"

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
    def native_value(self) -> dt_time | None:
        val = self._reg(self._register)
        if val is None or val == TIME_REG_UNSET:
            return None
        h, m = (val >> 8) & 0xFF, val & 0xFF
        if h >= 24 or m >= 60:
            return None
        return dt_time(h, m)

    async def async_set_value(self, value: dt_time) -> None:
        await self.coordinator.async_write_register(self._register, [(value.hour << 8) | value.minute])
