"""Switch entities for the Dontek Aquatek integration.

Heater ancillary switches:
- Heater 1 Run Till Heated  (65500)
- Heater 2 Boost            (57577)

VF port config switches (heating, sanitiser, chilling, hydrotherapy, setback):
- VF1: sanitiser (65501), chilling (65523), hydrotherapy (57586)
- VF2: sanitiser (57570), chilling (57569), hydrotherapy (57587), setback (57578)

Per-socket timer switches (all 5 sockets, always created):
- Socket N Schedule 1/2 Enable — bit field in 65362+(n-1)
- Socket N Run Once — 57613+(n-1)

Filter pump timer switches:
- Filter Schedule 1–4 Enable — bit field in 65318
- Filter Run Once — 57630 bit 0 (read-modify-write to preserve VF pump speed)

Heater schedule enable switches:
- Heater 1 Schedule Enable — 65517 bit 0
- Heater 2 Schedule Enable — 57606 bit 0
"""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    FILTER_SCHED_COUNT,
    REG_BOOST_MODE,
    REG_FILTER_RUNONCE_CTRL,
    REG_FILTER_SCHEDULE_ENABLE,
    REG_H1_POOL_SETPOINT,
    REG_H1_SCHEDULE_ENABLE,
    REG_H1_SPA_SETPOINT,
    REG_H2_POOL_SETPOINT,
    REG_H2_SCHEDULE_ENABLE,
    REG_H2_SPA_SETPOINT,
    REG_RUN_TILL_HEATED,
    REG_SOCKET_RUNONCE_ENABLE_BASE,
    REG_SOCKET_SCHEDULE_ENABLE_BASE,
    REG_VF1_CHILLING,
    REG_VF1_HYDRO,
    REG_VF1_SANITISER,
    REG_VF2_CHILLING,
    REG_VF2_HYDRO,
    REG_VF2_SANITISER,
    REG_VF2_SETBACK,
    SOCKET_COUNT,
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
        AquatekRunTillHeatedSwitch(coordinator),
        AquatekBoostSwitch(coordinator),
        AquatekVF1SanitiserSwitch(coordinator),
        AquatekVF1ChillingSwitch(coordinator),
        AquatekVF1HydroSwitch(coordinator),
        AquatekVF2SanitiserSwitch(coordinator),
        AquatekVF2ChillingSwitch(coordinator),
        AquatekVF2HydroSwitch(coordinator),
        AquatekVF2SetbackSwitch(coordinator),
        AquatekSetpointOffSwitch(coordinator, "heater_1_pool_off", "Heater 1 Pool Off", REG_H1_POOL_SETPOINT),
        AquatekSetpointOffSwitch(coordinator, "heater_1_spa_off",  "Heater 1 Spa Off",  REG_H1_SPA_SETPOINT),
        AquatekSetpointOffSwitch(coordinator, "heater_2_pool_off", "Heater 2 Pool Off", REG_H2_POOL_SETPOINT),
        AquatekSetpointOffSwitch(coordinator, "heater_2_spa_off",  "Heater 2 Spa Off",  REG_H2_SPA_SETPOINT),
    ]

    # Socket timer switches — all 5 sockets, always created
    for n in range(1, SOCKET_COUNT + 1):
        entities.append(AquatekSocketScheduleSwitch(coordinator, n, 0))
        entities.append(AquatekSocketScheduleSwitch(coordinator, n, 1))
        entities.append(AquatekSocketRunOnceSwitch(coordinator, n))

    # Filter pump schedule enable — 4 slots, bit field in 65318
    for slot in range(FILTER_SCHED_COUNT):
        entities.append(AquatekFilterScheduleSwitch(coordinator, slot))

    # Filter RunOnce enable
    entities.append(AquatekFilterRunOnceSwitch(coordinator))

    # Heater schedule enable
    entities.append(AquatekHeaterScheduleSwitch(coordinator, "heater_1_schedule_enable", "Heater 1 Schedule Enable", REG_H1_SCHEDULE_ENABLE))
    entities.append(AquatekHeaterScheduleSwitch(coordinator, "heater_2_schedule_enable", "Heater 2 Schedule Enable", REG_H2_SCHEDULE_ENABLE))

    async_add_entities(entities)


