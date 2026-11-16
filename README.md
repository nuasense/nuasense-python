# nuasense

NuaSense for Python: what your sensors mean for house, garden and farm. Frost tonight, how much to water today, the next calm and dry spray window, and a plausibility check of your sensor. Send readings from anything you build (a Raspberry Pi with a BME280, soil moisture probes, a water level sensor, a beehive scale, a cold room), and read East African farm and market data.

```
pip install nuasense
```

Standard library only, Python 3.9 or newer, so it runs on any Raspberry Pi.

## Send readings from a sensor you built

In the console at [platform.nuasense.com](https://platform.nuasense.com): **External stations → Add a station → I built it myself**, and copy the token after `/station/` on the last screen. Sending needs no API key. The first three stations on an account are free.

```python
import nuasense

nuasense.send(
    "kw7n-4hpd-x2vt",        # your station token
    "garden-pi",             # any name for this device; binds the token to it
    temperature=21.4,        # °C
    humidity=63,             # %
    pressure=1013.2,         # hPa at the station
    rain_mm=0.2,             # mm since the previous reading
    soil_moisture=34,        # % vol
    soil_moisture_2=41.5,    # a second probe: _2 … _8
    soil_temperature=18.2,   # °C
)
```

Send what your sensors measure, every few minutes. The names and units are NuaSense's own, the same as for the [Arduino, ESPHome, MicroPython and Tasmota code](https://github.com/nuasense/station-schema):

| group | fields (unit) |
|---|---|
| weather | `temperature` (°C) · `humidity` (%) · `pressure` (hPa) · `light` (lux) · `wind_speed`, `wind_gusts` (m/s) · `wind_direction` (°) · `rain_mm` (mm since the previous reading) · `uv_index` · `leaf_wetness` (%) |
| soil | `soil_moisture` (% vol) · `soil_temperature` (°C) · `soil_ec` (mS/cm) · `soil_tension` (kPa) · `soil_ph` · `probe_temperature` (°C) |
| water | `water_level` (m) · `water_temperature` (°C) · `water_ec` (mS/cm) · `water_ph` · `dissolved_oxygen` (mg/L) · `turbidity` (NTU) · `flow_rate` (L/min) · `water_pressure` (bar) |
| greenhouse, plant | `greenhouse_temperature` (°C) · `greenhouse_humidity` (%) · `co2` (ppm) · `par` (µmol/m²/s) · `leaf_temperature` (°C) · `stem_diameter` (µm) |
| livestock, beehive | `ammonia` (ppm) · `hive_weight` (kg) · `hive_temperature` (°C) · `hive_humidity` (%) |
| storage, cold chain | `storage_temperature` (°C) · `storage_humidity` (%) · `ethylene` (ppm) · `grain_moisture` (%) · `grain_temperature` (°C) · `door_open` (0/1) |
| air, energy, transport | `pm1`, `pm25`, `pm10` (µg/m³) · `voc_index` · `battery_voltage` (V) · `battery_percent` (%) · `power`, `pv_power` (W) · `gps_latitude`, `gps_longitude` (°) · `gps_speed` (km/h) |

A misspelt name raises at once (`NuaSense has no field "soil_moistur". Did you mean soil_moisture?`). A value outside its range, usually a sensor fault such as a DS18B20 reading -127, is left out and listed under `"skipped"` in the answer, so your loop keeps running.

### Raspberry Pi with a BME280

```python
import time

import board
from adafruit_bme280 import basic as adafruit_bme280  # pip install adafruit-circuitpython-bme280

import nuasense

TOKEN = "kw7n-4hpd-x2vt"
bme = adafruit_bme280.Adafruit_BME280_I2C(board.I2C())

while True:
    try:
        nuasense.send(
            TOKEN,
            "garden-pi",
            temperature=bme.temperature,
            humidity=bme.relative_humidity,
            pressure=bme.pressure,
        )
    except nuasense.NuaSenseError as err:   # offline, or the token is wrong
        print(err)
    time.sleep(300)
```

### Bridging a weather console

`nuasense.send_reading(token, device_id=..., temperature=..., rain_total=...)` sends the form a weather console sends (Ecowitt format, rain as a running total). Use it when you forward a console's values; pick *Home Assistant / weewx / Meteobridge / Node-RED* in the console. For anything you build, `send()` is the better fit.

## What your station means: frost, watering, spray window

Reading needs an API key: in the console under **API Keys**, verify your phone (a code by SMS or WhatsApp), then create a key. It is shown once. Keep it in an environment variable, not in your code.

```python
import nuasense

ns = nuasense.Client()   # reads NUASENSE_API_KEY

for station in ns.stations()["stations"]:
    print(station["station_id"], station["name"], station["last_seen_at"])

look = ns.first_look("garden-west")      # a station_id from stations() or the console
print(look["tonight"]["frost"], look["tonight"]["low_c"])   # e.g. "none", 7.8
print(look["garden"]["watering"]["need_mm"]["lawn"])        # mm to water today
```

The watering need already subtracts the rain of the last 24 hours and the rain forecast for the next 24 hours, so on a day with rain coming it is 0.

## Farm and market data

```python
ns = nuasense.Client()

ns.catalog()   # every dataset, its fields and filters your key reaches

prices = ns.rows("/market/prices", start="-14d", county="nakuru", commodity="maize")

import pandas as pd       # optional
df = pd.DataFrame(prices)

ns.analysis("/fertilizer/rank", county="nakuru")   # where fertilizer is cheapest
```

`dataset()` returns the whole answer (rows plus what the call cost); `rows()` returns only the rows. Options: `start`, `end`, `limit`, `every` with `agg`, `fields`, `oldest_first`; filters as keyword arguments.

Market data needs no station. The datasets cover Kenya, Tanzania, Uganda and Rwanda: county crop and input prices, satellite demand, food security, rainfall against normal.

## Errors

Every refusal raises `nuasense.NuaSenseError` with `.status`, `.body` and, on 429, `.retry_after`. The message says what to do: 401 a key, 402 credit, 403 scope or a station that is not yours, 429 wait.

## Your data

When you connect a station, NuaSense stores its readings and computes your forecast, spray windows and risks from them. The readings are used aggregated and anonymised to improve forecasts and models for everyone; they are never passed on individually without your opt-in. You can disconnect the station in the console at any time and have all its data deleted.

## Links

- Docs for developers and agents: https://api.nuasense.com/index.md
- OpenAPI: https://api.nuasense.com/openapi.json
- Console: https://platform.nuasense.com
- Other packages: [Home Assistant](https://github.com/nuasense/homeassistant-nuasense), [Node-RED](https://github.com/nuasense/node-red-contrib-nuasense), [weewx](https://github.com/nuasense/weewx-nuasense), [n8n](https://github.com/nuasense/n8n-nodes-nuasense)
- Issues: https://github.com/nuasense/nuasense-python/issues · info@nuasense.com

## Development

`python -m unittest discover -s tests` (with `PYTHONPATH=src`). `src/nuasense/reading.schema.json` is a copy of [station-schema](https://github.com/nuasense/station-schema)'s `nuasense-reading.schema.json`; update both together. Releases: bump `src/nuasense/_version.py` and `CHANGELOG.md`, push a tag `vX.Y.Z`; GitHub Actions tests, builds and publishes to PyPI by Trusted Publishing.

## License

MIT
