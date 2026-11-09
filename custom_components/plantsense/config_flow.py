"""Config flow for the PlantSense integration: Sign in with PlantSense.

Home Assistant opens the PlantSense sign-in page (oauth.py), where any sign-in
method works, Google and Apple included. Entries made before 1.4.0 hold an
email and password instead; they keep working, and a re-authentication moves
them to Sign in with PlantSense.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any

import aiohttp

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.const import CONF_URL
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import BASE_URL, DATA_ENDPOINT, DOMAIN, ENV_API_URL
from .oauth import async_register_implementation, async_revoke_token

_LOGGER = logging.getLogger(__name__)


class PlantSenseConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Sign in with PlantSense, for new entries and re-authentication."""

    DOMAIN = DOMAIN
    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        super().__init__()
        self._base_url = BASE_URL

    @property
    def logger(self) -> logging.Logger:
        """Logger used by the OAuth2 flow helper."""
        return _LOGGER

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start Sign in with PlantSense against the cloud, or a dev server."""
        if self.source != SOURCE_REAUTH:
            self._base_url = (
                os.environ.get(ENV_API_URL, BASE_URL).strip().rstrip("/")
            )
        if not self._base_url.startswith(("https://", "http://")):
            return self.async_abort(reason="invalid_api_url")
        if self._base_url != BASE_URL:
            _LOGGER.warning("Using PlantSense API override %s", self._base_url)
        async_register_implementation(self.hass, self._base_url)
        return await super().async_step_user(user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Re-authenticate after the token was refused (or an old password stopped working)."""
        self._base_url = entry_data.get(CONF_URL, BASE_URL)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Explain, then send the person to Sign in with PlantSense again."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Name the entry after the account, and keep one entry per account."""
        refresh_token = data["token"]["refresh_token"]
        email = await self._account_email(data["token"]["access_token"])
        if email is None:
            await async_revoke_token(self.hass, self._base_url, refresh_token)
            return self.async_abort(reason="cannot_connect")

        unique_id = email.lower()
        if self._base_url != BASE_URL:
            unique_id = f"{unique_id}@{self._base_url}"
            data[CONF_URL] = self._base_url

        if self.source == SOURCE_REAUTH:
            entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
            if entry is None or entry.unique_id != unique_id:
                await async_revoke_token(self.hass, self._base_url, refresh_token)
                return self.async_abort(reason="wrong_account")
            # The connection being replaced, if this entry already had one.
            if "token" in entry.data:
                await async_revoke_token(
                    self.hass, self._base_url, entry.data["token"]["refresh_token"]
                )
            # Replaces an old email + password entry's data entirely.
            self.hass.config_entries.async_update_entry(entry, data=data)
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        await self.async_set_unique_id(unique_id)
        try:
            self._abort_if_unique_id_configured()
        except AbortFlow:
            await async_revoke_token(self.hass, self._base_url, refresh_token)
            raise
        return self.async_create_entry(title=email, data=data)

    async def _account_email(self, access_token: str) -> str | None:
        """The signed-in account's email, from /api/me."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                f"{self._base_url}{DATA_ENDPOINT}",
                params={"images": "0"},
                headers={"Authorization": f"Bearer {access_token}"},
            ) as resp:
                if resp.status != 200:
                    _LOGGER.error("PlantSense /api/me returned HTTP %s", resp.status)
                    return None
                payload = await resp.json()
        except aiohttp.ClientError as err:
            _LOGGER.error("Error reaching PlantSense: %s", err)
            return None
        user = payload.get("user") if isinstance(payload, dict) else None
        email = user.get("email") if isinstance(user, dict) else None
        return email if isinstance(email, str) and email else None
