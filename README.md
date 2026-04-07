# Dontek Aquatek — Home Assistant Integration

> **Note:** This repository was 100% authored by [Claude](https://claude.ai) (Anthropic AI). The human owner provided hardware access, register discovery sessions, and direction — all code and documentation was written by Claude.

HACS custom integration for the **Dontek Aquatek / Theralux Pool+ Manager** pool controller.

Communicates via AWS IoT MQTT (cloud) by default. An optional local broker mode is available for use with patched firmware and a local MQTT server.

## Requirements

- Home Assistant 2024.1 or later
- [HACS](https://hacs.xyz) installed
- The MAC address or numeric QR code ID from the sticker on your controller

## Installation

1. In HACS, click **⋮ → Custom repositories** and add `https://github.com/jahmai/hacs-dontek-aquatek` with category **Integration**
2. Click **Download** on the Dontek Aquatek card
3. Restart Home Assistant
4. Go to **Settings → Devices & Services → Add Integration** and search for *Aquatek*

## Configuration

When prompted, enter the identifier from the sticker on your controller:

```
POOL+ MANAGER
4.10.2024
MAC SN:XXXXX          ← MAC address (use this, or...)
XXXXXXXXXXXXXXXXX     ← ...the numeric QR code ID (either works)
```

Accepted formats:
- MAC with colons — `AA:BB:CC:DD:EE:FF`
- MAC without separators — `aabbccddeeff`
- Numeric QR code ID — the long number printed below the QR code

### AWS Cloud (default)

Leave the **Use local MQTT broker** toggle off. The integration will automatically provision an AWS IoT certificate and connect to your controller via the cloud.

To switch connection mode later, use **Settings → Devices & Services → Dontek Aquatek → ⋮ → Reconfigure**.

### Local Broker (advanced)

Enable the **Use local MQTT broker** toggle if you are running a local MQTT broker (e.g. [hacs-dontek-aquatek-mqtt-server](https://github.com/jahmai/hacs-dontek-aquatek-mqtt-server)) and have patched your controller firmware to point at it. You will be prompted for the broker host and port (default `localhost:11883`). No AWS account or certificate provisioning is required in this mode.

## Entities

| Platform | Entity |
|----------|--------|
| Select | Socket 1–5 outputs (auto-discovered, Off/On/Auto) |
| Select | Socket 1–5 Appliance assignment |
| Select | Valve 1–4 Appliance assignment |
| Select | VF 1 & 2 Appliance assignment (None / Gas Heater / Heat Pump) |
| Select | Filter Pump (Off / Speed 1–4 / Auto) |
| Select | Filter Run Once Speed |
| Select | Filter Schedule 1–4 Speed |
| Select | Pool/Spa Mode |
| Select | Pool Light Type / Colour |
| Select | Heater 1 & 2 Heating Mode, Pump Type, Sensor Location, Pump Speed |
| Select | Heater 1 & 2 Smart Heater Type |
| Climate | Heater 1 (Gas Heater) — setpoint + Off/On/Auto |
| Climate | Heater 2 (Heat Pump) — setpoint + Off/Auto |
| Switch | Run Till Heated, Boost (Party Mode) |
| Switch | Heater 1 & 2 Run Once |
| Switch | Heater 1 & 2 Schedule 1/2 Enable |
| Switch | Socket 1–5 Schedule 1/2 Enable, Run Once |
| Switch | Filter Schedule 1–4 Enable, Run Once |
| Switch | Heater 1 & 2 Sanitiser, Chilling, Hydrotherapy |
| Switch | Heater 2 Track/Setback |
| Time | Heater 1 & 2 Schedule 1/2 Start/End |
| Time | Socket 1–5 Schedule 1/2 Start/End |
| Time | Filter Schedule 1–4 Start/End |
| Number | Heater 1 & 2 Cool-Down Time |
| Number | Heater 1 & 2 Run Once Duration |
| Number | Socket 1–5 Run Once Duration |
| Number | Filter Run Once Duration |
| Number | Heater 2 Setback Temperature |
| Number | Filter Duty Cycle (0–100%) |
| Sensor | Heater 1 Status, Heater 2 Status, Filter Pump Status |
| Sensor | Temperature Sensor 1 / 2 / 3 |
| Sensor | Connection Status, Last Message (timestamp), Device Name |
| Button | Refresh (request immediate state update) |

Socket output entities are auto-discovered at startup from the device's socket configuration registers — the set of entities will match however your controller is configured in the app.

## License

MIT
