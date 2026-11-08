"""Plant health, the way the PlantSense app judges it.

A port of the app's status logic (plantsense-mobile src/screens/plant-detail/stats.ts: deriveLightValue,
isAwaitingDaylight, isRecentlyWatered, isSetupAirReading, deriveStats, getStatusLabel, computeHealth) and its
plant list's "needs water" (src/screens/plants/plantRow.ts), so Home Assistant shows the same labels as the app.
Pure Python with no Home Assistant imports, so it can be checked against the app's own code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any

# Health states, worst last. Also the Health entity's enum options.
HEALTHY = "healthy"
FAIR = "fair"
WARNING = "warning"
NEEDS_ATTENTION = "needs_attention"
HEALTH_STATES = (HEALTHY, FAIR, WARNING, NEEDS_ATTENTION)

# The readings that make up plant health, and how a reason names them ("Light is low").
READING_NAMES = {
    "moisture": "Soil moisture",
    "temp": "Temperature",
    "humidity": "Humidity",
    "lux": "Light",
}
ALL_READINGS = ("moisture", "temp", "humidity", "lux", "battery", "wifisignal")

# Light is the peak of the last day: a reading more than this many times the runner-up is a spike.
LIGHT_WINDOW = timedelta(hours=24)
LIGHT_SPIKE_RATIO = 3
LIGHT_FLOOR_LUX = 1

# A new sensor's light waits for a daytime reading (local time) during its first day.
DAYLIGHT_WAIT = timedelta(hours=24)
DAYTIME_START_HOUR = 8
DAYTIME_END_HOUR = 18

# A watering marked by hand counts for 6 h; one the server inferred from a moisture rise, for 12 h.
MANUAL_WATERED = timedelta(hours=6)
INFERRED_WATERED = timedelta(hours=12)

# The setup reading is taken with the probe in the air; within this window of adding the plant, a reading at or
# below NOT_IN_SOIL_MAX_PCT means "not in the soil yet".
SETUP_READING_WINDOW = timedelta(minutes=15)
NOT_IN_SOIL_MAX_PCT = 2

# The app's gauge ranges for battery (%) and Wi-Fi (dBm).
BATTERY_RANGE = (0.0, 100.0)
WIFI_RANGE = (-80.0, -30.0)

# Care-parameter keys per reading (the plant DB's names on the device row).
CARE_KEYS = {
    "moisture": ("min_soil_moist", "max_soil_moist"),
    "temp": ("min_temp", "max_temp"),
    "humidity": ("min_env_humid", "max_env_humid"),
    "lux": ("min_light_lux", "max_light_lux"),
}

_SEVERITY = {HEALTHY: 0, FAIR: 1, WARNING: 2, NEEDS_ATTENTION: 3}


@dataclass
class Reading:
    """One dial: its value, its range and where the value sits in it."""

    key: str
    value: float | None
    low: float
    high: float
    fill: float = 0.0
    watered: bool = False
    not_in_soil: bool = False
    awaiting_daylight: bool = False


@dataclass
class PlantHealth:
    """Everything Home Assistant shows beyond the raw readings."""

    health: str | None
    reasons: list[str]
    statuses: dict[str, str]
    needs_water: bool
    daily_light: float | None
    care_range: dict[str, tuple[float, float]] = field(default_factory=dict)


def parse_time(value: Any) -> datetime | None:
    """An API timestamp ("2026-11-08T06:00:00.000Z") as an aware datetime, or None."""
    if not isinstance(value, str) or not value:
        return None
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _care(value: Any) -> float:
    """A care threshold; missing ones are 0, as in the app (stats.ts num())."""
    number = _number(value)
    return 0.0 if number is None or number != number else number


def _series(time_series: dict[str, Any], key: str) -> list[tuple[datetime, float]]:
    points: list[tuple[datetime, float]] = []
    for point in time_series.get(key) or []:
        if not isinstance(point, dict):
            continue
        when = parse_time(point.get("x"))
        value = _number(point.get("y"))
        if when is not None and value is not None:
            points.append((when, value))
    return points


def daily_light(latest: float | None, lux: list[tuple[datetime, float]], now: datetime) -> float | None:
    """The last 24 h's peak lux, the runner-up when the top reading is a spike (stats.ts deriveLightValue)."""
    since = now - LIGHT_WINDOW
    recent = sorted((y for when, y in lux if when > since and y > LIGHT_FLOOR_LUX), reverse=True)
    if len(recent) >= 2:
        return recent[1] if recent[0] > recent[1] * LIGHT_SPIKE_RATIO else recent[0]
    if len(recent) == 1:
        return recent[0]
    return latest


def awaiting_daylight(
    lux: list[tuple[datetime, float]], created: datetime | None, now: datetime, local: tzinfo
) -> bool:
    """A sensor in its first day with no daytime reading yet (stats.ts isAwaitingDaylight)."""
    if created is None or now - created > DAYLIGHT_WAIT:
        return False
    return not any(DAYTIME_START_HOUR <= when.astimezone(local).hour < DAYTIME_END_HOUR for when, _ in lux)


def recently_watered(watered_at: datetime | None, last_watered: datetime | None, now: datetime) -> bool:
    """Watered by hand in the last 6 h, or by the server's reckoning in the last 12 h (stats.ts isRecentlyWatered)."""
    manual = watered_at is not None and now - watered_at < MANUAL_WATERED
    inferred = last_watered is not None and now - last_watered < INFERRED_WATERED
    return manual or inferred


def setup_air_reading(
    moisture: float | None, series: list[tuple[datetime, float]], created: datetime | None, now: datetime
) -> bool:
    """The setup reading, probe still in the air (stats.ts isSetupAirReading)."""
    if moisture is None or moisture > NOT_IN_SOIL_MAX_PCT or created is None:
        return False
    reading_at = series[-1][0] if series else now
    return created - SETUP_READING_WINDOW < reading_at and reading_at - created < SETUP_READING_WINDOW


