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
WATCHDOG_TIMEOUT = 600  # mark offline if no status message in this many seconds (device heartbeat ~8min)

# ---------------------------------------------------------------------------
# Modbus register map — all confirmed against live hardware (2026-03-31)
# ---------------------------------------------------------------------------
#
# CONTROLLER OUTPUT ARCHITECTURE
# --------------------------------
# 5 Sockets   — relay outputs; each assigned an appliance type in the app
# 2 VF ports  — heater type assignment only (Heater 1 or Heater 2)
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
# Values: 0=None, 1=Heater 1, 2=Heater 2
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
# Heater 1: controlled via fireman's switch wired to a socket-output register
#            Output register follows the same 65336+ range as sockets.
#            Confirmed at reg 65348 on tested hardware (socket index 13 = 65336+12).
# Heater 2: connected via serial cable; controlled in the 57xxx register range.
REG_HEATER1_CTRL = 65348      # Heater 1 on/off/auto: 0=off, 1=on, 2=auto (confirmed)
REG_HEATER2_CTRL = 57517      # Heater 2 on/off/auto: 0=off, 2=auto (confirmed)
REG_HEAT_SETPOINT = 57575     # Heater 2 setpoint (Pool): value = °C × 2 (confirmed)
REG_SPA_SETPOINT = 65441      # Heater 1 setpoint (Spa): value = °C × 2 (confirmed)
REG_BOOST_MODE = 57577           # Heater 2 boost/party mode: 0=off, 1=on (confirmed)
REG_RUN_TILL_HEATED = 65500      # Heater 1 run till heated: 0=off, 1=on (confirmed)

# ---------------------------------------------------------------------------
# VF port heating configuration
# VF1 = Heater 1 (65xxx registers), VF2 = Heater 2 (57xxx registers)
#
# Heating mode values: 0=Off, 2=Pool & Spa, 3=Pool, 4=Spa (confirmed both VFs)
# Pump type + sensor location — identical packing for both VFs (confirmed):
#   0 = Filter (no sensor location)
#   1 = Independent + Filter sensor
#   2 = Independent + Heater Line sensor

REG_VF1_HEAT_MODE    = 65450     # VF1 heating mode (0=Off, 2=Pool&Spa, 3=Pool, 4=Spa)
REG_VF1_COOLDOWN     = 65451     # VF1 cool down time in minutes
REG_VF1_SANITISER    = 65501     # VF1 sanitiser: 0=off, 1=on
REG_VF1_PUMP_TYPE    = 65499     # VF1 pump type+sensor combined: 0=Filter, 1=Indep/Filter, 2=Indep/HeaterLine (confirmed)
REG_VF1_SENSOR_LOC   = 65499     # same register — sensor location encoded as 1=Filter, 2=HeaterLine
REG_VF1_PUMP_SPEED   = 65462     # VF1 pump speed: 0=Speed1, 1=Speed2, 2=Speed3, 3=Speed4 (confirmed)
REG_VF1_CHILLING     = 65523     # VF1 chilling: 0=off, 1=on (Heater 2 type only)
REG_VF1_HYDRO        = 57586     # VF1 hydrotherapy: 0=off, 1=on

REG_VF2_HEAT_MODE    = 57566     # VF2 heating mode (0=Off, 2=Pool&Spa, 3=Pool, 4=Spa)
REG_VF2_COOLDOWN     = 57568     # VF2 cool down time in minutes
REG_VF2_SANITISER    = 57570     # VF2 sanitiser: 0=off, 1=on
REG_VF2_PUMP_TYPE    = 57574     # VF2 pump type+sensor combined: 0=Filter, 1=Indep/Filter, 2=Indep/HeaterLine
REG_VF2_SENSOR_LOC   = 57574     # same register — sensor location encoded as 1=Filter, 2=HeaterLine
REG_VF2_CHILLING     = 57569     # VF2 chilling: 0=off, 1=on (Heater 2 type only)
REG_VF2_HYDRO        = 57587     # VF2 hydrotherapy: 0=off, 1=on
REG_VF2_SETBACK      = 57578     # VF2 setback: 0=off, 1=on (Secondary Heating only)
REG_VF2_SETBACK_TEMP = 57579     # VF2 setback temperature offset: stored as positive 0.5°C steps (e.g. 6=−3°C)

