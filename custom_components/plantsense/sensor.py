"""Sensor platform for the PlantSense integration."""

from __future__ import annotations

from datetime import datetime
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, OFFLINE_AFTER
from .coordinator import PlantSenseCoordinator
from .health import HEALTH_STATES, PlantHealth

# One description per metric returned by the coordinator. The ``key`` matches
# the reading key produced in coordinator._parse(). Display precision mirrors
# the PlantSense app (kFormatter: one decimal; lux and dBm as whole numbers).
SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="moisture",
        name="Moisture",
        device_class=SensorDeviceClass.MOISTURE,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:water-percent",
    ),
    SensorEntityDescription(
        key="temp",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="lux",
        name="Illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="battery",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="wifisignal",
        name="WiFi Signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

# When the sensor last reported. Enabled by default and available while the
# account can be polled, so an offline sensor can be automated on.
LAST_READING_DESCRIPTION = SensorEntityDescription(
    key="last_reading",
    translation_key="last_reading",
    name="Last reading",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_category=EntityCategory.DIAGNOSTIC,
)

# The plant as the PlantSense app sees it: Healthy, Fair, Warning or Needs attention, judged against the plant's own
# care ranges (health.py). Its attributes carry the reasons, each dial's label and the care ranges.
HEALTH_DESCRIPTION = SensorEntityDescription(
    key="health",
    translation_key="health",
    name="Health",
    device_class=SensorDeviceClass.ENUM,
    options=list(HEALTH_STATES),
    icon="mdi:sprout",
)

# Light is 0 at night, so the app shows the last 24 hours' peak; this is that value.
DAILY_LIGHT_DESCRIPTION = SensorEntityDescription(
    key="daily_light",
    translation_key="daily_light",
    name="Daily light",
    device_class=SensorDeviceClass.ILLUMINANCE,
    native_unit_of_measurement=LIGHT_LUX,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=0,
)

# When the plant was last watered: marked in the app, or detected from a rise in soil moisture.
LAST_WATERED_DESCRIPTION = SensorEntityDescription(
    key="last_watered",
    translation_key="last_watered",
    name="Last watered",
    device_class=SensorDeviceClass.TIMESTAMP,
    icon="mdi:watering-can",
)

# Care-range attributes on the Health entity: (attribute prefix, care key). Temperature is in °C.
CARE_RANGE_ATTRIBUTES = (
    ("moisture", "moisture"),
    ("temperature", "temp"),
    ("humidity", "humidity"),
    ("light", "lux"),
)

# Dial-label attributes on the Health entity: (attribute, reading key). The labels are the app's, in English.
STATUS_ATTRIBUTES = (
    ("moisture_status", "moisture"),
    ("temperature_status", "temp"),
    ("humidity_status", "humidity"),
    ("light_status", "lux"),
    ("battery_status", "battery"),
    ("wifi_status", "wifisignal"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PlantSense sensors for each device found by the coordinator.

    Devices added to the account later get their entities on the next poll,
    without a reload.
    """
    coordinator: PlantSenseCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_devices: set[str] = set()

    @callback
    def _add_new_devices() -> None:
        new_ids = [device_id for device_id in coordinator.data if device_id not in known_devices]
        if not new_ids:
            return
        known_devices.update(new_ids)
        entities: list[PlantSenseSensor] = [
            PlantSenseSensor(coordinator, device_id, description)
            for device_id in new_ids
            for description in SENSOR_DESCRIPTIONS
        ]
        # Last reading stays the first timestamp entity on the device: the PlantSense card before 1.3.0 finds it
        # as the device's first timestamp sensor.
        entities += [
            PlantSenseLastReadingSensor(coordinator, device_id, LAST_READING_DESCRIPTION)
            for device_id in new_ids
        ]
        for device_id in new_ids:
            entities += [
                PlantSenseHealthSensor(coordinator, device_id, HEALTH_DESCRIPTION),
                PlantSenseDailyLightSensor(coordinator, device_id, DAILY_LIGHT_DESCRIPTION),
                PlantSenseLastWateredSensor(coordinator, device_id, LAST_WATERED_DESCRIPTION),
            ]
        async_add_entities(entities)

    _add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))


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
            configuration_url=coordinator.base_url,
        )

    @property
    def _device(self) -> dict[str, Any]:
        """Return this device's parsed data (empty if it left the account)."""
        return self.coordinator.data.get(self._device_id, {})

    @property
    def _readings(self) -> dict[str, Any]:
        """Return the current reading map for this device (empty if gone)."""
        return self._device.get("readings", {})

    @property
    def native_value(self) -> float | None:
        """Return the latest value for this metric, or ``None`` if unknown."""
        return self._readings.get(self.entity_description.key)

    @property
    def available(self) -> bool:
        """Available when the last poll succeeded, there is a value, and the
        sensor's newest reading is no older than OFFLINE_AFTER."""
        last_reading: datetime | None = self._device.get("last_reading")
        return (
            self.coordinator.last_update_success
            and self.native_value is not None
            and last_reading is not None
            and dt_util.utcnow() - last_reading <= OFFLINE_AFTER
        )


class PlantSenseLastReadingSensor(PlantSenseSensor):
    """When a PlantSense device last reported (its own reading time)."""

    @property
    def native_value(self) -> datetime | None:
        """Return the newest reading time, or ``None`` if none in 7 days."""
        return self._device.get("last_reading")

    @property
    def available(self) -> bool:
        """Available while the account polls and the device is on it."""
        return self.coordinator.last_update_success and bool(self._device)


class PlantSenseHealthSensor(PlantSenseSensor):
    """The plant's health, as the PlantSense app shows it."""

    @property
    def _health(self) -> PlantHealth | None:
        return self._device.get("health")

    @property
    def native_value(self) -> str | None:
        """Return healthy / fair / warning / needs_attention, or ``None`` before any reading."""
        health = self._health
        return health.health if health else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The reasons behind the state, each dial's label and the plant's care ranges."""
        health = self._health
        if health is None:
            return {}
        attributes: dict[str, Any] = {"reasons": health.reasons}
        for attribute, key in STATUS_ATTRIBUTES:
            attributes[attribute] = health.statuses.get(key)
        for prefix, key in CARE_RANGE_ATTRIBUTES:
            if key in health.care_range:
                attributes[f"{prefix}_min"], attributes[f"{prefix}_max"] = health.care_range[key]
        return attributes


class PlantSenseDailyLightSensor(PlantSenseSensor):
    """The last 24 hours' peak light, as the app's Daily Light dial shows it."""

    @property
    def native_value(self) -> float | None:
        """Return the peak lux, or ``None`` while a new sensor waits for daylight."""
        health: PlantHealth | None = self._device.get("health")
        return health.daily_light if health else None


class PlantSenseLastWateredSensor(PlantSenseLastReadingSensor):
    """When the plant was last watered."""

    @property
    def native_value(self) -> datetime | None:
        """Return the newest watering, marked or detected, or ``None`` if none."""
        return self._device.get("last_watered")
