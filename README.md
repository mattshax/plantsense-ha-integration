# PlantSense for Home Assistant

A [Home Assistant](https://www.home-assistant.io/) custom integration that pulls
[PlantSense](https://myplantsense.com) soil-sensor readings from the PlantSense
**cloud API** — so Home Assistant always has data, even while the battery device
is deep-asleep.

## Why cloud polling?

PlantSense is a battery-powered soil sensor. To maximize battery life it
**deep-sleeps for ~90 minutes** and is only awake for ~30 seconds at a time. Its
local ESPHome native API is therefore unreachable most of the time. On each wake
the device POSTs its latest reading to the PlantSense cloud, so this integration
polls the cloud instead of the device. That means readings are **always
available** in Home Assistant regardless of the device's sleep state.

This is a `cloud_polling` integration: data comes from your PlantSense account
and refreshes roughly **every 20 minutes** (there is no benefit to polling faster
than the device's ~90-minute wake cycle).

## Entities

For every device on your PlantSense account, the integration creates one Home
Assistant device grouping six sensor entities:

| Entity | Device class | Unit | State class |
| --- | --- | --- | --- |
| Moisture | — | `%` | measurement |
| Temperature | temperature | `°C` | measurement |
| Humidity | humidity | `%` | measurement |
| Illuminance | illuminance | `lx` | measurement |
| Battery | battery | `%` | measurement |
| WiFi Signal | signal strength | `dBm` | measurement (diagnostic) |

Each value is the most recent point of that metric's time series (the cloud
keeps the last 7 days). If a series is empty or missing, the entity reports
`unknown`.

## Installation

### HACS (custom repository) — recommended

1. In Home Assistant, open **HACS**.
2. Click the three-dot menu (top right) → **Custom repositories**.
3. Add the repository URL `https://github.com/mattshax/plantsense-ha-integration`
   and choose the **Integration** category.
4. Find **PlantSense** in HACS and click **Download**.
5. Restart Home Assistant.

### Manual

1. Copy `custom_components/plantsense/` into your Home Assistant
   `config/custom_components/` directory (so you end up with
   `config/custom_components/plantsense/`).
2. Restart Home Assistant.

## Setup

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **PlantSense**.
3. Enter the **email** and **password** for your PlantSense account
   (the same credentials you use at <https://app.myplantsense.com>).

The integration validates your credentials on submit. If the login token later
expires, Home Assistant will prompt you to re-enter your password.

## How authentication works

- On setup the integration logs in via `POST /auth/login` and stores your email
  and password in the (encrypted) config entry.
- It polls `GET /api/me` with a `Bearer` JWT. The token is HS256 and expires
  after 7 days.
- If a poll returns `401`, the integration transparently re-logs-in with your
  stored credentials and retries once. If authentication then still fails, Home
  Assistant starts a re-auth flow so you can update your password.

## Companion

Pairs with the **PlantSense Lovelace card** for a richer dashboard view of your
plants.

## Support

Issues and questions:
<https://github.com/mattshax/plantsense-ha-integration/issues>
