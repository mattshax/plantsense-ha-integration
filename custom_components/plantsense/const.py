"""Constants for the PlantSense integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "plantsense"

# PlantSense cloud API. Every normal setup uses this.
BASE_URL = "https://app.myplantsense.com"

# Development override, never shown in the UI: when this environment variable
# is set on the Home Assistant process while an entry is being set up, that
# entry talks to the given PlantSense API (e.g. a local development server)
# instead of BASE_URL. The URL is stored in the entry as CONF_URL.
ENV_API_URL = "PLANTSENSE_API_URL"
LOGIN_ENDPOINT = "/auth/login"
DATA_ENDPOINT = "/api/me"

# Sign in with PlantSense (OAuth 2.0 + PKCE, oauth.py). The authorize page is
# the PlantSense web dashboard (same host as the API); the token endpoint is the
# API. The client is public: Home Assistant can't keep a client secret.
OAUTH_CLIENT_ID = "home-assistant"
AUTHORIZE_PATH = "/oauth/authorize"
TOKEN_PATH = "/auth/oauth/token"
REVOKE_PATH = "/auth/oauth/revoke"

# The sensor is a battery device that deep-sleeps for ~90 minutes and is only
# awake for ~30 seconds each cycle. It POSTs a reading to the cloud on each
# wake, so polling the cloud more often than the wake cycle just wastes API
# calls. 20 minutes gives us fresh-ish data without hammering the backend.
UPDATE_INTERVAL = timedelta(minutes=20)

# The six metrics exposed by /api/me under stats.time.<metric>.
METRICS = ("moisture", "temp", "humidity", "lux", "battery", "wifisignal")

# A sensor whose newest reading is older than this is offline: its reading
# entities become unavailable (the "Last reading" entity stays available).
# Same rule as the PlantSense app (plantsense-mobile stats.ts
# OFFLINE_AFTER_HOURS = 6): the longest normal sleep is 5 h, plus an hour.
OFFLINE_AFTER = timedelta(hours=6)
