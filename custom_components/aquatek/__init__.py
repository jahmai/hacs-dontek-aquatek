"""Dontek Aquatek pool controller integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .auth import delete_certificates, load_or_provision_certificates
from .const import CONF_DEVICE_ID, DOMAIN
from .coordinator import AquatekCoordinator
from .mqtt_client import AquatekMQTTClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.CLIMATE,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aquatek from a config entry."""
    mac = entry.data[CONF_DEVICE_ID]

    # Load or provision AWS IoT certificates
    try:
        certs = await load_or_provision_certificates(hass, entry.entry_id)
    except Exception:
        _LOGGER.exception("Failed to load/provision certificates for %s", mac)
        return False

    # Build MQTT client (not connected yet)
    coordinator = None  # forward-declare for callbacks

    def on_message(reg: int, values: list[int]) -> None:
        if coordinator is not None:
            coordinator.handle_message(reg, values)

    def on_state_change(state) -> None:
        if coordinator is not None:
            coordinator.handle_state_change(state)

    mqtt_client = AquatekMQTTClient(
        mac=mac,
        cert_pem=certs["cert_pem"],
        private_key=certs["private_key"],
        message_callback=on_message,
        state_callback=on_state_change,
    )

    coordinator = AquatekCoordinator(hass, entry, mqtt_client)

    # Connect
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
