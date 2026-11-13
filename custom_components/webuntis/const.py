"""Constants for the WebUntis integration."""

from datetime import timedelta

DOMAIN = "webuntis"

CONF_SCHOOL = "school"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_BASE_URL = "base_url"
CONF_CLIENT_IDENTITY = "client_identity"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_TIMETABLE_SCOPE = "timetable_scope"
CONF_CLASS_ID = "class_id"

TIMETABLE_SCOPE_OWN = "own"
TIMETABLE_SCOPE_CLASS = "class"

DEFAULT_NAME = "WebUntis"
DEFAULT_CLIENT_IDENTITY = "HomeAssistant"
DEFAULT_UPDATE_INTERVAL = 15
DEFAULT_TIMETABLE_SCOPE = TIMETABLE_SCOPE_OWN

PLATFORMS = ["sensor", "binary_sensor", "calendar"]

COORDINATOR_UPDATE_INTERVAL = timedelta(minutes=DEFAULT_UPDATE_INTERVAL)
