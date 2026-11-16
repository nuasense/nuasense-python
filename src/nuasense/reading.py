"""One reading in NuaSense's own names and units, checked before it leaves.

The names, units and ranges come from reading.schema.json, a copy of
github.com/nuasense/station-schema (generated from the receiver's own
vocabulary). An unknown name is a mistake in the script and raises at once; a
value outside its range is usually a sensor fault (a DS18B20 without contact
reads -127) and is left out, so a loop that sends every five minutes keeps
running.
"""

from __future__ import annotations

import difflib
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

MAX_VALUES = 40
_PUSH_ONLY = ("device_id", "software", "time")

_schema = json.loads(Path(__file__).with_name("reading.schema.json").read_text(encoding="utf-8"))
FIELDS: Dict[str, Dict[str, Any]] = {
    name: spec for name, spec in _schema["properties"].items() if name not in _PUSH_ONLY
}
_CHANNELS: List[Tuple[re.Pattern, Dict[str, Any]]] = [
    (re.compile(pattern), spec) for pattern, spec in _schema.get("patternProperties", {}).items()
]


def spec_of(name: str) -> Optional[Dict[str, Any]]:
    """The schema entry for a field name, also for channels like soil_moisture_2."""
    if name in FIELDS:
        return FIELDS[name]
    for pattern, spec in _CHANNELS:
        if pattern.match(name):
            return spec
    return None


def _number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def check(values: Mapping[str, Any]) -> Tuple[Dict[str, float], Dict[str, str]]:
    """(values to send, values left out with the reason).

    None and NaN are left out silently: a sensor that did not answer this
    time. Raises ValueError for a name NuaSense does not know.
    """
    clean: Dict[str, float] = {}
    skipped: Dict[str, str] = {}
    for raw_name, raw in values.items():
        name = str(raw_name).strip().lower()
        spec = spec_of(name)
        if spec is None:
            close = difflib.get_close_matches(name, list(FIELDS), n=2, cutoff=0.6)
            hint = f" Did you mean {' or '.join(close)}?" if close else ""
            raise ValueError(
                f'NuaSense has no field "{raw_name}".{hint} '
                "All names and units: https://github.com/nuasense/station-schema"
            )
        n = _number(raw)
        if n is None:
            if raw is not None and not (isinstance(raw, float) and math.isnan(raw)):
                skipped[name] = f"not a number: {raw!r}"
            continue
        low, high = spec.get("minimum"), spec.get("maximum")
        if (low is not None and n < low) or (high is not None and n > high):
            skipped[name] = f"{n:g} outside {low:g}…{high:g} {spec.get('description', '').split(';')[0]}".strip()
            continue
        clean[name] = int(n) if n.is_integer() and abs(n) < 2**53 else n
    if len(clean) > MAX_VALUES:
        raise ValueError(f"At most {MAX_VALUES} values per reading; this one has {len(clean)}.")
    return clean, skipped
