"""Select entities for the Dontek Aquatek integration.

Covers:
- One socket output entity per configured socket (auto-discovered from device config).
  Options: Off / On / Auto  (register values 0 / 1 / 2)
- Filter pump speed (VF connector, reg 65485).
  Options: Off / Speed 1 / Speed 2 / Speed 3 / Speed 4 / Auto
- Gas Heater (socket-output at reg 65348).
  Options: Off / Auto
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    REG_FILTER_PUMP,
    REG_GAS_HEATER_CTRL,
    REG_SOCKET_OUTPUT_BASE,
    SOCKET_TYPE_NAMES,
    SOCKET_TYPE_POOL_LIGHT,
)
from .coordinator import AquatekCoordinator
from .entity_base import AquatekEntity

# ---------------------------------------------------------------------------
# Socket output select — three states for all socket-type outputs

_SOCKET_OPTIONS = ["Off", "On", "Auto"]
_SOCKET_VALUES = [0, 1, 2]

# ---------------------------------------------------------------------------
# Filter pump — six states (VF speed control)

_FILTER_OPTIONS = ["Off", "Speed 1", "Speed 2", "Speed 3", "Speed 4", "Auto"]
_FILTER_VALUES = [0, 257, 513, 769, 1025, 65535]

# ---------------------------------------------------------------------------
# Gas heater — binary (off / auto); no manual-on mode

_GAS_OPTIONS = ["Off", "Auto"]
_GAS_VALUES = [0, 2]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AquatekCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SelectEntity] = []

    # Auto-discover socket outputs from device config registers
    for socket_n, type_idx in coordinator.get_socket_configs().items():
        entities.append(AquatekSocketSelect(coordinator, socket_n, type_idx))

    # Fixed entities — always present regardless of socket config
    entities.append(AquatekFilterPumpSelect(coordinator))
    entities.append(AquatekGasHeaterSelect(coordinator))
    # Heat pump is handled by the climate platform

    async_add_entities(entities)


class AquatekSocketSelect(AquatekEntity, SelectEntity):
    """Three-state (Off / On / Auto) control for a configurable socket output."""

    _attr_options = _SOCKET_OPTIONS
    _attr_icon = "mdi:power-socket"

    def __init__(
        self,
        coordinator: AquatekCoordinator,
        socket_n: int,
        type_idx: int,
    ) -> None:
        super().__init__(coordinator, f"socket_{socket_n}")
        self._register = REG_SOCKET_OUTPUT_BASE + (socket_n - 1)
        self._attr_name = SOCKET_TYPE_NAMES.get(type_idx, f"Socket {socket_n}")
        # Pool light uses explicit on (1); all other types default to auto (2) when turned on
        self._on_value = 1 if type_idx == SOCKET_TYPE_POOL_LIGHT else 2

    @property
    def current_option(self) -> str | None:
        val = self._reg(self._register)
        if val is None:
            return None
        try:
            return _SOCKET_OPTIONS[_SOCKET_VALUES.index(val)]
        except ValueError:
            return "Off"

    async def async_select_option(self, option: str) -> None:
        val = _SOCKET_VALUES[_SOCKET_OPTIONS.index(option)]
        await self.coordinator.async_write_register(self._register, [val])


class AquatekFilterPumpSelect(AquatekEntity, SelectEntity):
    """Speed control for the filter pump VF connector."""

    _attr_name = "Filter Pump"
    _attr_options = _FILTER_OPTIONS
    _attr_icon = "mdi:pump"

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "filter_pump")

    @property
    def current_option(self) -> str | None:
        val = self._reg(REG_FILTER_PUMP)
        if val is None:
            return None
        try:
            return _FILTER_OPTIONS[_FILTER_VALUES.index(val)]
        except ValueError:
            return "Off"

    async def async_select_option(self, option: str) -> None:
        val = _FILTER_VALUES[_FILTER_OPTIONS.index(option)]
        await self.coordinator.async_write_register(REG_FILTER_PUMP, [val])


class AquatekGasHeaterSelect(AquatekEntity, SelectEntity):
    """On/off control for the gas heater (fireman's switch output)."""

    _attr_name = "Gas Heater"
    _attr_options = _GAS_OPTIONS
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "gas_heater")

    @property
    def current_option(self) -> str | None:
        val = self._reg(REG_GAS_HEATER_CTRL)
        if val is None:
            return None
        try:
            return _GAS_OPTIONS[_GAS_VALUES.index(val)]
        except ValueError:
            return "Off"

    async def async_select_option(self, option: str) -> None:
        val = _GAS_VALUES[_GAS_OPTIONS.index(option)]
        await self.coordinator.async_write_register(REG_GAS_HEATER_CTRL, [val])
