# PlantSense for Home Assistant

<img src="https://raw.githubusercontent.com/scietas/plantsense-ha-integration/main/docs/plantsense-sensor.jpg" alt="The PlantSense sensor: a translucent green shell on two stainless soil probes" width="320">

[PlantSense](https://myplantsense.com) is a WiFi soil sensor for house plants
and garden beds. It measures **soil moisture, temperature, humidity and light**,
runs for weeks on a USB-C rechargeable battery, and needs no hub and no
subscription.

This integration brings every PlantSense sensor on your account into Home
Assistant, ready for dashboards and automations. Each sensor becomes a device,
named after the plant you gave it in the PlantSense app.

Don't have a sensor yet? PlantSense is designed and hand-assembled in Chicago:
[myplantsense.com/shop](https://myplantsense.com/shop).

<img src="https://raw.githubusercontent.com/scietas/plantsense-ha-integration/main/docs/device-page.png" alt="A PlantSense sensor's device page in Home Assistant" width="720">

## Installation

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=scietas&repository=plantsense-ha-integration&category=integration)

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
2. The PlantSense sign-in page opens. Sign in the way you do in the app:
   Google, Apple or email.
3. Check that the page names your Home Assistant, then choose **Connect**.

Home Assistant gets read-only access to your account and never sees your
password. To disconnect it, go to **Settings → Connected apps** at
<https://app.myplantsense.com>.

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
| Illuminance | illuminance | `lx` | Light level at the last reading (0 at night). |
| Daily light | illuminance | `lx` | The brightest light of the last 24 hours, as the app's Daily Light dial shows it. |
| Battery | battery | `%` | |
| WiFi Signal | signal strength | `dBm` | Diagnostic. |
| Health | enum | | `healthy`, `fair`, `warning` or `needs_attention`: the plant's health as the app shows it. |
| Needs water | binary sensor | | On when the app would say the plant needs water. |
| Last watered | timestamp | | When the plant was last watered, marked in the app or detected from a rise in soil moisture. |
| Last reading | timestamp | | Diagnostic. When the sensor last reported. |

The readings are `measurement` sensors, so Home Assistant keeps long-term
statistics for them. Each shows the sensor's most recent reading.

**Health and Needs water** judge the readings against the plant's own care
ranges (from the plant you picked in the app, editable in its Plant Settings),
by the same rules as the app:

- A reading below its range, or well above it, is **Needs attention**.
- One in the bottom fifth of its range, or just above it, is **Warning**.
- One between a fifth and about a third of the way up is **Fair**.
- Soil moisture has more room above its range before it counts.

A minimum of 0 means no minimum: light at the bottom of its range is fine.
Soil moisture doesn't count against the plant for a few hours after a
watering, and light waits for the first daytime reading on a new sensor.

**Needs water** is on when soil moisture is below the plant's range and it
hasn't just been watered. The Health entity's attributes carry:

- `reasons`: for example `Soil moisture is low`.
- Each dial's label: `moisture_status`, `light_status` and so on.
- The care ranges: `moisture_min`, `moisture_max`, `temperature_min` and
  `temperature_max` (in °C), `humidity_min`, `humidity_max`, `light_min`,
  `light_max`.

**Offline sensors.** A sensor normally reports at least every 5 hours. If its newest
reading is more than **6 hours** old (the same rule the PlantSense app uses to
show a sensor as *Offline*), its readings become **unavailable**, so
automations don't act on old values. **Last reading** stays available and
keeps the time of the newest reading (from the sensor itself, not from when
Home Assistant polled), so you can automate on it; it is `unknown` when the
sensor hasn't reported in 7 days.

## Example automations

Get a phone notification when a plant needs water, using the plant's own range:

```yaml
alias: Fiddle Leaf Fig needs water
triggers:
  - trigger: state
    entity_id: binary_sensor.fiddle_leaf_fig_needs_water
    to: "on"
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

The [PlantSense Card](https://github.com/scietas/plantsense-ha-card) shows a
sensor the way the PlantSense app does: the plant's health and why, and dials
for moisture, daily light, temperature and humidity. Search HACS for **PlantSense Card** and click
**Download**.

<img src="https://raw.githubusercontent.com/scietas/plantsense-ha-card/main/docs/card-dark.png" alt="PlantSense cards on a Home Assistant dashboard" width="720">

The full guide, with screenshots, is at
[myplantsense.com/docs/home-assistant](https://myplantsense.com/docs/home-assistant).

## How sign-in works

- **Sign in with PlantSense** is standard OAuth 2.0 (authorization code with
  PKCE), through Home Assistant's own OAuth support. The redirect goes through
  <https://my.home-assistant.io>, or straight back to your Home Assistant if
  the My Home Assistant integration isn't loaded.
- Home Assistant stores an access token, which lasts an hour, and a refresh
  token, which it uses to get the next one by itself. The refresh token changes
  every time it's used. Both are in the config entry, in Home Assistant's
  `.storage` folder. No password is stored.
- The tokens can only read: the integration fetches your sensors with
  `GET /api/me` and nothing else.
- If PlantSense stops accepting them (you disconnected Home Assistant, or
  removed the account), Home Assistant asks you to sign in again under
  **Settings → Devices & services**. Deleting the integration disconnects it
  from your PlantSense account too.
- Set up before 1.4.0 with an email and password? That entry keeps working.
  The next time Home Assistant asks you to sign in again, it moves to Sign in
  with PlantSense and the stored password is removed.

## Development

[![Validate](https://github.com/scietas/plantsense-ha-integration/actions/workflows/validate.yaml/badge.svg)](https://github.com/scietas/plantsense-ha-integration/actions/workflows/validate.yaml)

To run the integration against a PlantSense development server instead of the
production API, set the `PLANTSENSE_API_URL` environment variable on the Home
Assistant process (for example `-e PLANTSENSE_API_URL=http://192.168.1.10:5173`
with Docker) **before** adding the integration. That address has to serve the
sign-in page (`/oauth/authorize`) as well as the API, as the web dashboard's
development server does, and be reachable from both Home Assistant and your
browser. The URL is saved with that entry; entries added without the variable
always use `https://app.myplantsense.com`. It is not shown in the UI.

## Support

Questions and bug reports:
<https://github.com/scietas/plantsense-ha-integration/issues>

## License

[MIT](https://github.com/scietas/plantsense-ha-integration/blob/main/LICENSE)

PlantSense is made by [Scietas](https://scietas.com).
