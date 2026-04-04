"""Select entities for the Dontek Aquatek integration.

Covers:
- One socket output entity per configured socket (auto-discovered from device config).
  Options: Off / On / Auto  (register values 0 / 1 / 2)
- Filter pump speed (VF connector, reg 65485).
  Options: Off / Speed 1 / Speed 2 / Speed 3 / Speed 4 / Auto
- Pool Light Type (reg 65352 high byte): all brands from APK
- Pool Light Colour (reg 65352 low byte): dynamic list for the active light type
- VF1/VF2 heating mode (Off / Pool & Spa / Pool / Spa)
- VF1/VF2 pump type (Filter / Independent)
- VF1/VF2 sensor location (Filter / Heater Line)
- VF1/VF2 pump speed (Speed 1–4)
- VF1/VF2 smart heater protocol type (Auto / None / Theralux / Aquark / Oasis)
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    FILTER_SCHED_COUNT,
    FILTER_SCHED_SPEED_REGS,
    LIGHT_COLOURS,
    LIGHT_COLOURS_DEFAULT,
    LIGHT_TYPE_NAMES,
    REG_FILTER_PUMP,
    REG_FILTER_RUNONCE_CTRL,
    REG_SOCKET_TYPE_BASE,
    REG_VALVE_TYPE_BASE,
    REG_VF1_TYPE,
    REG_VF2_TYPE,
    SOCKET_COUNT,
    SOCKET_TYPE_OPTIONS,
    SOCKET_TYPE_VALUES,
    VALVE_COUNT,
    VALVE_TYPE_OPTIONS,
    VALVE_TYPE_VALUES,
    VF_TYPE_OPTIONS,
    VF_TYPE_VALUES,
    REG_JET_PUMP_SCHED1_ENABLE,
    REG_JET_PUMP_SCHED2_ENABLE,
    REG_POOL_LIGHT_CTRL,
    REG_POOL_SPA_MODE,
    REG_SOCKET_OUTPUT_BASE,
    REG_VF1_HEAT_MODE,
    REG_VF1_PUMP_TYPE,
    REG_VF1_SENSOR_LOC,
    REG_VF1_PUMP_SPEED,
    REG_VF1_SMART_HEATER_TYPE,
    REG_VF2_HEAT_MODE,
    REG_VF2_PUMP_TYPE,
    REG_VF2_SENSOR_LOC,
    REG_VF2_PUMP_SPEED,
    REG_VF2_SMART_HEATER_TYPE,
    SOCKET_TYPE_JET_PUMP,
    SOCKET_TYPE_POOL_LIGHT,
    SMART_HEATER_TYPE_OPTIONS,
    SMART_HEATER_TYPE_VALUES,
    VF1_PUMP_TYPE_OPTIONS,
    VF1_SENSOR_LOC_OPTIONS,
    VF1_SENSOR_LOC_VALUES,
    VF1_PUMP_SPEED_OPTIONS,
    VF1_PUMP_SPEED_VALUES,
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

    fixed: list = [
        AquatekFilterPumpSelect(coordinator),
        AquatekFilterRunOnceSpeedSelect(coordinator),
    ]
    for slot in range(FILTER_SCHED_COUNT):
        fixed.append(AquatekFilterScheduleSpeedSelect(coordinator, slot))
    data = coordinator.data or {}
    for n in range(1, SOCKET_COUNT + 1):
        fixed.append(AquatekSocketApplianceSelect(coordinator, n))
        if data.get(REG_SOCKET_TYPE_BASE + (n - 1), 0) == SOCKET_TYPE_JET_PUMP:
            fixed.append(AquatekJetPumpSchedEnableSelect(coordinator, n, 1, REG_JET_PUMP_SCHED1_ENABLE))
            fixed.append(AquatekJetPumpSchedEnableSelect(coordinator, n, 2, REG_JET_PUMP_SCHED2_ENABLE))
    fixed.append(AquatekVFContactApplianceSelect(coordinator, 1, REG_VF1_TYPE))
    fixed.append(AquatekVFContactApplianceSelect(coordinator, 2, REG_VF2_TYPE))
    for n in range(1, VALVE_COUNT + 1):
        fixed.append(AquatekValveApplianceSelect(coordinator, n))

    # Fixed entities — always present regardless of socket config
    async_add_entities(fixed + [
        AquatekPoolSpaSelect(coordinator),
        AquatekLightTypeSelect(coordinator),
        AquatekLightColourSelect(coordinator),
        AquatekVFHeatModeSelect(coordinator, "heater_1_heat_mode", "Heater 1 Mode", REG_VF1_HEAT_MODE),
        AquatekVFHeatModeSelect(coordinator, "heater_2_heat_mode", "Heater 2 Mode", REG_VF2_HEAT_MODE),
        AquatekVF1PumpTypeSelect(coordinator),
        AquatekVF1SensorLocSelect(coordinator),
        AquatekVF1PumpSpeedSelect(coordinator),
        AquatekVF2PumpTypeSelect(coordinator),
        AquatekVF2SensorLocSelect(coordinator),
        AquatekVF2PumpSpeedSelect(coordinator),
        AquatekVF1SmartHeaterTypeSelect(coordinator),
        AquatekVF2SmartHeaterTypeSelect(coordinator),
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
        self._attr_name = f"Socket {socket_n}"
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


class AquatekFilterRunOnceSpeedSelect(AquatekEntity, SelectEntity):
    """Speed for the filter pump RunOnce timer (bits 8-15 of reg 57630).

    0=Speed1, 1=Speed2, 2=Speed3, 3=Speed4 stored in the upper byte.
    Read-modify-write preserves the enable bit (bit 0) in the lower byte.
    """

    _attr_name = "Filter Run Once Speed"
    _attr_options = VF1_PUMP_SPEED_OPTIONS
    _attr_icon = "mdi:speedometer"

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "filter_runonce_speed")

    @property
    def current_option(self) -> str | None:
        val = self._reg(REG_FILTER_RUNONCE_CTRL)
        if val is None:
            return None
        speed_idx = (val >> 8) & 0xFF
        try:
            return VF1_PUMP_SPEED_OPTIONS[VF1_PUMP_SPEED_VALUES.index(speed_idx)]
        except ValueError:
            return VF1_PUMP_SPEED_OPTIONS[0]

    async def async_select_option(self, option: str) -> None:
        speed_idx = VF1_PUMP_SPEED_VALUES[VF1_PUMP_SPEED_OPTIONS.index(option)]
        current = self._reg(REG_FILTER_RUNONCE_CTRL) or 0
        await self.coordinator.async_write_register(REG_FILTER_RUNONCE_CTRL, [(current & 0x00FF) | (speed_idx << 8)])


class AquatekFilterScheduleSpeedSelect(AquatekEntity, SelectEntity):
    """Pump speed for one filter schedule slot (65473–65476, 0=Speed1..3=Speed4)."""

    _attr_options = VF1_PUMP_SPEED_OPTIONS
    _attr_icon = "mdi:speedometer"

    def __init__(self, coordinator: AquatekCoordinator, slot: int) -> None:
        slot_num = slot + 1
        super().__init__(coordinator, f"filter_schedule_{slot_num}_speed")
        self._attr_name = f"Filter Schedule {slot_num} Speed"
        self._register = FILTER_SCHED_SPEED_REGS[slot]

    @property
    def current_option(self) -> str | None:
        val = self._reg(self._register)
        if val is None:
            return None
        try:
            return VF1_PUMP_SPEED_OPTIONS[VF1_PUMP_SPEED_VALUES.index(val)]
        except ValueError:
            return VF1_PUMP_SPEED_OPTIONS[0]

    async def async_select_option(self, option: str) -> None:
        val = VF1_PUMP_SPEED_VALUES[VF1_PUMP_SPEED_OPTIONS.index(option)]
        await self.coordinator.async_write_register(self._register, [val])


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


class _AquatekVFPumpTypeSelect(AquatekEntity, SelectEntity):
    """Base for VF pump type selects (Filter / Independent).

    Both VF1 and VF2 share the same packed register encoding:
      0 = Filter; 1 = Independent+FilterSensor; 2 = Independent+HeaterLineSensor.
    Switching to Independent preserves the existing sensor location if already set.
    """

    _attr_options = VF1_PUMP_TYPE_OPTIONS
    _attr_icon = "mdi:pump"
    _register: int

    @property
    def current_option(self) -> str | None:
        val = self._reg(self._register)
        if val is None:
            return None
        return VF1_PUMP_TYPE_OPTIONS[0] if val == 0 else VF1_PUMP_TYPE_OPTIONS[1]

    async def async_select_option(self, option: str) -> None:
        if option == VF1_PUMP_TYPE_OPTIONS[0]:
            await self.coordinator.async_write_register(self._register, [0])
        else:
            current = self._reg(self._register) or 0
            val = current if current in (1, 2) else 1
            await self.coordinator.async_write_register(self._register, [val])


class AquatekVF1PumpTypeSelect(_AquatekVFPumpTypeSelect):
    """VF1 (Heater 1) pump type select."""

    _attr_name = "Heater 1 Pump Type"
    _register = REG_VF1_PUMP_TYPE

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_1_pump_type")


class _AquatekVFSensorLocSelect(AquatekEntity, SelectEntity):
    """Base for VF sensor location selects (Filter / Heater Line).

    Both VF1 and VF2 share the same register encoding: 1=Filter, 2=Heater Line.
    Only meaningful when the corresponding pump type is Independent.
    """

    _attr_options = VF1_SENSOR_LOC_OPTIONS
    _attr_icon = "mdi:thermometer-water"
    _register: int

    @property
    def current_option(self) -> str | None:
        val = self._reg(self._register)
        if val is None or val == 0:
            return None
        try:
            return VF1_SENSOR_LOC_OPTIONS[VF1_SENSOR_LOC_VALUES.index(val)]
        except ValueError:
            return VF1_SENSOR_LOC_OPTIONS[0]

    async def async_select_option(self, option: str) -> None:
        val = VF1_SENSOR_LOC_VALUES[VF1_SENSOR_LOC_OPTIONS.index(option)]
        await self.coordinator.async_write_register(self._register, [val])


class AquatekVF1SensorLocSelect(_AquatekVFSensorLocSelect):
    """VF1 (Heater 1) sensor location select."""

    _attr_name = "Heater 1 Sensor Location"
    _register = REG_VF1_SENSOR_LOC

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_1_sensor_location")


class _AquatekVFPumpSpeedSelect(AquatekEntity, SelectEntity):
    """Base for VF pump speed selects (Speed 1–4, Independent pump only)."""

    _attr_options = VF1_PUMP_SPEED_OPTIONS
    _attr_icon = "mdi:speedometer"
    _register: int

    @property
    def current_option(self) -> str | None:
        val = self._reg(self._register)
        if val is None:
            return None
        try:
            return VF1_PUMP_SPEED_OPTIONS[VF1_PUMP_SPEED_VALUES.index(val)]
        except ValueError:
            return "Speed 1"

    async def async_select_option(self, option: str) -> None:
        val = VF1_PUMP_SPEED_VALUES[VF1_PUMP_SPEED_OPTIONS.index(option)]
        await self.coordinator.async_write_register(self._register, [val])


class AquatekVF1PumpSpeedSelect(_AquatekVFPumpSpeedSelect):
    """VF1 (Heater 1) pump speed select."""

    _attr_name = "Heater 1 Pump Speed"
    _register = REG_VF1_PUMP_SPEED

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_1_pump_speed")


class AquatekVF2PumpTypeSelect(_AquatekVFPumpTypeSelect):
    """VF2 (Heater 2) pump type select."""

    _attr_name = "Heater 2 Pump Type"
    _register = REG_VF2_PUMP_TYPE

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_2_pump_type")


class AquatekVF2SensorLocSelect(_AquatekVFSensorLocSelect):
    """VF2 (Heater 2) sensor location select."""

    _attr_name = "Heater 2 Sensor Location"
    _register = REG_VF2_SENSOR_LOC

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_2_sensor_location")


class AquatekVF2PumpSpeedSelect(_AquatekVFPumpSpeedSelect):
    """VF2 (Heater 2) pump speed select."""

    _attr_name = "Heater 2 Pump Speed"
    _register = REG_VF2_PUMP_SPEED

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_2_pump_speed")


class _AquatekVFSmartHeaterTypeSelect(AquatekEntity, SelectEntity):
    """Base for VF smart heater type selects."""

    _attr_options = SMART_HEATER_TYPE_OPTIONS
    _attr_icon = "mdi:chip"
    _register: int

    @property
    def current_option(self) -> str | None:
        val = self._reg(self._register)
        if val is None:
            return None
        try:
            return SMART_HEATER_TYPE_OPTIONS[SMART_HEATER_TYPE_VALUES.index(val)]
        except ValueError:
            return "Auto"

    async def async_select_option(self, option: str) -> None:
        val = SMART_HEATER_TYPE_VALUES[SMART_HEATER_TYPE_OPTIONS.index(option)]
        await self.coordinator.async_write_register(self._register, [val])


class AquatekVF1SmartHeaterTypeSelect(_AquatekVFSmartHeaterTypeSelect):
    """VF1 (Heater 1) smart heater protocol type."""

    _attr_name = "Heater 1 Smart Heater Type"
    _register = REG_VF1_SMART_HEATER_TYPE

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_1_smart_heater_type")


class AquatekVF2SmartHeaterTypeSelect(_AquatekVFSmartHeaterTypeSelect):
    """VF2 (Heater 2) smart heater protocol type."""

    _attr_name = "Heater 2 Smart Heater Type"
    _register = REG_VF2_SMART_HEATER_TYPE

    def __init__(self, coordinator: AquatekCoordinator) -> None:
        super().__init__(coordinator, "heater_2_smart_heater_type")


_JET_PUMP_SCHED_ENABLE_OPTIONS = ["Off", "Gas Heater", "Heat Pump"]
_JET_PUMP_SCHED_ENABLE_VALUES = [0, 1, 257]


class AquatekJetPumpSchedEnableSelect(AquatekEntity, SelectEntity):
    """Schedule enable for a Jet Pump socket — tri-state: Off / Gas Heater / Heat Pump.

    0=Off, 1=Gas Heater (VF1), 257=Heat Pump (VF2).
    """

    _attr_options = _JET_PUMP_SCHED_ENABLE_OPTIONS
    _attr_icon = "mdi:calendar-clock"

    def __init__(
        self,
        coordinator: AquatekCoordinator,
        socket_n: int,
        sched_num: int,
        register: int,
    ) -> None:
        super().__init__(coordinator, f"socket_{socket_n}_schedule_{sched_num}_enable")
        self._attr_name = f"Socket {socket_n} Schedule {sched_num} Enable"
        self._register = register

    @property
    def current_option(self) -> str | None:
        val = self._reg(self._register)
        if val is None:
            return None
        try:
            return _JET_PUMP_SCHED_ENABLE_OPTIONS[_JET_PUMP_SCHED_ENABLE_VALUES.index(val)]
        except ValueError:
            return "Off"

    async def async_select_option(self, option: str) -> None:
        val = _JET_PUMP_SCHED_ENABLE_VALUES[_JET_PUMP_SCHED_ENABLE_OPTIONS.index(option)]
        await self.coordinator.async_write_register(self._register, [val])


class AquatekSocketApplianceSelect(AquatekEntity, SelectEntity):
    """Appliance assignment for a socket (reg 65323+(n-1), values 0–14)."""

    _attr_options = SOCKET_TYPE_OPTIONS
    _attr_icon = "mdi:power-socket"

    def __init__(self, coordinator: AquatekCoordinator, socket_n: int) -> None:
        super().__init__(coordinator, f"socket_{socket_n}_appliance")
        self._attr_name = f"Socket {socket_n} Appliance"
        self._register = REG_SOCKET_TYPE_BASE + (socket_n - 1)

    @property
    def current_option(self) -> str | None:
        val = self._reg(self._register)
        if val is None:
            return None
        try:
            return SOCKET_TYPE_OPTIONS[SOCKET_TYPE_VALUES.index(val)]
        except ValueError:
            return SOCKET_TYPE_OPTIONS[0]

    async def async_select_option(self, option: str) -> None:
        val = SOCKET_TYPE_VALUES[SOCKET_TYPE_OPTIONS.index(option)]
        await self.coordinator.async_write_register(self._register, [val])


class AquatekVFContactApplianceSelect(AquatekEntity, SelectEntity):
    """Appliance assignment for a VF contact port (None / Gas Heater / Heat Pump)."""

    _attr_options = VF_TYPE_OPTIONS
    _attr_icon = "mdi:heat-wave"

    def __init__(self, coordinator: AquatekCoordinator, vf_n: int, register: int) -> None:
        super().__init__(coordinator, f"vf_{vf_n}_appliance")
        self._attr_name = f"VF {vf_n} Appliance"
        self._register = register

    @property
    def current_option(self) -> str | None:
        val = self._reg(self._register)
        if val is None:
            return None
        try:
            return VF_TYPE_OPTIONS[VF_TYPE_VALUES.index(val)]
        except ValueError:
            return VF_TYPE_OPTIONS[0]

    async def async_select_option(self, option: str) -> None:
        val = VF_TYPE_VALUES[VF_TYPE_OPTIONS.index(option)]
        await self.coordinator.async_write_register(self._register, [val])


class AquatekValveApplianceSelect(AquatekEntity, SelectEntity):
    """Appliance assignment for a valve output (reg 65331+(n-1), values 0–7)."""

    _attr_options = VALVE_TYPE_OPTIONS
    _attr_icon = "mdi:valve"

    def __init__(self, coordinator: AquatekCoordinator, valve_n: int) -> None:
        super().__init__(coordinator, f"valve_{valve_n}_appliance")
        self._attr_name = f"Valve {valve_n} Appliance"
        self._register = REG_VALVE_TYPE_BASE + (valve_n - 1)

    @property
    def current_option(self) -> str | None:
        val = self._reg(self._register)
        if val is None:
            return None
        try:
            return VALVE_TYPE_OPTIONS[VALVE_TYPE_VALUES.index(val)]
        except ValueError:
            return VALVE_TYPE_OPTIONS[0]

    async def async_select_option(self, option: str) -> None:
        val = VALVE_TYPE_VALUES[VALVE_TYPE_OPTIONS.index(option)]
        await self.coordinator.async_write_register(self._register, [val])
