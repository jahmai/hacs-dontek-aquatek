"""Config flow for the Dontek Aquatek integration.

Steps:
  1. user     — collect and validate MAC address
  2. provision — run AWS IoT certificate provisioning (async, shows progress)
"""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .auth import provision_and_store
from .const import (
    CONF_LOCAL_BROKER_HOST,
    CONF_LOCAL_BROKER_PORT,
    CONF_MAC,
    CONF_USE_LOCAL_BROKER,
    DEFAULT_LOCAL_BROKER_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Accept: "AA:BB:CC:DD:EE:FF", "aa:bb:cc:dd:ee:ff", "aabbccddeeff", "AA-BB-CC-DD-EE-FF"
_MAC_RE = re.compile(r"^([0-9a-fA-F]{2}[:\-]?){5}[0-9a-fA-F]{2}$")


def _parse_mac(raw: str) -> str | None:
    """Parse any supported input to a lowercase no-colon MAC (e.g. 'aabbccddeeff').

    Accepted formats:
      - MAC with colons/dashes  — "AA:BB:CC:DD:EE:FF" or "AA-BB-CC-DD-EE-FF"
      - MAC without separators  — "aabbccddeeff"
      - QR-code numeric ID      — e.g. "62678480408215041" (integer whose upper
                                   6 bytes encode the MAC, as printed on the
                                   controller sticker)
    """
    raw = raw.strip()

    # Standard MAC formats
    if _MAC_RE.match(raw):
        return raw.replace(":", "").replace("-", "").lower()

    # Numeric QR-code ID: convert to hex, take first 12 nibbles (6 bytes)
    if raw.isdigit():
        hex_str = f"{int(raw):x}"
        if len(hex_str) >= 12:
            return hex_str[:12].lower()

    return None


STEP_USER_SCHEMA = vol.Schema({
    vol.Required(CONF_MAC): str,
    vol.Optional(CONF_USE_LOCAL_BROKER, default=False): bool,
})

STEP_LOCAL_BROKER_SCHEMA = vol.Schema({
    vol.Required(CONF_LOCAL_BROKER_HOST, default="localhost"): str,
    vol.Required(CONF_LOCAL_BROKER_PORT, default=DEFAULT_LOCAL_BROKER_PORT): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=65535)
    ),
})


class AquatekOptionsFlow(OptionsFlow):
    """Options flow — shows device info and triggers reload via HA's built-in button."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data={})

        mac = self.config_entry.data.get(CONF_MAC, "unknown")
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
            description_placeholders={"mac": mac},
        )


class AquatekConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Aquatek config flow."""

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> AquatekOptionsFlow:
        return AquatekOptionsFlow()

    VERSION = 1

    def __init__(self) -> None:
        self._mac: str = ""
        self._use_local_broker: bool = False
        self._provision_task = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            mac = _parse_mac(user_input[CONF_MAC])

            if mac is None:
                errors[CONF_MAC] = "invalid_mac"
            else:
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()

                self._mac = mac
                self._use_local_broker = user_input.get(CONF_USE_LOCAL_BROKER, False)

                if self._use_local_broker:
                    return await self.async_step_local_broker()
                return await self.async_step_provision()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_provision(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Run AWS IoT certificate provisioning."""
        if not self._provision_task:
            self._provision_task = self.hass.async_create_task(
                self._do_provision()
            )
            return self.async_show_progress(
                step_id="provision",
                progress_action="provision",
                progress_task=self._provision_task,
            )

        try:
            await self._provision_task
        except Exception:
            _LOGGER.exception("Certificate provisioning failed")
            return self.async_show_progress_done(next_step_id="provision_failed")

        return self.async_show_progress_done(next_step_id="provision_done")

    async def async_step_local_broker(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect local broker host and port."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(
                title=f"Aquatek {self._mac} (local)",
                data={
                    CONF_MAC: self._mac,
                    CONF_USE_LOCAL_BROKER: True,
                    CONF_LOCAL_BROKER_HOST: user_input[CONF_LOCAL_BROKER_HOST],
                    CONF_LOCAL_BROKER_PORT: user_input[CONF_LOCAL_BROKER_PORT],
                },
            )

        return self.async_show_form(
            step_id="local_broker",
            data_schema=STEP_LOCAL_BROKER_SCHEMA,
            errors=errors,
        )

    async def async_step_provision_done(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the config entry after successful provisioning."""
        return self.async_create_entry(
            title=f"Aquatek {self._mac}",
            data={
                CONF_MAC: self._mac,
                CONF_USE_LOCAL_BROKER: False,
            },
        )

    async def async_step_provision_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show error and let user retry."""
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors={"base": "provision_failed"},
        )

    async def _do_provision(self) -> None:
        """Run provisioning and store certs — called as an HA task."""
        await provision_and_store(self.hass, self._mac)
