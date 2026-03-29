"""
Smoke test — run manually to verify the real AWS service behaves as expected.

Usage:
    pip install boto3
    python local/smoke_aws.py

Standalone — no homeassistant package required.
"""

import os
import socket
import ssl
import tempfile
import traceback

# ── Constants (from const.py) ──────────────────────────────────────────────
COGNITO_POOL_ID = "ap-southeast-2:c45f75ed-a7e5-4a4f-b27a-ac3941f6d9bf"
AWS_REGION = "ap-southeast-2"
IOT_ENDPOINT = "a219g53ny7vwvd-ats.iot.ap-southeast-2.amazonaws.com"
IOT_POLICY_NAME = "pswpolicy"

PASS = "\033[32m PASS\033[0m"
FAIL = "\033[31m FAIL\033[0m"


def check(label: str, fn):
    try:
        result = fn()
        print(f"{PASS}  {label}")
        return result
    except Exception:
        print(f"{FAIL}  {label}")
        traceback.print_exc()
        return None


# ── 1. Cognito ─────────────────────────────────────────────────────────────
print("\n-- Cognito ----------------------------------------------")

import boto3

def _cognito_creds():
    cognito = boto3.client("cognito-identity", region_name=AWS_REGION)
    identity_id = cognito.get_id(IdentityPoolId=COGNITO_POOL_ID)["IdentityId"]
    creds = cognito.get_credentials_for_identity(IdentityId=identity_id)["Credentials"]
    return {
        "access_key": creds["AccessKeyId"],
        "secret_key": creds["SecretKey"],
        "session_token": creds["SessionToken"],
    }

creds = check("get_id + get_credentials_for_identity succeed", _cognito_creds)

if creds:
    check("access_key present", lambda: (True if creds["access_key"] else (_ for _ in ()).throw(AssertionError("empty"))))
    check("secret_key present", lambda: (True if creds["secret_key"] else (_ for _ in ()).throw(AssertionError("empty"))))
    check("session_token present", lambda: (True if creds["session_token"] else (_ for _ in ()).throw(AssertionError("empty"))))

# ── 2. IoT Certificate Provisioning ───────────────────────────────────────
print("\n-- IoT Certificate Provisioning -------------------------")

cert_data = None

def _provision(aws_creds):
    iot = boto3.client(
        "iot",
        region_name=AWS_REGION,
        aws_access_key_id=aws_creds["access_key"],
        aws_secret_access_key=aws_creds["secret_key"],
        aws_session_token=aws_creds["session_token"],
    )
    result = iot.create_keys_and_certificate(setAsActive=True)
    iot.attach_policy(policyName=IOT_POLICY_NAME, target=result["certificateArn"])
    return {
        "cert_id": result["certificateId"],
        "cert_pem": result["certificatePem"],
        "private_key": result["keyPair"]["PrivateKey"],
    }

if creds:
    cert_data = check("CreateKeysAndCertificate + attach pswpolicy succeed", lambda: _provision(creds))

if cert_data:
    check("cert_id is 64-char hex", lambda: (
        len(cert_data["cert_id"]) == 64
        and all(c in "0123456789abcdef" for c in cert_data["cert_id"])
    ) or (_ for _ in ()).throw(AssertionError(f"got: {cert_data['cert_id']!r}")))

    check("cert_pem is PEM", lambda: (
        "-----BEGIN CERTIFICATE-----" in cert_data["cert_pem"]
        and "-----END CERTIFICATE-----" in cert_data["cert_pem"]
    ) or (_ for _ in ()).throw(AssertionError("PEM markers missing")))

    check("private_key is PEM", lambda: (
        "-----BEGIN RSA PRIVATE KEY-----" in cert_data["private_key"]
        and "-----END RSA PRIVATE KEY-----" in cert_data["private_key"]
    ) or (_ for _ in ()).throw(AssertionError("key PEM markers missing")))

# ── 3. TLS Handshake ───────────────────────────────────────────────────────
print("\n-- MQTT Endpoint TLS Handshake --------------------------")

def _tls_handshake():
    with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as cf:
        cf.write(cert_data["cert_pem"].encode())
        cert_path = cf.name
    with tempfile.NamedTemporaryFile(suffix=".key", delete=False) as kf:
        kf.write(cert_data["private_key"].encode())
        key_path = kf.name
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
        with socket.create_connection((IOT_ENDPOINT, 8883), timeout=10) as raw:
            with ctx.wrap_socket(raw, server_hostname=IOT_ENDPOINT):
                pass
    finally:
        os.unlink(cert_path)
        os.unlink(key_path)

if cert_data:
    check("TLS handshake on :8883 accepted by AWS IoT", _tls_handshake)
else:
    print("  (skipping — no cert available)")

print()