class _AquatekBoolSwitch(AquatekEntity, SwitchEntity):
    """Simple 0/1 switch backed by a single Modbus register."""

    _register: int

    @property
    def is_on(self) -> bool | None:
        val = self._reg(self._register)
        return None if val is None else bool(val)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_write_register(self._register, [1])

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_write_register(self._register, [0])


class AquatekRunTillHeatedSwitch(_AquatekBoolSwitch):
    """Run Till Heated — Heater 1 runs until setpoint is reached (reg 65500)."""

    _attr_name = "Heater 1 Run Till Heated"
    _attr_icon = "mdi:thermometer-check"
    _register = REG_RUN_TILL_HEATED

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_1_run_till_heated")


class AquatekBoostSwitch(_AquatekBoolSwitch):
    """Boost / Party Mode — runs Heater 2 at full power (reg 57577)."""

    _attr_name = "Heater 2 Boost"
    _attr_icon = "mdi:rocket-launch"
    _register = REG_BOOST_MODE

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_2_boost")


class AquatekVF1SanitiserSwitch(_AquatekBoolSwitch):
    _attr_name = "Heater 1 Sanitiser"
    _attr_icon = "mdi:flask"
    _register = REG_VF1_SANITISER

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_1_sanitiser")


class AquatekVF1ChillingSwitch(_AquatekBoolSwitch):
    _attr_name = "Heater 1 Chilling"
    _attr_icon = "mdi:snowflake"
    _register = REG_VF1_CHILLING

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_1_chilling")


class AquatekVF1HydroSwitch(_AquatekBoolSwitch):
    _attr_name = "Heater 1 Hydrotherapy"
    _attr_icon = "mdi:hot-tub"
    _register = REG_VF1_HYDRO

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_1_hydrotherapy")


class AquatekVF2SanitiserSwitch(_AquatekBoolSwitch):
    _attr_name = "Heater 2 Sanitiser"
    _attr_icon = "mdi:flask"
    _register = REG_VF2_SANITISER

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_2_sanitiser")


class AquatekVF2ChillingSwitch(_AquatekBoolSwitch):
    _attr_name = "Heater 2 Chilling"
    _attr_icon = "mdi:snowflake"
    _register = REG_VF2_CHILLING

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_2_chilling")


class AquatekVF2HydroSwitch(_AquatekBoolSwitch):
    _attr_name = "Heater 2 Hydrotherapy"
    _attr_icon = "mdi:hot-tub"
    _register = REG_VF2_HYDRO

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_2_hydrotherapy")


class AquatekVF2SetbackSwitch(_AquatekBoolSwitch):
    _attr_name = "Heater 2 Track / Setback"
    _attr_icon = "mdi:thermometer-minus"
    _register = REG_VF2_SETBACK

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_2_setback")


class _AquatekBitSwitch(AquatekEntity, SwitchEntity):
    """Switch backed by a single bit in a shared register (read-modify-write)."""

    _register: int
    _bit: int

    @property
    def is_on(self) -> bool | None:
        val = self._reg(self._register)
        return None if val is None else bool((val >> self._bit) & 1)

    async def async_turn_on(self, **kwargs) -> None:
        current = self._reg(self._register) or 0
        await self.coordinator.async_write_register(self._register, [current | (1 << self._bit)])

    async def async_turn_off(self, **kwargs) -> None:
        current = self._reg(self._register) or 0
        await self.coordinator.async_write_register(self._register, [current & ~(1 << self._bit)])


