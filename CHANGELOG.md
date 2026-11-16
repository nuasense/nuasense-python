# Changelog

## 0.2.0 (2026-11-16)

- `send(token, device_id, ...)`: a reading from a sensor you build, in NuaSense's own names and units: weather, soil, water, greenhouse, beehive, storage, air, energy; several probes as `soil_moisture_2` … `_8`. The console path is **I built it myself**. Names are checked against the station schema before sending (a typo raises with a suggestion); impossible values (sensor faults) are left out and listed under `skipped`.
- `send_reading()` stays for bridging a weather console (Ecowitt form, rain as a running total).
- The API key goes only to `https://api.nuasense.com`; redirects are never followed.

## 0.1.0 (2026-11-16)

- `send_reading()`: one reading from any station you build (temperature, humidity, pressure, wind, rain total, solar or light), no API key, only the station token. Same upload and PASSKEY as the Node-RED, ioBroker and n8n packages.
- `Client`: `first_look()` (frost tonight, watering today, spray window, plausibility), `stations()`, `catalog()`, `dataset()` / `rows()` for the farm and market datasets, `analysis()` for the ready-made analyses.
- Standard library only; Python 3.9 or newer.
