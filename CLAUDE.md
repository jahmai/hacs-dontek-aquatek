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
| Subscribe | `dontek{mac}/status/psw` | Device pushes state updates and OTA progress |
| Publish | `dontek{mac}/cmd/psw` | Send commands to device (Modbus writes **and** OTA trigger) |
| Device → broker | `dontek/logging/+` | Device telemetry/logs; subscribed to in local broker mode only. Suffix observed as `THERALINK`. Message format: `{"recordType":"faults","recordID":"UID_...","version":"1.16B2","ioVersion":"1.00B5",...}` — not Modbus format, logged at debug level only |
| Subscribe | `$aws/things/{MAC_UPPER}_VERSION/shadow/get/+` | Firmware version shadow (uppercased MAC) |

`{mac}` is lowercase no-colon hex (e.g. `deadbeefcafe`).

OTA is triggered via `dontek{mac}/cmd/psw` using the standard message format with reg `65280`, val `[6880]`, and an extra `valueString` field containing the firmware URL. There is no separate OTA topic.

The `pswpolicy` IoT policy grants `iot:Connect`, `iot:Subscribe`, and `iot:Publish` scoped to the `dontek{mac}/` prefix. Subscribing to any topic outside this prefix is denied — the broker drops the connection immediately after the SUBSCRIBE packet. The `dontek/logging/+` topic uses a different prefix and is therefore not accessible via AWS with a provisioned cert; it is only subscribable via a local broker.

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

**Jet Pump (type 12) — dedicated registers** (confirmed 2026-04-04):

Schedule and run-once registers are **type-based, not position-based**. Any socket configured as Jet Pump uses the same fixed registers regardless of which socket number it occupies.

| Register | Feature | Values |
|----------|---------|--------|
| 65517 | Jet Pump schedule 1 enable | 0=Off, 1=Gas Heater (VF1), 257=Heat Pump (VF2) |
| 65518 | Jet Pump schedule 1 start | (hh<<8)\|mm |
| 65519 | Jet Pump schedule 1 end | (hh<<8)\|mm |
| 57606 | Jet Pump schedule 2 enable | same values as 65517 |
| 57607 | Jet Pump schedule 2 start | (hh<<8)\|mm |
| 57608 | Jet Pump schedule 2 end | (hh<<8)\|mm |
| 57632 | Jet Pump run-once enable | 0=off, 1=on |
| 57652 | Jet Pump run-once start | (hh<<8)\|mm |
| 57672 | Jet Pump run-once end | (hh<<8)\|mm |

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

**Heater 1 (VF1)** — Gas Heater on tested device (app label "Heater 1" = VF1 type):

| Register | Feature | Notes |
|----------|---------|-------|
| 81 | Heater 1 status | see heater status code table below ✓ |
| 65348 | Heater 1 on/off/auto | 0=off, 1=on, 2=auto ✓ — socket-output (65336+12) |
| 65441 | Heater 1 setpoint | value = °C × 2 (e.g. 38°C = 76) ✓ |
| 65450 | Heater 1 heating mode | 0=Off, 2=Pool & Spa, 3=Pool, 4=Spa ✓ |
| 65499 | Heater 1 pump type + sensor location | 0=Filter, 1=Indep/FilterSensor, 2=Indep/HeaterLine ✓ |
| 65462 | Heater 1 pump speed | 0=Speed1, 1=Speed2, 2=Speed3, 3=Speed4 ✓ (only when pump type=Independent) |
| 65451 | Heater 1 cool-down time | minutes |
| 65501 | Heater 1 sanitiser | bool |
| 65523 | Heater 1 chilling | bool |
| 57586 | Heater 1 hydrotherapy | bool |
| 65500 | Run Till Heated | bool (shared / Heater 1 context) |
| 65374 | Heater 1 schedule enable | bit field: bit 0=slot 1, bit 1=slot 2 ✓ confirmed 2026-04-03 |
| 65466 | Heater 1 schedule 1 start | (hh<<8)\|mm ✓ confirmed 2026-04-03 |
| 65467 | Heater 1 schedule 1 end | (hh<<8)\|mm ✓ confirmed 2026-04-03 |
| 65413 | Heater 1 schedule 2 start | (hh<<8)\|mm ✓ confirmed 2026-04-03 |
| 65426 | Heater 1 schedule 2 end | (hh<<8)\|mm ✓ confirmed 2026-04-03 |

