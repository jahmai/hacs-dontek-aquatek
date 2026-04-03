"""Tests for climate.py — heater HVAC mode and temperature logic."""
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from homeassistant.components.climate import HVACMode

from custom_components.dontek_aquatek.climate import AquatekHeater1, AquatekHeater2
from custom_components.dontek_aquatek.const import (
    REG_H1_POOL_SETPOINT,
    REG_H1_SPA_SETPOINT,
    REG_H2_POOL_SETPOINT,
    REG_H2_SPA_SETPOINT,
    REG_HEATER1_CTRL,
    REG_HEATER2_CTRL,
    REG_POOL_SPA_MODE,
    REG_SENSOR_READING_BASE,
    REG_SENSOR_TYPE_BASE,
    REG_VF1_HEAT_MODE,
    REG_VF2_HEAT_MODE,
    SENSOR_TYPE_POOL,
    SENSOR_TYPE_ROOF,
)

_SETPOINT_OFF = 255  # firmware sentinel for "Off" circuit


# ---------------------------------------------------------------------------
# Helpers

def _make_coordinator(registers: dict) -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = registers
    coordinator.async_write_register = AsyncMock()
    return coordinator


def _reg(coordinator, r):
    return coordinator.data.get(r)


def _heater1(registers: dict) -> AquatekHeater1:
    coordinator = _make_coordinator(registers)
    h = AquatekHeater1.__new__(AquatekHeater1)
    h.coordinator = coordinator
    h._reg = lambda r: _reg(coordinator, r)
    return h


def _heater2(registers: dict) -> AquatekHeater2:
    coordinator = _make_coordinator(registers)
    h = AquatekHeater2.__new__(AquatekHeater2)
    h.coordinator = coordinator
    h._reg = lambda r: _reg(coordinator, r)
    return h


# ---------------------------------------------------------------------------
# hvac_mode — Heater 1

def test_heater1_hvac_mode_off():
    assert _heater1({REG_HEATER1_CTRL: 0}).hvac_mode == HVACMode.OFF


def test_heater1_hvac_mode_heat():
    assert _heater1({REG_HEATER1_CTRL: 1}).hvac_mode == HVACMode.HEAT


def test_heater1_hvac_mode_auto():
    assert _heater1({REG_HEATER1_CTRL: 2}).hvac_mode == HVACMode.AUTO


def test_heater1_hvac_mode_none_when_no_data():
    assert _heater1({}).hvac_mode is None


def test_heater1_hvac_mode_unknown_val_defaults_to_auto():
    assert _heater1({REG_HEATER1_CTRL: 99}).hvac_mode == HVACMode.AUTO


# ---------------------------------------------------------------------------
# hvac_mode — Heater 2

def test_heater2_hvac_mode_off():
    assert _heater2({REG_HEATER2_CTRL: 0}).hvac_mode == HVACMode.OFF


def test_heater2_hvac_mode_auto():
    assert _heater2({REG_HEATER2_CTRL: 2}).hvac_mode == HVACMode.AUTO


def test_heater2_hvac_mode_none_when_no_data():
    assert _heater2({}).hvac_mode is None


# ---------------------------------------------------------------------------
# async_set_hvac_mode

@pytest.mark.asyncio
async def test_heater1_set_off_writes_zero():
    h = _heater1({REG_HEATER1_CTRL: 2})
    await h.async_set_hvac_mode(HVACMode.OFF)
    h.coordinator.async_write_register.assert_awaited_once_with(REG_HEATER1_CTRL, [0])


@pytest.mark.asyncio
async def test_heater1_set_heat_writes_one():
    h = _heater1({REG_HEATER1_CTRL: 0})
    await h.async_set_hvac_mode(HVACMode.HEAT)
    h.coordinator.async_write_register.assert_awaited_once_with(REG_HEATER1_CTRL, [1])


@pytest.mark.asyncio
async def test_heater1_set_auto_writes_two():
    h = _heater1({REG_HEATER1_CTRL: 0})
    await h.async_set_hvac_mode(HVACMode.AUTO)
    h.coordinator.async_write_register.assert_awaited_once_with(REG_HEATER1_CTRL, [2])


@pytest.mark.asyncio
async def test_heater2_set_auto_writes_two():
    h = _heater2({REG_HEATER2_CTRL: 0})
    await h.async_set_hvac_mode(HVACMode.AUTO)
    h.coordinator.async_write_register.assert_awaited_once_with(REG_HEATER2_CTRL, [2])