def status_label(reading: Reading) -> str:
    """The label under a dial (stats.ts getStatusLabel)."""
    fill = reading.fill
    if reading.awaiting_daylight:
        return "Waiting for daylight"
    if reading.value is None:
        return "No Data"
    if reading.key == "battery":
        if fill < 10:
            return "Critical"
        if fill < 20:
            return "Low"
        if fill < 50:
            return "Fair"
        return "Good"
    if reading.key == "wifisignal":
        if fill < 0:
            return "No Signal"
        if fill < 25:
            return "Weak"
        if fill < 50:
            return "Fair"
        if fill < 75:
            return "Good"
        return "Strong"
    if reading.key == "moisture":
        if reading.not_in_soil:
            return "Not in soil"
        if reading.watered and fill < 20:
            return "Watered"
        if fill < 0:
            return "Low"
        if fill > 150:
            return "Saturated"
        if fill < 20 and reading.low != 0:
            return "Low"
        if fill < 35:
            return "Fair"
        return "Good"
    if fill < 0:
        return "Low"
    if fill > 120:
        return "High"
    if fill < 20 and reading.low != 0:
        return "Low"
    if fill > 105 and reading.high != 0:
        return "High"
    # A 0 minimum means "no minimum": the bottom of the range is Good, not Fair.
    if fill < 35 and reading.low != 0:
        return "Fair"
    return "Good"


def _severity(reading: Reading, watered: bool) -> str | None:
    """How much one reading weighs on plant health (stats.ts readingSeverity); None = not a health signal."""
    fill = reading.fill
    if reading.key == "moisture":
        if reading.not_in_soil:
            return None
        if watered:
            return HEALTHY
        if fill < 0 or fill > 200:
            return NEEDS_ATTENTION
    elif fill < 0 or fill > 120:
        return NEEDS_ATTENTION
    label = status_label(reading)
    if label == "Fair":
        return FAIR
    if label in ("Low", "High", "Saturated"):
        return WARNING
    return HEALTHY


def _readings(device: dict[str, Any], now: datetime, local: tzinfo) -> tuple[list[Reading], bool]:
    stats = device.get("stats") if isinstance(device.get("stats"), dict) else {}
    time_series = stats.get("time") if isinstance(stats.get("time"), dict) else {}
    parameter = device.get("parameter") if isinstance(device.get("parameter"), dict) else {}
    created = parse_time(device.get("createdAt"))
    lux = _series(time_series, "lux")
    moisture_series = _series(time_series, "moisture")

    watered = recently_watered(parse_time(stats.get("_wateredAt")), parse_time(device.get("lastWatered")), now)
    waiting = awaiting_daylight(lux, created, now, local)
    moisture = _number(stats.get("moisture"))
    temp_c = _number(stats.get("temp"))

    def care(key: str) -> tuple[float, float]:
        low_key, high_key = CARE_KEYS[key]
        return _care(parameter.get(low_key)), _care(parameter.get(high_key))

    def fahrenheit(celsius: float) -> float:
        return celsius * 9 / 5 + 32

    # The app judges temperature in °F, so a missing minimum (0 °C) is 32 °F, not "no minimum".
    temp_low, temp_high = care("temp")
    readings = [
        Reading("moisture", moisture, *care("moisture"), watered=watered,
                not_in_soil=setup_air_reading(moisture, moisture_series, created, now)),
        Reading("temp", None if temp_c is None else fahrenheit(temp_c), fahrenheit(temp_low), fahrenheit(temp_high)),
        Reading("humidity", _number(stats.get("humidity")), *care("humidity")),
        Reading("lux", None if waiting else daily_light(_number(stats.get("lux")), lux, now), *care("lux"),
                awaiting_daylight=waiting),
        Reading("battery", _number(stats.get("battery")), *BATTERY_RANGE),
        Reading("wifisignal", _number(stats.get("wifisignal")), *WIFI_RANGE),
    ]
    for reading in readings:
        span = reading.high - reading.low
        if reading.value is not None and span != 0:
            reading.fill = (reading.value - reading.low) / span * 100
    return readings, watered


def plant_health(device: dict[str, Any], now: datetime, local: tzinfo) -> PlantHealth:
    """Health, per-reading labels, needs-water and daily light for one /api/me device."""
    readings, watered = _readings(device, now, local)
    by_key = {reading.key: reading for reading in readings}
    statuses = {reading.key: status_label(reading) for reading in readings}

    judged = [
        (reading, severity)
        for reading in readings
        if reading.key in READING_NAMES and reading.value is not None
        for severity in (_severity(reading, watered),)
        if severity is not None
    ]
    has_data = any(reading.key in READING_NAMES and reading.value is not None for reading in readings)
    worst = max((severity for _, severity in judged), key=_SEVERITY.__getitem__, default=HEALTHY)
    reasons = [
        f"{READING_NAMES[reading.key]} is {status_label(reading).lower()}"
        for reading, severity in judged
        if worst != HEALTHY and severity == worst
    ]

    parameter = device.get("parameter") if isinstance(device.get("parameter"), dict) else {}
    care_range = {
        key: (_care(parameter.get(low_key)), _care(parameter.get(high_key)))
        for key, (low_key, high_key) in CARE_KEYS.items()
        if _number(parameter.get(low_key)) is not None or _number(parameter.get(high_key)) is not None
    }

    return PlantHealth(
        health=worst if has_data else None,
        reasons=reasons,
        statuses=statuses,
        needs_water=by_key["moisture"].value is not None and statuses["moisture"] == "Low",
        daily_light=by_key["lux"].value,
        care_range=care_range,
    )
