"""Switch entities for the Dontek Aquatek integration.

Heater ancillary switches:
- Heater 1 Run Till Heated  (65500)
- Heater 2 Boost            (57577)

VF port config switches (heating, sanitiser, chilling, hydrotherapy, setback):
- VF1: sanitiser (65501), chilling (65523), hydrotherapy (57586)
- VF2: sanitiser (57570), chilling (57569), hydrotherapy (57587), setback (57578)
"""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    REG_BOOST_MODE,
    REG_RUN_TILL_HEATED,
    REG_VF1_CHILLING,
    REG_VF1_HYDRO,
    REG_VF1_SANITISER,
    REG_VF2_CHILLING,
    REG_VF2_HYDRO,
    REG_VF2_SANITISER,
    REG_VF2_SETBACK,
)
from .coordinator import AquatekCoordinator
from .entity_base import AquatekEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AquatekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        AquatekRunTillHeatedSwitch(coordinator),
        AquatekBoostSwitch(coordinator),
        AquatekVF1SanitiserSwitch(coordinator),
        AquatekVF1ChillingSwitch(coordinator),
        AquatekVF1HydroSwitch(coordinator),
        AquatekVF2SanitiserSwitch(coordinator),
        AquatekVF2ChillingSwitch(coordinator),
        AquatekVF2HydroSwitch(coordinator),
        AquatekVF2SetbackSwitch(coordinator),
    ])


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
