"""Sign in with PlantSense: OAuth 2.0 authorization code with PKCE.

People who sign in to PlantSense with Google or Apple have no password, so the
integration signs in through the PlantSense website instead: Home Assistant
opens the PlantSense sign-in page, the person signs in any way they like and
approves the connection, and Home Assistant gets a read-only token that it
renews by itself.

PlantSense is a public OAuth client (no client secret), so every sign-in uses
a fresh PKCE code verifier. Home Assistant's own
LocalOAuth2ImplementationWithPkce keeps one verifier per implementation and
only exists in newer Home Assistant versions, so this keeps one per flow.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from typing import Any

import aiohttp

from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import AUTHORIZE_PATH, DOMAIN, OAUTH_CLIENT_ID, REVOKE_PATH, TOKEN_PATH

_LOGGER = logging.getLogger(__name__)

# RFC 7636 section 4.1: 43 to 128 characters; 96 URL-safe characters here.
CODE_VERIFIER_BYTES = 72
# One implementation per PlantSense site, kept for the life of Home Assistant so
# a second sign-in never replaces the one holding another flow's verifier.
DATA_IMPLEMENTATIONS = f"{DOMAIN}_oauth_implementations"


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


class PlantSenseOAuth2Implementation(
    config_entry_oauth2_flow.LocalOAuth2Implementation
):
    """The PlantSense sign-in, with a PKCE code verifier per config flow."""

    def __init__(self, hass: HomeAssistant, base_url: str) -> None:
        """Point the implementation at a PlantSense site (the cloud, or a dev server)."""
        super().__init__(
            hass,
            DOMAIN,
            client_id=OAUTH_CLIENT_ID,
            client_secret="",
            authorize_url=f"{base_url}{AUTHORIZE_PATH}",
            token_url=f"{base_url}{TOKEN_PATH}",
        )
        self._verifiers: dict[str, str] = {}

    @property
    def name(self) -> str:
        """Name shown if Home Assistant ever lists more than one way to sign in."""
        return "PlantSense"

    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Authorize URL with a fresh S256 code challenge for this flow."""
        verifier = secrets.token_urlsafe(CODE_VERIFIER_BYTES)
        self._verifiers[flow_id] = verifier
        url = await super().async_generate_authorize_url(flow_id)
        return str(
            URL(url).update_query(
                {
                    "code_challenge": _code_challenge(verifier),
                    "code_challenge_method": "S256",
                }
            )
        )

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Exchange the code, sending the verifier of the flow that asked for it."""
        verifier = self._verifiers.pop(external_data["state"]["flow_id"], None)
        return await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": external_data["code"],
                "redirect_uri": external_data["state"]["redirect_uri"],
                "code_verifier": verifier or "",
            }
        )


def async_register_implementation(hass: HomeAssistant, base_url: str) -> None:
    """Make the PlantSense sign-in for base_url the one Home Assistant uses."""
    implementations: dict[str, PlantSenseOAuth2Implementation] = hass.data.setdefault(
        DATA_IMPLEMENTATIONS, {}
    )
    if base_url not in implementations:
        implementations[base_url] = PlantSenseOAuth2Implementation(hass, base_url)
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, implementations[base_url]
    )


async def async_revoke_token(hass: HomeAssistant, base_url: str, token: str) -> None:
    """Tell PlantSense to drop a connection this Home Assistant no longer uses.

    Called when an entry is removed, when a sign-in is abandoned (the account
    was already set up, or it was the wrong account) and for the old token on
    a fresh sign-in. Best effort: PlantSense also lets the account owner
    disconnect apps in its Settings.
    """
    session = async_get_clientsession(hass)
    try:
        async with session.post(
            f"{base_url}{REVOKE_PATH}",
            data={"token": token, "client_id": OAUTH_CLIENT_ID},
        ) as resp:
            if resp.status != 200:
                _LOGGER.warning("PlantSense token revocation returned HTTP %s", resp.status)
    except aiohttp.ClientError as err:
        _LOGGER.warning("Could not revoke the PlantSense token: %s", err)