**Heater 2 (VF2)** — Heat Pump on tested device (app label "Heater 2" = VF2 type):

| Register | Feature | Notes |
|----------|---------|-------|
| 184 | Heater 2 status | see heater status code table below ✓ |
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
| 57531 | Heater 2 schedule enable | bit field: bit 0=slot 1, bit 1=slot 2 ✓ confirmed 2026-04-03 |
| 57538 | Heater 2 schedule 1 start | (hh<<8)\|mm ✓ confirmed 2026-04-03 |
| 57545 | Heater 2 schedule 1 end | (hh<<8)\|mm ✓ confirmed 2026-04-03 |
| 57552 | Heater 2 schedule 2 start | (hh<<8)\|mm ✓ confirmed 2026-04-03 |
| 57559 | Heater 2 schedule 2 end | (hh<<8)\|mm ✓ confirmed 2026-04-03 |
| 57650 | Filter time 1 | |
| 57670 | Filter time 2 | |

> **VF2 pump type / sensor location register (57574):** Two separate logical settings share one register. Use read-modify-write to change either field without stomping the other. Pump type occupies the lower value bits (0=Filter, 1=Independent); sensor location values are 1=Filter, 2=Heater Line (only appears in app when pump type=Independent).

**Heater status code table** (APK `e3/f.java`, applies to both heaters):

| Code | Label | Notes |
|------|-------|-------|
| 0 | Off / Waiting | "Off" when ctrl=0; treat as code 1 (Waiting) when ctrl≠0 |
| 1 | Waiting | Transient armed-but-idle state |
| 2 | Sampling | |
| 3 | Checking | |
| 4 | Heating | |
| 5 | Run On | Cool-down after heating |
| 6 | Limit | |
| 7 | Stopping | |
| 8 | Fault | |
| 9 | Waiting (Solar Priority) | |
| 10 | Chilling | |
| 11 | Off in Pool | Device sends when ctrl=0 and in Pool mode; display as "Off". When ctrl≠0 treat as mode-blocked Waiting. |
| 12 | Off in Spa | Same as 11 but for Spa mode |

Waiting mode context labels: if the heater is Waiting (codes 0/1/11/12 with ctrl≠0) and its configured heating mode conflicts with the active Pool/Spa mode, append the blocking mode — e.g. "Waiting (Pool Mode)" when heat_mode=4 (Spa-only) but controller is in Pool mode.

**Filter pump status code table** (APK `e3/h.java`, register 92 high byte):

| Code(s) | Label |
|---------|-------|
| 0, 1 | Off |
| 2, 3, 4 | Power Up |
| 5 | Priming |
| 6, 7, 8 | Set Speed |
| 9, 10, 11 | On |
| 12 | Running |
| 13, 19 | Run On |
| 14, 15, 16 | Power Down |
| 17 | Fault |
| 18 | Prime Off |

