"""Tests for auth.py — AWS certificate provisioning."""
from unittest.mock import MagicMock, patch

import pytest

from custom_components.dontek_aquatek.auth import (
    _get_cognito_credentials,
    _provision_certificates,
    delete_certificates,
    load_or_provision_certificates,
)
from custom_components.dontek_aquatek.const import STORAGE_KEY, STORAGE_VERSION

from .conftest import DEVICE_ID, FAKE_CERTS


# ---------------------------------------------------------------------------
# _get_cognito_credentials
# ---------------------------------------------------------------------------


def test_get_cognito_credentials_returns_keys():
    """Returns access_key, secret_key, session_token from Cognito."""
    mock_cognito = MagicMock()
    mock_cognito.get_id.return_value = {"IdentityId": "ap-southeast-2:fake-id"}
    mock_cognito.get_credentials_for_identity.return_value = {
        "Credentials": {
            "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
            "SecretKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "SessionToken": "token123",
        }
    }

    with patch("boto3.client", return_value=mock_cognito):
        creds = _get_cognito_credentials()

    assert creds["access_key"] == "AKIAIOSFODNN7EXAMPLE"
    assert creds["secret_key"] == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    assert creds["session_token"] == "token123"


def test_get_cognito_credentials_uses_identity_id():
    """Passes the identity ID returned by get_id into get_credentials_for_identity."""
    mock_cognito = MagicMock()
    mock_cognito.get_id.return_value = {"IdentityId": "ap-southeast-2:specific-id"}
    mock_cognito.get_credentials_for_identity.return_value = {
        "Credentials": {
            "AccessKeyId": "A",
            "SecretKey": "B",
            "SessionToken": "C",
        }
    }

    with patch("boto3.client", return_value=mock_cognito):
        _get_cognito_credentials()

    mock_cognito.get_credentials_for_identity.assert_called_once_with(
        IdentityId="ap-southeast-2:specific-id"
    )


# ---------------------------------------------------------------------------
# _provision_certificates
# ---------------------------------------------------------------------------


def test_provision_certificates_returns_cert_fields():
    """Returns cert_id, cert_pem, and private_key."""
    mock_iot = MagicMock()
    mock_iot.create_keys_and_certificate.return_value = {
        "certificateId": FAKE_CERTS["cert_id"],
        "certificateArn": "arn:aws:iot:ap-southeast-2:123:cert/fake",
        "certificatePem": FAKE_CERTS["cert_pem"],
        "keyPair": {"PrivateKey": FAKE_CERTS["private_key"]},
    }

    with patch("boto3.client", return_value=mock_iot):
        result = _provision_certificates(
            {
                "access_key": "A",
                "secret_key": "B",
                "session_token": "C",
            }
        )

    assert result["cert_id"] == FAKE_CERTS["cert_id"]
    assert result["cert_pem"] == FAKE_CERTS["cert_pem"]
    assert result["private_key"] == FAKE_CERTS["private_key"]


def test_provision_certificates_attaches_policy():
    """Attaches 'pswpolicy' to the certificate ARN."""
    mock_iot = MagicMock()
    mock_iot.create_keys_and_certificate.return_value = {
        "certificateId": "id",
        "certificateArn": "arn:aws:iot:ap-southeast-2:123:cert/fake",
        "certificatePem": "pem",
        "keyPair": {"PrivateKey": "key"},
    }

    with patch("boto3.client", return_value=mock_iot):
        _provision_certificates({"access_key": "A", "secret_key": "B", "session_token": "C"})

    mock_iot.attach_policy.assert_called_once_with(
        policyName="pswpolicy",
        target="arn:aws:iot:ap-southeast-2:123:cert/fake",
    )


# ---------------------------------------------------------------------------
# load_or_provision_certificates
# ---------------------------------------------------------------------------


async def test_load_returns_stored_certs(hass):
    """Returns stored certs without calling AWS when storage is populated."""
    from homeassistant.helpers.storage import Store

    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{DEVICE_ID}")
    await store.async_save(FAKE_CERTS)

    with patch("custom_components.dontek_aquatek.auth._do_provision") as mock_provision:
        result = await load_or_provision_certificates(hass, DEVICE_ID)

    mock_provision.assert_not_called()
    assert result["cert_id"] == FAKE_CERTS["cert_id"]
    assert result["cert_pem"] == FAKE_CERTS["cert_pem"]


async def test_load_provisions_when_storage_empty(hass):
    """Calls _do_provision and saves result when no certs are stored."""
    with patch(
        "custom_components.dontek_aquatek.auth._do_provision", return_value=FAKE_CERTS
    ) as mock_provision:
        result = await load_or_provision_certificates(hass, DEVICE_ID)

    mock_provision.assert_called_once()
    assert result["cert_id"] == FAKE_CERTS["cert_id"]


async def test_load_saves_provisioned_certs(hass):
    """Provisioned certs are persisted so the next call doesn't re-provision."""
    from homeassistant.helpers.storage import Store

    with patch("custom_components.dontek_aquatek.auth._do_provision", return_value=FAKE_CERTS):
        await load_or_provision_certificates(hass, DEVICE_ID)

    # Second call — should hit storage, not boto3
    with patch("custom_components.dontek_aquatek.auth._do_provision") as mock_provision:
        result = await load_or_provision_certificates(hass, DEVICE_ID)

    mock_provision.assert_not_called()
    assert result["cert_id"] == FAKE_CERTS["cert_id"]


# ---------------------------------------------------------------------------
# delete_certificates
# ---------------------------------------------------------------------------


async def test_delete_certificates_removes_storage(hass):
    """Stored certs are gone after delete_certificates."""
    from homeassistant.helpers.storage import Store

    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{DEVICE_ID}")
    await store.async_save(FAKE_CERTS)

    await delete_certificates(hass, DEVICE_ID)

    remaining = await store.async_load()
    assert remaining is None
