"""NuaSense for Python: what your weather station means for house, garden and
farm, a way to send any sensor you build to NuaSense (weather, soil, water,
greenhouse, beehive, storage), and East African farm and market data.

    import nuasense

    # Send a reading from a sensor you built (no key, only the station token)
    nuasense.send("kw7n-4hpd-x2vt", "garden-pi", temperature=21.4, soil_moisture=34)

    # Read with an API key (or set NUASENSE_API_KEY)
    ns = nuasense.Client()
    ns.first_look("my-station-id")
"""

from ._version import __version__
from .client import Client, NuaSenseError, send, send_reading

__all__ = ["Client", "NuaSenseError", "send", "send_reading", "__version__"]
