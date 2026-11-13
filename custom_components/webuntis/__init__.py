"""The WebUntis integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WebUntisApiClient
from .const import (
    CONF_BASE_URL,
    CONF_CLASS_ID,
    CONF_CLIENT_IDENTITY,
    CONF_PASSWORD,
    CONF_SCHOOL,
    CONF_TIMETABLE_SCOPE,
    CONF_UPDATE_INTERVAL,
    CONF_USERNAME,
    DEFAULT_CLIENT_IDENTITY,
    DEFAULT_TIMETABLE_SCOPE,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .coordinator import WebUntisCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WebUntis from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    options = entry.options
    client_identity = options.get(
        CONF_CLIENT_IDENTITY,
        entry.data.get(CONF_CLIENT_IDENTITY, DEFAULT_CLIENT_IDENTITY),
    )
    interval_minutes = options.get(
        CONF_UPDATE_INTERVAL,
        entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
    )
    timetable_scope = options.get(
        CONF_TIMETABLE_SCOPE,
        entry.data.get(CONF_TIMETABLE_SCOPE, DEFAULT_TIMETABLE_SCOPE),
    )
    class_id = options.get(CONF_CLASS_ID, entry.data.get(CONF_CLASS_ID))

    api = WebUntisApiClient(
        session=async_get_clientsession(hass),
        school=entry.data[CONF_SCHOOL],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        base_url=entry.data[CONF_BASE_URL],
        client_identity=client_identity,
    )

    coordinator = WebUntisCoordinator(
        hass,
        api,
        int(interval_minutes),
        str(timetable_scope),
        int(class_id) if class_id not in (None, "") else None,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a WebUntis config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading the config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
