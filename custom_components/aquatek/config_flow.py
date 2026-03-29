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

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .auth import provision_and_store
from .const import CONF_DEVICE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

# The QR code encodes a numeric device ID (e.g. "12345678901234567").
_NUMERIC_ID_RE = re.compile(r"^\d+$")


def _parse_device_id(raw: str) -> str | None:
    """Validate and return the numeric device ID, or None if invalid."""
    raw = raw.strip()
    return raw if _NUMERIC_ID_RE.match(raw) else None


STEP_USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_DEVICE_ID): str}
)


class AquatekConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Aquatek config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._device_id: str = ""
        self._provision_task = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            device_id = _parse_device_id(user_input[CONF_DEVICE_ID])

            if device_id is None:
                errors[CONF_DEVICE_ID] = "invalid_device_id"
            else:
                # Abort if this controller is already set up
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()

                self._device_id = device_id
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

    async def async_step_provision_done(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the config entry after successful provisioning."""
        # cert_id was stashed on the instance by _do_provision
        return self.async_create_entry(
            title=f"Aquatek {self._device_id}",
            data={
                CONF_DEVICE_ID: self._device_id,
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
        # We use a temporary entry ID during flow; certs are re-keyed on entry creation
        # if needed. For now, use the MAC as the storage key during provisioning.
        await provision_and_store(self.hass, self._device_id)
