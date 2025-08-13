"""Constants for the BeHome integration."""

DOMAIN = "behome"

# OAuth2.0 Configuration
OAUTH2_AUTHORIZE_URL = "https://cloud.bemfa.com/web/mi/index.html"
OAUTH2_TOKEN_URL = "https://pro.bemfa.com/vs/speaker/v1/v2SpeakerToken"
OAUTH2_CLIENT_ID = "88ac425b4558463aa813aed1690db730"

# API Endpoints
API_BASE_URL = "https://apis.bemfa.com/vb/ha/v1"
API_DEVICE_LIST_URL = f"{API_BASE_URL}/device"
API_DEVICE_CONTROL_URL = f"{API_BASE_URL}/postMassage"

# Platforms
PLATFORMS = [
    "switch",
    "light",
    "fan",
    "sensor",
    "climate",
    "cover",
    "water_heater",
    "media_player",
]

# Device Type Suffixes
DEVICE_TYPE_SOCKET = "outlet"
DEVICE_TYPE_LIGHT = "light"
DEVICE_TYPE_FAN = "fan"
DEVICE_TYPE_SENSOR = "sensor"
DEVICE_TYPE_CLIMATE = "aircondition"
DEVICE_TYPE_SWITCH = "switch"
DEVICE_TYPE_COVER = "curtain"
DEVICE_TYPE_THERMOSTAT = "thermostat"
DEVICE_TYPE_WATER_HEATER = "waterheater"
DEVICE_TYPE_MEDIA_PLAYER = "television"
DEVICE_TYPE_AIR_PURIFIER = "airpurifier"

# Configuration
CONF_PRIVATE_KEY = "private_key"