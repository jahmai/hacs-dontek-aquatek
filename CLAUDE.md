# Dontek Aquatek — HACS Integration

Home Assistant custom integration for the Dontek Aquatek / Theralux Pool+ Manager pool controller.

## Project Structure

```
custom_components/dontek_aquatek/   — the HACS integration
hacs.json                           — HACS metadata
local/                              — gitignored local dev files
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
| `65336 + (n-1)` (n = 1–5) | Socket n output (0=off, 1=on, 2=auto) |
| `65323 + (n-1)` (n = 1–5) | Socket n type config — direct integer index (confirmed) |

**Socket type indices** (from APK `arrays.xml` `socket_type_options`, complete list confirmed):

| Index | Appliance |
|-------|-----------|
| 0 | None |
| 1 | Sanitiser |
| 2 | Filter Pump |
| 3 | Cleaning Pump |
| 4 | Blower |
| 5 | Pool Light |
| 6 | Spa Light |
| 7 | Garden Light |
| 8 | Water Feature |
| 9 | Solar |
| 10 | Other |
| 11 | Always On |
| 12 | Jet Pump |
| 13 | Heating Pump (Ind.) |
| 14 | UV Sanitiser |

**Confirmed socket assignments** on tested device:
- Socket 1 → reg 65336 → Sanitiser (type 1) ✓
- Socket 2 → reg 65337 → Heating Pump Ind. (type 13) ✓
- Socket 3 → reg 65338 → Jet Pump (type 12) ✓
- Socket 4 → reg 65339 → Pool Light (type 5) ✓
- Socket 5 → reg 65340 → None (type 0) ✓

### VF Connectors

Two VF ports exist but they are **heater type config only** — they determine which heater is assigned to each VF port, not speed. The filter pump has its own separate serial connection.

| Register | Feature | Values |
|----------|---------|--------|
| 65335 | VF1 type config | 0=None, 1=Gas Heater, 2=Heat Pump (confirmed) |
| 57510 | VF2 type config | 0=None, 1=Gas Heater, 2=Heat Pump (confirmed) |
| 65485 | Filter pump (serial) | 0=off, 257=spd1, 513=spd2, 769=spd3, 1025=spd4, 65535=auto (confirmed) |

### Temperature Sensors

Three physical temperature sensors. Each has a type config register and a reading register.

| Register | Feature | Values |
|----------|---------|--------|
| `65314 + (n-1)` (n = 1–3) | Sensor n type | 0=None, 1=Pool, 2=Roof, 15=Water |
| `55 + (n-1)` (n = 1–3) | Sensor n reading | value = °C × 2 |

`current_temperature` for heater climate entities is dynamically found by locating the sensor with type=Pool (1).

### Pool Light

The pool light output socket (type 5) has additional config for light brand and colour, packed into a single register:

| Register | Feature | Notes |
|----------|---------|-------|
| 65352 | Light type + colour | `(type_index << 8) \| colour_index` — packed |

Light type 0 = None. All brands and colour lists are in `LIGHT_COLOURS` in `const.py`.

### Heating

**Architecture:** Heater 1 = VF1 port (65xxx registers), Heater 2 = VF2 port (57xxx registers). Each heater has a **fixed setpoint register independent of Pool/Spa mode** — the setpoints shown in the app's heater page are per-heater, not per-mode.

**Heater 1 (VF1)** — Gas Heater or Heat Pump connected to the VF1 port:

| Register | Feature | Notes |
|----------|---------|-------|
| 65348 | Heater 1 on/off/auto | 0=off, 1=on, 2=auto ✓ — socket-output (65336+12) |
| 65441 | Heater 1 setpoint | value = °C × 2 (e.g. 38°C = 76) ✓ |
| 65450 | Heater 1 heating mode | 0=Off, 2=Pool & Spa, 3=Pool, 4=Spa ✓ |
| 65499 | Heater 1 pump type | 0=Filter, 1=Independent ✓ |
| 65462 | Heater 1 pump speed | 0=Speed1, 1=Speed2, 2=Speed3, 3=Speed4 ✓ (only when pump type=Independent) |
| 65451 | Heater 1 cool-down time | minutes |
| 65501 | Heater 1 sanitiser | bool |
| 65523 | Heater 1 chilling | bool |
| 57586 | Heater 1 hydrotherapy | bool |
| 65500 | Run Till Heated | bool (shared / Heater 1 context) |

**Heater 2 (VF2)** — Heat Pump connected to the VF2 port via serial cable:

| Register | Feature | Notes |
|----------|---------|-------|
| 57517 | Heater 2 on/off/auto | 0=off, 2=auto ✓ |
| 57575 | Heater 2 setpoint | value = °C × 2 (e.g. 32°C = 64) ✓ |
| 57566 | Heater 2 heating mode | 0=Off, 2=Pool & Spa, 3=Pool, 4=Spa ✓ |
| 57574 | Heater 2 pump type + sensor loc | packed: low byte = pump type (0=Filter, 1=Indep); high byte = sensor location (1=Filter, 2=Heater Line) |
| 57568 | Heater 2 cool-down time | minutes |
| 57570 | Heater 2 sanitiser | bool |
| 57569 | Heater 2 chilling | bool |
| 57587 | Heater 2 hydrotherapy | bool |
| 57578 | Heater 2 Track / Setback | bool — enables tracking Heater 1 setpoint with an offset |
| 57579 | Heater 2 setback temperature | stored as positive integer, 0.5°C steps; read: `-(val × 0.5)` °C; range 0 to −15°C |
| 57577 | Boost (Party Mode) | bool |
| 57583 | Heater mode | value=0 observed; purpose unconfirmed |
| 57650 | Filter time 1 | |
| 57670 | Filter time 2 | |

> **VF2 pump type / sensor location register (57574):** Two separate logical settings share one register. Use read-modify-write to change either field without stomping the other. Pump type occupies the lower value bits (0=Filter, 1=Independent); sensor location values are 1=Filter, 2=Heater Line (only appears in app when pump type=Independent).

### Pool / Spa Mode

| Register | Feature | Values |
|----------|---------|--------|
| 65313 | Pool/Spa mode | 0=Pool, 1=Spa (confirmed) |

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

**Current entities:**

| Platform | Entity | Register(s) |
|----------|--------|-------------|
| `select` | One per configured socket (auto-discovered) | 65336+(n-1); type from 65323+(n-1) |
| `select` | Filter Pump | 65485 (0/257/513/769/1025/65535) |
| `select` | Pool/Spa Mode | 65313 (0=Pool, 1=Spa) |
| `select` | Light Type | 65352 upper byte |
| `select` | Light Colour | 65352 lower byte (options vary per brand) |
| `select` | Heater 1 Heating Mode | 65450 (0=Off, 2=Pool & Spa, 3=Pool, 4=Spa) |
| `select` | Heater 1 Pump Type | 65499 (0=Filter, 1=Independent) |
| `select` | Heater 1 Pump Speed | 65462 (0–3 = Speed 1–4) |
| `select` | Heater 2 Heating Mode | 57566 (same values) |
| `select` | Heater 2 Pump Type | 57574 low bits |
| `select` | Heater 2 Sensor Location | 57574 high bits (1=Filter, 2=Heater Line) |
| `climate` | Heater 1 | ctrl=65348, setpoint=65441 |
| `climate` | Heater 2 | ctrl=57517, setpoint=57575 |
| `switch` | Run Till Heated | 65500 |
| `switch` | Boost (Party Mode) | 57577 |
| `switch` | Heater 1 Sanitiser | 65501 |
| `switch` | Heater 1 Chilling | 65523 |
| `switch` | Heater 1 Hydrotherapy | 57586 |
| `switch` | Heater 2 Sanitiser | 57570 |
| `switch` | Heater 2 Chilling | 57569 |
| `switch` | Heater 2 Hydrotherapy | 57587 |
| `switch` | Heater 2 Track / Setback | 57578 |
| `number` | Heater 1 Cool-Down Time | 65451 (minutes, 0–60) |
| `number` | Heater 2 Cool-Down Time | 57568 (minutes, 0–60) |
| `number` | Heater 2 Setback Temperature | 57579 (0 to −15°C, 0.5°C steps) |
| `sensor` | Temperature Sensor 1/2/3 | 55+(n-1); type from 65314+(n-1) |
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
| `switch.py` | Bool entities (boost, run-till-heated, sanitiser, chilling, hydro, track/setback) |
| `number.py` | Cool-down time and setback temperature |
| `climate.py` | Heater 1 and Heater 2 climate entities |
| `select.py` | Socket outputs, filter pump, pool/spa mode, light type/colour, VF config |
| `sensor.py` | Temperature sensors, connection status, device name |

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

- Solar register bit mask — `57585=65` (= 0x41, bit 0 set) observed in state dump; bit 0 = solar enabled confirmed, other bits unknown
- `57583` (Heater mode) — value=0 in state dump while HP heater was auto; purpose unclear, may overlap with 57517
- **VF1 sensor location register** — unconfirmed. The "Sensor Location" option only appears in the app when Heater 1 pump type is set to Independent. Needs a dedicated button test on that screen.
- **VF2 pump speed** — unknown if VF2 has a pump speed setting like VF1. Likely only relevant when VF2 pump type=Independent.
- **VF2 pump type / sensor location packing** — the read-modify-write split at reg 57574 is inferred from the app UI; exact bit layout not confirmed from raw register dumps.

## Confirmed via Live Hardware

### 2026-03-30
- Unauthenticated Cognito Identity Pool access still works
- MQTT topic prefix is `dontek{mac}` — without this prefix the broker closes the connection
- QR code numeric ID = MAC address encoded as big-endian integer (upper 6 bytes = MAC, lower byte unknown)
- `pswpolicy` restricts subscribe/publish to `dontek{mac}/` prefix only
- **65336 = Socket 1 (Sanitiser) output** — 0=off, 1=on, 2=auto
- **65337 = Socket 2 (Heating Pump) output** — 0=off, 2=auto
- **65338 = Socket 3 (Jet Pump) output** — 0=off, 2=auto
- **65339 = Socket 4 (Pool Light) output** — 0=off, 1=on, 2=auto
- **REG_SOCKET_OUTPUT_BASE = 65336**, socket n = 65336 + (n-1), 0-indexed
- **REG_SOCKET_TYPE_BASE = 65323**, socket n type = 65323 + (n-1), direct integer index
- **65485 = Filter Pump serial output** — 0=off, 65535=auto (257/513/769/1025 = speed 1–4)
- **65348 = Gas Heater output** — 0=off, 2=auto (socket-output at index 12, i.e. 65336+12)
- **57517 = Heat Pump on/off/auto** — 0=off, 2=auto
- **57575 = Pool setpoint** — value = °C × 2 (32°C=64); previous assumption of ×10 was wrong
- Socket outputs follow 0=off, 1=on(manual), 2=auto pattern (not boolean)
- Controller sends a `messageId="read"` echo on a lower register after each write (status feedback)
- Feedback register = output register − 65176 (consistent across all tested sockets)
- VF ports are heater type config only (not speed control); **65335 = VF1 type**, **57510 = VF2 type** (0=None, 1=Gas Heater, 2=Heat Pump)

### 2026-03-31
- **65313 = Pool/Spa mode** — 0=Pool, 1=Spa (write to switch modes)
- **65441 = Heater 1 setpoint** — value = °C × 2 (38°C=76); this is VF1's fixed setpoint, not a spa-mode-dependent register
- **57575 = Heater 2 setpoint** — value = °C × 2 (32°C=64); this is VF2's fixed setpoint
- Setpoints are per-heater, not per pool/spa mode — earlier assumption was wrong

### 2026-04-01
- **65348 = Heater 1 (VF1) on/off/on** — 0=off, 1=on, 2=auto ✓ (Gas Heater also supports manual On)
- **65450 = Heater 1 heating mode** — 0=Off, 2=Pool & Spa, 3=Pool, 4=Spa ✓ (was wrongly documented as 65449)
- **65499 = Heater 1 pump type** — 0=Filter, 1=Independent ✓ (confirmed via button test)
- **65462 = Heater 1 pump speed** — 0=Speed1, 1=Speed2, 2=Speed3, 3=Speed4 ✓ (was initially misidentified as sensor location)
- **57566 = Heater 2 heating mode** — 0=Off, 2=Pool & Spa, 3=Pool, 4=Spa ✓
- **57577 = Boost (Party Mode)** — bool ✓
- **65500 = Run Till Heated** — bool ✓
- **57578 = Heater 2 Track / Setback** — same register controls both track-heater-1 and setback toggle ✓
- **57579 = Heater 2 setback temperature** — stored as positive integer, 0.5°C steps (val=6 → −3°C) ✓
- **65501 = Heater 1 sanitiser**, **65523 = Heater 1 chilling**, **57586 = Heater 1 hydrotherapy** ✓
- **57570 = Heater 2 sanitiser**, **57569 = Heater 2 chilling**, **57587 = Heater 2 hydrotherapy** ✓
- **Hydrotherapy** option only appears in app after Chilling is enabled
- **Temperature sensors**: 3 physical sensors; type at 65314+(n-1), reading at 55+(n-1), value = °C × 2
- **Pool light control**: reg 65352, packed as `(type_index << 8) | colour_index`