VF_HEAT_MODE_OPTIONS = ["Off", "Pool & Spa", "Pool", "Spa"]
VF_HEAT_MODE_VALUES  = [0, 2, 3, 4]

VF1_PUMP_TYPE_OPTIONS = ["Filter", "Independent"]
VF1_PUMP_TYPE_VALUES  = [0, 1]  # 0=Filter, non-zero=Independent (confirmed)

VF1_SENSOR_LOC_OPTIONS = ["Filter", "Heater Line"]
VF1_SENSOR_LOC_VALUES  = [1, 2]  # 1=Filter sensor, 2=Heater Line sensor (confirmed)

VF1_PUMP_SPEED_OPTIONS = ["Speed 1", "Speed 2", "Speed 3", "Speed 4"]
VF1_PUMP_SPEED_VALUES  = [0, 1, 2, 3]  # confirmed

VF2_PUMP_TYPE_OPTIONS = ["Filter", "Independent"]
VF2_PUMP_TYPE_VALUES  = [0, 1]   # 0=Filter, non-zero=Independent

VF2_SENSOR_LOC_OPTIONS = ["Filter", "Heater Line"]
VF2_SENSOR_LOC_VALUES  = [1, 2]  # 1=Filter sensor, 2=Heater Line sensor
# ---------------------------------------------------------------------------
# Temperature sensors (3 physical sensors, each configurable to a role)
# Type config: 65314=Sensor1 type, 65315=Sensor2 type, 65316=Sensor3 type
# Reading:     reg 55=Sensor1, 56=Sensor2, 57=Sensor3  — value = °C × 2 (confirmed)
# Sensor type values:
#   1 = Pool  (confirmed: 65315=1 when Sensor2 configured as Pool)
#   2 = Roof  (confirmed: 65314=2 when Sensor1 configured as Roof)
#  15 = Water (observed: 65316=15 when Sensor3 configured as Water — value may vary)
REG_SENSOR_TYPE_BASE = 65314    # Sensor n type = base + (n-1), n=1..3
REG_SENSOR_READING_BASE = 55    # Sensor n reading = base + (n-1), value = °C × 2
SENSOR_COUNT = 3
SENSOR_TYPE_POOL = 1            # Pool temperature sensor
SENSOR_TYPE_ROOF = 2            # Roof/solar temperature sensor
# Water sensor type index observed as 15 on tested hardware — may vary
SENSOR_TYPE_WATER = 15

SENSOR_TYPE_NAMES: dict[int, str] = {
    0: "None",
    SENSOR_TYPE_POOL: "Pool",
    SENSOR_TYPE_ROOF: "Roof",
    SENSOR_TYPE_WATER: "Water",
}

# Alias used in climate.py for sensor 1 fallback (original name kept for compat)
REG_WATER_TEMP = REG_SENSOR_READING_BASE

# ---------------------------------------------------------------------------
# Pool light type and colour control
# reg 65352 packs: (light_type << 8) | colour_index (confirmed on hardware)
# Type indices: 2=Aquaquip, 3=Aquaquip Instatouch confirmed; others assumed sequential
# (0 and 1 are unconfirmed — likely None / Single Colour but not validated)
REG_POOL_LIGHT_CTRL = 65352

