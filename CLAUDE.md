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

The device is identified by a **numeric ID** encoded in the QR code sticker on the controller. This is printed below the QR code.

Example sticker:
```
POOL+ MANAGER
4.10.2024
MAC SN:XXXXX
XXXXXXXXXXXXXXXXX
```

### MQTT Topics

| Direction | Topic | Purpose |
|-----------|-------|---------|
| Subscribe | `{device_id}/status/psw` | Device pushes state updates |
| Publish | `{device_id}/cmd/psw` | Send commands to device |
| Subscribe | `$aws/things/{DEVICE_ID}_VERSION/shadow/get/+` | Firmware version (uppercased) |

### Message Format

All messages are JSON with a Modbus register structure:

```json
{"messageId": "read", "modbusReg": 123, "modbusVal": [0]}
{"messageId": "write", "modbusReg": 123, "modbusVal": [1]}
```

Multi-value messages set consecutive registers starting at `modbusReg`.

## Modbus Register Map

### Pumps
| Register | Feature |
|----------|---------|
| `0xFF3B + i` (65339+i) | Pump i on/off (i = 0–11) |
| `0xFF48 + i` (65352+i) | Pump i speed level (0–3) |
| 65335 | Spa pump on/off (pump index 12) |

### Filtration & Sanitization
| Register | Feature |
|----------|---------|
| 65430 | Filter pump enabled |
| 65431 | Sanitizer enabled |
| 57650 | Filter time 1 |
| 57670 | Filter time 2 |

### Heating
| Register | Feature | Notes |
|----------|---------|-------|
| 57510 | Heater type | 0=Smart, 1=Heat Pump, 2=Gas |
| 57566 | Heat pump setpoint | Stored as tenths of °C — **confirm on hardware** |
| 57583 | Heater mode | 0=off, else on |

### Solar
| Register | Feature | Notes |
|----------|---------|-------|
| 57585 | Solar enabled | Bit 0 = enabled; other bits used — **mask needed** |

### Lights
| Register | Feature |
|----------|---------|
| 65314 | Light 1 |
| 65315 | Light 2 |

### Device Info
| Register | Feature |
|----------|---------|
| 65488–65495 | Device name (8 ASCII bytes) |

## Home Assistant Integration

### Entities

| Platform | Entity | Register |
|----------|--------|---------|
| `switch` | Pump 1–12 | 65339–65350 |
| `switch` | Spa | 65335 |
| `switch` | Filter Pump | 65430 |
| `switch` | Sanitizer | 65431 |
| `switch` | Solar | 57585 |
| `switch` | Light 1 / Light 2 | 65314, 65315 |
| `number` | Pump 1–12 Speed | 65352–65363 |
| `climate` | Heater | 57566, 57583 |
| `sensor` | Connection Status | — |
| `sensor` | Device Name | 65488–65495 |

### Config Flow

User enters the numeric device ID from the QR code sticker. The flow:
1. Validates the ID (must be numeric)
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
```

### Windows Note

`pytest-homeassistant-custom-component` calls `disable_socket(allow_unix_socket=True)` before each test. On Linux/Mac, asyncio uses AF\_UNIX internally so this is fine. On Windows, `ProactorEventLoop` falls back to TCP `socketpair()` (AF\_INET) which gets blocked. The `pytest_fixture_setup` hook in `tests/conftest.py` re-enables sockets immediately before the `event_loop` fixture is created to work around this.

## Known Unknowns (Needs Hardware Validation)

- Temperature register scaling (`_TEMP_SCALE = 10.0` in `climate.py`) — may be whole degrees
- Pump speed range — currently 0–3 levels; may differ by pump model
- Solar register bit mask — bit 0 assumed; other bits interact
- Whether Cognito Identity Pool still accepts unauthenticated access
