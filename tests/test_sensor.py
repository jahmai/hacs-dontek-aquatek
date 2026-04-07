"""Tests for sensor.py — status sensors and helper functions."""
from unittest.mock import MagicMock

from datetime import datetime, timezone

from custom_components.dontek_aquatek.sensor import (
    AquatekFilterPumpStatusSensor,
    AquatekHeater1StatusSensor,
    AquatekHeater2StatusSensor,
    AquatekLastMessageSensor,
    AquatekTemperatureSensor,
    _decode_last_ran,
)
from custom_components.dontek_aquatek.const import (
    REG_HEATER1_CTRL,
    REG_HEATER2_CTRL,
    REG_POOL_SPA_MODE,
    REG_SENSOR_READING_BASE,
    REG_SENSOR_TYPE_BASE,
    REG_VF1_HEAT_MODE,
    REG_VF2_HEAT_MODE,
    SENSOR_TYPE_POOL,
    SENSOR_TYPE_ROOF,
    SENSOR_TYPE_WATER,
)


# ---------------------------------------------------------------------------
# _decode_last_ran
# ---------------------------------------------------------------------------


def test_decode_last_ran_none():
    assert _decode_last_ran(None) is None


def test_decode_last_ran_no_data():
    assert _decode_last_ran(65535) is None


def test_decode_last_ran_valid():
    # 0x1100 = hours=17, minutes=0
    assert _decode_last_ran(0x1100) == "17:00"


def test_decode_last_ran_valid_with_minutes():
    # 0x1303 = hours=19, minutes=3
    assert _decode_last_ran(0x1303) == "19:03"


def test_decode_last_ran_zero():
    # 0x0000 = 00:00
    assert _decode_last_ran(0x0000) == "00:00"


def test_decode_last_ran_invalid_minutes():
    # 0x11E9 = hours=17, minutes=233 — out of range
    assert _decode_last_ran(0x11E9) is None


def test_decode_last_ran_invalid_hours():
    # 0x1800 = hours=24 — out of range
    assert _decode_last_ran(0x1800) is None


# ---------------------------------------------------------------------------
# Helpers for entity tests
# ---------------------------------------------------------------------------


def _make_coordinator(registers: dict) -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = registers
    return coordinator


def _reg(coordinator, reg):
    return coordinator.data.get(reg)


# ---------------------------------------------------------------------------
# AquatekFilterPumpStatusSensor
# ---------------------------------------------------------------------------


def _filter_sensor(registers):
    coordinator = _make_coordinator(registers)
    sensor = AquatekFilterPumpStatusSensor.__new__(AquatekFilterPumpStatusSensor)
    sensor.coordinator = coordinator
    sensor._reg = lambda r: _reg(coordinator, r)
    return sensor


def test_filter_pump_status_running_speed_1():
    # 0x0C00 = state=12 (Running), raw_speed=0 → Speed 1 (0-indexed)
    sensor = _filter_sensor({92: 0x0C00})
    assert sensor.native_value == "Running (Speed 1)"


def test_filter_pump_status_running_speed_2():
    # 0x0C01 = state=12 (Running), raw_speed=1 → Speed 2
    sensor = _filter_sensor({92: 0x0C01})
    assert sensor.native_value == "Running (Speed 2)"


def test_filter_pump_status_running_speed_4():
    # 0x0C03 = state=12 (Running), raw_speed=3 → Speed 4
    sensor = _filter_sensor({92: 0x0C03})
    assert sensor.native_value == "Running (Speed 4)"


def test_filter_pump_status_off_no_speed():
    # 0x0101 = state=1 (Off), raw_speed=1 — stale speed, must not be shown
    sensor = _filter_sensor({92: 0x0101})
    assert sensor.native_value == "Off"


def test_filter_pump_status_priming_includes_speed():
    # 0x0502 = state=5 (Priming), raw_speed=2 → Speed 3
    sensor = _filter_sensor({92: 0x0502})
    assert sensor.native_value == "Priming (Speed 3)"


def test_filter_pump_status_set_speed_includes_speed():
    # 0x0802 = state=8 (Set Speed), raw_speed=2 → Speed 3
    sensor = _filter_sensor({92: 0x0802})
    assert sensor.native_value == "Set Speed (Speed 3)"


def test_filter_pump_status_unknown_state():
    # state=99 — unknown, no speed shown for unknown states
    sensor = _filter_sensor({92: 0x6301})
    assert sensor.native_value == "Unknown (99)"


def test_filter_pump_status_none_when_no_data():
    sensor = _filter_sensor({})
    assert sensor.native_value is None


def test_filter_pump_attrs_speed():
    # 0x0C03 = Running, raw_speed=3 → Speed 4
    sensor = _filter_sensor({92: 0x0C03, 94: None})
    assert sensor.extra_state_attributes["speed"] == 4


