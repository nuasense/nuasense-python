"""The NuaSense API from Python: standard library only, so it runs on any Raspberry Pi."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Mapping, Optional, Union
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from . import ecowitt, reading
from ._version import __version__
from .ecowitt import Number, When

API = "https://api.nuasense.com"
API_HOST = "api.nuasense.com"
DATA = API + "/api/nuasense/v1"
ANALYSIS = API + "/api/partner/v1/market"
KEY_ENV = "NUASENSE_API_KEY"
TIMEOUT = 30

# Tells NuaSense the call came from this package. Changes nothing in price or limits.
CLIENT = "python/" + __version__
USER_AGENT = "nuasense-python/" + __version__

_HINTS = {
    401: "Missing or invalid key. Create one at https://platform.nuasense.com under API Keys "
    "and pass it as Client(api_key=...) or set NUASENSE_API_KEY.",
    402: "This needs credit: history beyond the free 30 days, or prepaid credit spent.",
    403: "The key lacks the scope, or the station is not yours or not approved for API exposure.",
    429: "Rate or unit budget reached. Wait for Retry-After or ask with a smaller limit.",
    451: "This dataset is withheld on licence grounds; no key unlocks it.",
}


class NuaSenseError(Exception):
    """An answer NuaSense refused, with the HTTP status and the body it sent."""

    def __init__(self, message: str, status: Optional[int] = None, body: Any = None,
                 retry_after: Optional[str] = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body
        self.retry_after = retry_after


def _body_message(body: Any) -> str:
    if isinstance(body, dict):
        for key in ("error", "message", "detail"):
            value = body.get(key)
            if isinstance(value, str) and value:
                return value
            if isinstance(value, dict) and isinstance(value.get("message"), str):
                return value["message"]
    if isinstance(body, str):
        return body.strip()[:200]
    return ""


class _NoRedirect(HTTPRedirectHandler):
    """Never follow a redirect: urllib would carry the Authorization header to
    whatever host the redirect names, and could step down from https. A 3xx
    comes back as an answer instead."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


_opener = build_opener(_NoRedirect)


def urlopen(req: Request, timeout: float = TIMEOUT):
    return _opener.open(req, timeout=timeout)


def _check_url(url: str) -> None:
    parts = urlparse(url)
    if parts.scheme != "https" or parts.hostname != API_HOST:
        raise ValueError(f"nuasense only talks to {API}; refusing {parts.scheme}://{parts.hostname}")


def _http(method: str, url: str, headers: Dict[str, str], data: Optional[bytes] = None,
          timeout: float = TIMEOUT):
    """(status, text, headers) for any answer, also 3xx/4xx/5xx. Only https://api.nuasense.com."""
    _check_url(url)
    req = Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as res:
            return res.status, res.read().decode("utf-8", "replace"), res.headers
    except HTTPError as err:
        try:
            text = err.read().decode("utf-8", "replace") if err.fp is not None else ""
        finally:
            err.close()
        return err.code, text, err.headers
    except URLError as err:
        raise NuaSenseError(f"Could not reach NuaSense: {err.reason}") from err


_SEND_ANSWERS = {
    400: "NuaSense found nothing readable in the reading.",
    404: "NuaSense does not know this station token. Copy it again from the console "
         '(External stations → Add a station → "I built it myself"), or add the station first.',
    409: "This token belongs to another device: the first device_id that used it. "
         "Use that device_id again, or add a second station for this device.",
    429: "Too many uploads. Send every few minutes; uploads less than a minute apart are dropped anyway.",
}


