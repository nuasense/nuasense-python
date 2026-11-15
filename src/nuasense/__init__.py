"""NuaSense for Python: what your weather station means for house, garden and
farm, a way to send any station you build to NuaSense, and East African farm
and market data.

    import nuasense

    # Send a reading from your own station (no key, only the station token)
    nuasense.send_reading("kw7n-4hpd-x2vt", temperature=21.4, humidity=63, rain_total=12.2)

    # Read with an API key (or set NUASENSE_API_KEY)
    ns = nuasense.Client()
    ns.first_look("my-station-id")
"""

from ._version import __version__
from .client import Client, NuaSenseError, send_reading

__all__ = ["Client", "NuaSenseError", "send_reading", "__version__"]