def test_filter_pump_attrs_speed_1():
    # 0x0C00 = Running, raw_speed=0 → Speed 1
    sensor = _filter_sensor({92: 0x0C00, 94: None})
    assert sensor.extra_state_attributes["speed"] == 1


def test_filter_pump_attrs_speed_omitted_when_off():
    # Off state — stale speed byte must not appear in attributes
    sensor = _filter_sensor({92: 0x0103, 94: None})
    assert "speed" not in sensor.extra_state_attributes


def test_filter_pump_attrs_last_ran_at():
    sensor = _filter_sensor({92: 0x0C01, 94: 0x1100})
    assert sensor.extra_state_attributes["last_ran_at"] == "17:00"


def test_filter_pump_attrs_last_ran_at_omitted_when_invalid():
    sensor = _filter_sensor({92: 0x0C01, 94: 65535})
    assert "last_ran_at" not in sensor.extra_state_attributes


# ---------------------------------------------------------------------------
# AquatekHeater1StatusSensor
# ---------------------------------------------------------------------------


def _h1_sensor(registers):
    coordinator = _make_coordinator(registers)
    sensor = AquatekHeater1StatusSensor.__new__(AquatekHeater1StatusSensor)
    sensor.coordinator = coordinator
    sensor._reg = lambda r: _reg(coordinator, r)
    return sensor


def test_heater1_status_off():
    assert _h1_sensor({81: 0, REG_HEATER1_CTRL: 0}).native_value == "Off"


def test_heater1_status_waiting_pool_mode():
    # Heater 1 set to Spa only (heat_mode=4), controller in Pool → mismatch → label
    assert _h1_sensor({81: 0, REG_HEATER1_CTRL: 2, REG_VF1_HEAT_MODE: 4, REG_POOL_SPA_MODE: 0}).native_value == "Waiting (Pool Mode)"


def test_heater1_status_waiting_spa_mode():
    # Heater 1 set to Pool only (heat_mode=3), controller in Spa → mismatch → label
    assert _h1_sensor({81: 0, REG_HEATER1_CTRL: 2, REG_VF1_HEAT_MODE: 3, REG_POOL_SPA_MODE: 1}).native_value == "Waiting (Spa Mode)"


def test_heater1_status_waiting_no_mismatch():
    # Heater 1 set to Pool&Spa (heat_mode=2) — never blocked → just "Waiting"
    assert _h1_sensor({81: 0, REG_HEATER1_CTRL: 2, REG_VF1_HEAT_MODE: 2, REG_POOL_SPA_MODE: 0}).native_value == "Waiting"


def test_heater1_status_waiting_mode_unknown():
    # heat_mode not yet received — just show "Waiting"
    assert _h1_sensor({81: 0, REG_HEATER1_CTRL: 2, REG_POOL_SPA_MODE: 0}).native_value == "Waiting"


def test_heater1_status_sampling():
    assert _h1_sensor({81: 2}).native_value == "Sampling"


def test_heater1_status_checking():
    assert _h1_sensor({81: 3}).native_value == "Checking"


def test_heater1_status_heating():
    assert _h1_sensor({81: 4}).native_value == "Heating"


def test_heater1_status_run_on():
    assert _h1_sensor({81: 5}).native_value == "Run On"


def test_heater1_status_off_in_pool_ctrl_off():
    # Device sends code 11 when ctrl=0 — should show "Off"
    assert _h1_sensor({81: 11, REG_HEATER1_CTRL: 0}).native_value == "Off"


def test_heater1_status_off_in_spa_ctrl_off():
    # Device sends code 12 when ctrl=0 — should show "Off"
    assert _h1_sensor({81: 12, REG_HEATER1_CTRL: 0}).native_value == "Off"


def test_heater1_status_off_in_pool_ctrl_armed():
    # Code 11 with ctrl≠0: heater armed but blocked by Pool mode → "Waiting (Pool Mode)"
    assert _h1_sensor({81: 11, REG_HEATER1_CTRL: 2, REG_VF1_HEAT_MODE: 4, REG_POOL_SPA_MODE: 0}).native_value == "Waiting (Pool Mode)"


def test_heater1_status_off_in_spa_ctrl_armed():
    # Code 12 with ctrl≠0: heater armed but blocked by Spa mode → "Waiting (Spa Mode)"
    assert _h1_sensor({81: 12, REG_HEATER1_CTRL: 2, REG_VF1_HEAT_MODE: 3, REG_POOL_SPA_MODE: 1}).native_value == "Waiting (Spa Mode)"


def test_heater1_status_waiting_code1_direct():
    # Device can send code 1 directly as a transient waiting state
    assert _h1_sensor({81: 1, REG_VF1_HEAT_MODE: 2, REG_POOL_SPA_MODE: 0}).native_value == "Waiting"