Register 92 format: `(state_byte << 8) | speed_byte`. Speed byte is 0-indexed (0=Speed 1). Speed is only meaningful when state is in the running set {5, 6, 7, 8, 9, 10, 11, 12, 13} — stale in Off/Fault states.

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
| 65296 | Current year (e.g. 2026) |
| 65297 | Current month (1–12) |
| 65298 | Current day (1–31) |
| 65299 | Current hour (0–23) |
| 65300 | Current minute (0–59) |

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
| `select` | Socket 1–5 output (auto-discovered) | 65336+(n-1) |
| `select` | Socket 1–5 Appliance | 65323+(n-1) (0–14, see socket type table) |
| `select` | Jet Pump Schedule 1/2 Enable | 65517 / 57606 (0=Off, 1=Gas Heater, 257=Heat Pump) — Jet Pump sockets only |
| `select` | Valve 1–4 Appliance | 65331+(n-1) (0–7, see valve type table) |
| `select` | VF 1 Appliance | 65335 (0=None, 1=Gas Heater, 2=Heat Pump) |
| `select` | VF 2 Appliance | 57510 (same values) |
| `select` | Filter Pump | 65485 (0/257/513/769/1025/65535) |
| `select` | Filter Run Once Speed | 57630 bits 8-15 (0–3 = Speed 1–4) |
| `select` | Filter Schedule 1–4 Speed | 65473+(n-1) (0–3 = Speed 1–4) |
| `select` | Pool/Spa Mode | 65313 (0=Pool, 1=Spa) |
| `select` | Pool Light Type | 65352 upper byte |
| `select` | Pool Light Colour | 65352 lower byte (options vary per brand) |
| `select` | Heater 1 Heating Mode | 65450 (0=Off, 2=Pool & Spa, 3=Pool, 4=Spa) |
| `select` | Heater 1 Pump Type | 65499 (0=Filter, non-zero=Independent) |
| `select` | Heater 1 Sensor Location | 65499 (1=Filter, 2=Heater Line) |
| `select` | Heater 1 Pump Speed | 65462 (0–3 = Speed 1–4) |
| `select` | Heater 1 Smart Heater Type | 57582 (0=Auto, 1=None, 2=Theralux, 3=Aquark, 4=Oasis) |
| `select` | Heater 2 Heating Mode | 57566 (same values) |
| `select` | Heater 2 Pump Type | 57574 (0=Filter, non-zero=Independent) |
| `select` | Heater 2 Sensor Location | 57574 (1=Filter, 2=Heater Line) |
| `select` | Heater 2 Smart Heater Type | 57583 (same values) |
| `climate` | Heater 1 | ctrl=65348, setpoint=65441 |
| `climate` | Heater 2 | ctrl=57517, setpoint=57575 |
| `switch` | Run Till Heated | 65500 |
| `switch` | Boost (Party Mode) | 57577 |
| `switch` | Heater 1 Run Once | 57625 (0=off, 1=on) |
| `switch` | Heater 2 Run Once | 57626 (0=off, 1=on) |
| `number` | Heater 1 Run Once Duration | 57645 / 57665 (start=now, end=now+N; duration = end−start, exclusive) |
| `number` | Heater 2 Run Once Duration | 57646 / 57666 (same encoding) |
| `switch` | Heater 1 Schedule 1/2 Enable | 65374 (bit 0=slot 1, bit 1=slot 2) |
| `switch` | Heater 2 Schedule 1/2 Enable | 57531 (bit 0=slot 1, bit 1=slot 2) |
| `switch` | Heater 1 Sanitiser | 65501 |
| `switch` | Heater 1 Chilling | 65523 |
| `switch` | Heater 1 Hydrotherapy | 57586 |
| `switch` | Heater 2 Sanitiser | 57570 |
| `switch` | Heater 2 Chilling | 57569 |
| `switch` | Heater 2 Hydrotherapy | 57587 |
| `switch` | Heater 2 Track / Setback | 57578 |
| `switch` | Socket 1–5 Schedule 1/2 Enable | 65362+(n-1) bit-field (bit 0=sched1, bit 1=sched2) — non-Jet-Pump sockets only |
| `switch` | Socket 1–5 Run Once | 57613+(n-1) — non-Jet-Pump; Jet Pump uses 57632 |
| `time` | Heater 1 Schedule 1 Start/End | 65466 / 65467 |
| `time` | Heater 1 Schedule 2 Start/End | 65413 / 65426 |
| `time` | Heater 2 Schedule 1 Start/End | 57538 / 57545 |
| `time` | Heater 2 Schedule 2 Start/End | 57552 / 57559 |
| `time` | Socket 1–5 Schedule 1/2 Start/End | see const.py; Jet Pump uses 65518/65519 (sched1), 57607/57608 (sched2) |
| `time` | Filter Schedule 1–4 Start/End | see const.py |
| `number` | Socket 1–5 Run Once Duration | non-Jet-Pump: start=57633+(n-1)/end=57653+(n-1); Jet Pump: 57652/57672; duration = end−start |
| `number` | Filter Run Once Duration | 57650 / 57670 |
| `number` | Heater 1 Cool-Down Time | 65451 (minutes, 0–60) |
| `number` | Heater 2 Cool-Down Time | 57568 (minutes, 0–60) |
| `number` | Heater 2 Setback Temperature | 57579 (0 to −15°C, 0.5°C steps) |
| `number` | Filter Duty Cycle | 57681 (0–100%, 5% steps) |
| `sensor` | Heater 1 Status | 81 |
| `sensor` | Heater 2 Status | 184 |
| `sensor` | Filter Pump Status | 92 (state in high byte, speed in low byte) |
| `sensor` | Temperature Sensor 1/2/3 | 55+(n-1); type from 65314+(n-1) |
| `sensor` | Connection Status | — |
| `sensor` | Last Message | Timestamp of last MQTT message received |
| `sensor` | Device Name | 65488–65495 |
| `button` | Refresh | Sends full state dump request |

