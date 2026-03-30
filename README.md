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
| Switch | Pump 1–12 |
| Switch | Spa |
| Switch | Filter Pump |
| Switch | Sanitizer |
| Switch | Solar |
| Switch | Light 1 / Light 2 |
| Number | Pump 1–12 Speed (0–3) |
| Climate | Heater (setpoint + on/off) |
| Sensor | Connection Status |
| Sensor | Device Name |

## Known Limitations

The following have not yet been validated against hardware and may need adjustment:

- Heater temperature register scaling (may be whole degrees rather than tenths)
- Pump speed range (assumes 0–3 levels)
- Solar register bit mask

## License

MIT