def test_heater1_status_waiting_pool_mode_code1_direct():
    # val=1 sent directly with mode mismatch still produces the context label
    assert _h1_sensor({81: 1, REG_VF1_HEAT_MODE: 4, REG_POOL_SPA_MODE: 0}).native_value == "Waiting (Pool Mode)"


def test_heater1_status_waiting_no_conflict_spa_active():
    # Spa-only heater (heat_mode=4), Spa mode active → no conflict → "Waiting"
    assert _h1_sensor({81: 0, REG_HEATER1_CTRL: 2, REG_VF1_HEAT_MODE: 4, REG_POOL_SPA_MODE: 1}).native_value == "Waiting"


def test_heater1_status_waiting_no_conflict_pool_active():
    # Pool-only heater (heat_mode=3), Pool mode active → no conflict → "Waiting"
    assert _h1_sensor({81: 0, REG_HEATER1_CTRL: 2, REG_VF1_HEAT_MODE: 3, REG_POOL_SPA_MODE: 0}).native_value == "Waiting"


def test_heater1_status_waiting_heat_mode_off():
    # heat_mode=0 (Off) is excluded from mismatch logic → just "Waiting"
    assert _h1_sensor({81: 0, REG_HEATER1_CTRL: 2, REG_VF1_HEAT_MODE: 0, REG_POOL_SPA_MODE: 0}).native_value == "Waiting"


def test_heater1_status_limit():
    assert _h1_sensor({81: 6}).native_value == "Limit"


def test_heater1_status_stopping():
    assert _h1_sensor({81: 7}).native_value == "Stopping"


def test_heater1_status_fault():
    assert _h1_sensor({81: 8}).native_value == "Fault"


def test_heater1_status_waiting_solar_priority():
    assert _h1_sensor({81: 9}).native_value == "Waiting (Solar Priority)"


def test_heater1_status_chilling():
    assert _h1_sensor({81: 10}).native_value == "Chilling"


def test_heater1_status_unknown():
    assert _h1_sensor({81: 99}).native_value == "Unknown (99)"


def test_heater1_status_none_when_no_data():
    assert _h1_sensor({}).native_value is None


# ---------------------------------------------------------------------------
# AquatekHeater2StatusSensor
# ---------------------------------------------------------------------------


def _h2_sensor(registers):
    coordinator = _make_coordinator(registers)
    sensor = AquatekHeater2StatusSensor.__new__(AquatekHeater2StatusSensor)
    sensor.coordinator = coordinator
    sensor._reg = lambda r: _reg(coordinator, r)
    return sensor


def test_heater2_status_off():
    assert _h2_sensor({184: 0, REG_HEATER2_CTRL: 0}).native_value == "Off"


def test_heater2_status_waiting_no_mismatch():
    # Heater 2 set to Pool (heat_mode=3), controller in Pool → no mismatch → just "Waiting"
    assert _h2_sensor({184: 0, REG_HEATER2_CTRL: 2, REG_VF2_HEAT_MODE: 3, REG_POOL_SPA_MODE: 0}).native_value == "Waiting"


def test_heater2_status_waiting_spa_mode():
    # Heater 2 set to Pool (heat_mode=3), controller in Spa → mismatch
    assert _h2_sensor({184: 0, REG_HEATER2_CTRL: 2, REG_VF2_HEAT_MODE: 3, REG_POOL_SPA_MODE: 1}).native_value == "Waiting (Spa Mode)"


def test_heater2_status_waiting_pool_mode():
    # Heater 2 set to Spa only (heat_mode=4), controller in Pool → mismatch
    assert _h2_sensor({184: 0, REG_HEATER2_CTRL: 2, REG_VF2_HEAT_MODE: 4, REG_POOL_SPA_MODE: 0}).native_value == "Waiting (Pool Mode)"


def test_heater2_status_waiting_no_conflict_pool_active():
    # Pool-only heater, Pool mode active → no conflict
    assert _h2_sensor({184: 0, REG_HEATER2_CTRL: 2, REG_VF2_HEAT_MODE: 3, REG_POOL_SPA_MODE: 0}).native_value == "Waiting"


def test_heater2_status_waiting_heat_mode_unknown():
    # heat_mode not yet received → just "Waiting"
    assert _h2_sensor({184: 0, REG_HEATER2_CTRL: 2, REG_POOL_SPA_MODE: 0}).native_value == "Waiting"


def test_heater2_status_sampling():
    assert _h2_sensor({184: 2}).native_value == "Sampling"


def test_heater2_status_checking():
    assert _h2_sensor({184: 3}).native_value == "Checking"


def test_heater2_status_heating():
    assert _h2_sensor({184: 4}).native_value == "Heating"


def test_heater2_status_run_on():
    assert _h2_sensor({184: 5}).native_value == "Run On"


