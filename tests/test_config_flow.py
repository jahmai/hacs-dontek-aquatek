"""Tests for config_flow.py."""
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dontek_aquatek.config_flow import _parse_mac
from custom_components.dontek_aquatek.const import (
    CONF_LOCAL_BROKER_HOST,
    CONF_LOCAL_BROKER_PORT,
    CONF_MAC,
    CONF_USE_LOCAL_BROKER,
    DEFAULT_LOCAL_BROKER_PORT,
    DOMAIN,
)

from .conftest import MAC, FAKE_CERTS


# ---------------------------------------------------------------------------
# _parse_mac
# ---------------------------------------------------------------------------


def test_parse_mac_colon_format():
    assert _parse_mac("AA:BB:CC:DD:EE:FF") == "aabbccddeeff"


def test_parse_mac_dash_format():
    assert _parse_mac("AA-BB-CC-DD-EE-FF") == "aabbccddeeff"


def test_parse_mac_no_separator():
    assert _parse_mac("aabbccddeeff") == "aabbccddeeff"


def test_parse_mac_strips_whitespace():
    assert _parse_mac("  aa:bb:cc:dd:ee:ff  ") == "aabbccddeeff"


def test_parse_mac_lowercase_output():
    assert _parse_mac("AA:BB:CC:DD:EE:FF") == "aabbccddeeff"


def test_parse_mac_numeric_qr_id():
    # 62678480408215041 = 0xdeadbeefcafe01 → first 6 bytes → deadbeefcafe
    assert _parse_mac("62678480408215041") == "deadbeefcafe"


def test_parse_mac_rejects_garbage():
    assert _parse_mac("not-a-mac") is None


def test_parse_mac_rejects_empty():
    assert _parse_mac("") is None


def test_parse_mac_rejects_short_numeric():
    assert _parse_mac("12345") is None  # fewer than 12 hex digits when converted


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


async def test_step_user_invalid_mac_shows_error(hass):
    """Invalid MAC shows validation error without advancing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MAC: "not-a-mac"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert CONF_MAC in result["errors"]


# ---------------------------------------------------------------------------
# Config flow — happy path
# ---------------------------------------------------------------------------


async def test_full_flow_creates_entry(hass):
    """Valid MAC + successful provisioning creates a config entry."""
    with patch(
        "custom_components.dontek_aquatek.config_flow.provision_and_store",
        return_value=FAKE_CERTS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_MAC: "AA:BB:CC:DD:EE:FF"},
        )
        assert result["type"] == FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "provision"

        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Aquatek aabbccddeeff"
    assert result["data"][CONF_MAC] == "aabbccddeeff"


async def test_full_flow_accepts_numeric_qr_id(hass):
    """Numeric QR code ID is accepted and decoded to MAC."""
    with patch(
        "custom_components.dontek_aquatek.config_flow.provision_and_store",
        return_value=FAKE_CERTS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_MAC: "62678480408215041"},
        )
        assert result["type"] == FlowResultType.SHOW_PROGRESS

        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_MAC] == "deadbeefcafe"


# ---------------------------------------------------------------------------
# Config flow — duplicate device
# ---------------------------------------------------------------------------


async def test_flow_aborts_on_duplicate_device(hass):
    """Starting a flow for an already-configured MAC aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MAC: MAC},
        unique_id=MAC,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.dontek_aquatek.config_flow.provision_and_store",
        return_value=FAKE_CERTS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_MAC: MAC},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# Config flow — provision failure
# ---------------------------------------------------------------------------


async def test_full_flow_provision_failure_shows_error(hass):
    """A boto3 exception during provisioning returns to the user form with an error."""
    with patch(
        "custom_components.dontek_aquatek.config_flow.provision_and_store",
        side_effect=Exception("AWS unavailable"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_MAC: MAC},
        )
        assert result["type"] == FlowResultType.SHOW_PROGRESS

        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "provision_failed"}


# ---------------------------------------------------------------------------
# Config flow — local broker
# ---------------------------------------------------------------------------


async def test_local_broker_flow_creates_entry(hass):
    """Toggling local broker skips provisioning and prompts for host/port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MAC: MAC, CONF_USE_LOCAL_BROKER: True},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "local_broker"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LOCAL_BROKER_HOST: "192.168.1.10", CONF_LOCAL_BROKER_PORT: 1884},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USE_LOCAL_BROKER] is True
    assert result["data"][CONF_LOCAL_BROKER_HOST] == "192.168.1.10"
    assert result["data"][CONF_LOCAL_BROKER_PORT] == 1884
    assert result["data"][CONF_MAC] == MAC


def test_local_broker_default_port_is_nonstandard():
    """Default port avoids clashing with standard Mosquitto on 1883."""
    assert DEFAULT_LOCAL_BROKER_PORT != 1883
    assert DEFAULT_LOCAL_BROKER_PORT == 1884


# ---------------------------------------------------------------------------
# Reconfigure flow
# ---------------------------------------------------------------------------


async def test_reconfigure_aws_to_local(hass):
    """Reconfiguring from AWS to local broker updates entry without provisioning."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MAC: MAC, CONF_USE_LOCAL_BROKER: False},
        unique_id=MAC,
    )
    entry.add_to_hass(hass)

    with patch("custom_components.dontek_aquatek.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USE_LOCAL_BROKER: True},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure_broker"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_LOCAL_BROKER_HOST: "localhost", CONF_LOCAL_BROKER_PORT: 1884},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_USE_LOCAL_BROKER] is True
    assert entry.data[CONF_LOCAL_BROKER_HOST] == "localhost"
    assert entry.data[CONF_LOCAL_BROKER_PORT] == 1884


async def test_reconfigure_local_to_aws_provisions(hass):
    """Reconfiguring from local to AWS runs provisioning."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_MAC: MAC,
            CONF_USE_LOCAL_BROKER: True,
            CONF_LOCAL_BROKER_HOST: "localhost",
            CONF_LOCAL_BROKER_PORT: 1884,
        },
        unique_id=MAC,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.dontek_aquatek.config_flow.provision_and_store",
        return_value=FAKE_CERTS,
    ), patch("custom_components.dontek_aquatek.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USE_LOCAL_BROKER: False},
        )
        assert result["type"] == FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "reconfigure_provision"

        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_USE_LOCAL_BROKER] is False


async def test_reconfigure_broker_host_port_update(hass):
    """Reconfiguring host/port on an existing local broker entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_MAC: MAC,
            CONF_USE_LOCAL_BROKER: True,
            CONF_LOCAL_BROKER_HOST: "localhost",
            CONF_LOCAL_BROKER_PORT: 1884,
        },
        unique_id=MAC,
    )
    entry.add_to_hass(hass)

    with patch("custom_components.dontek_aquatek.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USE_LOCAL_BROKER: True},
        )
        assert result["step_id"] == "reconfigure_broker"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_LOCAL_BROKER_HOST: "192.168.1.50", CONF_LOCAL_BROKER_PORT: 1883},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_LOCAL_BROKER_HOST] == "192.168.1.50"
    assert entry.data[CONF_LOCAL_BROKER_PORT] == 1883


async def test_reconfigure_aws_no_change_reloads(hass):
    """Reconfiguring an AWS entry back to AWS just reloads without provisioning."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MAC: MAC, CONF_USE_LOCAL_BROKER: False},
        unique_id=MAC,
    )
    entry.add_to_hass(hass)

    with patch("custom_components.dontek_aquatek.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USE_LOCAL_BROKER: False},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
