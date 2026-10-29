"""A trip with a shared e-bike or e-scooter: walk to a free vehicle, ride it to a parking zone near the end, walk on.

The walks use OSM's walking network (OSMnx network_type="walk": streets with their pavements, footways, pedestrian
zones and steps, but no bike paths or motorways), the ride uses the bike graph with the request's penalties, as /route.
An e-scooter rides by the scooter rules: pushed on footways and in pedestrian zones (routing.route.scooter_pushes).

Where to leave it: Dott is free-floating, so at the destination unless that lies in one of its no-parking zones
(geofencing); then at the place allowed to park that gets you to the end soonest (walk from it to the end, plus riding
there from the start in a straight line): a street corner outside the no-parking zones, or a parking zone. Which
vehicle: the one that gets you there soonest (walk to it, plus riding from it in a straight line), with enough battery.
The CANDIDATES best vehicles are then routed for real and the quickest trip wins.
"""
import weakref
from itertools import islice
from pathlib import Path

import networkx as nx
import numpy as np
import osmnx as ox
import shapely
from shapely import Point, STRtree
from shapely.geometry import shape

from routing.calories import DEFAULT_WEIGHT_KG, walk_kcal
from routing.costs import MEDIAN_SPEED_KMH
from routing.graph import CACHE_DIR, PLACE
from routing.route import _GRAPH_LOCK, WALK_KMH, RouteError, edge_coords, find_route

WALK_GRAPH_PATH = CACHE_DIR / "heilbronn_walk.graphml"
WALK_MAX_M = 1000  # furthest walk to a vehicle, and from the parking zone to the end
DETOUR = 1.3  # streets are about this much longer than the straight line, to pick candidates
CANDIDATES = 3  # vehicles routed for real
RETURN_CANDIDATES = 30  # places to leave the vehicle whose walk to the end is computed
RANGE_MARGIN_M = 1000  # a vehicle needs this much more range than the ride


def load_walk_graph(path=WALK_GRAPH_PATH):
    """The Heilbronn walking network from cache/, downloading it from OSM the first time (~1.5 min)."""
    path = Path(path)
    if path.exists():
        return ox.load_graphml(path)
    ox.settings.cache_folder = CACHE_DIR
    G = ox.graph_from_place(PLACE, network_type="walk")
    ox.save_graphml(G, path)
    return G


def _metres(lat1, lon1, lat2, lon2):
    """Equirectangular distance in metres; good to well under 1% across a city. Works on numpy arrays."""
    x = np.radians(lon2 - lon1) * np.cos(np.radians((lat1 + lat2) / 2))
    return 6_371_000 * np.hypot(x, np.radians(lat2 - lat1))


def _plane(lat0):
    """(lat, lon) -> (x, y) in metres around latitude lat0, for STRtrees."""
    k = 6_371_000 * np.pi / 180
    return lambda lat, lon: (np.asarray(lon) * np.cos(np.radians(lat0)) * k, np.asarray(lat) * k)


