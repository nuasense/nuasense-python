# Changelog

## 0.1.0 (2026-11-16)

- `send_reading()`: one reading from any station you build (temperature, humidity, pressure, wind, rain total, solar or light), no API key, only the station token. Same upload and PASSKEY as the Node-RED, ioBroker and n8n packages.
- `Client`: `first_look()` (frost tonight, watering today, spray window, plausibility), `stations()`, `catalog()`, `dataset()` / `rows()` for the farm and market datasets, `analysis()` for the ready-made analyses.
- Standard library only; Python 3.9 or newer.
