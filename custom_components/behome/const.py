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

# WeChat scan login
WECHAT_QR_URL = "https://go.bemfa.com/v3/getwximg?key=bemfa&q=2"
WECHAT_QR_IMAGE_URL = "https://mp.weixin.qq.com/cgi-bin/showqrcode?ticket={ticket}"
WECHAT_LOGIN_POLL_URL = "https://go.bemfa.com/vb/web/v2/wechatLoginByEventKey"

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
CONF_SYNC_MODE = "sync_mode"
CONF_SELECTED_DEVICES = "selected_devices"

SYNC_MODE_AUTO = "auto"
SYNC_MODE_MANUAL = "manual"