class WalkNetwork:
    """The walking graph with its nodes in arrays and an STRtree, to find the nearest node of many points quickly."""

    def __init__(self, G):
        self.G = G
        self.nodes = list(G.nodes)
        self.lat = np.array([G.nodes[n]["y"] for n in self.nodes], dtype=float)
        self.lon = np.array([G.nodes[n]["x"] for n in self.nodes], dtype=float)
        self.to_xy = _plane(self.lat.mean())
        self.tree = STRtree(shapely.points(*self.to_xy(self.lat, self.lon)))

    def nearest(self, lat, lon):
        """(node, metres) of the walking node nearest to (lat, lon)."""
        p = Point(*self.to_xy(lat, lon))
        d0 = self.tree.query_nearest(p, return_distance=True)[1][0]
        # The tree's plane and _metres differ by far under 1% across the city: measure the few nodes about as near.
        near = np.sort(self.tree.query(p, predicate="dwithin", distance=d0 * 1.01 + 1))
        d = _metres(lat, lon, self.lat[near], self.lon[near])
        i = int(np.argmin(d))
        return self.nodes[near[i]], float(d[i])

    def from_point(self, lat, lon, cutoff=WALK_MAX_M):
        """Walking metres and paths from (lat, lon) to every node within `cutoff`, through its nearest node.
        The walking graph has every street both ways, so these are also the walks back to the point."""
        node, off = self.nearest(lat, lon)
        dist, paths = nx.single_source_dijkstra(self.G, node, cutoff=max(cutoff - off, 0), weight="length")
        return off, dist, paths

    def leg(self, path, a, b, reverse=False):
        """A walking leg along graph `path` from point a to point b (both (lat, lon)) as a GeoJSON Feature, the
        path run backwards with `reverse` (a walk found from b)."""
        path = path[::-1] if reverse else path
        coords = [[a[1], a[0]]]
        for u, v in zip(path[:-1], path[1:]):
            d = min(self.G[u][v].values(), key=lambda d: d["length"])
            coords.extend(edge_coords(self.G, u, v, d))
        if len(path) == 1:  # an empty path is no walk at all
            coords.append([self.G.nodes[path[0]]["x"], self.G.nodes[path[0]]["y"]])
        coords.append([b[1], b[0]])
        length = sum(_metres(p[1], p[0], q[1], q[0]) for p, q in zip(coords[:-1], coords[1:]))
        return {"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {"mode": "walk", "length_m": round(float(length), 1), "duration_s": round(length / (WALK_KMH / 3.6))}}


def _latlon(feature):
    lon, lat = feature["geometry"]["coordinates"]
    return lat, lon


def _walk_to(walk, reach, lat, lon):
    """Walking metres from the point `reach` was found from (walk.from_point) to (lat, lon), or None if too far."""
    off, dist, _ = reach
    node, node_off = walk.nearest(lat, lon)
    if node not in dist:
        return None
    m = off + dist[node] + node_off
    return m if m <= WALK_MAX_M else None


class ParkingRules:
    """Where a ride may end, from the provider's geofencing zones (backend.sharing: in feed order, each with an end
    rule per vehicle kind). The first zone containing a point decides, as in GBFS v3; outside every zone a ride may not
    end (Dott's last zone is its whole Heilbronn area)."""

    def __init__(self, geofencing):
        self.zones = geofencing
        self.tree = STRtree([shape(z["geometry"]) for z in geofencing])

    def rule(self, kind, lat, lon):
        """"anywhere", "parking_zone" (only at a parking zone) or "no" for vehicle kind "bike" / "scooter"."""
        for i in sorted(self.tree.query(Point(lon, lat), predicate="within")):
            if kind in self.zones[i]["properties"]:
                return self.zones[i]["properties"][kind]
        return "no"


_RULES = {}  # id(geofencing list) -> (that list, its ParkingRules): the saved zones stay the same while the API runs


def _parking_rules(geofencing):
    if id(geofencing) not in _RULES or _RULES[id(geofencing)][0] is not geofencing:
        _RULES.clear()
        _RULES[id(geofencing)] = (geofencing, ParkingRules(geofencing))
    return _RULES[id(geofencing)][1]


# The bike graph's corners as (lat, lon) arrays, per graph. Only snapping adds nodes while the API runs (snap-*, and
# removes them again), so they stay the same.
_CORNERS = weakref.WeakKeyDictionary()


def _corners(G):
    if G not in _CORNERS:
        with _GRAPH_LOCK:  # not while a route is snapping its ends
            nodes = [n for n in G.nodes if not str(n).startswith("snap-")]
            _CORNERS[G] = (np.array([G.nodes[n]["y"] for n in nodes], dtype=float),
                           np.array([G.nodes[n]["x"] for n in nodes], dtype=float))
    return _CORNERS[G]


def _return_points(G, walk, rules, zones, kind, origin, destination, to_end):
    """Where to leave a vehicle of `kind`, best first: [(score, (lat, lon), zone or None)].

    The destination itself where parking is allowed there; else the bike graph's corners within WALK_MAX_M walk of it
    where parking is allowed, and the parking zones. Score: walking from it to the end plus riding to it from the start
    in a straight line, in hours x km/h (only for ranking). Without `rules` (no geofencing feed), only the parking zones.
    """
    def score(lat, lon, walk_m):
        return walk_m / WALK_KMH + DETOUR * float(_metres(origin[0], origin[1], lat, lon)) / MEDIAN_SPEED_KMH

    if rules is not None and rules.rule(kind, *destination) == "anywhere":
        return [(score(*destination, 0.0), destination, None)]
    options = []
    for z in zones:
        m = _walk_to(walk, to_end, *_latlon(z))
        if m is not None:
            options.append((score(*_latlon(z), m), _latlon(z), z))
    if rules is not None:
        lat, lon = _corners(G)
        to_end_m = _metres(destination[0], destination[1], lat, lon)
        near = np.flatnonzero(to_end_m <= WALK_MAX_M)
        # Rank by straight lines first; parking rules and walking distances only for the most promising corners.
        straight = near[np.argsort(DETOUR * to_end_m[near] / WALK_KMH
                                   + DETOUR * _metres(origin[0], origin[1], lat[near], lon[near]) / MEDIAN_SPEED_KMH,
                                   kind="stable")]
        allowed = (i for i in straight if rules.rule(kind, lat[i], lon[i]) == "anywhere")
        for i in islice(allowed, RETURN_CANDIDATES):
            m = _walk_to(walk, to_end, lat[i], lon[i])
            if m is not None:
                options.append((score(lat[i], lon[i], m), (float(lat[i]), float(lon[i])), None))
    return sorted(options, key=lambda o: o[0])


def plan_sharing_trip(G, walk, vehicles, zones, origin, destination, penalties, vehicle="all", park_in_zone=False,
                      geofencing=None, weight_kg=DEFAULT_WEIGHT_KG):
    """The quickest walk - ride - walk trip from origin to destination (both (lat, lon)).

    `vehicles`, `zones` and `geofencing` are the GeoJSON Features of /sharing, /sharing/zones and /sharing/geofencing,
    `penalties` the routing penalties of /route, `vehicle` "bike", "scooter" or "all". kcal is for a rider of weight_kg:
    each walk, the ride (as a pedelec when the shared bike is electric; on an e-scooter only pushing it) and the
    whole trip. The ride ends at the destination
    where the provider allows parking there, else at the nearest place that it does (by walking to the end), or at a
    parking zone; with park_in_zone, always at a parking zone. Without geofencing (no saved copy), at a parking zone.
    Raises RouteError when no vehicle is in reach or there is nowhere to leave it near the destination.
    """
    from_start = walk.from_point(*origin)
    to_end = walk.from_point(*destination)
    rules = _parking_rules(geofencing) if geofencing and not park_in_zone else None
    returns = {}  # kind -> _return_points

    candidates = []
    for v in vehicles:
        p = v["properties"]
        if vehicle != "all" and p["vehicle"] != vehicle:
            continue
        if p["vehicle"] not in returns:
            returns[p["vehicle"]] = _return_points(G, walk, rules, zones, p["vehicle"], origin, destination, to_end)
        if not returns[p["vehicle"]]:
            continue
        lat, lon = _latlon(v)
        m = _walk_to(walk, from_start, lat, lon)
        if m is None:
            continue
        ride = DETOUR * float(_metres(lat, lon, *returns[p["vehicle"]][0][1]))
        if p.get("range_m") is not None and p["range_m"] < ride + RANGE_MARGIN_M:
            continue
        candidates.append((m / WALK_KMH + ride / MEDIAN_SPEED_KMH, m, v))
    if not candidates:
        kind = {"bike": "e-bike", "scooter": "e-scooter"}.get(vehicle, "e-bike or e-scooter")
        if returns and not any(returns.values()):
            raise RouteError(f"no place within {WALK_MAX_M} m walk of the end where a shared {kind} may be left")
        raise RouteError(f"no free {kind} with enough battery within {WALK_MAX_M} m walk of the start")

    trips = []
    for _, _, v in sorted(candidates, key=lambda c: c[0])[:CANDIDATES]:
        at = _latlon(v)
        kind = v["properties"]["vehicle"]
        for _, ride_to, zone in returns[kind][:CANDIDATES]:  # the best place can be next to the vehicle: no ride
            try:
                ride = find_route(G, at, ride_to, *penalties, weight_kg=weight_kg, scooter=kind == "scooter",
                                  e_bike=kind == "bike" and bool(v["properties"].get("electric")))["features"][0]
                break
            except RouteError:
                continue
        else:
            continue
        if v["properties"].get("range_m") is not None and v["properties"]["range_m"] < ride["properties"]["length_m"] + RANGE_MARGIN_M:
            continue
        ride["properties"]["mode"] = kind
        _, _, paths = from_start
        first = walk.leg(paths[walk.nearest(*at)[0]], origin, at)
        _, _, back = to_end
        last = (walk.leg([], destination, destination) if ride_to == destination
                else walk.leg(back[walk.nearest(*ride_to)[0]], ride_to, destination, reverse=True))
        for leg in (first, last):
            leg["properties"]["kcal"] = round(walk_kcal(leg["properties"]["duration_s"], weight_kg), 1)
        legs = [first, ride, last]
        trips.append({
            "vehicle": v,
            "zone": zone,
            "return_point": {"type": "Feature", "geometry": {"type": "Point", "coordinates": [ride_to[1], ride_to[0]]},
                             "properties": {"rule": "parking_zone" if zone else "anywhere", "at_destination": ride_to == destination,
                                            "name": zone["properties"]["name"] if zone else None}},
            "legs": legs,
            "duration_s": sum(leg["properties"]["duration_s"] for leg in legs),
            "walk_m": round(first["properties"]["length_m"] + last["properties"]["length_m"], 1),
            "ride_m": ride["properties"]["length_m"],
            "ride_s": ride["properties"]["duration_s"],
            "kcal": round(sum(leg["properties"]["kcal"] for leg in legs), 1),
        })
    if not trips:
        raise RouteError("no rideable route from the free vehicles near the start")
    return min(trips, key=lambda t: t["duration_s"])
