"""Constants for the Dontek Aquatek integration."""

DOMAIN = "aquatek"

# AWS / IoT
COGNITO_POOL_ID = "ap-southeast-2:c45f75ed-a7e5-4a4f-b27a-ac3941f6d9bf"
AWS_REGION = "ap-southeast-2"
IOT_ENDPOINT = "a219g53ny7vwvd-ats.iot.ap-southeast-2.amazonaws.com"
IOT_POLICY_NAME = "pswpolicy"

# MQTT topic templates — mac is lowercase no-colon hex (e.g. "aabbccddeeff")
# The broker requires the "dontek" prefix on all device topics.
TOPIC_STATUS = "dontek{mac}/status/psw"
TOPIC_CMD = "dontek{mac}/cmd/psw"
TOPIC_SHADOW = "$aws/things/{mac_upper}_VERSION/shadow/get/+"

# Config entry keys
# MAC address from the device sticker, normalised to lowercase no-colon hex.
CONF_MAC = "mac"
CONF_CERT_ID = "cert_id"

# HA storage
STORAGE_KEY = "aquatek_certs"
STORAGE_VERSION = 1

# MQTT reconnect timing (seconds)
RECONNECT_MIN = 2
RECONNECT_MAX = 60
WATCHDOG_TIMEOUT = 180  # mark offline if no status message in this many seconds

# ---------------------------------------------------------------------------
# Modbus register map
# ---------------------------------------------------------------------------
#
# SOCKET ARCHITECTURE
# -------------------
# The controller has configurable sockets. Each physical socket (5 total) is
# assigned an appliance type in the app (sanitiser, pool light, jet pump, etc.).
# The type assignment is stored on-device; entities must be auto-discovered by
# reading config registers at startup.
#
#   Output register:   REG_SOCKET_BASE + socket_number  (1-indexed)
#   e.g. socket 1 → 65335, socket 2 → 65336, ... socket 5 → 65339
#
#   Type register:     REG_SOCKET_TYPE_BASE + socket_number  (1-indexed)
#   e.g. socket 1 → reg 17, socket 2 → reg 18, ...
#   Encoding: hi byte = SOCKET_TYPE_* index  (confirmed from APK arrays.xml)
#
#   Output values:  0 = off, 1 = on (manual), 2 = auto
#
# VF CONNECTORS (variable-frequency drive outputs, 2 total)
# ---------------------------------------------------------
# Used for speed-controlled loads (filter pump) and heater enables.
# Filter pump VF encoding: 0=off, (speed<<8)|1 = speed 1–4, 65535=auto
#   i.e. 257=speed1, 513=speed2, 769=speed3, 1025=speed4

REG_SOCKET_BASE = 65335          # socket n output = REG_SOCKET_BASE + n (1-indexed)
                                 # e.g. socket 1 → 65336, socket 5 → 65340
SOCKET_COUNT = 5

REG_SOCKET_TYPE_BASE = 65322     # socket n type = REG_SOCKET_TYPE_BASE + n (1-indexed)
                                 # e.g. socket 1 → 65323, socket 5 → 65327
                                 # Value is the type index directly (0–14), NOT hi/lo encoded

# Socket type indices from APK arrays.xml socket_type_options
SOCKET_TYPE_NONE = 0
SOCKET_TYPE_SANITISER = 1
SOCKET_TYPE_FILTER_PUMP = 2
SOCKET_TYPE_CLEANING_PUMP = 3
SOCKET_TYPE_BLOWER = 4
SOCKET_TYPE_POOL_LIGHT = 5
SOCKET_TYPE_SPA_LIGHT = 6
SOCKET_TYPE_GARDEN_LIGHT = 7
SOCKET_TYPE_WATER_FEATURE = 8
SOCKET_TYPE_SOLAR = 9
SOCKET_TYPE_OTHER = 10
SOCKET_TYPE_ALWAYS_ON = 11
SOCKET_TYPE_JET_PUMP = 12
SOCKET_TYPE_HEATING_PUMP = 13
SOCKET_TYPE_UV_SANITISER = 14

# Human-readable names for each socket type (used for entity naming)
SOCKET_TYPE_NAMES: dict[int, str] = {
    SOCKET_TYPE_SANITISER: "Sanitiser",
    SOCKET_TYPE_FILTER_PUMP: "Filter Pump",
    SOCKET_TYPE_CLEANING_PUMP: "Cleaning Pump",
    SOCKET_TYPE_BLOWER: "Blower",
    SOCKET_TYPE_POOL_LIGHT: "Pool Light",
    SOCKET_TYPE_SPA_LIGHT: "Spa Light",
    SOCKET_TYPE_GARDEN_LIGHT: "Garden Light",
    SOCKET_TYPE_WATER_FEATURE: "Water Feature",
    SOCKET_TYPE_SOLAR: "Solar",
    SOCKET_TYPE_OTHER: "Other",
    SOCKET_TYPE_ALWAYS_ON: "Always On",
    SOCKET_TYPE_JET_PUMP: "Jet Pump",
    SOCKET_TYPE_HEATING_PUMP: "Heating Pump",
    SOCKET_TYPE_UV_SANITISER: "UV Sanitiser",
}

# Confirmed socket→appliance mapping on hardware-tested device (socket 1-indexed):
#   Socket 2 (65336) = Sanitiser
#   Socket 4 (65338) = Jet Pump
#   Socket 5 (65339) = Pool Light
# (other devices may differ — always use auto-discovery)

# ---------------------------------------------------------------------------
# VF connector — filter pump (confirmed on hardware: reg 65485)
# Values: 0=off, 257=speed1, 513=speed2, 769=speed3, 1025=speed4, 65535=auto
REG_FILTER_PUMP = 65485

# ---------------------------------------------------------------------------
# Heater registers (57xxx range)
REG_HEATER_TYPE = 57510         # 0=Smart Heater, 1=Heat Pump, 2=Gas (config, not on/off)
REG_HEAT_PUMP_CTRL = 57517      # Heat Pump Heater on/off/auto: 0=off, 2=auto (confirmed)
REG_GAS_HEATER = 65348          # Gas Heater on/off/auto: 0=off, 2=auto (confirmed; = 65334+14)
REG_HEAT_SETPOINT = 57575       # Target temperature; value = °C × 2 (e.g. 32°C = 64, 33°C = 66)
REG_HEATER_MODE = 57583         # 0=off, else on (purpose unconfirmed, may overlap with above)

REG_SOLAR_ENABLED = 57585       # bit 0 = solar enabled

# ---------------------------------------------------------------------------
# Pump base registers (the socket output range starts here at socket 5)
# REG_PUMP_BASE == REG_SOCKET_BASE + 5 == 65339
REG_PUMP_BASE = 0xFF3B          # 65339 — socket 5 output (= pump 0 in original firmware model)
REG_PUMP_SPEED_BASE = 0xFF48    # 65352 — pump 0 speed (0–3 or 0–4, confirm on hardware)
PUMP_COUNT = 13                 # indices 0–12; index 12 = spa pump

REG_SPA_ENABLE = 65335          # socket 1 output (= REG_SOCKET_BASE + 1)

REG_DEVICE_NAME_BASE = 65488    # 8 registers, each an ASCII byte
