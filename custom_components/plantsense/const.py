"""Constants for the PlantSense integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "plantsense"

# PlantSense cloud API.
BASE_URL = "https://app.myplantsense.com"
LOGIN_ENDPOINT = "/auth/login"
DATA_ENDPOINT = "/api/me"

# The sensor is a battery device that deep-sleeps for ~90 minutes and is only
# awake for ~30 seconds each cycle. It POSTs a reading to the cloud on each
# wake, so polling the cloud more often than the wake cycle just wastes API
# calls. 20 minutes gives us fresh-ish data without hammering the backend.
UPDATE_INTERVAL = timedelta(minutes=20)

# The six metrics exposed by /api/me under stats.time.<metric>.
METRICS = ("moisture", "temp", "humidity", "lux", "battery", "wifisignal")
