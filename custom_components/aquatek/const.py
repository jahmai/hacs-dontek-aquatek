"""Constants for the Dontek Aquatek integration."""

DOMAIN = "aquatek"

# AWS / IoT
COGNITO_POOL_ID = "ap-southeast-2:c45f75ed-a7e5-4a4f-b27a-ac3941f6d9bf"
AWS_REGION = "ap-southeast-2"
IOT_ENDPOINT = "a219g53ny7vwvd-ats.iot.ap-southeast-2.amazonaws.com"
IOT_POLICY_NAME = "pswpolicy"

# MQTT topic templates — MAC address as stored (e.g. "AA:BB:CC:DD:EE:FF")
TOPIC_STATUS = "{mac}/status/psw"
TOPIC_CMD = "{mac}/cmd/psw"
TOPIC_SHADOW = "$aws/things/{mac_upper}_VERSION/shadow/get/+"

# Config entry keys
# The device ID is the numeric string encoded in the QR code sticker
# (e.g. "12345678901234567").
CONF_DEVICE_ID = "device_id"
CONF_CERT_ID = "cert_id"

# HA storage
STORAGE_KEY = "aquatek_certs"
STORAGE_VERSION = 1

# MQTT reconnect timing (seconds)
RECONNECT_MIN = 2
RECONNECT_MAX = 60
WATCHDOG_TIMEOUT = 180  # mark offline if no status message in this many seconds

# Modbus registers
# Pump on/off: REG_PUMP_BASE + pump_index (0–12)
REG_PUMP_BASE = 0xFF3B          # 65339 — pump 0 on/off
REG_PUMP_SPEED_BASE = 0xFF48    # 65352 — pump 0 speed
PUMP_COUNT = 13                 # indices 0–12; index 12 = spa pump

REG_FILTER_ENABLED = 65430
REG_SANITIZER_ENABLED = 65431

REG_HEATER_TYPE = 57510         # 0=Smart Heater, 1=Heat Pump, 2=Gas
REG_HEAT_SETPOINT = 57566       # target temperature (× 10 = tenths of °C, confirm on hardware)
REG_HEATER_MODE = 57583         # 0=off, else on

REG_SOLAR_ENABLED = 57585       # bit 0 = solar enabled

REG_LIGHT1 = 65314
REG_LIGHT2 = 65315

REG_SPA_ENABLE = 65335          # same as REG_PUMP_BASE + 12

REG_DEVICE_NAME_BASE = 65488    # 8 registers, each an ASCII byte
