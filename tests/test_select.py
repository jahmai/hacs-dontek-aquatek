"""Tests for select.py — current_option logic for all select entities."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.dontek_aquatek.select import (
    AquatekFilterPumpSelect,
    AquatekFilterRunOnceSpeedSelect,
    AquatekFilterScheduleSpeedSelect,
    AquatekLightColourSelect,
    AquatekLightTypeSelect,
    AquatekPoolSpaSelect,
    AquatekSocketApplianceSelect,
    AquatekSocketSelect,
    AquatekVF1PumpSpeedSelect,
    AquatekVF1PumpTypeSelect,
    AquatekVF1SensorLocSelect,
    AquatekVF1SmartHeaterTypeSelect,
    AquatekVF2PumpTypeSelect,
    AquatekVF2SensorLocSelect,
    AquatekVF2SmartHeaterTypeSelect,
    AquatekVFContactApplianceSelect,
    AquatekVFHeatModeSelect,
    AquatekValveApplianceSelect,
)
from custom_components.dontek_aquatek.const import (
    FILTER_SCHED_SPEED_REGS,
    LIGHT_TYPE_AQUAQUIP,
    LIGHT_TYPE_AQUAQUIP_INSTATOUCH,
    LIGHT_TYPE_SINGLE_COLOUR,
    REG_FILTER_PUMP,
    REG_FILTER_RUNONCE_CTRL,
    REG_POOL_LIGHT_CTRL,
    REG_POOL_SPA_MODE,
    REG_SOCKET_TYPE_BASE,
    REG_VALVE_TYPE_BASE,
    REG_VF1_HEAT_MODE,
    REG_VF1_PUMP_TYPE,
    REG_VF1_PUMP_SPEED,
    REG_VF1_SENSOR_LOC,
    REG_VF1_SMART_HEATER_TYPE,
    REG_VF1_TYPE,
    REG_VF2_PUMP_TYPE,
    REG_VF2_SENSOR_LOC,
    REG_VF2_SMART_HEATER_TYPE,
    REG_VF2_TYPE,
    SOCKET_TYPE_POOL_LIGHT,
    SOCKET_TYPE_SANITISER,
)


# ---------------------------------------------------------------------------
# Helpers

def _make_coordinator(registers: dict) -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = registers
    coordinator.async_write_register = AsyncMock()
    return coordinator


def _reg(coordinator, r):
    return coordinator.data.get(r)


def _socket_select(socket_n: int, type_idx: int, registers: dict) -> AquatekSocketSelect:
    coordinator = _make_coordinator(registers)
    sel = AquatekSocketSelect.__new__(AquatekSocketSelect)
    sel.coordinator = coordinator
    sel._socket_n = socket_n
    sel._register = 65336 + (socket_n - 1)
    sel._reg = lambda r: _reg(coordinator, r)
    sel._on_value = 1 if type_idx == SOCKET_TYPE_POOL_LIGHT else 2
    return sel


def _filter_select(registers: dict) -> AquatekFilterPumpSelect:
    coordinator = _make_coordinator(registers)
    sel = AquatekFilterPumpSelect.__new__(AquatekFilterPumpSelect)
    sel.coordinator = coordinator
    sel._reg = lambda r: _reg(coordinator, r)
    return sel


def _pool_spa_select(registers: dict) -> AquatekPoolSpaSelect:
    coordinator = _make_coordinator(registers)
    sel = AquatekPoolSpaSelect.__new__(AquatekPoolSpaSelect)
    sel.coordinator = coordinator
    sel._reg = lambda r: _reg(coordinator, r)
    return sel


def _light_type_select(registers: dict) -> AquatekLightTypeSelect:
    coordinator = _make_coordinator(registers)
    sel = AquatekLightTypeSelect.__new__(AquatekLightTypeSelect)
    sel.coordinator = coordinator
    sel._reg = lambda r: _reg(coordinator, r)
    return sel


def _light_colour_select(registers: dict) -> AquatekLightColourSelect:
    coordinator = _make_coordinator(registers)
    sel = AquatekLightColourSelect.__new__(AquatekLightColourSelect)
    sel.coordinator = coordinator
    sel._reg = lambda r: _reg(coordinator, r)
    return sel


def _vf_heat_mode_select(register: int, registers: dict) -> AquatekVFHeatModeSelect:
    coordinator = _make_coordinator(registers)
    sel = AquatekVFHeatModeSelect.__new__(AquatekVFHeatModeSelect)
    sel.coordinator = coordinator
    sel._register = register
    sel._reg = lambda r: _reg(coordinator, r)
    return sel


def _vf1_pump_type_select(registers: dict) -> AquatekVF1PumpTypeSelect:
    coordinator = _make_coordinator(registers)
    sel = AquatekVF1PumpTypeSelect.__new__(AquatekVF1PumpTypeSelect)
    sel.coordinator = coordinator
    sel._reg = lambda r: _reg(coordinator, r)
    return sel


def _vf1_sensor_loc_select(registers: dict) -> AquatekVF1SensorLocSelect:
    coordinator = _make_coordinator(registers)
    sel = AquatekVF1SensorLocSelect.__new__(AquatekVF1SensorLocSelect)
    sel.coordinator = coordinator
    sel._reg = lambda r: _reg(coordinator, r)
    return sel


def _vf1_pump_speed_select(registers: dict) -> AquatekVF1PumpSpeedSelect:
    coordinator = _make_coordinator(registers)
    sel = AquatekVF1PumpSpeedSelect.__new__(AquatekVF1PumpSpeedSelect)
    sel.coordinator = coordinator
    sel._reg = lambda r: _reg(coordinator, r)
    return sel


def _vf2_pump_type_select(registers: dict) -> AquatekVF2PumpTypeSelect:
    coordinator = _make_coordinator(registers)
    sel = AquatekVF2PumpTypeSelect.__new__(AquatekVF2PumpTypeSelect)
    sel.coordinator = coordinator
    sel._reg = lambda r: _reg(coordinator, r)
    return sel


def _vf2_sensor_loc_select(registers: dict) -> AquatekVF2SensorLocSelect:
    coordinator = _make_coordinator(registers)
    sel = AquatekVF2SensorLocSelect.__new__(AquatekVF2SensorLocSelect)
    sel.coordinator = coordinator
    sel._reg = lambda r: _reg(coordinator, r)
    return sel


# ---------------------------------------------------------------------------
# AquatekSocketSelect

def test_socket_select_off():
    assert _socket_select(1, SOCKET_TYPE_SANITISER, {65336: 0}).current_option == "Off"


def test_socket_select_on():
    assert _socket_select(1, SOCKET_TYPE_SANITISER, {65336: 1}).current_option == "On"


def test_socket_select_auto():
    assert _socket_select(1, SOCKET_TYPE_SANITISER, {65336: 2}).current_option == "Auto"


def test_socket_select_none_when_no_data():
    assert _socket_select(1, SOCKET_TYPE_SANITISER, {}).current_option is None


def test_socket_select_unknown_value_defaults_to_off():
    assert _socket_select(1, SOCKET_TYPE_SANITISER, {65336: 99}).current_option == "Off"


def test_socket_select_socket_4_reads_correct_register():
    # Socket 4 → register 65339
    assert _socket_select(4, SOCKET_TYPE_SANITISER, {65339: 1}).current_option == "On"


# ---------------------------------------------------------------------------
# AquatekFilterPumpSelect

def test_filter_pump_off():
    assert _filter_select({REG_FILTER_PUMP: 0}).current_option == "Off"


def test_filter_pump_speed1():
    assert _filter_select({REG_FILTER_PUMP: 257}).current_option == "Speed 1"


def test_filter_pump_speed4():
    assert _filter_select({REG_FILTER_PUMP: 1025}).current_option == "Speed 4"


def test_filter_pump_auto():
    assert _filter_select({REG_FILTER_PUMP: 65535}).current_option == "Auto"


def test_filter_pump_none_when_no_data():
    assert _filter_select({}).current_option is None


def test_filter_pump_unknown_defaults_to_off():
    assert _filter_select({REG_FILTER_PUMP: 42}).current_option == "Off"


# ---------------------------------------------------------------------------
# AquatekPoolSpaSelect

def test_pool_spa_pool():
    assert _pool_spa_select({REG_POOL_SPA_MODE: 0}).current_option == "Pool"


def test_pool_spa_spa():
    assert _pool_spa_select({REG_POOL_SPA_MODE: 1}).current_option == "Spa"


def test_pool_spa_none_when_no_data():
    assert _pool_spa_select({}).current_option is None


def test_pool_spa_unknown_defaults_to_pool():
    assert _pool_spa_select({REG_POOL_SPA_MODE: 99}).current_option == "Pool"


# ---------------------------------------------------------------------------
# AquatekLightTypeSelect

def test_light_type_aquaquip():
    # type index 2 in high byte
    val = LIGHT_TYPE_AQUAQUIP << 8
    assert _light_type_select({REG_POOL_LIGHT_CTRL: val}).current_option == "Aquaquip"


def test_light_type_instatouch():
    val = LIGHT_TYPE_AQUAQUIP_INSTATOUCH << 8
    assert _light_type_select({REG_POOL_LIGHT_CTRL: val}).current_option == "Aquaquip Instatouch"


def test_light_type_preserves_colour_index():
    # High byte=2 (Aquaquip), low byte=3 (4th colour)
    val = (LIGHT_TYPE_AQUAQUIP << 8) | 3
    assert _light_type_select({REG_POOL_LIGHT_CTRL: val}).current_option == "Aquaquip"


def test_light_type_none_when_no_data():
    assert _light_type_select({}).current_option is None


# ---------------------------------------------------------------------------
# AquatekLightColourSelect

def test_light_colour_options_for_aquaquip_instatouch():
    val = LIGHT_TYPE_AQUAQUIP_INSTATOUCH << 8
    sel = _light_colour_select({REG_POOL_LIGHT_CTRL: val})
    opts = sel.options
    assert "Blue" in opts
    assert "Disco" in opts
    assert len(opts) == 13


def test_light_colour_current_option():
    # Aquaquip Instatouch (type 3), colour index 1 → "Aqua"
    val = (LIGHT_TYPE_AQUAQUIP_INSTATOUCH << 8) | 1
    assert _light_colour_select({REG_POOL_LIGHT_CTRL: val}).current_option == "Aqua"


def test_light_colour_index_out_of_range_returns_none():
    # Single Colour type has only 1 colour; index 5 is out of range
    val = (LIGHT_TYPE_SINGLE_COLOUR << 8) | 5
    assert _light_colour_select({REG_POOL_LIGHT_CTRL: val}).current_option is None


def test_light_colour_none_when_no_data():
    assert _light_colour_select({}).current_option is None


def test_light_colour_fallback_options_for_unknown_type():
    # Type 0 is not in LIGHT_COLOURS → should fall back to default
    val = 0 << 8
    sel = _light_colour_select({REG_POOL_LIGHT_CTRL: val})
    assert sel.options == ["Colour 0"]


# ---------------------------------------------------------------------------
# AquatekVFHeatModeSelect

def test_vf_heat_mode_off():
    assert _vf_heat_mode_select(REG_VF1_HEAT_MODE, {REG_VF1_HEAT_MODE: 0}).current_option == "Off"


def test_vf_heat_mode_pool_and_spa():
    assert _vf_heat_mode_select(REG_VF1_HEAT_MODE, {REG_VF1_HEAT_MODE: 2}).current_option == "Pool & Spa"


def test_vf_heat_mode_pool():
    assert _vf_heat_mode_select(REG_VF1_HEAT_MODE, {REG_VF1_HEAT_MODE: 3}).current_option == "Pool"


def test_vf_heat_mode_spa():
    assert _vf_heat_mode_select(REG_VF1_HEAT_MODE, {REG_VF1_HEAT_MODE: 4}).current_option == "Spa"


def test_vf_heat_mode_unknown_defaults_to_off():
    assert _vf_heat_mode_select(REG_VF1_HEAT_MODE, {REG_VF1_HEAT_MODE: 99}).current_option == "Off"


def test_vf_heat_mode_none_when_no_data():
    assert _vf_heat_mode_select(REG_VF1_HEAT_MODE, {}).current_option is None


# ---------------------------------------------------------------------------
# AquatekVF1PumpTypeSelect

def test_vf1_pump_type_filter():
    assert _vf1_pump_type_select({REG_VF1_PUMP_TYPE: 0}).current_option == "Filter"


def test_vf1_pump_type_independent_val_1():
    assert _vf1_pump_type_select({REG_VF1_PUMP_TYPE: 1}).current_option == "Independent"


def test_vf1_pump_type_independent_val_2():
    assert _vf1_pump_type_select({REG_VF1_PUMP_TYPE: 2}).current_option == "Independent"


def test_vf1_pump_type_none_when_no_data():
    assert _vf1_pump_type_select({}).current_option is None


@pytest.mark.asyncio
async def test_vf1_pump_type_switch_to_filter_writes_zero():
    sel = _vf1_pump_type_select({REG_VF1_PUMP_TYPE: 2})
    await sel.async_select_option("Filter")
    sel.coordinator.async_write_register.assert_awaited_once_with(REG_VF1_PUMP_TYPE, [0])


@pytest.mark.asyncio
async def test_vf1_pump_type_switch_to_independent_preserves_sensor_loc():
    # Current val=2 (Independent+HeaterLine) — switching to Independent should keep 2
    sel = _vf1_pump_type_select({REG_VF1_PUMP_TYPE: 2})
    await sel.async_select_option("Independent")
    sel.coordinator.async_write_register.assert_awaited_once_with(REG_VF1_PUMP_TYPE, [2])


@pytest.mark.asyncio
async def test_vf1_pump_type_switch_to_independent_defaults_sensor_loc_when_filter():
    # Current val=0 (Filter) — switching to Independent defaults to 1 (FilterSensor)
    sel = _vf1_pump_type_select({REG_VF1_PUMP_TYPE: 0})
    await sel.async_select_option("Independent")
    sel.coordinator.async_write_register.assert_awaited_once_with(REG_VF1_PUMP_TYPE, [1])


# ---------------------------------------------------------------------------
# AquatekVF1SensorLocSelect

def test_vf1_sensor_loc_filter():
    assert _vf1_sensor_loc_select({REG_VF1_SENSOR_LOC: 1}).current_option == "Filter"


def test_vf1_sensor_loc_heater_line():
    assert _vf1_sensor_loc_select({REG_VF1_SENSOR_LOC: 2}).current_option == "Heater Line"


def test_vf1_sensor_loc_none_when_zero():
    assert _vf1_sensor_loc_select({REG_VF1_SENSOR_LOC: 0}).current_option is None


def test_vf1_sensor_loc_none_when_no_data():
    assert _vf1_sensor_loc_select({}).current_option is None


# ---------------------------------------------------------------------------
# AquatekVF1PumpSpeedSelect

def test_vf1_pump_speed_1():
    assert _vf1_pump_speed_select({REG_VF1_PUMP_SPEED: 0}).current_option == "Speed 1"


def test_vf1_pump_speed_4():
    assert _vf1_pump_speed_select({REG_VF1_PUMP_SPEED: 3}).current_option == "Speed 4"


def test_vf1_pump_speed_none_when_no_data():
    assert _vf1_pump_speed_select({}).current_option is None


def test_vf1_pump_speed_unknown_defaults_to_speed1():
    assert _vf1_pump_speed_select({REG_VF1_PUMP_SPEED: 99}).current_option == "Speed 1"


# ---------------------------------------------------------------------------
# AquatekVF2PumpTypeSelect (mirrors VF1 logic)

def test_vf2_pump_type_filter():
    assert _vf2_pump_type_select({REG_VF2_PUMP_TYPE: 0}).current_option == "Filter"


def test_vf2_pump_type_independent():
    assert _vf2_pump_type_select({REG_VF2_PUMP_TYPE: 1}).current_option == "Independent"


def test_vf2_pump_type_independent_val_2():
    assert _vf2_pump_type_select({REG_VF2_PUMP_TYPE: 2}).current_option == "Independent"


@pytest.mark.asyncio
async def test_vf2_pump_type_switch_to_independent_preserves_sensor_loc():
    sel = _vf2_pump_type_select({REG_VF2_PUMP_TYPE: 2})
    await sel.async_select_option("Independent")
    sel.coordinator.async_write_register.assert_awaited_once_with(REG_VF2_PUMP_TYPE, [2])


@pytest.mark.asyncio
async def test_vf2_pump_type_switch_to_independent_defaults_when_filter():
    sel = _vf2_pump_type_select({REG_VF2_PUMP_TYPE: 0})
    await sel.async_select_option("Independent")
    sel.coordinator.async_write_register.assert_awaited_once_with(REG_VF2_PUMP_TYPE, [1])


# ---------------------------------------------------------------------------
# AquatekVF2SensorLocSelect

def test_vf2_sensor_loc_filter():
    assert _vf2_sensor_loc_select({REG_VF2_SENSOR_LOC: 1}).current_option == "Filter"


def test_vf2_sensor_loc_heater_line():
    assert _vf2_sensor_loc_select({REG_VF2_SENSOR_LOC: 2}).current_option == "Heater Line"


def test_vf2_sensor_loc_none_when_zero():
    assert _vf2_sensor_loc_select({REG_VF2_SENSOR_LOC: 0}).current_option is None


# ---------------------------------------------------------------------------
# AquatekFilterRunOnceSpeedSelect

def _filter_runonce_speed_select(registers: dict) -> AquatekFilterRunOnceSpeedSelect:
    coordinator = _make_coordinator(registers)
    sel = AquatekFilterRunOnceSpeedSelect.__new__(AquatekFilterRunOnceSpeedSelect)
    sel.coordinator = coordinator
    sel._reg = lambda r: _reg(coordinator, r)
    return sel


def test_filter_runonce_speed_1():
    # upper byte = 0 → Speed 1
    assert _filter_runonce_speed_select({REG_FILTER_RUNONCE_CTRL: 0x0001}).current_option == "Speed 1"


def test_filter_runonce_speed_4():
    # upper byte = 3 → Speed 4
    assert _filter_runonce_speed_select({REG_FILTER_RUNONCE_CTRL: 0x0301}).current_option == "Speed 4"


def test_filter_runonce_speed_none_when_no_data():
    assert _filter_runonce_speed_select({}).current_option is None


@pytest.mark.asyncio
async def test_filter_runonce_speed_write_preserves_lower_byte():
    # lower byte = 0x01 (enable bit set); selecting Speed 2 (idx=1) should write 0x0101
    sel = _filter_runonce_speed_select({REG_FILTER_RUNONCE_CTRL: 0x0001})
    await sel.async_select_option("Speed 2")
    sel.coordinator.async_write_register.assert_awaited_once_with(REG_FILTER_RUNONCE_CTRL, [0x0101])


# ---------------------------------------------------------------------------
# AquatekFilterScheduleSpeedSelect

def _filter_sched_speed_select(slot: int, registers: dict) -> AquatekFilterScheduleSpeedSelect:
    coordinator = _make_coordinator(registers)
    sel = AquatekFilterScheduleSpeedSelect.__new__(AquatekFilterScheduleSpeedSelect)
    sel.coordinator = coordinator
    sel._register = FILTER_SCHED_SPEED_REGS[slot]
    sel._reg = lambda r: _reg(coordinator, r)
    return sel


def test_filter_sched_speed_slot1_speed1():
    assert _filter_sched_speed_select(0, {FILTER_SCHED_SPEED_REGS[0]: 0}).current_option == "Speed 1"


def test_filter_sched_speed_slot1_speed4():
    assert _filter_sched_speed_select(0, {FILTER_SCHED_SPEED_REGS[0]: 3}).current_option == "Speed 4"


def test_filter_sched_speed_slot4_reads_correct_register():
    assert _filter_sched_speed_select(3, {FILTER_SCHED_SPEED_REGS[3]: 2}).current_option == "Speed 3"


def test_filter_sched_speed_none_when_no_data():
    assert _filter_sched_speed_select(0, {}).current_option is None


# ---------------------------------------------------------------------------
# AquatekSocketApplianceSelect

def _socket_appliance_select(socket_n: int, registers: dict) -> AquatekSocketApplianceSelect:
    coordinator = _make_coordinator(registers)
    sel = AquatekSocketApplianceSelect.__new__(AquatekSocketApplianceSelect)
    sel.coordinator = coordinator
    sel._register = REG_SOCKET_TYPE_BASE + (socket_n - 1)
    sel._reg = lambda r: _reg(coordinator, r)
    return sel


def test_socket_appliance_none():
    assert _socket_appliance_select(1, {REG_SOCKET_TYPE_BASE: 0}).current_option == "None"


def test_socket_appliance_sanitiser():
    assert _socket_appliance_select(1, {REG_SOCKET_TYPE_BASE: 1}).current_option == "Sanitiser"


def test_socket_appliance_pool_light():
    assert _socket_appliance_select(1, {REG_SOCKET_TYPE_BASE: 5}).current_option == "Pool Light"


def test_socket_appliance_socket5_reads_correct_register():
    assert _socket_appliance_select(5, {REG_SOCKET_TYPE_BASE + 4: 12}).current_option == "Jet Pump"


def test_socket_appliance_none_when_no_data():
    assert _socket_appliance_select(1, {}).current_option is None


# ---------------------------------------------------------------------------
# AquatekVFContactApplianceSelect

def _vf_appliance_select(vf_n: int, register: int, registers: dict) -> AquatekVFContactApplianceSelect:
    coordinator = _make_coordinator(registers)
    sel = AquatekVFContactApplianceSelect.__new__(AquatekVFContactApplianceSelect)
    sel.coordinator = coordinator
    sel._register = register
    sel._reg = lambda r: _reg(coordinator, r)
    return sel


def test_vf1_appliance_none():
    assert _vf_appliance_select(1, REG_VF1_TYPE, {REG_VF1_TYPE: 0}).current_option == "None"


def test_vf1_appliance_gas_heater():
    assert _vf_appliance_select(1, REG_VF1_TYPE, {REG_VF1_TYPE: 1}).current_option == "Gas Heater"


def test_vf2_appliance_heat_pump():
    assert _vf_appliance_select(2, REG_VF2_TYPE, {REG_VF2_TYPE: 2}).current_option == "Heat Pump"


def test_vf_appliance_none_when_no_data():
    assert _vf_appliance_select(1, REG_VF1_TYPE, {}).current_option is None


# ---------------------------------------------------------------------------
# AquatekValveApplianceSelect

def _valve_appliance_select(valve_n: int, registers: dict) -> AquatekValveApplianceSelect:
    coordinator = _make_coordinator(registers)
    sel = AquatekValveApplianceSelect.__new__(AquatekValveApplianceSelect)
    sel.coordinator = coordinator
    sel._register = REG_VALVE_TYPE_BASE + (valve_n - 1)
    sel._reg = lambda r: _reg(coordinator, r)
    return sel


def test_valve_appliance_none():
    assert _valve_appliance_select(1, {REG_VALVE_TYPE_BASE: 0}).current_option == "None"


def test_valve_appliance_pool_spa():
    assert _valve_appliance_select(1, {REG_VALVE_TYPE_BASE: 1}).current_option == "Pool Spa"


def test_valve_appliance_heating():
    assert _valve_appliance_select(1, {REG_VALVE_TYPE_BASE: 7}).current_option == "Heating"


def test_valve_appliance_valve4_reads_correct_register():
    assert _valve_appliance_select(4, {REG_VALVE_TYPE_BASE + 3: 3}).current_option == "Water Feature"


def test_valve_appliance_none_when_no_data():
    assert _valve_appliance_select(1, {}).current_option is None


# ---------------------------------------------------------------------------
# AquatekVF1SmartHeaterTypeSelect / AquatekVF2SmartHeaterTypeSelect

def _vf1_smart_heater_select(registers: dict) -> AquatekVF1SmartHeaterTypeSelect:
    coordinator = _make_coordinator(registers)
    sel = AquatekVF1SmartHeaterTypeSelect.__new__(AquatekVF1SmartHeaterTypeSelect)
    sel.coordinator = coordinator
    sel._reg = lambda r: _reg(coordinator, r)
    return sel


def _vf2_smart_heater_select(registers: dict) -> AquatekVF2SmartHeaterTypeSelect:
    coordinator = _make_coordinator(registers)
    sel = AquatekVF2SmartHeaterTypeSelect.__new__(AquatekVF2SmartHeaterTypeSelect)
    sel.coordinator = coordinator
    sel._reg = lambda r: _reg(coordinator, r)
    return sel


def test_smart_heater_auto():
    assert _vf1_smart_heater_select({REG_VF1_SMART_HEATER_TYPE: 0}).current_option == "Auto"


def test_smart_heater_theralux():
    assert _vf1_smart_heater_select({REG_VF1_SMART_HEATER_TYPE: 2}).current_option == "Theralux"


def test_smart_heater_oasis():
    assert _vf1_smart_heater_select({REG_VF1_SMART_HEATER_TYPE: 4}).current_option == "Oasis"


def test_smart_heater_vf2_aquark():
    assert _vf2_smart_heater_select({REG_VF2_SMART_HEATER_TYPE: 3}).current_option == "Aquark"


def test_smart_heater_unknown_defaults_to_auto():
    assert _vf1_smart_heater_select({REG_VF1_SMART_HEATER_TYPE: 99}).current_option == "Auto"


def test_smart_heater_none_when_no_data():
    assert _vf1_smart_heater_select({}).current_option is None