# ---------------------------------------------------------------------------
# target_temperature — mode-aware setpoint selection

def test_heater1_target_temp_spa_only_returns_spa_setpoint():
    # H1 heating mode = 4 (Spa only) → use spa setpoint
    registers = {REG_VF1_HEAT_MODE: 4, REG_H1_SPA_SETPOINT: 76}  # 38°C
    assert _heater1(registers).target_temperature == 38.0


def test_heater1_target_temp_pool_only_returns_pool_setpoint():
    registers = {REG_VF1_HEAT_MODE: 3, REG_H1_POOL_SETPOINT: 60}  # 30°C
    assert _heater1(registers).target_temperature == 30.0


def test_heater1_target_temp_pool_and_spa_pool_mode_returns_pool_setpoint():
    # H1 = Pool & Spa, controller in Pool mode → show pool setpoint
    registers = {
        REG_VF1_HEAT_MODE: 2,
        REG_POOL_SPA_MODE: 0,
        REG_H1_POOL_SETPOINT: 60,
        REG_H1_SPA_SETPOINT: 76,
    }
    assert _heater1(registers).target_temperature == 30.0


def test_heater1_target_temp_pool_and_spa_spa_mode_returns_spa_setpoint():
    # H1 = Pool & Spa, controller in Spa mode → show spa setpoint
    registers = {
        REG_VF1_HEAT_MODE: 2,
        REG_POOL_SPA_MODE: 1,
        REG_H1_POOL_SETPOINT: 60,
        REG_H1_SPA_SETPOINT: 76,
    }
    assert _heater1(registers).target_temperature == 38.0


def test_heater1_target_temp_pool_and_spa_spa_mode_spa_off_sentinel_returns_pool():
    # H1 = Pool & Spa, controller in Spa mode, but spa setpoint is Off (255)
    # → fall back to pool setpoint rather than showing 127.5°C
    registers = {
        REG_VF1_HEAT_MODE: 2,
        REG_POOL_SPA_MODE: 1,
        REG_H1_POOL_SETPOINT: 60,
        REG_H1_SPA_SETPOINT: _SETPOINT_OFF,
    }
    assert _heater1(registers).target_temperature == 30.0


def test_heater1_target_temp_pool_and_spa_pool_mode_pool_off_sentinel_returns_spa():
    # H1 = Pool & Spa, controller in Pool mode, but pool setpoint is Off (255)
    # → fall back to spa setpoint
    registers = {
        REG_VF1_HEAT_MODE: 2,
        REG_POOL_SPA_MODE: 0,
        REG_H1_POOL_SETPOINT: _SETPOINT_OFF,
        REG_H1_SPA_SETPOINT: 76,
    }
    assert _heater1(registers).target_temperature == 38.0


def test_heater1_target_temp_off_mode_returns_pool_setpoint():
    # Heat mode = 0 (Off) falls back to pool setpoint
    registers = {REG_VF1_HEAT_MODE: 0, REG_H1_POOL_SETPOINT: 60}
    assert _heater1(registers).target_temperature == 30.0


def test_heater1_target_temp_none_when_no_data():
    assert _heater1({}).target_temperature is None


def test_heater2_target_temp_pool_only_returns_pool_setpoint():
    registers = {REG_VF2_HEAT_MODE: 3, REG_H2_POOL_SETPOINT: 64}  # 32°C
    assert _heater2(registers).target_temperature == 32.0


def test_heater2_target_temp_spa_only_returns_spa_setpoint():
    registers = {REG_VF2_HEAT_MODE: 4, REG_H2_SPA_SETPOINT: 56}  # 28°C
    assert _heater2(registers).target_temperature == 28.0


def test_target_temperature_half_degree():
    registers = {REG_VF2_HEAT_MODE: 3, REG_H2_POOL_SETPOINT: 65}  # 32.5°C
    assert _heater2(registers).target_temperature == 32.5


# ---------------------------------------------------------------------------
# async_set_temperature — writes to correct register(s) based on heating mode

@pytest.mark.asyncio
async def test_set_temperature_pool_only_writes_pool_reg():
    h = _heater1({REG_VF1_HEAT_MODE: 3})
    await h.async_set_temperature(temperature=30.0)
    h.coordinator.async_write_register.assert_awaited_once_with(REG_H1_POOL_SETPOINT, [60])