class AquatekSocketScheduleSwitch(_AquatekBitSwitch):
    """Enable/disable one recurring schedule slot for a socket.

    Enable register (65362 + socket_n - 1) is a bit-field:
      bit 0 = Schedule 1, bit 1 = Schedule 2.
    """

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: AquatekCoordinator, socket_n: int, schedule_idx: int) -> None:
        sched_num = schedule_idx + 1
        super().__init__(coordinator, f"socket_{socket_n}_schedule_{sched_num}_enable")
        self._attr_name = f"Socket {socket_n} Schedule {sched_num} Enable"
        self._register = REG_SOCKET_SCHEDULE_ENABLE_BASE + (socket_n - 1)
        self._bit = schedule_idx


class AquatekSocketRunOnceSwitch(_AquatekBoolSwitch):
    """Enable/disable the Run Once timer for a socket (57613 + socket_n - 1)."""

    _attr_icon = "mdi:timer-play"

    def __init__(self, coordinator: AquatekCoordinator, socket_n: int) -> None:
        super().__init__(coordinator, f"socket_{socket_n}_runonce")
        self._attr_name = f"Socket {socket_n} Run Once"
        self._register = REG_SOCKET_RUNONCE_ENABLE_BASE + (socket_n - 1)


class AquatekFilterScheduleSwitch(_AquatekBitSwitch):
    """Enable/disable one filter pump schedule slot (bit in 65318)."""

    _attr_icon = "mdi:calendar-clock"
    _register = REG_FILTER_SCHEDULE_ENABLE

    def __init__(self, coordinator: AquatekCoordinator, slot: int) -> None:
        slot_num = slot + 1
        super().__init__(coordinator, f"filter_schedule_{slot_num}_enable")
        self._attr_name = f"Filter Schedule {slot_num} Enable"
        self._bit = slot


class AquatekFilterRunOnceSwitch(AquatekEntity, SwitchEntity):
    """Enable/disable the filter pump Run Once timer.

    Register 57630 is packed: bit 0 = enable, bits 8-15 = VF pump speed index.
    Read-modify-write preserves the speed index when toggling.
    """

    _attr_name = "Filter Run Once"
    _attr_icon = "mdi:timer-play"

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "filter_runonce")

    @property
    def is_on(self) -> bool | None:
        val = self._reg(REG_FILTER_RUNONCE_CTRL)
        return None if val is None else bool(val & 0x01)

    async def async_turn_on(self, **kwargs) -> None:
        current = self._reg(REG_FILTER_RUNONCE_CTRL) or 0
        await self.coordinator.async_write_register(REG_FILTER_RUNONCE_CTRL, [(current & ~0x0F) | 1])

    async def async_turn_off(self, **kwargs) -> None:
        current = self._reg(REG_FILTER_RUNONCE_CTRL) or 0
        await self.coordinator.async_write_register(REG_FILTER_RUNONCE_CTRL, [current & ~0x0F])


class AquatekHeaterScheduleSwitch(_AquatekBitSwitch):
    """Enable/disable the recurring schedule for a heater (bit 0 of enable register)."""

    _attr_icon = "mdi:calendar-clock"
    _bit = 0

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


class AquatekSetpointOffSwitch(AquatekEntity, SwitchEntity):
    """Setpoint 'Off' switch — writes 255 to disable a heating circuit.

    When ON: setpoint register holds 255 (firmware sentinel for Off); that circuit won't heat.
    When turned OFF: restores setpoint to 40°C (80 raw); adjust with the companion number entity.
    """

    _attr_icon = "mdi:thermometer-off"
    _SETPOINT_OFF = 255
    _SETPOINT_RESTORE = 80  # 40°C — safe default when re-enabling

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
    def is_on(self) -> bool | None:
        val = self._reg(self._register)
        return None if val is None else val == self._SETPOINT_OFF

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_write_register(self._register, [self._SETPOINT_OFF])

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_write_register(self._register, [self._SETPOINT_RESTORE])
