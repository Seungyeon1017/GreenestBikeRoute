"""Place search in Heilbronn: a landmark, address or street name -> candidate points, via Nominatim (OpenStreetMap).

The frontend searches with /geocode, lets the rider pick a candidate and routes with its coordinates, so a route
never goes to a guess. Nominatim's usage policy (https://operations.osmfoundation.org/policies/nominatim/) asks for
at most 1 request a second, an identifying User-Agent, cached results and no search-as-you-type; it also only finds
whole words ("Wests" finds nothing, "Weststraße" does).

So the suggestions while typing (/geocode/suggest) don't ask Nominatim: they complete what is typed from what the
server knows itself, at once: the street names of the bike graph (street_places) and every place Nominatim found
before. Those answers are kept in cache/geocode_cache.json, so a search made once stays fast after a restart.

Data: © OpenStreetMap contributors, ODbL.
"""
import json
import os
import threading
import time
import unicodedata
from collections import OrderedDict
from pathlib import Path

import requests

from backend.sharing import distance_m
from download_data import HEILBRONN_BBOX
from routing.naming import _names

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "greenest-bike-route/0.1 (+https://github.com/Seungyeon1017/GreenestBikeRoute)"
MAX_RESULTS = 10        # always ask for this many, so one request serves every `limit`
MIN_INTERVAL_S = 1.0    # Nominatim's limit for the public server
CACHE_SIZE = 2000       # queries kept, oldest dropped first
ATTRIBUTION = "© OpenStreetMap contributors (ODbL), search by Nominatim"
SUGGEST_ATTRIBUTION = "© OpenStreetMap contributors (ODbL)"
CACHE_PATH = Path(__file__).resolve().parent.parent / "cache" / "geocode_cache.json"
SAME_STREET_M = 600     # stretches of one street name further apart than this are different streets
SAME_PLACE_M = 400      # two suggestions of one name this close are the same place


class GeocodingUnavailable(RuntimeError):
    """Nominatim can't be reached or sent something unreadable."""


class SearchDropped(RuntimeError):
    """Whoever asked is gone (the rider typed on) before the search's turn, so it was not sent."""


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


def folded(text):
    """For matching names: case, accents and umlauts don't matter (Sülmertor = sulmertor)."""
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


def _starts(name, q):
    """How well folded `name` completes folded `q`: 0 it starts with it, 1 one of its words does, None neither."""
    if name.startswith(q):
        return 0
    return 1 if any(name.startswith(q, i + 1) for i, c in enumerate(name) if c in " -/,(") else None


