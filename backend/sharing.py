"""Shared e-bikes and e-scooters free to rent in Heilbronn, live from MobiData BW's bundled GBFS feeds.

Heilbronn has one sharing provider in the feed: Dott (free-floating pedelecs and e-scooters). Each vehicle
comes with its battery level, range and a link that opens it in the provider's app. Dott is free-floating: a ride
may end anywhere in its Heilbronn area except in the no-parking zones of its geofencing feed (pedestrian zones,
parks, ...), and in a few zones only at a parking zone (virtual station). /sharing/zones lists the parking zones,
/sharing/geofencing the geofencing zones.

Data: MobiData BW, "Gebündelte Daten Bikesharing Baden-Württemberg" (https://mobidata-bw.de/dataset/bikesh)
and its scooter counterpart, Datenlizenz Deutschland – Namensnennung – 2.0. Positions refresh about every
5 minutes upstream.
"""
import math
import time
from datetime import datetime, timezone

import requests

from download_data import HEILBRONN_BBOX

GBFS_URL = "https://api.mobidata-bw.de/sharing/gbfs/v3/{system}/{feed}"
SYSTEMS = ("dott_heilbronn",)  # add more GBFS systems here if a provider starts in Heilbronn
# GBFS form_factor -> what we call it. Cars, mopeds and other types are left out.
VEHICLES = {"bicycle": "bike", "cargo_bicycle": "bike", "scooter_standing": "scooter", "scooter_seated": "scooter",
            "scooter": "scooter"}
CACHE_S = 60          # serve the same snapshot for this long
STALE_S = 30 * 60     # if the feed is down, keep serving the last snapshot this long
ATTRIBUTION = "MobiData BW (dl-de/by-2-0), sharing data by the providers"


class SharingUnavailable(RuntimeError):
    """The feed can't be read and there is no recent snapshot to fall back on."""


def _text(value):
    """GBFS v3 localised strings are [{"text": ..., "language": ...}]; v2 uses plain strings."""
    if isinstance(value, list):
        return next((v["text"] for v in value if v.get("language") == "en"), value[0]["text"] if value else "")
    return value or ""


def fetch_json(system, feed, timeout=10):
    r = requests.get(GBFS_URL.format(system=system, feed=feed), timeout=timeout)
    r.raise_for_status()
    return r.json()


def _in_heilbronn(lon, lat):
    west, south, east, north = HEILBRONN_BBOX
    return west <= lon <= east and south <= lat <= north


def _price(plan):
    """"€1.00 to unlock + €0.44/min" from a GBFS pricing plan, or its description."""
    if not plan:
        return None
    per_min = plan.get("per_min_pricing") or []
    if plan.get("currency") == "EUR" and per_min:
        return f"€{plan.get('price', 0):.2f} to unlock + €{per_min[0]['rate']:.2f}/min"
    return _text(plan.get("description")) or None


