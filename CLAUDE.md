# Dontek Aquatek — HACS Integration

Home Assistant custom integration for the Dontek Aquatek / Theralux Pool+ Manager pool controller.

## Project Structure

```
custom_components/aquatek/   — the HACS integration
hacs.json                    — HACS metadata
local/                       — gitignored local dev files
```

## Protocol

The controller communicates exclusively via **AWS IoT MQTT** (cloud). There is no local API.

### Authentication

No user account is required. Auth flow:

1. Get temporary AWS credentials from the **unauthenticated** Cognito Identity Pool:
   - Pool ID: `ap-southeast-2:c45f75ed-a7e5-4a4f-b27a-ac3941f6d9bf`
   - Region: `ap-southeast-2`
2. Call AWS IoT `CreateKeysAndCertificate` → get X.509 cert + private key
3. Attach IoT policy `pswpolicy` to the certificate ARN
4. Connect to MQTT using the certificate

Certificates are stored in HA's `.storage/` directory (never written as raw files).
Keystore password (from device firmware): `d0nt3k_2k22`

### MQTT Connection

- **Endpoint**: `a219g53ny7vwvd-ats.iot.ap-southeast-2.amazonaws.com`
- **Auth**: X.509 mutual TLS
- **Client ID**: random UUID per session

### Device Identity

The device is identified by its **MAC address** (lowercase, no colons — e.g. `deadbeefcafe`).

The sticker on the controller shows both:
```
POOL+ MANAGER
4.10.2024
MAC SN:XXXXX          ← MAC address (colons may or may not be printed)
XXXXXXXXXXXXXXXXX     ← numeric QR code ID
```

The **numeric QR code ID** is the MAC address encoded as a big-endian integer in its upper 6 bytes. For example `62678480408215041` → hex `deadbeefcafe01` → MAC `deadbeefcafe`. The integration accepts either format and normalises to the no-colon lowercase MAC.

Internally the config entry stores `CONF_MAC` (the normalised MAC), not the QR code number.

### MQTT Topics

All topics use a `dontek` prefix followed by the MAC (confirmed against live hardware):

| Direction | Topic | Purpose |
|-----------|-------|---------|
| Subscribe | `dontek{mac}/status/psw` | Device pushes state updates |
| Publish | `dontek{mac}/cmd/psw` | Send commands to device |
| Subscribe | `$aws/things/{MAC_UPPER}_VERSION/shadow/get/+` | Firmware version (uppercased) |

`{mac}` is lowercase no-colon hex (e.g. `deadbeefcafe`).

The `pswpolicy` IoT policy grants `iot:Connect`, `iot:Subscribe`, and `iot:Publish` scoped to the `dontek{mac}/` prefix. Subscribing to any topic without this prefix is denied — the broker drops the connection immediately after the SUBSCRIBE packet.

### Message Format

All messages are JSON with a Modbus register structure:

```json
{"messageId": "read", "modbusReg": 123, "modbusVal": [0]}
{"messageId": "write", "modbusReg": 123, "modbusVal": [1]}
```

Multi-value messages set consecutive registers starting at `modbusReg`.

## Modbus Register Map

### Socket Architecture

The controller has **5 configurable output sockets**. Each socket is assigned an appliance type in the app (sanitiser, pool light, jet pump, etc.) and the assignment is stored on-device. The HA integration must auto-discover socket→appliance mappings at startup by reading config registers.

| Register | Feature |
|----------|---------|
| `65334 + n` (n = 1–5) | Socket n output (0=off, 1=on, 2=auto) |
| `16 + n` (n = 1–5) | Socket n type config — hi byte = type index (see below) |

**Socket type indices** (from APK `arrays.xml` `socket_type_options`):

| Index | Appliance |
|-------|-----------|
| 0 | None |
| 1 | Sanitiser |
| 2 | Filter Pump |
| 3 | Cleaning Pump |
| 4 | Blower |
| 5 | Pool Light |
| 12 | Jet Pump |
| 13 | Heating Pump |

**Confirmed socket assignments** on tested device:
- Socket 2 → reg 65336 → Sanitiser ✓
- Socket 4 → reg 65338 → Jet Pump ✓
- Socket 5 → reg 65339 → Pool Light ✓

### VF Connectors (variable-frequency drives, 2 total)

Used for speed-controlled loads. Filter pump confirmed on hardware:

| Register | Feature | Values |
|----------|---------|--------|
| 65485 | Filter pump | 0=off, 257=spd1, 513=spd2, 769=spd3, 1025=spd4, 65535=auto |

### Heating

| Register | Feature | Notes |
|----------|---------|-------|
| 57510 | Heater type | 0=Smart, 1=Heat Pump, 2=Gas |
| 57517 | Heater on/off/auto | 0=off, 2=auto — **confirm which heater (gas or heat pump)** |
| 57566 | Heat pump setpoint | Stored as tenths of °C — **confirm on hardware** |
| 57583 | Heater mode | 0=off, else on |
| 57650 | Filter time 1 | |
| 57670 | Filter time 2 | |

### Solar
| Register | Feature | Notes |
|----------|---------|-------|
| 57585 | Solar enabled | Bit 0 = enabled; other bits used — **mask needed** |

### Device Info
| Register | Feature |
|----------|---------|
| 65488–65495 | Device name (8 ASCII bytes) |

