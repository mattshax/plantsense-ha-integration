"""Sensor platform for the PlantSense integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PlantSenseCoordinator

# One description per metric returned by the coordinator. The ``key`` matches
# the reading key produced in coordinator._parse().
SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="moisture",
        name="Moisture",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
    ),
    SensorEntityDescription(
        key="temp",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="lux",
        name="Illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="battery",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="wifisignal",
        name="WiFi Signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PlantSense sensors for each device found by the coordinator."""
    coordinator: PlantSenseCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[PlantSenseSensor] = [
        PlantSenseSensor(coordinator, device_id, description)
        for device_id in coordinator.data
        for description in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)


class PlantSenseSensor(CoordinatorEntity[PlantSenseCoordinator], SensorEntity):
    """A single metric of a single PlantSense device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PlantSenseCoordinator,
        device_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
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
            configuration_url="https://app.myplantsense.com",
        )

    @property
    def _readings(self) -> dict[str, Any]:
        """Return the current reading map for this device (empty if gone)."""
        return self.coordinator.data.get(self._device_id, {}).get("readings", {})

    @property
    def native_value(self) -> float | None:
        """Return the latest value for this metric, or ``None`` if unknown."""
        return self._readings.get(self.entity_description.key)

    @property
    def available(self) -> bool:
        """Available only when the last poll succeeded and we have a value."""
        return self.coordinator.last_update_success and self.native_value is not None
