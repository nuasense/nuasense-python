# nuasense

NuaSense for Python: what your weather station means for house, garden and farm. Frost tonight, how much to water today, the next calm and dry spray window, and a plausibility check of your sensor. Send readings from any station you build (a Raspberry Pi with a BME280, an ESP32, a rain gauge on a GPIO pin), and read East African farm and market data.

```
pip install nuasense
```

Standard library only, Python 3.9 or newer, so it runs on any Raspberry Pi.

## Send readings from your own station

In the console at [platform.nuasense.com](https://platform.nuasense.com): **External stations → Add a station**, pick *Home Assistant / weewx / Meteobridge / Node-RED*, and copy the token after `/station/` on the last screen. Sending needs no API key. The first three stations on an account are free.

```python
import nuasense

nuasense.send_reading(
    "kw7n-4hpd-x2vt",        # your station token
    device_id="garden-pi",   # any stable name for this device
    temperature=21.4,        # °C
    humidity=63,             # %
    pressure=1013.2,         # hPa
    wind_speed=2.1,          # m/s (wind_unit="kmh" for km/h)
    wind_direction=270,      # degrees
    rain_total=12.2,         # mm, a counter that only grows
    solar=412,               # W/m² (or lux=...)
)
```

Every value is optional; send what your station measures.

### Raspberry Pi with a BME280

```python
import time

import board
from adafruit_bme280 import basic as adafruit_bme280  # pip install adafruit-circuitpython-bme280

import nuasense

TOKEN = "kw7n-4hpd-x2vt"
bme = adafruit_bme280.Adafruit_BME280_I2C(board.I2C())

while True:
    nuasense.send_reading(
        TOKEN,
        device_id="garden-pi",
        temperature=bme.temperature,
        humidity=bme.relative_humidity,
        pressure=bme.pressure,
    )
    time.sleep(300)
```

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

`python -m unittest discover -s tests` (with `PYTHONPATH=src`). Releases: bump `src/nuasense/_version.py` and `CHANGELOG.md`, push a tag `vX.Y.Z`; GitHub Actions tests, builds and publishes to PyPI by Trusted Publishing.

## License

MIT