def test_heater2_status_chilling():
    assert _h2_sensor({184: 10}).native_value == "Chilling"


def test_heater2_status_off_in_pool_ctrl_off():
    # Device sends code 11 when ctrl=0 — should show "Off"
    assert _h2_sensor({184: 11, REG_HEATER2_CTRL: 0}).native_value == "Off"


def test_heater2_status_off_in_spa_ctrl_off():
    # Device sends code 12 when ctrl=0 — should show "Off"
    assert _h2_sensor({184: 12, REG_HEATER2_CTRL: 0}).native_value == "Off"


def test_heater2_status_off_in_pool_ctrl_armed():
    # Code 11 with ctrl≠0: armed but blocked → "Waiting (Pool Mode)"
    assert _h2_sensor({184: 11, REG_HEATER2_CTRL: 2, REG_VF2_HEAT_MODE: 4, REG_POOL_SPA_MODE: 0}).native_value == "Waiting (Pool Mode)"


def test_heater2_status_off_in_spa_ctrl_armed():
    # Code 12 with ctrl≠0: armed but blocked → "Waiting (Spa Mode)"
    assert _h2_sensor({184: 12, REG_HEATER2_CTRL: 2, REG_VF2_HEAT_MODE: 3, REG_POOL_SPA_MODE: 1}).native_value == "Waiting (Spa Mode)"


def test_heater2_status_unknown():
    assert _h2_sensor({184: 99}).native_value == "Unknown (99)"


def test_heater2_status_none_when_no_data():
    assert _h2_sensor({}).native_value is None


# ---------------------------------------------------------------------------
# AquatekTemperatureSensor
# ---------------------------------------------------------------------------


def _temp_sensor(sensor_n: int, registers: dict):
    coordinator = _make_coordinator(registers)
    sensor = AquatekTemperatureSensor.__new__(AquatekTemperatureSensor)
    sensor.coordinator = coordinator
    sensor._sensor_n = sensor_n
    sensor._reg = lambda r: _reg(coordinator, r)
    return sensor


def test_temperature_sensor_scaling():
    # Sensor 1 at base reg 55; 76 → 38.0°C
    sensor = _temp_sensor(1, {REG_SENSOR_READING_BASE: 76})
    assert sensor.native_value == 38.0


def test_temperature_sensor_half_degree():
    # 65 → 32.5°C
    sensor = _temp_sensor(1, {REG_SENSOR_READING_BASE: 65})
    assert sensor.native_value == 32.5


def test_temperature_sensor_none_when_no_data():
    sensor = _temp_sensor(1, {})
    assert sensor.native_value is None


def test_temperature_sensor_2_reads_correct_register():
    # Sensor 2 reads REG_SENSOR_READING_BASE + 1 = 56
    sensor = _temp_sensor(2, {REG_SENSOR_READING_BASE + 1: 64})
    assert sensor.native_value == 32.0


def test_temperature_sensor_attrs_known_type():
    sensor = _temp_sensor(1, {REG_SENSOR_TYPE_BASE: SENSOR_TYPE_POOL})
    assert sensor.extra_state_attributes == {"configured_type": "Pool"}


def test_temperature_sensor_attrs_roof():
    sensor = _temp_sensor(1, {REG_SENSOR_TYPE_BASE: SENSOR_TYPE_ROOF})
    assert sensor.extra_state_attributes == {"configured_type": "Roof"}


def test_temperature_sensor_attrs_water():
    sensor = _temp_sensor(1, {REG_SENSOR_TYPE_BASE: SENSOR_TYPE_WATER})
    assert sensor.extra_state_attributes == {"configured_type": "Water"}


def test_temperature_sensor_attrs_unknown_type():
    sensor = _temp_sensor(1, {REG_SENSOR_TYPE_BASE: 99})
    assert sensor.extra_state_attributes == {"configured_type": "unknown (99)"}


def test_temperature_sensor_attrs_empty_when_no_data():
    sensor = _temp_sensor(1, {})
    assert sensor.extra_state_attributes == {}


# ---------------------------------------------------------------------------
# AquatekLastMessageSensor
# ---------------------------------------------------------------------------


def _last_message_sensor(last_message_time):
    coordinator = MagicMock()
    coordinator.last_message_time = last_message_time
    sensor = AquatekLastMessageSensor.__new__(AquatekLastMessageSensor)
    sensor.coordinator = coordinator
    return sensor


def test_last_message_none_before_first_message():
    sensor = _last_message_sensor(None)
    assert sensor.native_value is None


def test_last_message_returns_datetime():
    dt = datetime(2026, 4, 7, 12, 34, 56, tzinfo=timezone.utc)
    sensor = _last_message_sensor(dt)
    assert sensor.native_value == dt


def test_last_message_always_available():
    sensor = _last_message_sensor(None)
    assert sensor.available is True
