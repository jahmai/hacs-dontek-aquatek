"""Tests for config_flow.py."""
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aquatek.config_flow import _parse_device_id
from custom_components.aquatek.const import CONF_DEVICE_ID, DOMAIN

from .conftest import DEVICE_ID, FAKE_CERTS


# ---------------------------------------------------------------------------
# _parse_device_id
# ---------------------------------------------------------------------------


def test_parse_device_id_valid():
    assert _parse_device_id("12345678901234567") == "12345678901234567"


def test_parse_device_id_strips_whitespace():
    assert _parse_device_id("  12345  ") == "12345"


def test_parse_device_id_rejects_non_numeric():
    assert _parse_device_id("ABCDEF") is None


def test_parse_device_id_rejects_alphanumeric():
    assert _parse_device_id("1234abc") is None


def test_parse_device_id_rejects_empty():
    assert _parse_device_id("") is None


# ---------------------------------------------------------------------------
# Config flow — step_user
# ---------------------------------------------------------------------------


async def test_step_user_shows_form(hass):
    """Initial visit returns the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_step_user_invalid_id_shows_error(hass):
    """Non-numeric device ID shows validation error without advancing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_ID: "not-a-number"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "device_id" in result["errors"]


# ---------------------------------------------------------------------------
# Config flow — happy path
# ---------------------------------------------------------------------------


async def test_full_flow_creates_entry(hass):
    """Valid device ID + successful provisioning creates a config entry."""
    with patch(
        "custom_components.aquatek.config_flow.provision_and_store",
        return_value=FAKE_CERTS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE_ID: DEVICE_ID},
        )
        assert result["type"] == FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "provision"

        # Let the provision task complete
        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Aquatek {DEVICE_ID}"
    assert result["data"][CONF_DEVICE_ID] == DEVICE_ID


# ---------------------------------------------------------------------------
# Config flow — duplicate device
# ---------------------------------------------------------------------------


async def test_flow_aborts_on_duplicate_device(hass):
    """Starting a flow for an already-configured device ID aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE_ID: DEVICE_ID},
        unique_id=DEVICE_ID,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.aquatek.config_flow.provision_and_store",
        return_value=FAKE_CERTS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE_ID: DEVICE_ID},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# Config flow — provision failure
# ---------------------------------------------------------------------------


async def test_full_flow_provision_failure_shows_error(hass):
    """A boto3 exception during provisioning returns to the user form with an error."""
    with patch(
        "custom_components.aquatek.config_flow.provision_and_store",
        side_effect=Exception("AWS unavailable"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE_ID: DEVICE_ID},
        )
        assert result["type"] == FlowResultType.SHOW_PROGRESS

        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "provision_failed"}