### Config Flow

User enters the device identifier from the sticker. Accepted formats:
- MAC with colons/dashes — `AA:BB:CC:DD:EE:FF` or `AA-BB-CC-DD-EE-FF`
- MAC without separators — `aabbccddeeff`
- Numeric QR code ID — e.g. `62678480408215041` (decoded to MAC automatically)

The flow:
1. Parses and normalises input to a lowercase no-colon MAC (`CONF_MAC`)
2. User selects connection mode (AWS Cloud or Local Broker toggle)
3. **AWS Cloud:** provisions an AWS IoT certificate (Cognito → IoT → attach policy) → creates config entry
4. **Local Broker:** prompts for host + port (default `localhost:883`) → creates config entry (no cert provisioning)

### Reconfigure Flow

Accessible via **Settings → Devices & Services → Dontek Aquatek → ⋮ → Reconfigure**. Allows switching connection mode without deleting and re-adding the integration:
- **AWS → Local:** shows host/port form (pre-populated with current values) → updates entry + reloads
- **Local → AWS:** runs certificate provisioning → updates entry + reloads
- **No change:** reloads immediately

### Connection Modes

**AWS Cloud** (default) — `CONF_USE_LOCAL_BROKER = False`
- Connects to `a219g53ny7vwvd-ats.iot.ap-southeast-2.amazonaws.com` via `awsiotsdk` mutual TLS
- Requires unauthenticated Cognito provisioning on first setup

**Local Broker** — `CONF_USE_LOCAL_BROKER = True`
- Connects to a plain-TCP MQTT broker (e.g. the `hacs-dontek-aquatek-mqtt-server` project)
- TLS enabled but server certificate validation disabled (`ssl.CERT_NONE` + `tls_insecure_set(True)`) — firmware requires TLS but cannot validate a self-signed broker cert
- Requires firmware patched to point at the local broker
- Config entry also stores `CONF_LOCAL_BROKER_HOST` and `CONF_LOCAL_BROKER_PORT`
- Default port `883` (capped at 2047)
- **Periodic state refresh**: polls the device every 5 seconds (safe for local connections; not done in AWS mode to avoid unnecessary cloud traffic)
- **Post-command poll**: after each successful write command, requests a full state dump after a 1-second delay to capture any reactive register changes
- Subscribes to `dontek/logging/+` in addition to the status topic

### Python Dependencies

- `awsiotsdk>=1.21.0` — MQTT with X.509 auth (AWS Cloud mode)
- `boto3>=1.34.0` — Cognito + IoT provisioning (AWS Cloud mode)
- `paho-mqtt` — plain-TCP MQTT client (Local Broker mode); ships with HA, not listed in manifest

## Key Files

| File | Purpose |
|------|---------|
| `const.py` | All constants and register map |
| `auth.py` | AWS certificate provisioning and HA storage |
| `mqtt_client.py` | `AquatekMQTTClient` (AWS/mutual TLS) and `AquatekLocalMQTTClient` (TLS, no cert validation) |
| `coordinator.py` | Push-based DataUpdateCoordinator |
| `config_flow.py` | HA config flow UI — AWS Cloud or Local Broker selection |
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
- **VF1 sensor location** — confirmed identical packing to VF2: reg 65499, 0=Filter, 1=Indep/FilterSensor, 2=Indep/HeaterLineSensor ✓
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
- **65499 = Heater 1 pump type + sensor location** — identical packing to VF2/57574: 0=Filter, 1=Indep/FilterSensor, 2=Indep/HeaterLineSensor ✓
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

### 2026-04-01 (continued)
- **65499 = Heater 1 pump type + sensor location** — identical packing to VF2 (57574): 0=Filter, 1=Indep/FilterSensor, 2=Indep/HeaterLineSensor ✓
- VF1 and VF2 use the exact same packed register encoding for pump type and sensor location

### 2026-04-07
- **65296–65300 = device RTC** — confirmed via live dump matching wall-clock time: 65296=year, 65297=month, 65298=day, 65299=hour, 65300=minute. Values updated correctly between repeated dumps (minute incremented).
- **No uptime register found** — reg 321 was a candidate but values decreased across dumps; likely a countdown timer for an unidentified feature, not uptime.