### Status Feedback Registers

After each write command, the controller sends a `messageId="read"` response on a lower-numbered register. These appear to be the "actual state" feedback for each output:

| Output register | Feedback register | Observed |
|-----------------|-------------------|---------|
| 65336 (Sanitiser) | 160 | val=0 after off/auto |
| 65338 (Jet Pump) | 162 | val=0 after off |
| 65339 (Pool Light) | 163 | val=0 off / val=1 on |

## Home Assistant Integration

### Entities

Entities must be **auto-discovered** from the socket config registers on connect. The static pump/light map in the original design is wrong — socket assignments vary per device.

**Planned auto-discovered entities:**

| Platform | Entity | Source |
|----------|--------|--------|
| `switch` | One per configured socket | Socket type → appliance name; register = 65334+n |
| `number` | Filter pump speed | VF reg 65485 (0/257/513/769/1025/65535) |
| `climate` | Heater | 57517 (mode), 57566 (setpoint) |
| `sensor` | Connection Status | — |
| `sensor` | Device Name | 65488–65495 |

### Config Flow

User enters the device identifier from the sticker. Accepted formats:
- MAC with colons/dashes — `AA:BB:CC:DD:EE:FF` or `AA-BB-CC-DD-EE-FF`
- MAC without separators — `aabbccddeeff`
- Numeric QR code ID — e.g. `62678480408215041` (decoded to MAC automatically)

The flow:
1. Parses and normalises input to a lowercase no-colon MAC (`CONF_MAC`)
2. Provisions an AWS IoT certificate (Cognito → IoT → attach policy)
3. Creates the config entry

### Python Dependencies

- `awsiotsdk>=1.21.0` — MQTT with X.509 auth
- `boto3>=1.34.0` — Cognito + IoT provisioning

## Key Files

| File | Purpose |
|------|---------|
| `const.py` | All constants and register map |
| `auth.py` | AWS certificate provisioning and HA storage |
| `mqtt_client.py` | MQTT connection, reconnect, watchdog |
| `coordinator.py` | Push-based DataUpdateCoordinator |
| `config_flow.py` | HA config flow UI |
| `entity_base.py` | Shared base class |
| `switch.py` | Binary on/off entities |
| `number.py` | Pump speed controls |
| `climate.py` | Heater setpoint + mode |
| `sensor.py` | Connection status + device name |

## Development

### Requirements

Python **3.12** is required. Python 3.13 fails to install `pytest-homeassistant-custom-component` because `homeassistant` pins `lru-dict==1.3.0` which has no pre-built 3.13 wheel and requires MSVC to compile.

### Setup

```bash
python3.12 -m venv .venv
.venv/Scripts/activate      # Windows
pip install -r requirements_test.txt
```

### Running Tests

```bash
pytest                      # unit tests (all mocked, no AWS)
python scripts/smoke_aws.py # live AWS smoke test — provisions a real cert each run, use sparingly
python scripts/smoke_device.py <mac_or_qr_id> --listen 30  # connect to real device and print live messages
```

`smoke_device.py` caches the provisioned cert in `local/smoke_cert.json` so repeated runs reuse it. Use `--fresh-cert` to force a new one.

### Windows Note

`pytest-homeassistant-custom-component` calls `disable_socket(allow_unix_socket=True)` before each test. On Linux/Mac, asyncio uses AF\_UNIX internally so this is fine. On Windows, `ProactorEventLoop` falls back to TCP `socketpair()` (AF\_INET) which gets blocked. The `pytest_fixture_setup` hook in `tests/conftest.py` re-enables sockets immediately before the `event_loop` fixture is created to work around this.

## Known Unknowns (Needs Hardware Validation)

- Temperature register scaling (`_TEMP_SCALE = 10.0` in `climate.py`) — may be whole degrees
- Solar register bit mask — bit 0 assumed; other bits interact
- Register 57517 — confirmed values 0 and 2 observed when toggling a heater; need to confirm whether this is Gas Heater, Heat Pump Heater, or shared
- Gas Heater and Heat Pump Heater registers — not yet button-tested (57510 may just be type config, actual on/off may be 57517 or another register)
- Socket config encoding — hi byte confirmed as type index for most sockets, but socket 4 decoded as type=1 (sanitiser) while hardware confirms it's Jet Pump; lo byte meaning unclear
- Status feedback registers 160, 162, 163 — purpose confirmed (actual state echo), mapping to outputs partially confirmed

## Confirmed via Live Hardware (2026-03-30)

- Unauthenticated Cognito Identity Pool access still works
- MQTT topic prefix is `dontek{mac}` — without this prefix the broker closes the connection
- QR code numeric ID = MAC address encoded as big-endian integer (upper 6 bytes = MAC, lower byte unknown)
- `pswpolicy` restricts subscribe/publish to `dontek{mac}/` prefix only
- **65336 = Sanitiser socket output** — 0=off, 2=auto
- **65338 = Jet Pump socket output** — 0=off, 2=auto
- **65339 = Pool Light socket output** — 0=off, 1=on, 2=auto
- **65485 = Filter Pump VF output** — 0=off, 65535=auto (257/513/769/1025 = speed 1–4)
- Socket outputs follow 0=off, 1=on(manual), 2=auto pattern (not boolean)
- Controller sends a `messageId="read"` echo on a lower register after each write (status feedback)
