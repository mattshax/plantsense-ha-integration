"""Binary sensor platform for the PlantSense integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, OFFLINE_AFTER
from .coordinator import PlantSenseCoordinator
from .health import PlantHealth

# On when the app would say the plant needs water: its soil moisture dial reads Low (below the plant's own range, and
# not just watered).
NEEDS_WATER_DESCRIPTION = BinarySensorEntityDescription(
    key="needs_water",
    translation_key="needs_water",
    name="Needs water",
    icon="mdi:watering-can-outline",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Needs water sensor for each device, including ones added to the account later."""
    coordinator: PlantSenseCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_devices: set[str] = set()

    @callback
    def _add_new_devices() -> None:
        new_ids = [device_id for device_id in coordinator.data if device_id not in known_devices]
        if not new_ids:
            return
        known_devices.update(new_ids)
        async_add_entities(
            PlantSenseNeedsWaterSensor(coordinator, device_id, NEEDS_WATER_DESCRIPTION) for device_id in new_ids
        )

    _add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))


class PlantSenseNeedsWaterSensor(CoordinatorEntity[PlantSenseCoordinator], BinarySensorEntity):
    """Whether a PlantSense plant needs water."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PlantSenseCoordinator,
        device_id: str,
        description: BinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{description.key}"
        device = coordinator.data.get(device_id, {})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device.get("name") or device_id,
            manufacturer="PlantSense",
            model="PlantSense Sensor",
            configuration_url=coordinator.base_url,
        )

    @property
    def _device(self) -> dict[str, Any]:
        return self.coordinator.data.get(self._device_id, {})

    @property
    def is_on(self) -> bool | None:
        """Return True when the soil moisture reads Low for this plant."""
        health: PlantHealth | None = self._device.get("health")
        return health.needs_water if health else None

    @property
    def available(self) -> bool:
        """Available while the sensor reports a moisture reading and isn't offline (as the readings are)."""
        last_reading: datetime | None = self._device.get("last_reading")
        return (
            self.coordinator.last_update_success
            and self._device.get("readings", {}).get("moisture") is not None
            and last_reading is not None
            and dt_util.utcnow() - last_reading <= OFFLINE_AFTER
        )