# Light type indices (from APK arrays.xml light_type_options order, offset confirmed at 2/3)
LIGHT_TYPE_AQUAQUIP           = 2   # confirmed
LIGHT_TYPE_AQUAQUIP_INSTATOUCH = 3  # confirmed
LIGHT_TYPE_AQUATIGHT          = 4   # assumed sequential
LIGHT_TYPE_AQUATIGHT_SUPANOVA = 5   # assumed sequential
LIGHT_TYPE_ASTRAL_POOL        = 6   # assumed sequential
LIGHT_TYPE_JANDY              = 7   # assumed sequential
LIGHT_TYPE_PENTAIR_GLOBRITE   = 8   # assumed sequential
LIGHT_TYPE_SPA_ELECTRICS      = 9   # assumed sequential
LIGHT_TYPE_SPA_ELECTRICS_MULTI = 10 # assumed sequential
LIGHT_TYPE_WATERCO            = 11  # assumed sequential
LIGHT_TYPE_SR_SMITH_MODLITE   = 12  # assumed sequential
LIGHT_TYPE_SINGLE_COLOUR      = 13  # assumed sequential

LIGHT_TYPE_NAMES: dict[int, str] = {
    LIGHT_TYPE_AQUAQUIP:            "Aquaquip",
    LIGHT_TYPE_AQUAQUIP_INSTATOUCH: "Aquaquip Instatouch",
    LIGHT_TYPE_AQUATIGHT:           "Aquatight",
    LIGHT_TYPE_AQUATIGHT_SUPANOVA:  "Aquatight Supa Nova",
    LIGHT_TYPE_ASTRAL_POOL:         "Astral Pool",
    LIGHT_TYPE_JANDY:               "Jandy",
    LIGHT_TYPE_PENTAIR_GLOBRITE:    "Pentair GloBrite",
    LIGHT_TYPE_SPA_ELECTRICS:       "Spa Electrics",
    LIGHT_TYPE_SPA_ELECTRICS_MULTI: "Spa Electrics Multi-Plus",
    LIGHT_TYPE_WATERCO:             "Waterco",
    LIGHT_TYPE_SR_SMITH_MODLITE:    "Mod-Lite (SR Smith)",
    LIGHT_TYPE_SINGLE_COLOUR:       "Single Colour",
}

# Colour/mode lists per light type — order matches app UI (index = colour_index in register)
# Source: APK arrays.xml (confirmed for Aquaquip Instatouch via hardware button test)
LIGHT_COLOURS: dict[int, list[str]] = {
    LIGHT_TYPE_AQUAQUIP: [
        "Pure Red", "Deep Orange", "Pure Green", "Emerald", "Digital Blue",
        "Indigo", "Magenta", "Yellow", "Cyan", "RGB White", "Pink",
        "Pastel Green", "Pastel Blue", "Mauve", "Lime Green", "Baby Blue",
    ],
    LIGHT_TYPE_AQUAQUIP_INSTATOUCH: [
        "Blue", "Aqua", "Green", "Gold", "Magenta", "Red", "White",
        "Seaside", "Slow Scroll", "Fast Scroll", "Fireworks", "Disco", "Flash",
    ],
    LIGHT_TYPE_AQUATIGHT: [
        "Season Transition", "Daybreak Transition", "Neutral White", "Rainbow",
        "River of Colours", "Disco", "Four Seasons", "Party", "Sun White",
        "Red", "Lush Green", "Storm Blue", "Sky Blue", "Sunset Amber", "Violet",
        "Storm Transition",
    ],
    LIGHT_TYPE_AQUATIGHT_SUPANOVA: [
        "Green", "Blue", "Red and Green", "Red and Blue", "Green and Blue",
        "Red and Green and Blue", "Red and Green and Blue Fade", "Red Green Blue Fade",
        "Green Red Blue Fade", "Blue Red Green Fade", "Combo Fade",
        "Red and Green Blue Fade", "Red and Blue Green Fade", "Green and Blue Red Fade",
        "Multiple Flash", "Multiple Fade",
    ],
    LIGHT_TYPE_ASTRAL_POOL: [
        "Blue", "Magenta", "Red", "Orange", "Green", "Aqua", "White",
        "Custom 1", "Custom 2", "Rainbow", "Ocean", "Disco",
    ],
    LIGHT_TYPE_JANDY: [
        "Alpine White", "Sky Blue", "Cobalt Blue", "Caribbean Blue", "Spring Green",
        "Emerald Green", "Emerald Rose", "Magenta", "Violet",
        "Slow Colour Splash", "Fast Colour Splash", "America the Beautiful",
        "Fat Tuesday", "Disco Tech",
    ],
    LIGHT_TYPE_PENTAIR_GLOBRITE: [
        "Sam Mode", "Party Mode", "Romance Mode", "Caribbean Mode", "American Mode",
        "California Sunset Mode", "Royal Mode",
        "Blue", "Green", "Red", "White", "Magenta", "Hold", "Recall",
    ],
    LIGHT_TYPE_SPA_ELECTRICS: [
        "Blue", "Magenta", "Red", "Lime", "Green", "Aqua",
        "Daylight White 4000k", "Warm White 3000k",
        "Slow Colour Blend", "Fast Colour Change",
    ],
    LIGHT_TYPE_SPA_ELECTRICS_MULTI: [
        "Blue", "Magenta", "Red", "Lime", "Green", "Aqua", "White",
        "Oceanic Views", "Transcendence", "Outback Australia", "Spring Equinox",
    ],
    LIGHT_TYPE_WATERCO: [
        "White", "Slow Changing Colours", "Fast Changing Colours",
        "Blue", "Magenta", "Red", "Yellow Green Gold", "Green", "Aqua",
    ],
    LIGHT_TYPE_SR_SMITH_MODLITE: [
        "Slow Colour Change", "White", "Blue", "Green", "Red", "Amber",
        "Magenta", "Fast Colour Change",
    ],
    LIGHT_TYPE_SINGLE_COLOUR: [
        "Single Colour",
    ],
}

