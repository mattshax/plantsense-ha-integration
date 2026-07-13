"""Config flow for the PlantSense integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import BASE_URL, DOMAIN, LOGIN_ENDPOINT

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class InvalidAuth(Exception):
    """Error to indicate the credentials were rejected."""


class CannotConnect(Exception):
    """Error to indicate we could not reach the PlantSense backend."""


async def _validate_login(hass: HomeAssistant, email: str, password: str) -> None:
    """Validate credentials against /auth/login.

    Raises:
        InvalidAuth: the credentials were rejected.
        CannotConnect: the backend was unreachable or returned a hard error.
    """
    session = async_get_clientsession(hass)
    try:
        async with session.post(
            f"{BASE_URL}{LOGIN_ENDPOINT}",
            json={"email": email, "pass": password},
        ) as resp:
            if resp.status in (400, 401, 403):
                raise InvalidAuth
            if resp.status != 200:
                raise CannotConnect
            payload = await resp.json()
    except aiohttp.ClientError as err:
        raise CannotConnect from err

    if payload.get("message") != "success" or not payload.get("token"):
        raise InvalidAuth


class PlantSenseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the PlantSense config and re-auth flows."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._reauth_email: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step where the user enters account credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()

            errors = await self._try_login(email, password)
            if not errors:
                return self.async_create_entry(
                    title=email,
                    data={CONF_EMAIL: email, CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start re-authentication after the coordinator hit a hard auth failure."""
        self._reauth_email = entry_data[CONF_EMAIL]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a fresh password and update the existing entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            password = user_input[CONF_PASSWORD]

            errors = await self._try_login(self._reauth_email, password)
            if not errors:
                entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={CONF_EMAIL: self._reauth_email, CONF_PASSWORD: password},
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            description_placeholders={CONF_EMAIL: self._reauth_email or ""},
            errors=errors,
        )

    async def _try_login(self, email: str, password: str) -> dict[str, str]:
        """Validate credentials and map failures to config-flow error keys."""
        try:
            await _validate_login(self.hass, email, password)
        except InvalidAuth:
            return {"base": "invalid_auth"}
        except CannotConnect:
            return {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001 - surface anything unexpected as a soft error
            _LOGGER.exception("Unexpected error validating PlantSense login")
            return {"base": "cannot_connect"}
        return {}