def send(
    token: str,
    device_id: str,
    values: Optional[Mapping[str, Any]] = None,
    *,
    timeout: float = TIMEOUT,
    **more: Any,
) -> Dict[str, Any]:
    """Send one reading from a sensor you built. Needs no API key, only the station token.

        nuasense.send("kw7n-4hpd-x2vt", "garden-pi", temperature=21.4, soil_moisture=34)
        nuasense.send("kw7n-4hpd-x2vt", "garden-pi", {"soil_moisture": 34, "soil_moisture_2": 41.5})

    Names and units are NuaSense's own (weather, soil, water, greenhouse,
    beehive, storage, air, energy; several sensors as soil_moisture_2 … _8):
    https://github.com/nuasense/station-schema. device_id is any name for the
    device (4 characters or more); it binds the token to this device. The time
    is the moment NuaSense receives the reading. rain_mm is the rain since the
    previous reading.

    Returns {"sent", "status", "answer", "values", "skipped"}; "skipped" lists
    values left out as impossible (usually a sensor fault). A reading with no
    value left is not sent.
    """
    url = ecowitt.upload_url(token)
    device = str(device_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._:-]{4,48}", device):
        raise ValueError("device_id: 4 to 48 letters, digits or . _ : - (e.g. garden-pi). It binds the token to this device.")
    merged: Dict[str, Any] = dict(values or {})
    merged.update(more)
    clean, skipped = reading.check(merged)
    if not clean:
        return {"sent": False, "status": None, "answer": "nothing to send", "values": {}, "skipped": skipped}
    body = {"device_id": device, "software": USER_AGENT, **clean}
    status, text, _ = _http(
        "POST", url,
        {"Content-Type": "application/json", "X-NuaSense-Client": CLIENT, "User-Agent": USER_AGENT},
        json.dumps(body).encode("utf-8"), timeout,
    )
    if status >= 300:
        message = _SEND_ANSWERS.get(status) or f"NuaSense refused the reading ({status}): {text.strip()[:200]}"
        raise NuaSenseError(message, status, text)
    return {"sent": True, "status": status, "answer": text.strip(), "values": clean, "skipped": skipped}


def send_reading(
    token: str,
    *,
    device_id: str = "python",
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
    timeout: float = TIMEOUT,
) -> Dict[str, Any]:
    """Send one weather reading the way a weather console does (Ecowitt form). No API key.

    For a bridge from a console or a script that keeps console-style values:
    rain as a running total. For a sensor you build, use send(): every field
    (soil, water, greenhouse …), rain since the last reading.

    Units: temperature °C, humidity %, pressure hPa, wind m/s (or km/h with
    wind_unit="kmh"), wind_direction degrees, rain_total mm as a counter that
    only grows, solar W/m² (or lux). The token is the part after /station/ on
    the last screen of "Add a station" in the console.
    """
    url = ecowitt.upload_url(token)
    fields = ecowitt.to_ecowitt_fields(
        device_id=device_id, station_type=CLIENT.replace("/", "_"),
        temperature=temperature, humidity=humidity, pressure=pressure,
        wind_speed=wind_speed, wind_unit=wind_unit, wind_gusts=wind_gusts,
        wind_direction=wind_direction, rain_total=rain_total, solar=solar, lux=lux, time=time,
    )
    if not ecowitt.has_values(fields):
        raise ValueError("Add at least one value to the reading.")
    status, text, _ = _http(
        "POST", url,
        {"Content-Type": "application/x-www-form-urlencoded", "X-NuaSense-Client": CLIENT,
         "User-Agent": USER_AGENT},
        ecowitt.encode_form(fields).encode("ascii"), timeout,
    )
    if status == 404:
        raise NuaSenseError(
            "NuaSense does not know this station token. Copy it again from the console, "
            "or add the station first.", status, text)
    if status >= 300:
        raise NuaSenseError(f"NuaSense refused the reading ({status}): {text.strip()[:200]}", status, text)
    return {"sent": True, "status": status, "answer": text.strip(), "fields": fields}


Params = Dict[str, Union[str, int, float, bool, None]]