### 2026-04-04
- **Run-once duration encoding**: `duration = end_reg − start_reg` (exclusive range, not inclusive). Write `end = now + N` for N minutes. Read `delta = (end_mins − start_mins) % 1440`. Applies to all run-once timers (sockets, filter, heater 1, heater 2).
- **57625 = Heater 1 Run Once enable**, **57645 / 57665 = Heater 1 Run Once start / end** ✓ confirmed via toggle test
- **57626 = Heater 2 Run Once enable**, **57646 / 57666 = Heater 2 Run Once start / end** ✓ confirmed via toggle test
- **Jet Pump (type 12) uses dedicated registers**, not the sequential `base + (n-1)` pattern — confirmed by assigning the same socket to Pool Light (which uses sequential registers) vs Jet Pump (which does not):
  - **65517 = Jet Pump schedule 1 enable** — 0=Off, 1=Gas Heater (VF1), 257=Heat Pump (VF2) ✓ (tri-state, not a bit-field)
  - **65518 / 65519 = Jet Pump schedule 1 start / end** — (hh<<8)|mm ✓
  - **57606 = Jet Pump schedule 2 enable** — same values as 65517 ✓
  - **57607 / 57608 = Jet Pump schedule 2 start / end** — (hh<<8)|mm ✓
  - **57632 = Jet Pump run-once enable** — 0=off, 1=on ✓ (offset +2 from filter run-once at 57630)
  - **57652 / 57672 = Jet Pump run-once start / end** ✓ (offset +2 from filter 57650/57670)
- Schedule enable for Jet Pump is a **tri-state heater selector**, not a boolean: 0=Off (not scheduled), 1=runs with Gas Heater (VF1), 257=runs with Heat Pump (VF2). Implemented as `select` entity, not `switch`.

### 2026-04-03
- **65374 = Heater 1 schedule enable** — bit field: bit 0=slot 1, bit 1=slot 2 ✓ confirmed via toggle test
- **57531 = Heater 2 schedule enable** — bit field: bit 0=slot 1, bit 1=slot 2 ✓ confirmed via toggle test (was previously and incorrectly assigned to H1)
- **65466 = Heater 1 schedule 1 start**, **65467 = Heater 1 schedule 1 end** — (hh<<8)|mm ✓ (H1 schedule consistently in 65xxx)
- **65413 = Heater 1 schedule 2 start**, **65426 = Heater 1 schedule 2 end** — (hh<<8)|mm ✓ confirmed via live register change
- **57538 = Heater 2 schedule 1 start**, **57545 = Heater 2 schedule 1 end** — (hh<<8)|mm ✓ (H2 schedule consistently in 57xxx)
- **57552 = Heater 2 schedule 2 start**, **57559 = Heater 2 schedule 2 end** — (hh<<8)|mm ✓ confirmed via live register change
- H1 schedule registers are entirely in 65xxx range; H2 schedule registers are entirely in 57xxx range

### 2026-04-02
- **81 = Heater 1 (Gas Heater / VF1) status** ✓ — confirmed via live dump with heater in "Run On" (code 5); reg 81=5 matched exactly. Prior assumption of reg 185 was wrong.
- **184 = Heater 2 (Heat Pump / VF2) status** ✓ — previously confirmed in Pool mode, re-confirmed in Spa mode (reg 184=4 = Heating)
- **reg 185 is NOT a heater status register** — was assigned by adjacency to 184; discard that assumption
- **App label mapping confirmed**: "Heater 1" in app = VF1 (Gas Heater); "Heater 2" in app = VF2 (Heat Pump)
- **Heater status code table confirmed** (APK `e3/f.java`): 0=Off/Waiting, 1=Waiting, 2=Sampling, 3=Checking, 4=Heating, 5=Run On, 6=Limit, 7=Stopping, 8=Fault, 9=Waiting(Solar), 10=Chilling, 11=Off in Pool, 12=Off in Spa
- **Codes 11/12 behaviour**: device sends code 11 ("Off in Pool") even when ctrl=0 (heater explicitly off). When ctrl=0, display as "Off". When ctrl≠0, treat same as code 1 (Waiting) and apply mode-conflict labelling.
- **Filter pump full state table confirmed** (APK `e3/h.java`): 0-1=Off, 2-4=Power Up, 5=Priming, 6-8=Set Speed, 9-11=On, 12=Running, 13/19=Run On, 14-16=Power Down, 17=Fault, 18=Prime Off. States 6-8 (Set Speed) include active speed byte.
