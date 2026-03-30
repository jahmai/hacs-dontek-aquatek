"""
Smoke test — connect to a real Aquatek device via AWS IoT MQTT and dump live state.

Usage:
    python scripts/smoke_device.py <device_id>
    python scripts/smoke_device.py <device_id> --listen 60
    python scripts/smoke_device.py <device_id> --fresh-cert

    # Button-test mode: suppress initial state dump, show only change events
    python scripts/smoke_device.py <device_id> --button-test --listen 600

The device ID can be:
  - MAC with colons/dashes:   AA:BB:CC:DD:EE:FF
  - MAC without separators:   aabbccddeeff
  - Numeric QR code ID:       62678480408215041

Certificates are cached in local/smoke_cert.json so you don't provision a new one
every run (each provisioned cert is permanent in AWS IoT). Use --fresh-cert to force
a new one.

Requirements:
    pip install boto3 awsiotsdk
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

# ── Constants (mirrors const.py) ──────────────────────────────────────────────
COGNITO_POOL_ID = "ap-southeast-2:c45f75ed-a7e5-4a4f-b27a-ac3941f6d9bf"
AWS_REGION = "ap-southeast-2"
IOT_ENDPOINT = "a219g53ny7vwvd-ats.iot.ap-southeast-2.amazonaws.com"
IOT_POLICY_NAME = "pswpolicy"

CERT_CACHE = Path(__file__).parent.parent / "local" / "smoke_cert.json"

# ── Register name map ─────────────────────────────────────────────────────────
# Socket output registers (REG_SOCKET_BASE=65334, socket n = 65334+n, 1-indexed)
# Socket type is configured per-device; labels below are from hardware testing.
REG_NAMES: dict[int, str] = {
    # Socket outputs (0=off, 1=on, 2=auto)
    65335: "Socket 1 output",
    65336: "Socket 2 output [Sanitiser confirmed]",
    65337: "Socket 3 output",
    65338: "Socket 4 output [Jet Pump confirmed]",
    65339: "Socket 5 output [Pool Light confirmed]",
    # Socket type config registers (hi byte = type index from APK arrays.xml)
    17: "Socket 1 type config",
    18: "Socket 2 type config",
    19: "Socket 3 type config",
    20: "Socket 4 type config",
    21: "Socket 5 type config",
    # Pump speed outputs (socket 5 onwards = pump 0+)
    **{65352 + i: f"Pump {i} speed" for i in range(12)},
    # VF connector — filter pump (0=off, 257/513/769/1025=speed1-4, 65535=auto)
    65485: "Filter pump VF [confirmed]",
    # Filter times
    57650: "Filter time 1",
    57670: "Filter time 2",
    # Heating (57xxx range)
    57510: "Heater type config (0=Smart,1=HeatPump,2=Gas)",
    57517: "Heat Pump on/off/auto [confirmed] (0=off,2=auto)",
    57575: "Heat setpoint [confirmed] (value = C x2, e.g. 32C=64)",
    57583: "Heater mode (0=off)",
    # Gas Heater output (socket-output range, 65334+14)
    65348: "Gas Heater on/off/auto [confirmed] (0=off,2=auto)",
    # Solar
    57585: "Solar enabled (bit 0)",
    # Device name
    **{65488 + i: f"Device name byte {i}" for i in range(8)},
}


def reg_label(reg: int) -> str:
    return REG_NAMES.get(reg, f"reg {reg}")


# ── Terminal colours ──────────────────────────────────────────────────────────
GREEN  = "\033[32m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


# ── Certificate provisioning ──────────────────────────────────────────────────

def provision_certificates() -> dict:
    """Get Cognito credentials and create a new IoT certificate."""
    import boto3

    print(f"{YELLOW}Provisioning new AWS IoT certificate...{RESET}")
    cognito = boto3.client("cognito-identity", region_name=AWS_REGION)
    identity_id = cognito.get_id(IdentityPoolId=COGNITO_POOL_ID)["IdentityId"]
    creds = cognito.get_credentials_for_identity(IdentityId=identity_id)["Credentials"]

    iot = boto3.client(
        "iot",
        region_name=AWS_REGION,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretKey"],
        aws_session_token=creds["SessionToken"],
    )
    result = iot.create_keys_and_certificate(setAsActive=True)
    iot.attach_policy(policyName=IOT_POLICY_NAME, target=result["certificateArn"])

    cert_data = {
        "cert_id": result["certificateId"],
        "cert_pem": result["certificatePem"],
        "private_key": result["keyPair"]["PrivateKey"],
    }
    print(f"{GREEN}  cert_id: {cert_data['cert_id'][:16]}...{RESET}")
    return cert_data


def load_or_provision(fresh: bool) -> dict:
    if not fresh and CERT_CACHE.exists():
        data = json.loads(CERT_CACHE.read_text())
        print(f"{GREEN}Reusing cached cert: {data['cert_id'][:16]}...{RESET}")
        return data

    CERT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    data = provision_certificates()
    CERT_CACHE.write_text(json.dumps(data, indent=2))
    print(f"  Cached to {CERT_CACHE}")
    return data


# ── MQTT smoke test ───────────────────────────────────────────────────────────

async def run(device_id: str, cert_data: dict, listen_secs: int, button_test: bool) -> None:
    from awscrt import mqtt
    from awsiot import mqtt_connection_builder

    mac = device_id.replace(":", "").replace("-", "").lower()
    topic_status = f"dontek{mac}/status/psw"
    topic_shadow = f"$aws/things/{mac.upper()}_VERSION/shadow/get/+"
    client_id = f"aquatek-{mac}-{uuid.uuid4().hex[:8]}"

    register_state: dict[int, int] = {}
    message_count = 0
    # In button-test mode suppress the initial state dump (first burst on connect).
    # We ignore messages until the stream goes quiet for a moment: track connect time
    # and skip for the first DUMP_SETTLE_SECS seconds.
    DUMP_SETTLE_SECS = 8
    connect_time: float = 0.0

    def on_message(topic, payload, **kwargs):
        nonlocal message_count
        try:
            data = json.loads(payload)
            msg_id = data.get("messageId", "?")
            reg = int(data["modbusReg"])
            vals = [int(v) for v in data["modbusVal"]]
        except Exception as e:
            print(f"  [parse error] {e}: {payload[:80]}")
            return

        # Update register state regardless of suppression
        for offset, val in enumerate(vals):
            register_state[reg + offset] = val

        # In button-test mode, skip the initial dump
        if button_test and connect_time and (time.time() - connect_time < DUMP_SETTLE_SECS):
            return

        message_count += 1
        ts = time.strftime("%H:%M:%S")
        label = reg_label(reg)
        vals_str = ", ".join(str(v) for v in vals)
        if button_test:
            # Compact format for reading register changes while pressing buttons
            print(f"{ts}  [{msg_id:<5}] reg={reg:>6}  val=[{vals_str}]  {label}")
        else:
            print(f"  {CYAN}{ts}{RESET}  reg={reg} ({label})  val=[{vals_str}]")

    def on_shadow(topic, payload, **kwargs):
        ts = time.strftime("%H:%M:%S")
        print(f"  {CYAN}{ts}{RESET}  [shadow] {payload[:120]}")

    def on_interrupted(connection, error, **kwargs):
        print(f"\n{YELLOW}  MQTT interrupted: {error}{RESET}")

    def on_resumed(connection, return_code, session_present, **kwargs):
        print(f"\n{GREEN}  MQTT resumed{RESET}")

    print(f"\n{BOLD}Connecting to AWS IoT MQTT...{RESET}")
    print(f"  endpoint : {IOT_ENDPOINT}")
    print(f"  device   : {device_id} -> mac={mac}")
    print(f"  client_id: {client_id}")
    print(f"  topics   : {topic_status}")
    print(f"             {topic_shadow}")

    connection = mqtt_connection_builder.mtls_from_bytes(
        endpoint=IOT_ENDPOINT,
        cert_bytes=cert_data["cert_pem"].encode(),
        pri_key_bytes=cert_data["private_key"].encode(),
        client_id=client_id,
        clean_session=False,
        keep_alive_secs=60,
        on_connection_interrupted=on_interrupted,
        on_connection_resumed=on_resumed,
    )

    await asyncio.wrap_future(connection.connect())
    connect_time = time.time()
    print(f"{GREEN}Connected.{RESET}")

    sub_future, _ = connection.subscribe(
        topic=topic_status,
        qos=mqtt.QoS.AT_MOST_ONCE,
        callback=on_message,
    )
    await asyncio.wrap_future(sub_future)

    shadow_future, _ = connection.subscribe(
        topic=topic_shadow,
        qos=mqtt.QoS.AT_MOST_ONCE,
        callback=on_shadow,
    )
    await asyncio.wrap_future(shadow_future)

    if button_test:
        print(f"\n{BOLD}READY — button-test mode, suppressing initial dump ({DUMP_SETTLE_SECS}s){RESET}")
        print(f"Press appliance buttons in the app. Each change prints one line.\n")
    else:
        print(f"\n{BOLD}Listening for {listen_secs}s — waiting for device messages...{RESET}\n")
    await asyncio.sleep(listen_secs)

    await asyncio.wrap_future(connection.disconnect())

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{BOLD}── Summary ────────────────────────────────────────────────{RESET}")
    print(f"  Messages received : {message_count}")
    print(f"  Registers seen    : {len(register_state)}")

    if register_state:
        print(f"\n  {BOLD}Register state snapshot:{RESET}")
        for reg in sorted(register_state):
            val = register_state[reg]
            print(f"    {reg:>6}  {val:>6}   {reg_label(reg)}")

        # Device name
        chars = []
        for i in range(8):
            v = register_state.get(65488 + i)
            if v and v != 0:
                chars.append(chr(v))
        if chars:
            print(f"\n  Device name: {''.join(chars)!r}")
    else:
        print(f"\n  {YELLOW}No messages received — is the device ID correct and the device online?{RESET}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Aquatek device smoke test")
    parser.add_argument("device_id", help="MAC address or numeric QR code ID")
    parser.add_argument("--listen", type=int, default=30,
                        help="Seconds to listen for messages (default: 30)")
    parser.add_argument("--fresh-cert", action="store_true",
                        help="Force new AWS IoT certificate (don't reuse cache)")
    parser.add_argument("--button-test", action="store_true",
                        help="Suppress initial state dump; print only change events (for mapping registers)")
    args = parser.parse_args()

    cert_data = load_or_provision(args.fresh_cert)
    asyncio.run(run(args.device_id, cert_data, args.listen, args.button_test))


if __name__ == "__main__":
    main()
