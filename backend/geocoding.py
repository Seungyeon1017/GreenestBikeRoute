"""Place search in Heilbronn: a landmark, address or street name -> candidate points, via Nominatim (OpenStreetMap).

The frontend searches with /geocode, lets the rider pick a candidate and routes with its coordinates, so a route
never goes to a guess. Nominatim's usage policy (https://operations.osmfoundation.org/policies/nominatim/) asks for
at most 1 request a second, an identifying User-Agent, cached results and no search-as-you-type.

Data: © OpenStreetMap contributors, ODbL.
"""
import threading
import time
from collections import OrderedDict

import requests

from download_data import HEILBRONN_BBOX

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "greenest-bike-route/0.1 (+https://github.com/Seungyeon1017/GreenestBikeRoute)"
MAX_RESULTS = 10        # always ask for this many, so one request serves every `limit`
MIN_INTERVAL_S = 1.0    # Nominatim's limit for the public server
CACHE_SIZE = 2000       # queries kept, oldest dropped first
ATTRIBUTION = "© OpenStreetMap contributors (ODbL), search by Nominatim"


class GeocodingUnavailable(RuntimeError):
    """Nominatim can't be reached or sent something unreadable."""


def fetch_json(q, timeout=10):
    """Nominatim's jsonv2 results for `q`, only places inside HEILBRONN_BBOX, best first."""
    west, south, east, north = HEILBRONN_BBOX
    r = requests.get(NOMINATIM_URL, timeout=timeout, headers={"User-Agent": USER_AGENT}, params={
        "q": q, "format": "jsonv2", "limit": MAX_RESULTS, "viewbox": f"{west},{north},{east},{south}",
        "bounded": 1, "countrycodes": "de", "accept-language": "de"})
    r.raise_for_status()
    return r.json()


def normalize(q):
    """The cache key: case and extra spaces don't make a different search."""
    return " ".join(q.split()).casefold()


def _feature(place):
    return {"type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(float(place["lon"]), 6), round(float(place["lat"]), 6)]},
            "properties": {"label": place["display_name"], "name": place.get("name") or None,
                           "category": place.get("category"), "type": place.get("type")}}


def _unique(features):
    """The first feature of each label: OSM splits a street into several ways that Nominatim lists alike."""
    seen = set()
    return [f for f in features if not (f["properties"]["label"] in seen or seen.add(f["properties"]["label"]))]


class Geocoder:
    """Cached, throttled Nominatim search. `fetch(q)` returns Nominatim's JSON (tests pass a fake)."""

    def __init__(self, fetch=fetch_json, clock=time.monotonic, sleep=time.sleep):
        self.fetch, self.clock, self.sleep = fetch, clock, sleep
        self._cache = OrderedDict()
        self._lock = threading.Lock()
        self._last = None

    def _places(self, q):
        key = normalize(q)
        with self._lock:  # one request at a time, at least MIN_INTERVAL_S apart, across all users
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            if self._last is not None:
                self.sleep(max(0.0, self._last + MIN_INTERVAL_S - self.clock()))
            try:
                places = _unique([_feature(p) for p in self.fetch(" ".join(q.split()))])
            except (requests.RequestException, KeyError, TypeError, ValueError) as e:
                raise GeocodingUnavailable(f"place search unavailable ({type(e).__name__}), try again later") from e
            finally:
                self._last = self.clock()
            self._cache[key] = places
            if len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
            return places

    def collection(self, q, limit=5):
        """A FeatureCollection of up to `limit` places matching `q`, best first; empty if nothing matches."""
        return {"type": "FeatureCollection", "features": self._places(q)[:limit], "attribution": ATTRIBUTION}