# Fallback colour list for unknown types
LIGHT_COLOURS_DEFAULT = ["Colour 0"]

# ---------------------------------------------------------------------------
# Status registers (read-only, pushed by the device on state changes)
#
# Filter pump packed status — confirmed via APK f3/l.java line 212:
#   state = (reg92 & 0xFF00) >> 8   (high byte)
#   speed = reg92 & 0x00FF          (low byte, 0-indexed: 0=Speed1, 1=Speed2, 2=Speed3, 3=Speed4)
# Speed byte is stale when pump is off — only valid for running states (5, 9-13).
# State values from e3.h.g(): 0-1=Off, 5=Priming, 9-11=On, 12=Running, 13=Run On, 17=Fault
#
# Last-ran-at register — packed as (hours << 8) | minutes; 65535 = no data
# (Observed to update to current time when the pump transitions to Off)
#
# Heater status registers — reg 184 = Heater 1, reg 185 = Heater 2.
# Both heaters share the same status code table (HEATER_STATUS_NAMES).
# Values taken directly from APK e3/f.java method a(int, f.m, String[]).
REG_FILTER_PUMP_STATUS = 92
REG_FILTER_PUMP_LAST_RAN = 94
REG_HEATER1_STATUS = 81
REG_HEATER2_STATUS = 184

HEATER_STATUS_NAMES: dict[int, str] = {
    0: "Off",
    1: "Waiting",
    2: "Sampling",
    3: "Checking",
    4: "Heating",
    5: "Run On",
    6: "Limit",
    7: "Stopping",
    8: "Fault",
    9: "Waiting (Solar Priority)",
    10: "Chilling",
    11: "Off in Pool",
    12: "Off in Spa",
}

FILTER_PUMP_STATUS_NAMES: dict[int, str] = {
    0: "Off",
    1: "Off",
    2: "Power Up",
    3: "Power Up",
    4: "Power Up",
    5: "Priming",
    6: "Set Speed",
    7: "Set Speed",
    8: "Set Speed",
    9: "On",
    10: "On",
    11: "On",
    12: "Running",
    13: "Run On",
    14: "Power Down",
    15: "Power Down",
    16: "Power Down",
    17: "Fault",
    18: "Prime Off",
    19: "Run On",
}

# ---------------------------------------------------------------------------
# Device info
REG_DEVICE_NAME_BASE = 65488     # 8 registers, 2 packed ASCII bytes each (big-endian)