@pytest.mark.asyncio
async def test_set_temperature_spa_only_writes_spa_reg():
    h = _heater1({REG_VF1_HEAT_MODE: 4})
    await h.async_set_temperature(temperature=38.0)
    h.coordinator.async_write_register.assert_awaited_once_with(REG_H1_SPA_SETPOINT, [76])


@pytest.mark.asyncio
async def test_set_temperature_pool_and_spa_writes_both():
    h = _heater1({REG_VF1_HEAT_MODE: 2})
    await h.async_set_temperature(temperature=32.0)
    h.coordinator.async_write_register.assert_any_await(REG_H1_POOL_SETPOINT, [64])
    h.coordinator.async_write_register.assert_any_await(REG_H1_SPA_SETPOINT, [64])
    assert h.coordinator.async_write_register.await_count == 2


@pytest.mark.asyncio
async def test_set_temperature_off_mode_writes_both():
    h = _heater2({REG_VF2_HEAT_MODE: 0})
    await h.async_set_temperature(temperature=28.0)
    h.coordinator.async_write_register.assert_any_await(REG_H2_POOL_SETPOINT, [56])
    h.coordinator.async_write_register.assert_any_await(REG_H2_SPA_SETPOINT, [56])
    assert h.coordinator.async_write_register.await_count == 2


@pytest.mark.asyncio
async def test_set_temperature_pool_and_spa_spa_off_sentinel_writes_pool_only():
    # Spa setpoint is 255 (Off sentinel) — adjusting temp must not overwrite it
    h = _heater1({REG_VF1_HEAT_MODE: 2, REG_H1_SPA_SETPOINT: _SETPOINT_OFF})
    await h.async_set_temperature(temperature=32.0)
    h.coordinator.async_write_register.assert_awaited_once_with(REG_H1_POOL_SETPOINT, [64])


@pytest.mark.asyncio
async def test_set_temperature_pool_and_spa_pool_off_sentinel_writes_spa_only():
    # Pool setpoint is 255 (Off sentinel) — adjusting temp must not overwrite it
    h = _heater1({REG_VF1_HEAT_MODE: 2, REG_H1_POOL_SETPOINT: _SETPOINT_OFF})
    await h.async_set_temperature(temperature=32.0)
    h.coordinator.async_write_register.assert_awaited_once_with(REG_H1_SPA_SETPOINT, [64])


@pytest.mark.asyncio
async def test_set_temperature_off_mode_spa_off_sentinel_writes_pool_only():
    h = _heater2({REG_VF2_HEAT_MODE: 0, REG_H2_SPA_SETPOINT: _SETPOINT_OFF})
    await h.async_set_temperature(temperature=28.0)
    h.coordinator.async_write_register.assert_awaited_once_with(REG_H2_POOL_SETPOINT, [56])


@pytest.mark.asyncio
async def test_set_temperature_no_temp_kwarg_does_nothing():
    h = _heater1({REG_VF1_HEAT_MODE: 3})
    await h.async_set_temperature()
    h.coordinator.async_write_register.assert_not_awaited()


# ---------------------------------------------------------------------------
# current_temperature — finds Pool sensor dynamically

def test_current_temperature_uses_pool_sensor():
    # Sensor 2 (index 1) is Pool type; reading = 56 → 28°C
    registers = {
        REG_SENSOR_TYPE_BASE: SENSOR_TYPE_ROOF,       # sensor 1 = Roof
        REG_SENSOR_TYPE_BASE + 1: SENSOR_TYPE_POOL,   # sensor 2 = Pool
        REG_SENSOR_READING_BASE + 1: 56,              # 28°C
        REG_HEATER1_CTRL: 0,
    }
    assert _heater1(registers).current_temperature == 28.0


def test_current_temperature_none_when_no_pool_sensor():
    registers = {
        REG_SENSOR_TYPE_BASE: SENSOR_TYPE_ROOF,
        REG_SENSOR_READING_BASE: 60,
    }
    assert _heater1(registers).current_temperature is None


def test_current_temperature_none_when_pool_sensor_has_no_reading():
    registers = {
        REG_SENSOR_TYPE_BASE: SENSOR_TYPE_POOL,
        # no reading register
    }
    assert _heater1(registers).current_temperature is None
