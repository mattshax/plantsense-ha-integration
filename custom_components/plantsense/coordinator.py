"""DataUpdateCoordinator for the PlantSense cloud API."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    BASE_URL,
    DATA_ENDPOINT,
    DOMAIN,
    LOGIN_ENDPOINT,
    METRICS,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class _AuthExpired(Exception):
    """Raised internally when /api/me returns 401 (token expired)."""


def _last_value(series: Any) -> float | None:
    """Return the ``y`` of the last point of a time series, or ``None``.

    The series is time-ascending, so the current reading is the last element.
    Any missing/empty/malformed series yields ``None`` (entity value unknown).
    """
    if not isinstance(series, list) or not series:
        return None
    last = series[-1]
    if not isinstance(last, dict):
        return None
    value = last.get("y")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _last_time(series: Any) -> datetime | None:
    """Return the time (``x``) of the last point of a time series, or ``None``."""
    if not isinstance(series, list) or not series:
        return None
    last = series[-1]
    if not isinstance(last, dict) or not isinstance(last.get("x"), str):
        return None
    when = dt_util.parse_datetime(last["x"])
    if when is not None and when.tzinfo is None:
        when = when.replace(tzinfo=dt_util.UTC)  # the API sends UTC ("...Z")
    return when


class PlantSenseCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Poll the PlantSense cloud API and expose the latest reading per device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator from a config entry."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.base_url: str = entry.data.get(CONF_URL, BASE_URL)
        self._email: str = entry.data[CONF_EMAIL]
        self._password: str = entry.data[CONF_PASSWORD]
        self._session = async_get_clientsession(hass)
        self._token: str | None = None

    async def _login(self) -> None:
        """Authenticate with stored credentials and cache a fresh JWT.

        Raises:
            ConfigEntryAuthFailed: credentials were rejected.
            UpdateFailed: the backend was unreachable or returned a hard error.
        """
        try:
            async with self._session.post(
                f"{self.base_url}{LOGIN_ENDPOINT}",
                json={"email": self._email, "pass": self._password},
            ) as resp:
                if resp.status in (400, 401, 403):
                    raise ConfigEntryAuthFailed("PlantSense rejected the credentials")
                if resp.status != 200:
                    raise UpdateFailed(f"PlantSense login returned HTTP {resp.status}")
                payload = await resp.json()
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error connecting to PlantSense: {err}") from err

        if payload.get("message") != "success" or not payload.get("token"):
            raise ConfigEntryAuthFailed("PlantSense rejected the credentials")

        self._token = payload["token"]

    async def _fetch_me(self) -> dict[str, Any]:
        """Fetch /api/me with the cached token.

        Raises:
            _AuthExpired: the token expired (HTTP 401).
            UpdateFailed: the backend was unreachable or returned a hard error.
        """
        try:
            async with self._session.get(
                f"{self.base_url}{DATA_ENDPOINT}",
                headers={"Authorization": f"Bearer {self._token}"},
            ) as resp:
                if resp.status == 401:
                    raise _AuthExpired
                if resp.status != 200:
                    raise UpdateFailed(f"PlantSense API returned HTTP {resp.status}")
                return await resp.json()
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error fetching PlantSense data: {err}") from err

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Log in if needed, fetch data, and re-login+retry once on 401."""
        if self._token is None:
            await self._login()

        try:
            payload = await self._fetch_me()
        except _AuthExpired:
            # Token expired mid-session. Re-login once with stored creds and
            # retry. A second 401 (or rejected creds) is a hard auth failure.
            await self._login()
            try:
                payload = await self._fetch_me()
            except _AuthExpired as err:
                raise ConfigEntryAuthFailed(
                    "PlantSense authentication failed after re-login"
                ) from err

        return self._parse(payload)

    @staticmethod
    def _parse(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Convert an /api/me response into ``{device_id: {name, location, readings, last_reading}}``.

        ``last_reading`` is the newest point time across all metrics (the
        sensor's own reading time, not the poll time), or ``None`` when there
        is no reading in the 7-day window.
        """
        result: dict[str, dict[str, Any]] = {}
        for device in payload.get("devices") or []:
            if not isinstance(device, dict):
                continue
            device_id = device.get("device")
            if not device_id:
                continue
            time_series = ((device.get("stats") or {}).get("time")) or {}
            readings: dict[str, float | None] = {
                metric: _last_value(time_series.get(metric)) for metric in METRICS
            }
            times = [
                t for t in (_last_time(time_series.get(m)) for m in METRICS) if t
            ]
            result[device_id] = {
                "name": device.get("name") or device_id,
                "location": device.get("location"),
                "readings": readings,
                "last_reading": max(times) if times else None,
            }
        return result
