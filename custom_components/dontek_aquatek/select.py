"""Select entities for the Dontek Aquatek integration.

Covers:
- One socket output entity per configured socket (auto-discovered from device config).
  Options: Off / On / Auto  (register values 0 / 1 / 2)
- Filter pump speed (VF connector, reg 65485).
  Options: Off / Speed 1 / Speed 2 / Speed 3 / Speed 4 / Auto
- Pool Light Type (reg 65352 high byte): all brands from APK
- Pool Light Colour (reg 65352 low byte): dynamic list for the active light type
- VF1/VF2 heating mode (Off / Pool & Spa / Pool / Spa)
- VF1 pump type (Filter / Independent)
- VF2 pump type+sensor (Filter / Independent+Filter / Independent+HeaterLine)
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    LIGHT_COLOURS,
    LIGHT_COLOURS_DEFAULT,
    LIGHT_TYPE_NAMES,
    REG_FILTER_PUMP,
    REG_POOL_LIGHT_CTRL,
    REG_POOL_SPA_MODE,
    REG_SOCKET_OUTPUT_BASE,
    REG_VF1_HEAT_MODE,
    REG_VF1_PUMP_TYPE,
    REG_VF1_PUMP_SPEED,
    REG_VF2_HEAT_MODE,
    REG_VF2_PUMP_TYPE,
    REG_VF2_SENSOR_LOC,
    SOCKET_TYPE_NAMES,
    SOCKET_TYPE_POOL_LIGHT,
    VF1_PUMP_TYPE_OPTIONS,
    VF1_PUMP_TYPE_VALUES,
    VF1_PUMP_SPEED_OPTIONS,
    VF1_PUMP_SPEED_VALUES,
    VF2_PUMP_TYPE_OPTIONS,
    VF2_SENSOR_LOC_OPTIONS,
    VF2_SENSOR_LOC_VALUES,
    VF_HEAT_MODE_OPTIONS,
    VF_HEAT_MODE_VALUES,
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
# Pool / Spa mode

_POOL_SPA_OPTIONS = ["Pool", "Spa"]
_POOL_SPA_VALUES = [0, 1]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AquatekCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Fixed entities — always present regardless of socket config
    async_add_entities([
        AquatekFilterPumpSelect(coordinator),
        AquatekPoolSpaSelect(coordinator),
        AquatekLightTypeSelect(coordinator),
        AquatekLightColourSelect(coordinator),
        AquatekVFHeatModeSelect(coordinator, "heater_1_heat_mode", "Heater 1 Mode", REG_VF1_HEAT_MODE),
        AquatekVFHeatModeSelect(coordinator, "heater_2_heat_mode", "Heater 2 Mode", REG_VF2_HEAT_MODE),
        AquatekVF1PumpTypeSelect(coordinator),
        AquatekVF1PumpSpeedSelect(coordinator),
        AquatekVF2PumpTypeSelect(coordinator),
        AquatekVF2SensorLocSelect(coordinator),
    ])

    # Socket entities are auto-discovered from device config registers.
    # If data is already available, add them now; otherwise a coordinator
    # listener will add them on the first update (handles timeout case).
    discovered: set[int] = set()

    def _add_new_sockets() -> None:
        new = [
            AquatekSocketSelect(coordinator, n, t)
            for n, t in coordinator.get_socket_configs().items()
            if n not in discovered
        ]
        if new:
            for entity in new:
                discovered.add(entity._socket_n)
            async_add_entities(new)

    # Add any sockets available right now
    _add_new_sockets()

    # Register listener for sockets that arrive after initial timeout
    @callback
    def _on_coordinator_update() -> None:
        _add_new_sockets()

    entry.async_on_unload(coordinator.async_add_listener(_on_coordinator_update))


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
        self._socket_n = socket_n
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



class AquatekPoolSpaSelect(AquatekEntity, SelectEntity):
    """Pool / Spa mode switch (reg 65313: 0=Pool, 1=Spa)."""

    _attr_name = "Pool/Spa Mode"
    _attr_options = _POOL_SPA_OPTIONS
    _attr_icon = "mdi:pool"

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "pool_spa_mode")

    @property
    def current_option(self) -> str | None:
        val = self._reg(REG_POOL_SPA_MODE)
        if val is None:
            return None
        try:
            return _POOL_SPA_OPTIONS[_POOL_SPA_VALUES.index(val)]
        except ValueError:
            return "Pool"

    async def async_select_option(self, option: str) -> None:
        val = _POOL_SPA_VALUES[_POOL_SPA_OPTIONS.index(option)]
        await self.coordinator.async_write_register(REG_POOL_SPA_MODE, [val])


class AquatekLightTypeSelect(AquatekEntity, SelectEntity):
    """Selects the light brand/type for the pool light (reg 65352 high byte).

    Preserves the current colour index when switching type.
    """

    _attr_name = "Pool Light Type"
    _attr_options = list(LIGHT_TYPE_NAMES.values())
    _attr_icon = "mdi:lightbulb-multiple"

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "pool_light_type")

    @property
    def current_option(self) -> str | None:
        val = self._reg(REG_POOL_LIGHT_CTRL)
        if val is None:
            return None
        return LIGHT_TYPE_NAMES.get(val >> 8)

    async def async_select_option(self, option: str) -> None:
        type_val = next((k for k, v in LIGHT_TYPE_NAMES.items() if v == option), None)
        if type_val is None:
            return
        current = self._reg(REG_POOL_LIGHT_CTRL) or 0
        colour_idx = current & 0xFF
        await self.coordinator.async_write_register(REG_POOL_LIGHT_CTRL, [(type_val << 8) | colour_idx])


class AquatekLightColourSelect(AquatekEntity, SelectEntity):
    """Selects the colour/mode for the pool light (reg 65352 low byte).

    Preserves the current light type when changing colour.
    Options are dynamically derived from the current light type.
    """

    _attr_name = "Pool Light Colour"
    _attr_icon = "mdi:palette"

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "pool_light_colour")

    def _colours(self) -> list[str]:
        val = self._reg(REG_POOL_LIGHT_CTRL)
        if val is None:
            return LIGHT_COLOURS_DEFAULT
        return LIGHT_COLOURS.get(val >> 8, LIGHT_COLOURS_DEFAULT)

    @property
    def options(self) -> list[str]:
        return self._colours()

    @property
    def current_option(self) -> str | None:
        val = self._reg(REG_POOL_LIGHT_CTRL)
        if val is None:
            return None
        colours = self._colours()
        colour_idx = val & 0xFF
        if colour_idx >= len(colours):
            return None
        return colours[colour_idx]

    async def async_select_option(self, option: str) -> None:
        colours = self._colours()
        if option not in colours:
            return
        colour_idx = colours.index(option)
        current = self._reg(REG_POOL_LIGHT_CTRL) or 0
        light_type = current >> 8
        await self.coordinator.async_write_register(REG_POOL_LIGHT_CTRL, [(light_type << 8) | colour_idx])


class AquatekVFHeatModeSelect(AquatekEntity, SelectEntity):
    """Heating mode for a VF port: Off / Pool & Spa / Pool / Spa."""

    _attr_options = VF_HEAT_MODE_OPTIONS
    _attr_icon = "mdi:radiator"

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
    def current_option(self) -> str | None:
        val = self._reg(self._register)
        if val is None:
            return None
        try:
            return VF_HEAT_MODE_OPTIONS[VF_HEAT_MODE_VALUES.index(val)]
        except ValueError:
            return "Off"

    async def async_select_option(self, option: str) -> None:
        val = VF_HEAT_MODE_VALUES[VF_HEAT_MODE_OPTIONS.index(option)]
        await self.coordinator.async_write_register(self._register, [val])


class AquatekVF1PumpTypeSelect(AquatekEntity, SelectEntity):
    """VF1 pump type: Filter or Independent (reg 65450)."""

    _attr_name = "Heater 1 Pump Type"
    _attr_options = VF1_PUMP_TYPE_OPTIONS
    _attr_icon = "mdi:pump"

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_1_pump_type")

    @property
    def current_option(self) -> str | None:
        val = self._reg(REG_VF1_PUMP_TYPE)
        if val is None:
            return None
        try:
            return VF1_PUMP_TYPE_OPTIONS[VF1_PUMP_TYPE_VALUES.index(val)]
        except ValueError:
            return "Filter"

    async def async_select_option(self, option: str) -> None:
        val = VF1_PUMP_TYPE_VALUES[VF1_PUMP_TYPE_OPTIONS.index(option)]
        await self.coordinator.async_write_register(REG_VF1_PUMP_TYPE, [val])


class AquatekVF1PumpSpeedSelect(AquatekEntity, SelectEntity):
    """VF1 pump speed: Speed 1–4 (reg 65462, Independent pump only)."""

    _attr_name = "Heater 1 Pump Speed"
    _attr_options = VF1_PUMP_SPEED_OPTIONS
    _attr_icon = "mdi:speedometer"

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_1_pump_speed")

    @property
    def current_option(self) -> str | None:
        val = self._reg(REG_VF1_PUMP_SPEED)
        if val is None:
            return None
        try:
            return VF1_PUMP_SPEED_OPTIONS[VF1_PUMP_SPEED_VALUES.index(val)]
        except ValueError:
            return "Speed 1"

    async def async_select_option(self, option: str) -> None:
        val = VF1_PUMP_SPEED_VALUES[VF1_PUMP_SPEED_OPTIONS.index(option)]
        await self.coordinator.async_write_register(REG_VF1_PUMP_SPEED, [val])


class AquatekVF2PumpTypeSelect(AquatekEntity, SelectEntity):
    """VF2 pump type: Filter or Independent (reg 57574, upper decode).

    0=Filter; 1 or 2=Independent (sensor loc encoded in same reg).
    When switching to Independent, preserves existing sensor location if set.
    """

    _attr_name = "Heater 2 Pump Type"
    _attr_options = VF2_PUMP_TYPE_OPTIONS
    _attr_icon = "mdi:pump"

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_2_pump_type")

    @property
    def current_option(self) -> str | None:
        val = self._reg(REG_VF2_PUMP_TYPE)
        if val is None:
            return None
        return "Filter" if val == 0 else "Independent"

    async def async_select_option(self, option: str) -> None:
        if option == "Filter":
            await self.coordinator.async_write_register(REG_VF2_PUMP_TYPE, [0])
        else:
            # Independent: preserve current sensor loc (1 or 2); default to 1
            current = self._reg(REG_VF2_PUMP_TYPE) or 0
            val = current if current in (1, 2) else 1
            await self.coordinator.async_write_register(REG_VF2_PUMP_TYPE, [val])


class AquatekVF2SensorLocSelect(AquatekEntity, SelectEntity):
    """VF2 sensor location: Filter or Heater Line (reg 57574, lower decode).

    1=Filter sensor, 2=Heater Line. Only meaningful when pump type=Independent.
    """

    _attr_name = "Heater 2 Sensor Location"
    _attr_options = VF2_SENSOR_LOC_OPTIONS
    _attr_icon = "mdi:thermometer-water"

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_2_sensor_location")

    @property
    def current_option(self) -> str | None:
        val = self._reg(REG_VF2_SENSOR_LOC)
        if val is None or val == 0:
            return None
        try:
            return VF2_SENSOR_LOC_OPTIONS[VF2_SENSOR_LOC_VALUES.index(val)]
        except ValueError:
            return "Filter"

    async def async_select_option(self, option: str) -> None:
        val = VF2_SENSOR_LOC_VALUES[VF2_SENSOR_LOC_OPTIONS.index(option)]
        await self.coordinator.async_write_register(REG_VF2_SENSOR_LOC, [val])
