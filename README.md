# Dontek Aquatek — Home Assistant Integration

HACS custom integration for the **Dontek Aquatek / Theralux Pool+ Manager** pool controller.

Communicates via AWS IoT MQTT (cloud). No local API is available.

## Requirements

- Home Assistant 2024.1 or later
- [HACS](https://hacs.xyz) installed
- The MAC address or numeric QR code ID from the sticker on your controller

## Installation

1. In HACS, add this repository as a custom repository (Integration category)
2. Install **Dontek Aquatek**
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

The integration will automatically provision an AWS IoT certificate and connect to your controller.

## Entities

| Platform | Entity |
|----------|--------|
| Select | Socket outputs (auto-discovered: Sanitiser, Jet Pump, Pool Light, etc.) |
| Select | Filter Pump (Off / Speed 1–4 / Auto) |
| Select | Pool/Spa Mode |
| Select | Pool Light Type / Colour |
| Select | Heater 1 & 2 Heating Mode, Pump Type, Sensor Location |
| Select | Heater 1 Pump Speed |
| Climate | Heater 1 (Gas Heater) — setpoint + Off/On/Auto |
| Climate | Heater 2 (Heat Pump) — setpoint + Off/Auto |
| Switch | Run Till Heated, Boost (Party Mode) |
| Switch | Heater 1 & 2 Sanitiser, Chilling, Hydrotherapy |
| Switch | Heater 2 Track/Setback |
| Number | Heater 1 & 2 Cool-Down Time |
| Number | Heater 2 Setback Temperature |
| Sensor | Heater 1 Status, Heater 2 Status |
| Sensor | Temperature Sensor 1 / 2 / 3 |
| Sensor | Connection Status, Device Name |

Socket output entities are auto-discovered at startup from the device's socket configuration registers — the set of entities will match however your controller is configured in the app.

## License

MIT
