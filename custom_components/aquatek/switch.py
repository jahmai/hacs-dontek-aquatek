"""Switch entities for the Dontek Aquatek integration.

Covers: pumps 0–11, spa, filter pump, sanitizer, solar, light 1, light 2.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    PUMP_COUNT,
    REG_FILTER_ENABLED,
    REG_LIGHT1,
    REG_LIGHT2,
    REG_PUMP_BASE,
    REG_SANITIZER_ENABLED,
    REG_SOLAR_ENABLED,
    REG_SPA_ENABLE,
)
from .coordinator import AquatekCoordinator
from .entity_base import AquatekEntity


@dataclass(frozen=True, kw_only=True)
class AquatekSwitchDescription(SwitchEntityDescription):
    register: int
    # Some registers use bit masking (e.g. solar)
    on_mask: int = 0


# Named switches (non-pump)
_NAMED_SWITCHES: list[AquatekSwitchDescription] = [
    AquatekSwitchDescription(
        key="spa",
        name="Spa",
        register=REG_SPA_ENABLE,
    ),
    AquatekSwitchDescription(
        key="filter",
        name="Filter Pump",
        register=REG_FILTER_ENABLED,
    ),
    AquatekSwitchDescription(
        key="sanitizer",
        name="Sanitizer",
        register=REG_SANITIZER_ENABLED,
    ),
    AquatekSwitchDescription(
        key="solar",
        name="Solar",
        register=REG_SOLAR_ENABLED,
        on_mask=0x01,  # bit 0 = solar enabled (b3/v.java & 0xBF mask noted)
    ),
    AquatekSwitchDescription(
        key="light1",
        name="Light 1",
        register=REG_LIGHT1,
    ),
    AquatekSwitchDescription(
        key="light2",
        name="Light 2",
        register=REG_LIGHT2,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AquatekCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[AquatekSwitch] = []

    # Pump switches 0–11 (index 12 = spa, handled as named switch above)
    for i in range(PUMP_COUNT - 1):
        desc = AquatekSwitchDescription(
            key=f"pump_{i}",
            name=f"Pump {i + 1}",
            register=REG_PUMP_BASE + i,
            entity_registry_enabled_default=(i == 0),  # only pump 1 on by default
        )
        entities.append(AquatekSwitch(coordinator, desc))

    for desc in _NAMED_SWITCHES:
        entities.append(AquatekSwitch(coordinator, desc))

    async_add_entities(entities)


class AquatekSwitch(AquatekEntity, SwitchEntity):
    """A binary on/off switch backed by a Modbus register."""

    def __init__(
        self,
        coordinator: AquatekCoordinator,
        description: AquatekSwitchDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._register = description.register
        self._on_mask = description.on_mask

    @property
    def is_on(self) -> bool | None:
        val = self._reg(self._register)
        if val is None:
            return None
        if self._on_mask:
            return bool(val & self._on_mask)
        return val != 0

    async def async_turn_on(self, **kwargs) -> None:
        if self._on_mask:
            current = self._reg(self._register) or 0
            await self.coordinator.async_write_register(
                self._register, [current | self._on_mask]
            )
        else:
            await self.coordinator.async_write_register(self._register, [1])

    async def async_turn_off(self, **kwargs) -> None:
        if self._on_mask:
            current = self._reg(self._register) or 0
            await self.coordinator.async_write_register(
                self._register, [current & ~self._on_mask]
            )
        else:
            await self.coordinator.async_write_register(self._register, [0])