def street_places(G):
    """One place per street name of the bike graph, for suggestions: [(folded name, feature)], the feature a point
    on the street. Of a name used for several streets (Hauptstraße in two districts: stretches more than
    SAME_STREET_M apart) only the longest is kept, the graph can't tell them apart by district; Nominatim's results,
    which can, list the others."""
    by_name = {}
    for u, v, d in G.edges(data=True):
        names = _names(d)
        if not names:
            continue
        geometry = d.get("geometry")
        if geometry is not None:
            middle = geometry.interpolate(0.5, normalized=True)
            lon, lat = middle.x, middle.y
        else:
            lon, lat = (G.nodes[u]["x"] + G.nodes[v]["x"]) / 2, (G.nodes[u]["y"] + G.nodes[v]["y"]) / 2
        for name in names:
            by_name.setdefault(name, []).append((lat, lon, float(d.get("length") or 0)))
    places = []
    for name, pieces in by_name.items():
        streets = []  # [[piece, ...]]: pieces chained by nearness
        for piece in pieces:
            near = [s for s in streets
                    if any(distance_m(piece[0], piece[1], p[0], p[1]) <= SAME_STREET_M for p in s)]
            for s in near:
                streets.remove(s)
            streets.append([piece, *(p for s in near for p in s)])
        street = max(streets, key=lambda s: sum(p[2] for p in s))
        lat = sum(p[0] * (p[2] or 1) for p in street) / sum(p[2] or 1 for p in street)
        lon = sum(p[1] * (p[2] or 1) for p in street) / sum(p[2] or 1 for p in street)
        at = min(street, key=lambda p: distance_m(lat, lon, p[0], p[1]))  # on the street, not beside its bend
        places.append((folded(name), {
            "type": "Feature", "geometry": {"type": "Point", "coordinates": [round(at[1], 6), round(at[0], 6)]},
            "properties": {"label": name, "name": name, "category": "highway", "type": "street", "local": True}}))
    return places


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
    """Cached, throttled Nominatim search. `fetch(q)` returns Nominatim's JSON (tests pass a fake). With `cache_path`
    the answers are kept in that file across restarts (the default search keeps them in CACHE_PATH)."""

    def __init__(self, fetch=fetch_json, clock=time.monotonic, sleep=time.sleep, cache_path=None):
        self.fetch, self.clock, self.sleep = fetch, clock, sleep
        self.cache_path = Path(cache_path) if cache_path else CACHE_PATH if fetch is fetch_json else None
        self._cache = OrderedDict()
        self._known = {}  # (folded name, rounded place) -> feature: every named place Nominatim found, for suggest
        self._lock = threading.Lock()
        self._last = None
        if self.cache_path and self.cache_path.exists():
            try:
                self._cache.update(json.loads(self.cache_path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass  # an unreadable file: start empty, it is written again
            for places in self._cache.values():
                self._learn(places)

    def _learn(self, places):
        for f in places:
            name = f["properties"].get("name")
            if name:
                lon, lat = f["geometry"]["coordinates"]
                self._known.setdefault((folded(name), round(lat, 3), round(lon, 3)), f)

    def _save(self):
        if not self.cache_path:
            return
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            part = self.cache_path.with_suffix(".part")
            part.write_text(json.dumps(self._cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            os.replace(part, self.cache_path)
        except OSError:
            pass  # kept in memory only

    def _places(self, q, gone):
        key = normalize(q)
        with self._lock:  # one request at a time, at least MIN_INTERVAL_S apart, across all users
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            # Searches pile up while a rider types: skip the ones nobody waits for any more, so the last one
            # doesn't queue behind them.
            if gone():
                raise SearchDropped(q)
            if self._last is not None:
                self.sleep(max(0.0, self._last + MIN_INTERVAL_S - self.clock()))
                if gone():
                    raise SearchDropped(q)
            try:
                places = _unique([_feature(p) for p in self.fetch(" ".join(q.split()))])
            except (requests.RequestException, KeyError, TypeError, ValueError) as e:
                raise GeocodingUnavailable(f"place search unavailable ({type(e).__name__}), try again later") from e
            finally:
                self._last = self.clock()
            self._cache[key] = places
            if len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
            self._learn(places)
            self._save()
            return places

    def collection(self, q, limit=5, gone=lambda: False):
        """A FeatureCollection of up to `limit` places matching `q`, best first; empty if nothing matches.

        `gone()` says the asker no longer waits: then, unless cached, SearchDropped instead of asking Nominatim."""
        return {"type": "FeatureCollection", "features": self._places(q, gone)[:limit], "attribution": ATTRIBUTION}

    def suggest(self, q, streets=(), limit=5):
        """A FeatureCollection of up to `limit` places whose name completes `q` ("wests" -> Weststraße), without
        asking Nominatim: from `streets` (street_places) and the places found before. A name starting with `q`
        first, then one with a word starting with it; places before streets, shorter names first."""
        key = folded(" ".join(q.split()))
        found = []
        with self._lock:
            known = [(name, f) for (name, _, _), f in self._known.items()]
        for order, source in enumerate((known, streets)):
            for name, feature in source:
                rank = _starts(name, key)
                if rank is not None:
                    found.append((rank, order, len(name), name, feature))
        found.sort(key=lambda x: x[:4])
        features = []
        for _, _, _, name, feature in found:
            lon, lat = feature["geometry"]["coordinates"]
            same = any(folded(f["properties"]["name"]) == name
                       and distance_m(lat, lon, *reversed(f["geometry"]["coordinates"])) <= SAME_PLACE_M
                       for f in features)
            if not same:
                features.append(feature)
            if len(features) == limit:
                break
        return {"type": "FeatureCollection", "features": features, "attribution": SUGGEST_ATTRIBUTION}
