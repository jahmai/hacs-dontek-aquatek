"""Base entity class for all Dontek Aquatek entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, DOMAIN
from .coordinator import AquatekCoordinator


class AquatekEntity(CoordinatorEntity[AquatekCoordinator]):
    """Base class providing device info, availability, and register helpers."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AquatekCoordinator,
        unique_id_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        mac = coordinator.entry.data[CONF_MAC]
        self._attr_unique_id = f"{DOMAIN}_{mac}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=coordinator.get_device_name() or f"Aquatek {mac}",
            manufacturer="Dontek Electronics",
            model="Pool+ Manager",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.is_connected

    def _reg(self, register: int) -> int | None:
        """Get the current value of a Modbus register."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(register)
