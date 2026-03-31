"""Constants for the Dontek Aquatek integration."""

DOMAIN = "dontek_aquatek"

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
# Modbus register map — all confirmed against live hardware (2026-03-31)
# ---------------------------------------------------------------------------
#
# CONTROLLER OUTPUT ARCHITECTURE
# --------------------------------
# 5 Sockets   — relay outputs; each assigned an appliance type in the app
# 2 VF ports  — heater type assignment only (Gas Heater or Heat Pump)
# 1 Filter pump serial port — dedicated speed-control serial connection
#
# SOCKET REGISTERS
# -----------------
# Output register:  65336 + (socket_n - 1)  i.e. socket 1=65336 ... socket 5=65340
# Type register:    65323 + (socket_n - 1)  i.e. socket 1=65323 ... socket 5=65327
# Type value is stored directly as an integer index (0–14) from SOCKET_TYPE_*.
# Output values: 0=off, 1=on (manual / schedule running), 2=auto (schedule idle)

REG_SOCKET_OUTPUT_BASE = 65336   # socket n output = REG_SOCKET_OUTPUT_BASE + (n-1)
REG_SOCKET_TYPE_BASE = 65323     # socket n type   = REG_SOCKET_TYPE_BASE   + (n-1)
SOCKET_COUNT = 5

# Socket type indices — from APK arrays.xml socket_type_options (confirmed complete list)
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

# ---------------------------------------------------------------------------
# Pool / Spa mode (write to switch between pool and spa mode)
# 0 = Pool, 1 = Spa (confirmed on hardware)
REG_POOL_SPA_MODE = 65313

# ---------------------------------------------------------------------------
# VF port type config (which heater is connected to each VF port)
# Values: 0=None, 1=Gas Heater, 2=Heat Pump
REG_VF1_TYPE = 65335             # VF port 1 type config (confirmed)
REG_VF2_TYPE = 57510             # VF port 2 type config (confirmed)

VF_TYPE_NONE = 0
VF_TYPE_GAS_HEATER = 1
VF_TYPE_HEAT_PUMP = 2

# ---------------------------------------------------------------------------
# Filter pump — dedicated serial port (not a socket, not a VF port)
# Values: 0=off, 257=speed1, 513=speed2, 769=speed3, 1025=speed4, 65535=auto
REG_FILTER_PUMP = 65485

# ---------------------------------------------------------------------------
# Heater control registers
# Gas Heater:  controlled via fireman's switch wired to a socket-output register
#              Output register follows the same 65336+ range as sockets.
#              Confirmed at reg 65348 on tested hardware (socket index 13 = 65336+12).
# Heat Pump:   connected via serial cable; controlled in the 57xxx register range.
REG_GAS_HEATER_CTRL = 65348      # Gas Heater on/off/auto: 0=off, 2=auto (confirmed)
REG_HEAT_PUMP_CTRL = 57517       # Heat Pump on/off/auto:  0=off, 2=auto (confirmed)
REG_HEAT_SETPOINT = 57575        # Pool setpoint: value = °C × 2 (e.g. 32°C=64, confirmed)
REG_SPA_SETPOINT = 65441         # Spa setpoint:  value = °C × 2 (e.g. 38°C=76, confirmed)

# ---------------------------------------------------------------------------
# Device info
REG_DEVICE_NAME_BASE = 65488     # 8 registers, 2 packed ASCII bytes each (big-endian)
