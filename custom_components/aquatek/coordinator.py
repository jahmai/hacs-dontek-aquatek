"""DataUpdateCoordinator for the Dontek Aquatek integration.

Owns the device state dict (register → value) and dispatches updates to entities
when MQTT messages arrive. No polling — the device pushes all state changes.
"""

from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    REG_DEVICE_NAME_BASE,
    REG_SOCKET_TYPE_BASE,
    SOCKET_COUNT,
    SOCKET_TYPE_NONE,
)
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
        self._initial_data_event: asyncio.Event = asyncio.Event()

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

    async def async_wait_for_initial_data(self, timeout: float = 15.0) -> bool:
        """Wait until the device sends its initial full state dump.

        Returns True when data arrives, False on timeout. Safe to call even if
        data has already arrived.
        """
        try:
            await asyncio.wait_for(self._initial_data_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            _LOGGER.warning("Timed out waiting for initial device data")
            return False

    def get_socket_configs(self) -> dict[int, int]:
        """Return {socket_n: type_index} for every configured socket (type != None).

        Reads the socket type config registers (REG_SOCKET_TYPE_BASE + n, 1-indexed).
        The type index is the hi byte of the register value.
        """
        if not self.data:
            return {}
        configs: dict[int, int] = {}
        for n in range(1, SOCKET_COUNT + 1):
            val = self.data.get(REG_SOCKET_TYPE_BASE + n, 0)
            type_idx = (val >> 8) & 0xFF
            if type_idx != SOCKET_TYPE_NONE:
                configs[n] = type_idx
        return configs

    def handle_message(self, reg: int, values: list[int]) -> None:
        """Called by MQTT client on each incoming status message.

        Two message formats exist:
        - reg != 1: values are consecutive starting at reg (sequential update)
        - reg == 1: values are [r1, v1, r2, v2, ...] key-value pairs (bulk state dump)
        """
        if self.data is None:
            self.data = {}

        changed = False

        if reg == 1 and len(values) > 2:
            # Bulk state dump — decode as (register, value) pairs
            for i in range(0, len(values) - 1, 2):
                r, v = values[i], values[i + 1]
                if self.data.get(r) != v:
                    self.data[r] = v
                    changed = True
            # Signal that we now have full device state
            if not self._initial_data_event.is_set():
                self._initial_data_event.set()
        else:
            # Sequential update: values at reg, reg+1, reg+2, ...
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
        """Reconstruct the device name from registers 65488–65495.

        Each register holds two packed ASCII bytes (big-endian).
        A zero low-byte or zero register marks end of string.
        Example: reg=0x5448 → 'T','H' ; reg=0x4B00 → 'K' then stop.
        """
        if not self.data:
            return None
        chars = []
        for i in range(8):
            val = self.data.get(REG_DEVICE_NAME_BASE + i, 0)
            if val == 0:
                break
            hi = (val >> 8) & 0xFF
            lo = val & 0xFF
            if hi:
                chars.append(chr(hi))
            if lo:
                chars.append(chr(lo))
            else:
                break  # null terminator in low byte
        return "".join(chars) if chars else None
