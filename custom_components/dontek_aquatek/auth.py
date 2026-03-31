"""AWS IoT certificate provisioning for the Dontek Aquatek integration.

Flow (mirrors b3/q.java case 1 in the decompiled app):
  1. Get temporary AWS credentials via unauthenticated Cognito Identity Pool.
  2. Call AWS IoT CreateKeysAndCertificate to get a cert + private key pair.
  3. Attach the hardcoded IoT policy ("pswpolicy") to the certificate.
  4. Persist the cert/key in HA storage so they survive restarts.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    AWS_REGION,
    COGNITO_POOL_ID,
    DOMAIN,
    IOT_POLICY_NAME,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


def _get_cognito_credentials() -> dict[str, str]:
    """Get temporary AWS credentials from the unauthenticated Cognito Identity Pool.

    This is a synchronous blocking call — must be run in an executor.
    """
    import boto3  # noqa: PLC0415

    cognito = boto3.client("cognito-identity", region_name=AWS_REGION)

    identity = cognito.get_id(IdentityPoolId=COGNITO_POOL_ID)
    identity_id = identity["IdentityId"]

    creds_response = cognito.get_credentials_for_identity(IdentityId=identity_id)
    creds = creds_response["Credentials"]

    return {
        "access_key": creds["AccessKeyId"],
        "secret_key": creds["SecretKey"],
        "session_token": creds["SessionToken"],
    }


def _provision_certificates(aws_creds: dict[str, str]) -> dict[str, str]:
    """Create an AWS IoT certificate and attach the device policy.

    This is a synchronous blocking call — must be run in an executor.
    Returns a dict with: cert_id, cert_pem, private_key.
    """
    import boto3  # noqa: PLC0415

    iot = boto3.client(
        "iot",
        region_name=AWS_REGION,
        aws_access_key_id=aws_creds["access_key"],
        aws_secret_access_key=aws_creds["secret_key"],
        aws_session_token=aws_creds["session_token"],
    )

    result = iot.create_keys_and_certificate(setAsActive=True)
    cert_id = result["certificateId"]
    cert_arn = result["certificateArn"]
    cert_pem = result["certificatePem"]
    private_key = result["keyPair"]["PrivateKey"]

    iot.attach_policy(policyName=IOT_POLICY_NAME, target=cert_arn)

    _LOGGER.debug("Provisioned IoT certificate: %s...", cert_id[:10])

    return {
        "cert_id": cert_id,
        "cert_pem": cert_pem,
        "private_key": private_key,
    }


def _do_provision() -> dict[str, str]:
    """Full synchronous provisioning sequence."""
    aws_creds = _get_cognito_credentials()
    return _provision_certificates(aws_creds)


async def load_or_provision_certificates(
    hass: HomeAssistant, entry_id: str
) -> dict[str, str]:
    """Return stored certificates, provisioning new ones if needed.

    Certificates are stored in HA's .storage directory under a key
    scoped to the config entry ID so multiple controllers are independent.
    """
    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}")
    stored: dict[str, Any] | None = await store.async_load()

    if stored and stored.get("cert_pem") and stored.get("private_key"):
        _LOGGER.debug("Loaded existing IoT certificates from storage.")
        return stored

    _LOGGER.info("No certificates found — provisioning new AWS IoT certificate.")
    certs = await hass.async_add_executor_job(_do_provision)
    await store.async_save(certs)
    return certs


async def provision_and_store(
    hass: HomeAssistant, entry_id: str
) -> dict[str, str]:
    """Force fresh provisioning (used during config flow for new entries)."""
    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}")
    certs = await hass.async_add_executor_job(_do_provision)
    await store.async_save(certs)
    return certs


async def delete_certificates(hass: HomeAssistant, entry_id: str) -> None:
    """Remove stored certificates when an entry is removed."""
    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}")
    await store.async_remove()
