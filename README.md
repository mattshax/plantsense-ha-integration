# PlantSense for Home Assistant

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mattshax&repository=plantsense-ha-integration&category=integration)
[![Validate](https://github.com/mattshax/plantsense-ha-integration/actions/workflows/validate.yaml/badge.svg)](https://github.com/mattshax/plantsense-ha-integration/actions/workflows/validate.yaml)

A [Home Assistant](https://www.home-assistant.io/) integration that brings your
[PlantSense](https://myplantsense.com) soil sensors into Home Assistant: soil
moisture, temperature, humidity, light and battery for every sensor on your
PlantSense account, ready for dashboards and automations.

![A PlantSense sensor's device page in Home Assistant](https://raw.githubusercontent.com/mattshax/plantsense-ha-integration/main/docs/device-page.png)

## Why cloud polling?

PlantSense is a battery-powered soil sensor. To last on a small battery it
**deep-sleeps between readings, from 90 minutes up to 5 hours**, and is awake
for only ~30 seconds at a time, so its local ESPHome API is unreachable most of
the time. On each wake the sensor sends its reading to your PlantSense account.
This integration reads them from there, so Home Assistant always has the latest
values, whether the sensor is asleep or not, and whether or not it is on the
same network as Home Assistant.

This is a `cloud_polling` integration: it signs in with your PlantSense account
and refreshes **every 20 minutes** (polling faster gains nothing, the sensors
report far less often).

## Installation

### HACS (recommended)

1. Open **HACS** in Home Assistant, or use the **Open in HACS** button above.
2. Search for **PlantSense** and click **Download**.
   - Not listed yet? In HACS, open the menu (top right) → **Custom
     repositories**, add `https://github.com/mattshax/plantsense-ha-integration`
     with type **Integration**, then search again.
3. Restart Home Assistant.

### Manual

1. Copy `custom_components/plantsense/` from this repository into your Home
   Assistant `config/custom_components/` directory, so you end up with
   `config/custom_components/plantsense/`.
2. Restart Home Assistant.

## Configuration

[![Open your Home Assistant instance and start setting up PlantSense.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=plantsense)

1. Go to **Settings → Devices & services → Add integration** and search for
   **PlantSense** (or use the button above).
2. Enter the **email** and **password** of your PlantSense account, the same
   ones you use in the PlantSense app and at <https://app.myplantsense.com>.

If you sign in to PlantSense with Apple or Google, your account has no
password yet: tap **Forgot your password?** on the PlantSense app's sign-in screen to set
one, then use it here.

Each PlantSense sensor appears as its own device, named after the plant you
gave it in the app. Sensors you add to your account later show up on the next
refresh, no restart needed. A sensor you remove from your account can then be
deleted from its device page.

## Entities

Every sensor gets these entities:

| Entity | Device class | Unit | Notes |
| --- | --- | --- | --- |
| Moisture | moisture | `%` | Soil moisture. |
| Temperature | temperature | `°C` (shown in your unit system) | Air temperature next to the plant. |
| Humidity | humidity | `%` | Relative humidity of the air. |
| Illuminance | illuminance | `lx` | Light level at the last reading. |
| Battery | battery | `%` | |
| WiFi Signal | signal strength | `dBm` | Diagnostic. |

All are `measurement` sensors, so Home Assistant keeps long-term statistics for
them. Each value is the sensor's most recent reading from the last 7 days; if
there is none, the entity is unavailable.

## Example automation

Get a phone notification when a plant needs water:

```yaml
alias: Fiddle Leaf Fig needs water
triggers:
  - trigger: numeric_state
    entity_id: sensor.fiddle_leaf_fig_moisture
    below: 25
conditions:
  - condition: time
    after: "08:00:00"
    before: "21:00:00"
actions:
  - action: notify.mobile_app_your_phone
    data:
      title: Time to water the Fiddle Leaf Fig
      message: >-
        Soil moisture is down to
        {{ states('sensor.fiddle_leaf_fig_moisture') | round(0) }}%.
mode: single
```

## Dashboard card

The [PlantSense Card](https://github.com/mattshax/plantsense-ha-card) shows a
sensor the way the PlantSense app does: a status pill and dials for moisture,
light, temperature and humidity.

## How sign-in works

- The integration signs in with `POST /auth/login` and reads your sensors with
  `GET /api/me`, using the token it gets back.
- Your email and password are saved in the config entry, like the credentials
  of other cloud integrations (in Home Assistant's `.storage` folder), so the
  integration can sign in again on its own.
- If the token is rejected, it signs in again and retries once. If the
  password itself is rejected (for example after you changed it), Home
  Assistant asks you to enter the new one under **Settings → Devices &
  services**.

## Development

To run the integration against a PlantSense development server instead of the
production API, set the `PLANTSENSE_API_URL` environment variable on the Home
Assistant process (for example `-e PLANTSENSE_API_URL=http://192.168.1.10:9005`
with Docker) **before** adding the integration. The URL is saved with that
entry; entries added without the variable always use
`https://app.myplantsense.com`. It is not shown in the UI.

## Support

Questions and bug reports:
<https://github.com/mattshax/plantsense-ha-integration/issues>

## License

[MIT](LICENSE)
