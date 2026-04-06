"""Dontek Aquatek pool controller integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .auth import delete_certificates, load_or_provision_certificates
from .const import (
    CONF_LOCAL_BROKER_HOST,
    CONF_LOCAL_BROKER_PORT,
    CONF_MAC,
    CONF_USE_LOCAL_BROKER,
    DEFAULT_LOCAL_BROKER_PORT,
    DOMAIN,
)
from .coordinator import AquatekCoordinator
from .mqtt_client import AquatekLocalMQTTClient, AquatekMQTTClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aquatek from a config entry."""
    mac = entry.data[CONF_MAC]

    coordinator = None  # forward-declare for callbacks

    def on_message(reg: int, values: list[int]) -> None:
        if coordinator is not None:
            coordinator.handle_message(reg, values)

    def on_state_change(state) -> None:
        if coordinator is not None:
            coordinator.handle_state_change(state)

    if entry.data.get(CONF_USE_LOCAL_BROKER):
        host = entry.data.get(CONF_LOCAL_BROKER_HOST, "localhost")
        port = entry.data.get(CONF_LOCAL_BROKER_PORT, DEFAULT_LOCAL_BROKER_PORT)
        mqtt_client = AquatekLocalMQTTClient(
            mac=mac,
            host=host,
            port=port,
            message_callback=on_message,
            state_callback=on_state_change,
        )
    else:
        try:
            certs = await load_or_provision_certificates(hass, entry.entry_id)
        except Exception:
            _LOGGER.exception("Failed to load/provision certificates for %s", mac)
            return False
        mqtt_client = AquatekMQTTClient(
            mac=mac,
            cert_pem=certs["cert_pem"],
            private_key=certs["private_key"],
            message_callback=on_message,
            state_callback=on_state_change,
        )

    coordinator = AquatekCoordinator(hass, entry, mqtt_client)

    # Connect — platforms set up immediately; socket entities are discovered
    # dynamically when the first device state dump arrives via coordinator listener.
    await coordinator.async_setup()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: AquatekCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.mqtt_client.disconnect()

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up stored certificates when entry is deleted."""
    await delete_certificates(hass, entry.entry_id)