class Client:
    """Reads from NuaSense with an API key.

    >>> import nuasense
    >>> ns = nuasense.Client()            # key from NUASENSE_API_KEY
    >>> ns.first_look("my-station-id")    # frost tonight, watering today, spray window
    >>> ns.dataset("/market/prices", start="-14d", county="nakuru", commodity="maize")
    """

    def __init__(self, api_key: Optional[str] = None, *, timeout: float = TIMEOUT,
                 client_name: Optional[str] = None) -> None:
        self.api_key = (api_key or os.environ.get(KEY_ENV) or "").strip() or None
        self.timeout = timeout
        # Optional: name your tool or agent, e.g. "garden-pi"; shown in your usage, nothing else.
        self.client_header = CLIENT + (f"; app={client_name}" if client_name else "")

    def __repr__(self) -> str:
        return f"Client(api_key={'set' if self.api_key else 'missing'})"

    def get(self, url: str, params: Optional[Params] = None) -> Any:
        """GET a URL under https://api.nuasense.com with the key; returns the parsed JSON.
        Any other host is refused before the key leaves the machine."""
        _check_url(url)
        query = {k: ("true" if v is True else "false" if v is False else v)
                 for k, v in (params or {}).items() if v is not None and v != ""}
        if query:
            url += ("&" if "?" in url else "?") + urlencode(query)
        headers = {"Accept": "application/json", "X-NuaSense-Client": self.client_header,
                   "User-Agent": USER_AGENT}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        status, text, res_headers = _http("GET", url, headers, None, self.timeout)
        try:
            body: Any = json.loads(text) if text else None
        except ValueError:
            body = text
        if status >= 300:
            said = _body_message(body)
            hint = _HINTS.get(status, "")
            message = f"NuaSense answered {status}" + (f": {said}" if said else "") + (f". {hint}" if hint else "")
            retry = res_headers.get("Retry-After") if res_headers is not None else None
            raise NuaSenseError(message, status, body, retry)
        return body

    # --- your stations -------------------------------------------------------

    def stations(self) -> Any:
        """The external stations on your account, with when each last sent."""
        return self.get(DATA + "/ingest/stations")

    def first_look(self, station_id: str) -> Any:
        """Frost tonight, watering today (mm for lawn, vegetables, beds), the next
        spray window and a plausibility check of the latest reading."""
        return self.get(DATA + "/ingest/first-look", {"station_id": station_id})

    # --- datasets and analyses ----------------------------------------------

    def catalog(self) -> Any:
        """The datasets, fields and filters your key reaches."""
        return self.get(DATA + "/catalog")

    def dataset(self, path: str, *, start: str = "-24h", limit: int = 50, end: Optional[str] = None,
                every: Optional[str] = None, agg: Optional[str] = None, fields: Optional[str] = None,
                oldest_first: bool = False, **filters: Union[str, int, float, None]) -> Any:
        """Rows from one dataset, e.g. dataset("/market/prices", county="nakuru").

        `path` is a catalog path such as "/market/prices" or "/farm/weather".
        Filters go as keyword arguments. Returns the API's answer; the rows are
        under "rows" (pandas: pd.DataFrame(answer["rows"])).
        """
        params: Params = {"start": start, "limit": limit, "end": end, "every": every,
                          "agg": agg or ("mean" if every else None), "fields": fields,
                          "order": "asc" if oldest_first else None}
        params.update(filters)
        return self.get(DATA + _path(path), params)

    def rows(self, path: str, **kwargs: Any) -> list:
        """Only the rows of dataset(...), as a list of dicts."""
        answer = self.dataset(path, **kwargs)
        rows = answer.get("rows") if isinstance(answer, dict) else None
        return rows if isinstance(rows, list) else []

    def analysis(self, path: str, **params: Union[str, int, float, None]) -> Any:
        """One of the ready-made analyses, e.g. analysis("/fertilizer/rank", county="nakuru")."""
        return self.get(ANALYSIS + _path(path), params)


def _path(path: str) -> str:
    p = str(path or "").strip()
    if not p:
        raise ValueError('Give a catalog path such as "/market/prices".')
    return p if p.startswith("/") else "/" + p
