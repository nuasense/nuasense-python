"""Metric readings in, an Ecowitt-format upload out.

NuaSense's station receiver speaks what consumer consoles speak, and the
Ecowitt format is the richest of them. So this module builds the same form a
GW2000 console would send: imperial units, rain as a running counter, and a
PASSKEY that names the device so the receiver can bind the station's path to
it. Same numbers as the Node-RED, ioBroker and n8n packages, so one device
keeps one PASSKEY whichever package sends for it.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Dict, Optional, Union
from urllib.parse import quote

INHG_PER_HPA = 1 / 33.8639
MPH_PER_MS = 1 / 0.44704
IN_PER_MM = 1 / 25.4
# Daylight: 120 lux per W/m² of global radiation, the receiver's own factor
# used the other way, so a script that only has lux lands on the same number.
LUX_PER_WM2 = 120

UPLOAD_BASE = "https://api.nuasense.com/station/"
_TOKEN_RE = re.compile(r"^[a-z0-9-]{12,29}$")
_META = ("PASSKEY", "stationtype", "dateutc")

Number = Union[int, float]
When = Union[str, datetime, None]


def _num(value: object) -> Optional[float]:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        n = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def _fix(n: float, digits: int) -> str:
    """Rounded to `digits`, trailing zeros dropped: 29.920 -> "29.92", 500.00 -> "500"."""
    r = float(f"{n:.{digits}f}")
    if r == 0:
        return "0"
    if r.is_integer():
        return str(int(r))
    return repr(r)


def _round(n: float) -> int:
    """JavaScript's Math.round: halves go up, not to even."""
    return int(math.floor(n + 0.5))


def date_utc(when: When = None) -> str:
    """Ecowitt's `dateutc`: "YYYY-MM-DD HH:MM:SS" in UTC.

    Accepts a datetime or an ISO 8601 string; a time without an offset is
    local time. Anything unreadable becomes now.
    """
    t: Optional[datetime] = None
    if isinstance(when, datetime):
        t = when
    elif isinstance(when, str) and when.strip():
        text = when.strip()
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            t = datetime.fromisoformat(text)
        except ValueError:
            t = None
    if t is None:
        t = datetime.now(timezone.utc)
    return t.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def passkey_for(device_id: str) -> str:
    """A stable 32-hex PASSKEY from the device name.

    Four FNV-1a passes with different offsets over the name's UTF-16 code
    units, exactly like the JavaScript packages. Not a secret and not a
    security measure; it only has to stay the same for the same device,
    because the receiver binds a station's path to the first device that
    uses it.
    """
    text = str(device_id or "python")
    raw = text.encode("utf-16-le")
    units = [raw[i] | (raw[i + 1] << 8) for i in range(0, len(raw), 2)]
    out = ""
    for seed in (0x811C9DC5, 0x01000193, 0x6C62272E, 0x9E3779B9):
        h = seed
        for unit in units:
            h ^= unit
            h = (h * 0x01000193) & 0xFFFFFFFF
        out += f"{h:08x}"
    return out.upper()


def to_ecowitt_fields(
    *,
    device_id: str,
    station_type: str,
    temperature: Optional[Number] = None,
    humidity: Optional[Number] = None,
    pressure: Optional[Number] = None,
    wind_speed: Optional[Number] = None,
    wind_unit: str = "ms",
    wind_gusts: Optional[Number] = None,
    wind_direction: Optional[Number] = None,
    rain_total: Optional[Number] = None,
    solar: Optional[Number] = None,
    lux: Optional[Number] = None,
    time: When = None,
) -> Dict[str, str]:
    """The form fields, as strings, in the order a console sends them.

    Units in: °C, %, hPa, m/s (or km/h with wind_unit="kmh"), degrees,
    mm as a counter that only grows, W/m² (or lux).
    """
    fields: Dict[str, str] = {
        "PASSKEY": passkey_for(device_id),
        "stationtype": station_type,
        "dateutc": date_utc(time),
    }
    t = _num(temperature)
    if t is not None:
        fields["tempf"] = _fix(t * 9 / 5 + 32, 2)
    h = _num(humidity)
    if h is not None:
        fields["humidity"] = str(_round(h))
    p = _num(pressure)
    if p is not None:
        fields["baromabsin"] = _fix(p * INHG_PER_HPA, 3)
    to_ms = 1 / 3.6 if wind_unit == "kmh" else 1
    ws = _num(wind_speed)
    if ws is not None:
        fields["windspeedmph"] = _fix(ws * to_ms * MPH_PER_MS, 2)
    wg = _num(wind_gusts)
    if wg is not None:
        fields["windgustmph"] = _fix(wg * to_ms * MPH_PER_MS, 2)
    wd = _num(wind_direction)
    if wd is not None:
        fields["winddir"] = str(_round(math.fmod(math.fmod(wd, 360) + 360, 360)))
    rain = _num(rain_total)
    if rain is not None:
        fields["yearlyrainin"] = _fix(rain * IN_PER_MM, 3)
    sol = _num(solar)
    lx = _num(lux)
    if sol is not None:
        fields["solarradiation"] = _fix(sol, 2)
    elif lx is not None:
        fields["solarradiation"] = _fix(lx / LUX_PER_WM2, 2)
    return fields


def encode_form(fields: Dict[str, str]) -> str:
    return "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in fields.items())


def upload_url(token: str) -> str:
    """The upload URL for a token as the console shows it, e.g. kw7n-4hpd-x2vt."""
    tok = str(token or "").strip().lower()
    if not _TOKEN_RE.match(tok):
        raise ValueError(
            'The station token looks wrong. Copy it from the last screen of "Add a station" in the console.'
        )
    return UPLOAD_BASE + tok


def has_values(fields: Dict[str, str]) -> bool:
    """True when at least one measured value is present."""
    return any(k not in _META for k in fields)
