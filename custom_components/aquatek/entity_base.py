"""Base entity class for all Dontek Aquatek entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_ID, DOMAIN
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
        device_id = coordinator.entry.data[CONF_DEVICE_ID]
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=f"Aquatek {device_id}",
            manufacturer="Dontek Electronics",
            model="Aquatek",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.is_connected

    def _reg(self, register: int) -> int | None:
        """Get the current value of a Modbus register."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(register)
