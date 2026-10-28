"""A trip with a shared e-bike or e-scooter: walk to a free vehicle, ride it to a parking zone near the end, walk on.

The walks use OSM's walking network (OSMnx network_type="walk": streets with their pavements, footways, pedestrian
zones and steps, but no bike paths or motorways), the ride uses the bike graph with the request's penalties, as /route.
An e-scooter rides by the scooter rules: pushed on footways and in pedestrian zones (routing.route.scooter_pushes).

Which vehicle and which zone: the zone is the one that gets you to the end soonest (walk from it to the end, plus
riding there from the start in a straight line), the vehicle the one that gets you to that zone soonest (walk to it,
plus riding from it to the zone in a straight line), with enough battery for the ride. The CANDIDATES best vehicles are
then routed for real and the quickest trip wins.
"""
from pathlib import Path

import networkx as nx
import numpy as np
import osmnx as ox

from routing.costs import MEDIAN_SPEED_KMH
from routing.graph import CACHE_DIR, PLACE
from routing.route import WALK_KMH, RouteError, edge_coords, find_route

WALK_GRAPH_PATH = CACHE_DIR / "heilbronn_walk.graphml"
WALK_MAX_M = 1000  # furthest walk to a vehicle, and from the parking zone to the end
DETOUR = 1.3  # streets are about this much longer than the straight line, to pick candidates
CANDIDATES = 3  # vehicles routed for real
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


class WalkNetwork:
    """The walking graph with its nodes in arrays, to find the nearest node of many points quickly."""

    def __init__(self, G):
        self.G = G
        self.nodes = list(G.nodes)
        self.lat = np.array([G.nodes[n]["y"] for n in self.nodes], dtype=float)
        self.lon = np.array([G.nodes[n]["x"] for n in self.nodes], dtype=float)

    def nearest(self, lat, lon):
        """(node, metres) of the walking node nearest to (lat, lon)."""
        d = _metres(lat, lon, self.lat, self.lon)
        i = int(np.argmin(d))
        return self.nodes[i], float(d[i])

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
        if len(path) == 1:
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


def plan_sharing_trip(G, walk, vehicles, zones, origin, destination, penalties, vehicle="all", park_in_zone=True):
    """The quickest walk - ride - walk trip from origin to destination (both (lat, lon)).

    `vehicles` and `zones` are the GeoJSON Features of /sharing and /sharing/zones, `penalties` the routing penalties
    of /route, `vehicle` "bike", "scooter" or "all". With park_in_zone the ride ends at a parking zone, else at the
    destination (only if no zone is within WALK_MAX_M of it does it end there anyway).
    Raises RouteError when no vehicle is in reach.
    """
    from_start = walk.from_point(*origin)
    to_end = walk.from_point(*destination)

    end_zone, ride_to = None, destination
    if park_in_zone:
        options = []
        for z in zones:
            lat, lon = _latlon(z)
            m = _walk_to(walk, to_end, lat, lon)
            if m is not None:
                ride = DETOUR * float(_metres(origin[0], origin[1], lat, lon))
                options.append((m / WALK_KMH + ride / MEDIAN_SPEED_KMH, z))
        if options:
            end_zone = min(options, key=lambda o: o[0])[1]
            ride_to = _latlon(end_zone)

    candidates = []
    for v in vehicles:
        p = v["properties"]
        if vehicle != "all" and p["vehicle"] != vehicle:
            continue
        lat, lon = _latlon(v)
        m = _walk_to(walk, from_start, lat, lon)
        if m is None:
            continue
        ride = DETOUR * float(_metres(lat, lon, *ride_to))
        if p.get("range_m") is not None and p["range_m"] < ride + RANGE_MARGIN_M:
            continue
        candidates.append((m / WALK_KMH + ride / MEDIAN_SPEED_KMH, m, v))
    if not candidates:
        kind = {"bike": "e-bike", "scooter": "e-scooter"}.get(vehicle, "e-bike or e-scooter")
        raise RouteError(f"no free {kind} with enough battery within {WALK_MAX_M} m walk of the start")

    trips = []
    for _, _, v in sorted(candidates, key=lambda c: c[0])[:CANDIDATES]:
        at = _latlon(v)
        scooter = v["properties"]["vehicle"] == "scooter"
        try:
            ride = find_route(G, at, ride_to, *penalties, scooter=scooter)["features"][0]
        except RouteError:
            continue
        if v["properties"].get("range_m") is not None and v["properties"]["range_m"] < ride["properties"]["length_m"] + RANGE_MARGIN_M:
            continue
        ride["properties"]["mode"] = v["properties"]["vehicle"]
        _, _, paths = from_start
        first = walk.leg(paths[walk.nearest(*at)[0]], origin, at)
        _, _, back = to_end
        last = walk.leg(back[walk.nearest(*ride_to)[0]], ride_to, destination, reverse=True)
        legs = [first, ride, last]
        trips.append({
            "vehicle": v,
            "zone": end_zone,
            "legs": legs,
            "duration_s": sum(leg["properties"]["duration_s"] for leg in legs),
            "walk_m": round(first["properties"]["length_m"] + last["properties"]["length_m"], 1),
            "ride_m": ride["properties"]["length_m"],
            "ride_s": ride["properties"]["duration_s"],
        })
    if not trips:
        raise RouteError("no rideable route from the free vehicles near the start")
    return min(trips, key=lambda t: t["duration_s"])
