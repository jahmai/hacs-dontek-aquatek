"""DataUpdateCoordinator for the Dontek Aquatek integration.

Owns the device state dict (register → value) and dispatches updates to entities
when MQTT messages arrive. No polling — the device pushes all state changes.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, REG_DEVICE_NAME_BASE
from .mqtt_client import AquatekMQTTClient, ConnectionState

_LOGGER = logging.getLogger(__name__)


class AquatekCoordinator(DataUpdateCoordinator[dict[int, int]]):
    """Coordinator that holds Modbus register state for one Aquatek controller."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        mqtt_client: AquatekMQTTClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=None,  # push-only, no polling
        )
        self.entry = entry
        self.mqtt_client = mqtt_client
        self._connection_state = ConnectionState.DISCONNECTED

    async def async_setup(self) -> None:
        """Connect the MQTT client with callbacks wired to this coordinator."""
        await self.mqtt_client.connect()

    @property
    def is_connected(self) -> bool:
        return self._connection_state in (
            ConnectionState.CONNECTED,
            ConnectionState.ONLINE,
        )

    @property
    def connection_state(self) -> ConnectionState:
        return self._connection_state

    def handle_message(self, reg: int, values: list[int]) -> None:
        """Called by MQTT client on each incoming status message.

        Updates the register state dict and notifies all subscribed entities.
        Multiple values in a single message are stored at consecutive registers
        (matches the app's behaviour for multi-register reads in e3/g.java).
        """
        if self.data is None:
            self.data = {}

        changed = False
        for offset, val in enumerate(values):
            r = reg + offset
            if self.data.get(r) != val:
                self.data[r] = val
                changed = True

        if changed:
            self.async_set_updated_data(self.data)

    def handle_state_change(self, state: ConnectionState) -> None:
        """Called by MQTT client when the connection state changes."""
        self._connection_state = state
        # Notify entities so connection sensor and availability update
        if self.data is not None:
            self.async_set_updated_data(self.data)
        else:
            self.async_set_updated_data({})

    async def async_write_register(self, reg: int, values: list[int]) -> bool:
        """Publish a Modbus write command and optimistically update local state."""
        ok = await self.mqtt_client.publish_command(reg, values)
        if ok and self.data is not None:
            for offset, val in enumerate(values):
                self.data[reg + offset] = val
            self.async_set_updated_data(self.data)
        return ok

    def get_device_name(self) -> str | None:
        """Reconstruct the device name from registers 65488–65495 (8 ASCII bytes)."""
        if not self.data:
            return None
        chars = []
        for i in range(8):
            val = self.data.get(REG_DEVICE_NAME_BASE + i)
            if val is None or val == 0:
                break
            chars.append(chr(val))
        return "".join(chars) if chars else None
