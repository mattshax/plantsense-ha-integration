"""The PlantSense integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.device_registry import DeviceEntry

from .const import BASE_URL, DOMAIN
from .coordinator import PlantSenseCoordinator
from .oauth import async_register_implementation, async_revoke_token

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PlantSense from a config entry."""
    oauth_session = None
    if "token" in entry.data:
        # Sign in with PlantSense. Entries from before 1.4.0 hold an email and
        # password instead, and the coordinator logs in with those.
        async_register_implementation(hass, entry.data.get(CONF_URL, BASE_URL))
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )
        oauth_session = config_entry_oauth2_flow.OAuth2Session(
            hass, entry, implementation
        )
    coordinator = PlantSenseCoordinator(hass, entry, oauth_session)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Disconnect from PlantSense when the integration entry is deleted."""
    if "token" in entry.data:
        await async_revoke_token(
            hass, entry.data.get(CONF_URL, BASE_URL), entry.data["token"]["refresh_token"]
        )


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Allow deleting a device from the UI once it is no longer on the account."""
    coordinator: PlantSenseCoordinator = hass.data[DOMAIN][entry.entry_id]
    return not any(
        domain == DOMAIN and device_id in coordinator.data
        for domain, device_id in device_entry.identifiers
    )
