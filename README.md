# PlantSense for Home Assistant

<img src="https://raw.githubusercontent.com/mattshax/plantsense-ha-integration/main/docs/plantsense-sensor.jpg" alt="The PlantSense sensor: a translucent green shell on two stainless soil probes" width="320">

[PlantSense](https://myplantsense.com) is a WiFi soil sensor for house plants
and garden beds. It measures **soil moisture, temperature, humidity and light**,
runs for weeks on a USB-C rechargeable battery, and needs no hub and no
subscription.

This integration brings every PlantSense sensor on your account into Home
Assistant, ready for dashboards and automations. Each sensor becomes a device,
named after the plant you gave it in the PlantSense app.

Don't have a sensor yet? PlantSense is designed and hand-assembled in Chicago:
[myplantsense.com/shop](https://myplantsense.com/shop).

![A PlantSense sensor's device page in Home Assistant](https://raw.githubusercontent.com/mattshax/plantsense-ha-integration/main/docs/device-page.png)

## Installation

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mattshax&repository=plantsense-ha-integration&category=integration)

### HACS (recommended)

1. Open **HACS** in Home Assistant, or use the button above.
2. Search for **PlantSense** and click **Download**.
3. Restart Home Assistant.

From Home Assistant 2026.11, HACS is built in as the **Marketplace**: go to
**Settings → Marketplace**, search for **PlantSense** and select **Install**.
If Home Assistant asks for a restart, restart it.

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

Sensors you add to your account later show up on the next refresh, no restart
needed. A sensor you remove from your account can then be deleted from its
device page.

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
| Last reading | timestamp | | Diagnostic. When the sensor last reported. |

The readings are `measurement` sensors, so Home Assistant keeps long-term
statistics for them. Each shows the sensor's most recent reading.

**Offline sensors.** A sensor normally reports at least every 5 hours. If its newest
reading is more than **6 hours** old (the same rule the PlantSense app uses to
show a sensor as *Offline*), its readings become **unavailable**, so
automations don't act on old values. **Last reading** stays available and
keeps the time of the newest reading (from the sensor itself, not from when
Home Assistant polled), so you can automate on it; it is `unknown` when the
sensor hasn't reported in 7 days.

## Example automations

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

And one when a sensor stops reporting (for example, its battery is empty):

```yaml
alias: Tomato Bed sensor is offline
triggers:
  - trigger: template
    value_template: >-
      {{ now() - (states('sensor.tomato_bed_last_reading') | as_datetime(now()))
         > timedelta(hours=8) }}
actions:
  - action: notify.mobile_app_your_phone
    data:
      title: PlantSense sensor offline
      message: The Tomato Bed sensor hasn't reported for 8 hours. Check its battery.
mode: single
```

## Dashboard card

The [PlantSense Card](https://github.com/mattshax/plantsense-ha-card) shows a
sensor the way the PlantSense app does: a status pill and dials for moisture,
light, temperature and humidity. Search HACS for **PlantSense Card**; if it
isn't listed in your HACS yet, add `https://github.com/mattshax/plantsense-ha-card`
as a custom repository of type **Dashboard**.

![PlantSense cards on a Home Assistant dashboard](https://raw.githubusercontent.com/mattshax/plantsense-ha-card/main/docs/card-light.png)

The full guide, with screenshots, is at
[myplantsense.com/docs/home-assistant](https://myplantsense.com/docs/home-assistant).

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

[![Validate](https://github.com/mattshax/plantsense-ha-integration/actions/workflows/validate.yaml/badge.svg)](https://github.com/mattshax/plantsense-ha-integration/actions/workflows/validate.yaml)

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

[MIT](https://github.com/mattshax/plantsense-ha-integration/blob/main/LICENSE)
