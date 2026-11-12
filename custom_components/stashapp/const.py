"""Constants for the Stash integration."""

DOMAIN = "stashapp"

CONF_URL = "url"
CONF_API_KEY = "api_key"

SUBENTRY_TYPE_FEED = "feed"
CONF_TAGS = "tags"
CONF_AUTO_REFRESH_INTERVAL = "auto_refresh_interval"
CONF_AUTO_REFRESH_MINUTES = "auto_refresh_minutes"
CONF_AUTO_REFRESH_SECONDS = "auto_refresh_seconds"
MIN_AUTO_REFRESH_SECONDS = 10

DEFAULT_SCAN_INTERVAL = 300
REQUEST_TIMEOUT = 15

ACTIVE_JOB_STATUSES = {"READY", "RUNNING", "STOPPING"}

SERVICE_RANDOM_IMAGE = "random_image"
SERVICE_RANDOM_SCENE = "random_scene"
SERVICE_SCAN_LIBRARY = "scan_library"
SERVICE_REFRESH_FEED = "refresh_feed"

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_TAGS = "tags"
