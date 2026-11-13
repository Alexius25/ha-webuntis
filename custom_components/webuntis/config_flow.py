"""Config flow for WebUntis integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WebUntisApiAuthError, WebUntisApiClient, WebUntisApiError
from .const import (
    CONF_BASE_URL,
    CONF_CLASS_ID,
    CONF_CLIENT_IDENTITY,
    CONF_SCHOOL,
    CONF_TIMETABLE_SCOPE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_CLIENT_IDENTITY,
    DEFAULT_NAME,
    DEFAULT_TIMETABLE_SCOPE,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    TIMETABLE_SCOPE_CLASS,
    TIMETABLE_SCOPE_OWN,
)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_SCHOOL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_BASE_URL): str,
        vol.Required(CONF_CLIENT_IDENTITY, default=DEFAULT_CLIENT_IDENTITY): str,
        vol.Required(CONF_TIMETABLE_SCOPE, default=DEFAULT_TIMETABLE_SCOPE): vol.In(
            [TIMETABLE_SCOPE_OWN, TIMETABLE_SCOPE_CLASS]
        ),
        vol.Optional(CONF_CLASS_ID): vol.Any(None, vol.Coerce(int)),
        vol.Required(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=240)
        ),
    }
)


def _options_schema(data: Mapping[str, Any]) -> vol.Schema:
    """Build options schema with defaults from entry data/options."""
    return vol.Schema(
        {
            vol.Required(
                CONF_CLIENT_IDENTITY,
                default=data.get(CONF_CLIENT_IDENTITY, DEFAULT_CLIENT_IDENTITY),
            ): str,
            vol.Required(
                CONF_TIMETABLE_SCOPE,
                default=data.get(CONF_TIMETABLE_SCOPE, DEFAULT_TIMETABLE_SCOPE),
            ): vol.In([TIMETABLE_SCOPE_OWN, TIMETABLE_SCOPE_CLASS]),
            vol.Optional(
                CONF_CLASS_ID,
                default=data.get(CONF_CLASS_ID),
            ): vol.Any(None, vol.Coerce(int)),
            vol.Required(
                CONF_UPDATE_INTERVAL,
                default=data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=240)),
        }
    )


async def _validate_input(hass: HomeAssistant, data: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    api = WebUntisApiClient(
        session=async_get_clientsession(hass),
        school=data[CONF_SCHOOL],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        base_url=data[CONF_BASE_URL],
        client_identity=data[CONF_CLIENT_IDENTITY],
    )

    await api.async_login()

    if data.get(CONF_TIMETABLE_SCOPE) == TIMETABLE_SCOPE_CLASS and data.get(CONF_CLASS_ID) in (
        None,
        "",
    ):
        raise CannotConnect("Class timetable requires class id")

    return {"title": data[CONF_NAME]}


class ConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WebUntis."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> WebUntisOptionsFlowHandler:
        """Return the options flow for this handler."""
        return WebUntisOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            scope = user_input.get(CONF_TIMETABLE_SCOPE, DEFAULT_TIMETABLE_SCOPE)
            class_id = user_input.get(CONF_CLASS_ID)
            profile_key = class_id if scope == TIMETABLE_SCOPE_CLASS else "self"
            await self.async_set_unique_id(
                f"{user_input[CONF_SCHOOL]}::{user_input[CONF_USERNAME]}::{scope}::{profile_key}"
            )
            self._abort_if_unique_id_configured()

            try:
                info = await _validate_input(self.hass, user_input)
            except WebUntisApiAuthError:
                errors["base"] = "invalid_auth"
            except WebUntisApiError:
                errors["base"] = "cannot_connect"
            except CannotConnect:
                errors["base"] = "invalid_timetable_config"
            except Exception:
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class WebUntisOptionsFlowHandler(OptionsFlow):
    """Handle WebUntis options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage WebUntis options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input.get(CONF_TIMETABLE_SCOPE) == TIMETABLE_SCOPE_CLASS and user_input.get(
                CONF_CLASS_ID
            ) in (None, ""):
                errors["base"] = "invalid_timetable_config"
            else:
                return self.async_create_entry(title="", data=user_input)

        merged: dict[str, Any] = {**self._config_entry.data, **self._config_entry.options}

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(merged),
            errors=errors,
        )