def read_system(system, fetch=fetch_json):
    """(vehicles, zones, geofencing) of one GBFS system, as GeoJSON Features: the vehicles and zones inside Heilbronn,
    and all its geofencing zones in feed order (an earlier zone's rules win where zones overlap, GBFS v3), each with
    the end rule per vehicle kind (`bike`, `scooter`: see _end_rule); geofencing is None if the system has no feed."""
    provider = _text(fetch(system, "system_information")["data"].get("operator")) or system
    types = {t["vehicle_type_id"]: t for t in fetch(system, "vehicle_types")["data"]["vehicle_types"]}
    kind = {i: VEHICLES[t["form_factor"]] for i, t in types.items() if t.get("form_factor") in VEHICLES}
    try:
        plans = {p["plan_id"]: p for p in fetch(system, "system_pricing_plans")["data"]["plans"]}
    except (requests.RequestException, KeyError):
        plans = {}

    vehicles = []
    for v in fetch(system, "vehicle_status")["data"]["vehicles"]:
        if v.get("vehicle_type_id") not in kind or v.get("is_reserved") or v.get("is_disabled"):
            continue
        if "lat" not in v or not _in_heilbronn(v["lon"], v["lat"]):
            continue
        t = types[v["vehicle_type_id"]]
        uris = v.get("rental_uris") or {}
        fuel = v.get("current_fuel_percent")
        vehicles.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [v["lon"], v["lat"]]}, "properties": {
            "provider": provider,
            "vehicle": kind[v["vehicle_type_id"]],
            "vehicle_id": v["vehicle_id"],
            "electric": t.get("propulsion_type") in ("electric_assist", "electric"),
            "battery_pct": None if fuel is None else round(fuel * 100),
            "range_m": v.get("current_range_meters"),
            "price": _price(plans.get(v.get("pricing_plan_id")) or plans.get(t.get("default_pricing_plan_id"))),
            "rent_url": uris.get("web") or uris.get("android") or uris.get("ios"),
            "last_reported": v.get("last_reported"),
        }})

    geofencing = []
    try:
        fences = fetch(system, "geofencing_zones")["data"]["geofencing_zones"]["features"]
    except (requests.RequestException, KeyError):
        fences = None
    for i, f in enumerate(fences or []):
        rules = {}
        for rule in f["properties"].get("rules") or []:
            for type_id in rule.get("vehicle_type_ids") or kind:
                if type_id in kind and kind[type_id] not in rules:
                    rules[kind[type_id]] = _end_rule(rule)
        if rules:
            geofencing.append({"type": "Feature", "geometry": f["geometry"], "properties": {
                "provider": provider, "name": _text(f["properties"].get("name")) or None, "order": i, **rules}})

    zones = []
    status = {s["station_id"]: s for s in fetch(system, "station_status")["data"]["stations"]}
    for s in fetch(system, "station_information")["data"]["stations"]:
        if not _in_heilbronn(s["lon"], s["lat"]):
            continue
        st = status.get(s["station_id"], {})
        counts = st.get("vehicle_types_available") or []
        capacity = s.get("vehicle_types_capacity") or []

        def available(k):
            return sum(c["count"] for c in counts if kind.get(c["vehicle_type_id"]) == k)

        def room(k):
            return sum(c["count"] for c in capacity if any(kind.get(i) == k for i in c["vehicle_type_ids"])) or None

        zones.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]}, "properties": {
            "provider": provider,
            "name": _text(s.get("name")),
            "bikes_available": available("bike"),
            "scooters_available": available("scooter"),
            "bike_capacity": room("bike"),
            "scooter_capacity": room("scooter"),
        }})
    return vehicles, zones, (geofencing if fences is not None else None)


def _end_rule(rule):
    """Where a ride may end inside a geofencing zone: "anywhere", "parking_zone" (only at a station) or "no"."""
    if rule.get("station_parking"):
        return "parking_zone"
    return "anywhere" if rule.get("ride_end_allowed") else "no"


def distance_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(a))


def nearest(features, lat, lon, limit):
    """The `limit` features closest to (lat, lon), closest first, each with `distance_m`."""
    out = []
    for f in features:
        f_lon, f_lat = f["geometry"]["coordinates"]
        out.append({**f, "properties": {**f["properties"], "distance_m": round(distance_m(lat, lon, f_lat, f_lon))}})
    return sorted(out, key=lambda f: f["properties"]["distance_m"])[:limit]


class Sharing:
    """Cached snapshot of all SYSTEMS. `fetch(system, feed)` returns a GBFS feed's JSON (tests pass a fake)."""

    def __init__(self, fetch=fetch_json, systems=SYSTEMS, clock=time.monotonic):
        self.fetch, self.systems, self.clock = fetch, systems, clock
        self._snapshot, self._taken = None, None

    def snapshot(self):
        """{"vehicles": [...], "zones": [...], "updated": ISO time}; refetched after CACHE_S."""
        now = self.clock()
        if self._snapshot is not None and now - self._taken < CACHE_S:
            return self._snapshot
        try:
            vehicles, zones, geofencing = [], [], []
            for system in self.systems:
                v, z, g = read_system(system, self.fetch)
                vehicles += v
                zones += z
                geofencing = None if g is None or geofencing is None else geofencing + g
        except (requests.RequestException, KeyError, ValueError) as e:
            if self._snapshot is not None and now - self._taken < STALE_S:
                return self._snapshot
            raise SharingUnavailable(f"sharing data unavailable ({type(e).__name__}), try again later") from e
        self._snapshot = {"vehicles": vehicles, "zones": zones, "geofencing": geofencing,
                          "updated": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        self._taken = now
        return self._snapshot

    def collection(self, kind, near=None, limit=None, vehicle="all"):
        """A FeatureCollection of "vehicles" (all, or only vehicle="bike" / "scooter"), "zones" or "geofencing";
        with near=(lat, lon), the closest `limit` first."""
        snap = self.snapshot()
        features = snap[kind] or []
        if kind == "vehicles" and vehicle != "all":
            features = [f for f in features if f["properties"]["vehicle"] == vehicle]
        if near is not None:
            features = nearest(features, *near, limit or len(features))
        elif limit:
            features = features[:limit]
        return {"type": "FeatureCollection", "features": features, "updated": snap["updated"], "attribution": ATTRIBUTION}
