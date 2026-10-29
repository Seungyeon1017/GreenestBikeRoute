"""A-to-B routing on the bike graph, returned as GeoJSON."""
import math
import threading
import weakref
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import networkx as nx
import numpy as np
import shapely
from shapely import LineString, Point, STRtree
from shapely.ops import substring

from routing.calories import DEFAULT_WEIGHT_KG, ride_kcal, route_climb, walk_kcal
from routing.costs import BAD_AIR_RISK, BUMPY_ROUGHNESS, DEFAULT_BUMP_PENALTY, DEFAULT_DANGER_PENALTY, DEFAULT_DARK_PENALTY, DEFAULT_LIT, \
    DEFAULT_PM_PENALTY, DEFAULT_PM_RISK, DEFAULT_PREFER_BIKE_FRIENDLY, DEFAULT_ROUGHNESS, DEFAULT_SHADE, DEFAULT_SHADE_PENALTY, DEFAULT_STOP_GO, \
    DEFAULT_STOP_PENALTY, LIFT_WAIT_M, MEDIAN_SPEED_KMH, STOP_GO_HEAVY, edge_cost, osm_way_ids
from routing.shadow import sun_position

# Start/end points further than this from any street are treated as outside Heilbronn.
MAX_SNAP_M = 500
# Routing temporarily splits streets in the shared graph, so one request at a time may use it.
_GRAPH_LOCK = threading.Lock()
# Departure times without a time zone are Heilbronn local time.
LOCAL_TZ = ZoneInfo("Europe/Berlin")
# Sunrise and sunset: the top of the sun on the horizon, refraction included (the usual -0.833 deg).
SUNSET_ALTITUDE = -0.833
# A street users reported closed, by too few people yet to close it (backend/reports.py), costs this many times as
# much: routes ride up to this much further to avoid it, but still use it when there is no sensible way round.
REPORTED_CLOSED_FACTOR = 4
# E-scooters must not ride on footways or in pedestrian zones, even where bikes may (eKFV §10): on those a scooter
# route pushes the scooter at walking pace, so they cost and take as long as walking. Shared paths signed for bikes
# (Zeichen 240/241, bicycle=designated) are bike paths, which scooters must use.
SCOOTER_PUSH_HIGHWAYS = {"footway", "path", "pedestrian"}
WALK_KMH = 4.8
# day_routes tries departure times this many minutes apart.
DAY_STEP_MIN = 15


class RouteError(ValueError):
    """The request can't be routed (point off the map, no connection, ...)."""


class _Plane:
    """Equirectangular metres around a latitude; good to well under 1% across a city."""

    def __init__(self, lat0):
        self.scale = 111_320
        self.cos_lat = math.cos(math.radians(lat0))

    def to_m_point(self, lon, lat):
        return lon * self.cos_lat * self.scale, lat * self.scale

    def to_lonlat_point(self, x, y):
        return x / (self.cos_lat * self.scale), y / self.scale

    def to_m(self, line):
        return LineString([self.to_m_point(x, y) for x, y in line.coords])

    def to_lonlat(self, line):
        return LineString([self.to_lonlat_point(x, y) for x, y in line.coords])


def _edge_line(G, u, v, d):
    """The edge's street as (lon, lat) from u to v: its OSM geometry, or a straight line between the corners."""
    if "geometry" in d:
        return d["geometry"]
    return LineString([(G.nodes[u]["x"], G.nodes[u]["y"]), (G.nodes[v]["x"], G.nodes[v]["y"])])


class _SnapIndex:
    """The streets of the main network as lines in metres around the graph's mean latitude, in an STRtree.

    Only streets of the main network count: a point next to a cut-off island (say a service road whose
    only link is a footway bikes may not use) snaps to the nearest street that can be routed from.
    Building it takes ~0.3 s on Heilbronn, so it is built once per graph (see _snap_index).
    """

    def __init__(self, G):
        self.size = (G.number_of_nodes(), G.number_of_edges())
        self.lat0 = sum(y for _, y in G.nodes(data="y")) / G.number_of_nodes()
        main = max(nx.weakly_connected_components(G), key=len)
        self.edges = [(u, v, k) for u, v, k in G.edges(keys=True) if u in main and v in main]
        plane = _Plane(self.lat0)
        scale = (plane.cos_lat * plane.scale, plane.scale)
        lines = shapely.transform([_edge_line(G, u, v, G.edges[u, v, k]) for u, v, k in self.edges], lambda xy: xy * scale)
        self.tree = STRtree(lines)


# One _SnapIndex per graph; a graph whose node or edge count changed gets a new one.
_SNAP_INDEXES = weakref.WeakKeyDictionary()


def _snap_index(G):
    index = _SNAP_INDEXES.get(G)
    if index is None or index.size != (G.number_of_nodes(), G.number_of_edges()):
        index = _SNAP_INDEXES[G] = _SnapIndex(G)
    return index


def _nearest_edge(G, index, lat, lon, extra=()):
    """The edge (u, v, key, data) closest to (lat, lon), its distance in metres and the point on it.

    Candidates are the streets of `index` still in G, plus the edges in `extra` (pieces of streets split
    since the index was built). The index only narrows them down: each candidate is measured in metres
    around the point's own latitude.
    """
    plane = _Plane(lat)
    point = Point(plane.to_m_point(lon, lat))
    near = Point(_Plane(index.lat0).to_m_point(lon, lat))
    nearest_m = index.tree.query_nearest(near, return_distance=True)[1][0]  # several on a tie (a two-way street)
    # The two projections differ by well under 1% within 50 km, so 5% plus a metre keeps the nearest street.
    # A point that far from every street will be refused anyway: then the index's nearest is enough.
    found = (index.tree.query(near, predicate="dwithin", distance=nearest_m * 1.05 + 1)
             if nearest_m <= 2 * MAX_SNAP_M else index.tree.query_nearest(near))
    edges = [index.edges[i] for i in sorted(found) if G.has_edge(*index.edges[i])] + list(extra)
    lines = [plane.to_m(_edge_line(G, u, v, G.edges[u, v, k])) for u, v, k in edges]
    i = min(range(len(lines)), key=lambda i: lines[i].distance(point))
    u, v, key = edges[i]
    on_street = lines[i].interpolate(lines[i].project(point))
    return (u, v, key, G.edges[u, v, key]), point.distance(on_street), plane.to_lonlat_point(on_street.x, on_street.y)


def _metres_apart(G, node, point_lonlat, plane):
    a = plane.to_m_point(G.nodes[node]["x"], G.nodes[node]["y"])
    return Point(a).distance(Point(plane.to_m_point(*point_lonlat)))


def segment_id(u, v):
    """A street segment (graph edge between two junctions, either direction) as riders' closure reports name it:
    "u-v" with the smaller OSM node id first."""
    return f"{min(u, v)}-{max(u, v)}"


def _split_edge(G, u, v, data, node, point_lonlat, plane):
    """Replace edge u->v by u->node and node->v, cut where it passes `point_lonlat`.

    A bridge crest inside the edge (`crest`, from routing.elevation) stays with the piece it is on, and the new
    node gets the height on the line through it, so /route/grade still shows the climb."""
    line = plane.to_m(_edge_line(G, u, v, data))
    cut = line.project(Point(plane.to_m_point(*point_lonlat)))
    share = cut / line.length
    first = plane.to_lonlat(substring(line, 0, cut))
    second = plane.to_lonlat(substring(line, cut, line.length))
    crests = (None, None)
    if data.get("crest") is not None:
        frac, top = data["crest"]
        crests = ((frac / share, top) if frac < share else None, ((frac - share) / (1 - share), top) if frac > share else None)
        hu, hv = G.nodes[u].get("elevation"), G.nodes[v].get("elevation")
        if hu is not None and hv is not None:
            G.nodes[node]["elevation"] = (hu + (top - hu) * share / frac if share <= frac
                                          else top + (hv - top) * (share - frac) / (1 - frac))
    # Both pieces keep the segment of the street they were cut from, for riders' closure reports.
    segment = data.get("segment", segment_id(u, v))
    G.add_edge(u, node, **{**data, "length": data["length"] * share, "geometry": first, "lift_end": False, "crest": crests[0],
                           "segment": segment})
    G.add_edge(node, v, **{**data, "length": data["length"] * (1 - share), "geometry": second, "lift_start": False,
                           "crest": crests[1], "segment": segment})


@contextmanager
def _snapped_ends(G, origin, destination):
    """Yield graph nodes for origin and destination, both (lat, lon).

    Each end point is put on the street nearest to it: that street is split in two at the point, and
    the point becomes a node, in both directions. G is restored when the block ends.
    """
    undo = []  # (node, [(u, v, key, data) removed edges]) in the order they were made
    ends = []
    try:
        with _GRAPH_LOCK:
            index = _snap_index(G)  # before the first split changes G
            for label, (lat, lon) in (("start", origin), ("end", destination)):
                # The end may lie on a piece of the street the start split.
                pieces = [e for node, _ in undo for e in (*G.in_edges(node, keys=True), *G.out_edges(node, keys=True))]
                (u, v, key, data), dist, point_lonlat = _nearest_edge(G, index, lat, lon, pieces)
                if dist > MAX_SNAP_M:
                    raise RouteError(f"{label} point is {dist:.0f} m from the nearest Heilbronn street")
                plane = _Plane(lat)
                corner = next((n for n in (u, v) if _metres_apart(G, n, point_lonlat, plane) < 1), None)
                if corner is not None:  # the point is a junction already, nothing to split
                    ends.append(corner)
                    continue
                node = f"snap-{label}"
                G.add_node(node, x=point_lonlat[0], y=point_lonlat[1])
                removed = []
                undo.append((node, removed))  # recorded first, so an error while splitting is undone too
                # Split the street in both directions (a one-way street has only one), so the point can be
                # reached and left either way.
                for a, b in ((u, v), (v, u)):
                    for k, d in list((G.get_edge_data(a, b) or {}).items()):
                        # Merged ways list their ids in riding order, so the two directions list them reversed.
                        if set(osm_way_ids(d.get("osmid"))) != set(osm_way_ids(data.get("osmid"))):
                            continue
                        # A way can have parallel edges between the same corners (a loop, a stub): split only
                        # the ones the point is on.
                        if plane.to_m(_edge_line(G, a, b, d)).distance(Point(plane.to_m_point(*point_lonlat))) > 1:
                            continue
                        _split_edge(G, a, b, d, node, point_lonlat, plane)
                        removed.append((a, b, k, d))
                        G.remove_edge(a, b, k)
                ends.append(node)
            if ends[0] == ends[1]:
                raise RouteError("start and end snap to the same spot")
            yield ends
    finally:
        for node, removed in reversed(undo):
            G.remove_node(node)
            for a, b, k, d in removed:
                G.add_edge(a, b, key=k, **d)


def _roughness(d):
    return DEFAULT_ROUGHNESS if d["roughness"] is None else d["roughness"]


def _pm_risk(d):
    return d.get("pm_prior", DEFAULT_PM_RISK) if d.get("pm_risk") is None else d["pm_risk"]


def _stop_go(d):
    return DEFAULT_STOP_GO if d.get("stop_go") is None else d["stop_go"]


def _speed_kmh(d):
    return MEDIAN_SPEED_KMH if d.get("speed_kmh") is None else d["speed_kmh"]


def _shade(d, slot):
    return DEFAULT_SHADE if d.get("shade") is None else d["shade"][slot]


def _lit(d):
    return DEFAULT_LIT if d.get("lit") is None else d["lit"]


def local_time(depart_time):
    """`depart_time` in Heilbronn local time; one without a time zone is taken as local time already."""
    return depart_time.replace(tzinfo=LOCAL_TZ) if depart_time.tzinfo is None else depart_time.astimezone(LOCAL_TZ)


def sky(G, depart_time):
    """(shade slot, dark) for a trip leaving at `depart_time` (a datetime, or None when the time doesn't matter).

    dark: the sun is below the horizon, after sunset or before sunrise on that date, so unlit streets cost extra.
    Shade slot: by day, the index into G.graph["shade_slots"] of the slot nearest the time of day (shade is
    computed for a few hours of one summer day); None at night, without a time or without shade data.
    """
    if depart_time is None:
        return None, False
    local = local_time(depart_time)
    if sun_position(local)[1] < SUNSET_ALTITUDE:
        return None, True
    slots = [datetime.fromisoformat(s) for s in G.graph.get("shade_slots", ())]
    if not slots:
        return None, False
    minutes = local.hour * 60 + local.minute
    return min(range(len(slots)), key=lambda i: abs(slots[i].hour * 60 + slots[i].minute - minutes)), False


def _plan(G, penalties, scooter=False):
    """The request's penalties with depart_time resolved by sky() into (shade slot, dark), plus whether the route is
    for an e-scooter: what _cost needs."""
    *weights, depart_time = penalties
    return (*weights, *sky(G, depart_time), scooter)


def scooter_pushes(d):
    """Whether an e-scooter must be pushed along the edge: a footway, path or pedestrian street not signed for bikes."""
    highways = {str(h) for h in (d["highway"] if isinstance(d.get("highway"), list) else [d.get("highway")])}
    bicycle = d.get("bicycle") if isinstance(d.get("bicycle"), list) else [d.get("bicycle")]
    return highways <= SCOOTER_PUSH_HIGHWAYS and "designated" not in bicycle


def _cost(d, plan):
    bump_penalty, danger_penalty, pm_penalty, stop_penalty, prefer_time, shade_penalty, dark_penalty, prefer_bike_friendly, \
        slot, dark, scooter = plan
    push = MEDIAN_SPEED_KMH / WALK_KMH if scooter and scooter_pushes(d) else 1
    return push * edge_cost(d["length"], _roughness(d), bump_penalty,
                     d.get("danger", 0.0), danger_penalty, _pm_risk(d), pm_penalty, _stop_go(d), stop_penalty,
                     lift_ends=d.get("lift_start", False) + d.get("lift_end", False),
                     speed_kmh=_speed_kmh(d) if prefer_time else MEDIAN_SPEED_KMH,
                     sun=0.0 if slot is None else 1 - _shade(d, slot), shade_penalty=shade_penalty,
                     dark=1 - _lit(d) if dark else 0.0, dark_penalty=dark_penalty,
                     bike_friendly=d.get("bike_friendly", False), prefer_bike_friendly=prefer_bike_friendly)


def street_scores(G, bump_penalty=DEFAULT_BUMP_PENALTY, danger_penalty=DEFAULT_DANGER_PENALTY,
                  pm_penalty=DEFAULT_PM_PENALTY, stop_penalty=DEFAULT_STOP_PENALTY, prefer_time=False,
                  shade_penalty=DEFAULT_SHADE_PENALTY, dark_penalty=DEFAULT_DARK_PENALTY,
                  prefer_bike_friendly=DEFAULT_PREFER_BIKE_FRIENDLY, depart_time=None):
    """Each street once (a two-way street is two edges) as a GeoJSON LineString with `score` 0-100: its percentile, by
    street length, among Heilbronn streets ranked by routing cost per metre for these penalties (as find_route),
    cheapest at 100 (higher = better).

    The cost is routing's (_cost): roughness, overtaking spots and air points snapped to the street, stop-and-go
    and lifts, plus by day sun or after dark unlit streets when depart_time is given; with prefer_time, slow streets
    cost more. Per metre, so a short street with one overtaking spot ranks low. All penalties 0 (and no prefer_time)
    make every street cost the same: all score 50.
    """
    plan = _plan(G, (bump_penalty, danger_penalty, pm_penalty, stop_penalty, prefer_time, shade_penalty, dark_penalty,
                     prefer_bike_friendly, depart_time))
    streets = {}
    for u, v, d in G.edges(data=True):
        street = (min(u, v), max(u, v), str(d["osmid"]), round(float(d["length"]), 1))
        length = max(float(d["length"]), 1.0)  # a few edges are a few cm long
        per_m = _cost(d, plan) / length
        if street not in streets or per_m < streets[street][0]:
            streets[street] = (per_m, length, u, v, d)
    ranked = sorted(streets.values(), key=lambda s: s[0])
    per_m = np.array([s[0] for s in ranked])
    # Length of the streets costing more than each one, plus half of those costing the same (midpoint rank): the
    # many streets without any data all cost the routing defaults.
    above = np.concatenate([np.cumsum([s[1] for s in ranked][::-1])[::-1], [0.0]])
    first, after = np.searchsorted(per_m, per_m, side="left"), np.searchsorted(per_m, per_m, side="right")
    worse = (above[first] + above[after]) / 2
    features = [
        {"type": "Feature",
         "geometry": {"type": "LineString", "coordinates": [[round(x, 6), round(y, 6)] for x, y in edge_coords(G, u, v, d)]},
         "properties": {"score": round(100 * float(w) / above[0], 1)}}
        for (_, _, u, v, d), w in zip(ranked, worse)
    ]
    return {"type": "FeatureCollection", "features": features}


def route_duration(G, edges, scooter=False):
    """Expected riding time in s of a route given as (u, v, data) edges: speed_map per street (unmeasured streets at
    the median speed), plus waiting for each lift at the median speed. With `scooter`, pushed edges (scooter_pushes)
    at walking pace."""
    lifts = sum(1 for _, n, _ in edges[:-1] if "elevator" in str(G.nodes[n].get("highway")))
    duration = lifts * LIFT_WAIT_M / (MEDIAN_SPEED_KMH / 3.6)
    for _, _, d in edges:
        kmh = WALK_KMH if scooter and scooter_pushes(d) else _speed_kmh(d)
        duration += float(d["length"]) / (kmh / 3.6)
    return duration


# Roads a footway, bike path or access road without a name can run beside (see _NamedRoads).
ROAD_HIGHWAYS = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
                 "living_street", "service", "motorway_link", "trunk_link", "primary_link", "secondary_link",
                 "tertiary_link"}
# An unnamed way runs beside a named road when at least 2 of 3 points along it are this close to the road and head the
# same way (either direction) to within this angle; a crossing takes the road it crosses within CROSSING_M.
ALONG_M = 20
ALONG_DEG = 25
CROSSING_M = 3
# The kind of way a stretch is on, from its OSM tags, in this order; null for an ordinary road.
WAY_KINDS = ("crossing", "sidewalk", "cycleway", "footway", "path", "track", "service", "pedestrian")


def _tags(d, key):
    value = d.get(key)
    return {str(v) for v in (value if isinstance(value, list) else [value])}


def _street_name(d):
    name = d.get("name")
    return (name[0] if isinstance(name, list) else name) or None


def way_kind(d):
    """What kind of way the edge is (WAY_KINDS), from highway=* and footway=*; None for an ordinary road."""
    tags = _tags(d, "highway") | _tags(d, "footway")
    return next((kind for kind in WAY_KINDS if kind in tags), None)


class _NamedRoads:
    """The named roads (ROAD_HIGHWAYS) as lines in metres around the graph's mean latitude, in an STRtree."""

    def __init__(self, G):
        self.plane = _Plane(sum(y for _, y in G.nodes(data="y")) / G.number_of_nodes())
        roads = [(u, v, d) for u, v, d in G.edges(data=True)
                 if _street_name(d) and _tags(d, "highway") & ROAD_HIGHWAYS]
        self.names = [_street_name(d) for *_, d in roads]
        self.lines = [self.plane.to_m(_edge_line(G, u, v, d)) for u, v, d in roads]
        self.tree = STRtree(self.lines)

    def along(self, line, crossing=False):
        """Name of the road the line (lon, lat) runs beside, or for a crossing the road it crosses; None if none."""
        line = self.plane.to_m(line)
        found = self.tree.query(line, predicate="dwithin", distance=CROSSING_M if crossing else ALONG_M)
        if crossing or not len(found):
            return min(((line.distance(self.lines[i]), self.names[i]) for i in found), default=(0, None))[1]
        samples = [line.interpolate(f, normalized=True) for f in (0.2, 0.5, 0.8)]
        headings = [_heading(line, p) for p in samples]
        best = {}
        for i in found:
            road, matched, metres = self.lines[i], 0, 0.0
            for p, heading in zip(samples, headings):
                dist = road.distance(p)
                turn = abs(heading - _heading(road, p)) % 180
                if dist <= ALONG_M and min(turn, 180 - turn) <= ALONG_DEG:
                    matched, metres = matched + 1, metres + dist
            if matched >= 2:
                best[self.names[i]] = max(best.get(self.names[i], (0, 0.0)), (matched, -metres))
        return max(best, key=best.get, default=None)


def _heading(line, point):
    """Direction in degrees of `line` (metres) where it passes nearest to `point`, over 6 m."""
    at = line.project(point)
    a, b = line.interpolate(max(at - 3, 0)), line.interpolate(min(at + 3, line.length))
    return math.degrees(math.atan2(b.y - a.y, b.x - a.x))


# One _NamedRoads per graph; rebuilt when its nodes change, not counting the temporary start and end points.
_NAMED_ROADS = weakref.WeakKeyDictionary()


def _named_roads(G):
    size = G.number_of_nodes() - sum(n in G for n in ("snap-start", "snap-end"))
    cached = _NAMED_ROADS.get(G)
    if cached is None or cached[0] != size:
        cached = _NAMED_ROADS[G] = (size, _NamedRoads(G))
    return cached[1]


# Fields of a stretch (see _stretches) that are length-weighted means over its edges with data.
_STRETCH_MEANS = ("roughness", "pm_risk", "stop_go", "speed_kmh", "shade", "lit")


def street_name(G, u, v, d):
    """The street name of edge (u, v); a way without one (a sidewalk, a bike path) takes the name of the road it runs
    beside or, for a crossing, crosses. None if there is neither."""
    name = _street_name(d)
    return name or _named_roads(G).along(_edge_line(G, u, v, d), crossing=way_kind(d) == "crossing")


def _edge_facts(G, u, v, d, slot, dark, scooter):
    """What a stretch shows for one edge: street name, kind of way, the measured values (None where unknown) and
    `flags`, the bad or good things it counts towards (the route's bumpy_m, danger_points, ... with the same
    thresholds). A way without a name (a sidewalk, a bike path) takes the name of the road it runs beside, `along`."""
    name, way = _street_name(d), way_kind(d)
    beside = None if name else _named_roads(G).along(_edge_line(G, u, v, d), crossing=way == "crossing")
    facts = {
        "name": name or beside,
        "way": way,
        "along": beside is not None,
        "roughness": d["roughness"],
        "danger_points": int(d.get("danger_points", 0)),
        "pm_risk": d.get("pm_risk"),
        "stop_go": d.get("stop_go"),
        "speed_kmh": d.get("speed_kmh"),
        "shade": d["shade"][slot] if slot is not None and d.get("shade") is not None else None,
        "lit": d.get("lit"),
        "bike_friendly": bool(d.get("bike_friendly")),
        "pushed": bool(scooter and scooter_pushes(d)),
    }
    flags = [key for key, bad in (
        ("bumpy_m", facts["roughness"] is not None and facts["roughness"] >= BUMPY_ROUGHNESS),
        ("danger_points", facts["danger_points"] > 0),
        ("bad_air_m", facts["pm_risk"] is not None and facts["pm_risk"] >= BAD_AIR_RISK),
        ("stop_go_m", facts["stop_go"] is not None and facts["stop_go"] >= STOP_GO_HEAVY),
        ("sunny_m", facts["shade"] is not None and facts["shade"] < 0.5),
        ("unlit_m", dark and facts["lit"] is not None and facts["lit"] < 0.5),
        ("bike_friendly_m", facts["bike_friendly"]),
    ) if bad]
    return {**facts, "flags": flags}


def _stretches(pieces):
    """The route as stretches for the map: runs of consecutive edges on the same street with the same flags, from
    `pieces` [(first coordinate index, last coordinate index, length, _edge_facts, segment_id)]. Values are
    length-weighted over the edges with data. Unnamed ways are told apart by their kind; a sidewalk joins the road it
    runs beside, and then the stretch has no single `way`. `segments` are the street segments it rides, for reporting
    the stretch closed."""
    out, start_m = [], 0.0
    for first, last, length, facts, segment in pieces:
        prev = out[-1] if out else None
        key = (facts["name"] or facts["way"], facts["flags"], facts["pushed"])
        if prev is None or (prev["name"] or prev["way"], prev["flags"], prev["pushed"]) != key:
            prev = {"from_index": first, "start_m": start_m, "length_m": 0.0, "name": facts["name"], "way": facts["way"],
                    "along": facts["along"], "danger_points": 0, "bike_friendly": facts["bike_friendly"],
                    "pushed": facts["pushed"], "flags": facts["flags"], "segments": [],
                    "_sums": {k: [0.0, 0.0] for k in _STRETCH_MEANS}}
            out.append(prev)
        elif prev["way"] != facts["way"]:
            prev["way"] = None
        prev["along"] = prev["along"] and facts["along"]
        prev["to_index"] = last
        prev["length_m"] += length
        if segment not in prev["segments"]:
            prev["segments"].append(segment)
        prev["danger_points"] += facts["danger_points"]
        for k in _STRETCH_MEANS:
            if facts[k] is not None:
                prev["_sums"][k][0] += float(facts[k]) * length
                prev["_sums"][k][1] += length
        start_m += length
    means = [{k: round(total / known, 3) if known else None for k, (total, known) in s.pop("_sums").items()} for s in out]
    return [{"from_index": s["from_index"], "to_index": s["to_index"], "start_m": round(s["start_m"], 1),
             "length_m": round(s["length_m"], 1), "name": s["name"], "way": s["way"], "along": s["along"],
             "flags": s["flags"], "roughness": m["roughness"],
             "danger_points": s["danger_points"], "pm_risk": m["pm_risk"], "stop_go": m["stop_go"],
             "speed_kmh": m["speed_kmh"], "shade": m["shade"], "lit": m["lit"], "bike_friendly": s["bike_friendly"],
             "pushed": s["pushed"], "segments": s["segments"]} for s, m in zip(out, means)]


def _route_feature(G, a, b, penalties, weight_kg=DEFAULT_WEIGHT_KG, e_bike=False, scooter=False):
    """The cheapest route between graph nodes a and b for `penalties` (the six penalties, prefer_time,
    prefer_bike_friendly and depart_time), as one GeoJSON Feature. kcal is for a rider of weight_kg; for an e-scooter
    with `scooter`."""
    bump_penalty, danger_penalty, pm_penalty, stop_penalty, prefer_time, shade_penalty, dark_penalty, prefer_bike_friendly, \
        depart_time = penalties
    plan = _plan(G, penalties, scooter)
    slot, dark = plan[-3:-1]
    path = _path(G, a, b, plan)

    lifts = sum(1 for n in path[1:-1] if "elevator" in str(G.nodes[n].get("highway")))
    coords, length, rough_len, measured_len, estimated_len = [], 0.0, 0.0, 0.0, 0.0
    danger, danger_points, pm_len, pm_measured_len = 0.0, 0, 0.0, 0.0
    stop_len, stop_measured_len = 0.0, 0.0
    shade_len, shade_known_len, lit_len, lit_known_len = 0.0, 0.0, 0.0, 0.0
    bumpy_m, bad_air_m, stop_go_m, sunny_m, unlit_m, bike_friendly_m, pushed_m = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    speed_measured_len = 0.0
    closures, edges, pieces = set(), [], []
    for u, v in zip(path[:-1], path[1:]):
        d = _edge(G, u, v, plan)
        edges.append((u, v, d))
        if d.get("closure"):
            closures.add(str(d["osmid"]))
        pts = edge_coords(G, u, v, d)
        first = max(len(coords) - 1, 0)
        coords.extend(pts if not coords else pts[1:])
        edge_len = float(d["length"])  # numpy float when loaded from GraphML
        pieces.append((first, len(coords) - 1, edge_len, _edge_facts(G, u, v, d, slot, dark, scooter),
                       d.get("segment") or segment_id(u, v)))
        length += edge_len
        if d.get("roughness_source") == "estimated":
            estimated_len += edge_len
        elif d["roughness"] is not None:
            measured_len += edge_len
            rough_len += d["roughness"] * edge_len
        if d["roughness"] is not None and d["roughness"] >= BUMPY_ROUGHNESS:
            bumpy_m += edge_len
        danger += d.get("danger", 0.0)
        danger_points += d.get("danger_points", 0)
        if d.get("pm_risk") is not None:
            pm_measured_len += edge_len
            pm_len += d["pm_risk"] * edge_len
            bad_air_m += edge_len * (d["pm_risk"] >= BAD_AIR_RISK)
        if d.get("stop_go") is not None:
            stop_measured_len += edge_len
            stop_len += d["stop_go"] * edge_len
            stop_go_m += edge_len * (d["stop_go"] >= STOP_GO_HEAVY)
        if d.get("shade") is not None:
            shade_known_len += edge_len
            if slot is not None:
                shade_len += d["shade"][slot] * edge_len
                sunny_m += (1 - d["shade"][slot]) * edge_len
        if d.get("lit") is not None:
            lit_known_len += edge_len
            lit_len += d["lit"] * edge_len
            unlit_m += (1 - d["lit"]) * edge_len
        if d.get("bike_friendly"):
            bike_friendly_m += edge_len
        if scooter and scooter_pushes(d):
            pushed_m += edge_len
        if d.get("speed_kmh") is not None:
            speed_measured_len += edge_len
    duration, climb = route_duration(G, edges, scooter), route_climb(G, edges)

    properties = {
        "bump_penalty": bump_penalty,
        "danger_penalty": danger_penalty,
        "pm_penalty": pm_penalty,
        "stop_penalty": stop_penalty,
        "prefer_time": prefer_time,
        "shade_penalty": shade_penalty,
        "dark_penalty": dark_penalty,
        "prefer_bike_friendly": prefer_bike_friendly,
        "depart_time": local_time(depart_time).isoformat(timespec="minutes") if depart_time else None,
        # Sun above the horizon at depart_time (null without one): shade counts by day, lighting after dark.
        "daylight": None if depart_time is None else not dark,
        "shade_slot": G.graph["shade_slots"][slot] if slot is not None else None,
        "length_m": round(length, 1),
        # Expected riding time from speed_map (unmeasured streets at the median speed), lifts included.
        "duration_s": round(duration),
        # Total ascent, bridge humps included (null without elevation data), and the rough energy use for it
        # and the riding time, see routing/calories.py. On an e-scooter only pushing it counts, as walking.
        "climb_m": None if climb is None else round(climb, 1),
        "kcal": round(walk_kcal(pushed_m / (WALK_KMH / 3.6), weight_kg) if scooter
                      else ride_kcal(duration, climb or 0.0, weight_kg, e_bike), 1),
        "speed_measured_share": round(speed_measured_len / length, 2),
        # Length-weighted over the measured part of the route only.
        "mean_roughness": round(rough_len / measured_len, 1) if measured_len else None,
        "measured_share": round(measured_len / length, 2),
        # Roughness estimated from nearby measured streets (estimation/README.md); the rest of the route is unknown.
        "estimated_share": round(estimated_len / length, 2),
        # Overtaking spots (danger_zones) on the route and their summed Risk Index Overtaking.
        "danger_points": danger_points,
        "danger_risk": round(danger, 2),
        # Length-weighted over the part of the route with air_quality measurements.
        "mean_pm_risk": round(pm_len / pm_measured_len, 3) if pm_measured_len else None,
        "pm_measured_share": round(pm_measured_len / length, 2),
        # Length-weighted over the part of the route with traffic_flow measurements.
        "mean_stop_go": round(stop_len / stop_measured_len, 3) if stop_measured_len else None,
        "stop_measured_share": round(stop_measured_len / length, 2),
        # Length-weighted share in shade at shade_slot, over the part of the route with shade data; null unless by day.
        "mean_shade": round(shade_len / shade_known_len, 3) if slot is not None and shade_known_len else None,
        "shade_known_share": round(shade_known_len / length, 2),
        # Length-weighted chance the streets are lit at night, over the part of the route with lighting data.
        "mean_lit": round(lit_len / lit_known_len, 3) if lit_known_len else None,
        "lit_known_share": round(lit_known_len / length, 2),
        # Lifts the route rides through; each costs stop_penalty x 25 m.
        "lifts": lifts,
        # Streets on the route that users reported closed (backend/reports.py) and that it still rides.
        "reported_closures": len(closures),
        # Metres on bad streets (the worst tenth of measured street length for that factor), to compare routes by.
        "bumpy_m": round(bumpy_m),
        "bad_air_m": round(bad_air_m),
        "stop_go_m": round(stop_go_m),
        # Metres in the sun by day / on probably unlit streets after dark (share not in shade / not lit, over the
        # streets with data); null at other times.
        "sunny_m": round(sunny_m) if slot is not None else None,
        "unlit_m": round(unlit_m) if dark else None,
        # Metres on bike paths, bike lanes and bike routes (/bike-friendly-streets).
        "bike_friendly_m": round(bike_friendly_m),
        # Metres an e-scooter is pushed (footways and pedestrian streets); 0 for bikes.
        "pushed_m": round(pushed_m),
        # The route as stretches with what is measured on them, to show when the rider points at the line.
        "segments": _stretches(pieces),
    }
    return {"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords}, "properties": properties}


def nearest_street(G, lat, lon):
    """The street of the main network nearest to (lat, lon): (u, v, data, metres away)."""
    with _GRAPH_LOCK:
        (u, v, _, d), dist, _ = _nearest_edge(G, _snap_index(G), lat, lon)
    return u, v, d, dist


def set_closures(G, closures):
    """Set edge attribute `closure` ("closed", or "reported" / "unconfirmed", which only cost more) on the streets in
    `closures`, {(u, v): status}, in both directions, and remove it from every other street. Streets no longer in G
    are skipped."""
    closures = dict(closures)
    with _GRAPH_LOCK:
        if G.graph.get("closures") == closures:
            return
        for u, v in G.graph.get("closures", {}):
            for a, b in ((u, v), (v, u)):
                for d in (G.get_edge_data(a, b) or {}).values():
                    d.pop("closure", None)
        for (u, v), status in closures.items():
            for a, b in ((u, v), (v, u)):
                for d in (G.get_edge_data(a, b) or {}).values():
                    d["closure"] = status
        G.graph["closures"] = closures


def _snapped(n):
    return isinstance(n, str) and n.startswith("snap-")


def _route_cost(u, v, d, plan):
    """_cost, REPORTED_CLOSED_FACTOR times as much on a street reported closed; None (can't be ridden) on a closed
    street, except its piece up to a start or end point on it, so places on a closed street can still be reached."""
    closure = d.get("closure")
    if closure == "closed" and not (_snapped(u) or _snapped(v)):
        return None
    return _cost(d, plan) * (REPORTED_CLOSED_FACTOR if closure else 1)


def _path(G, a, b, plan):
    """The nodes of the cheapest route between graph nodes a and b for `plan` (see _plan)."""
    # MultiDiGraph: between two nodes there can be parallel edges; use the cheapest. None hides a closed street.
    def weight(u, v, parallel):
        return min((c for d in parallel.values() if (c := _route_cost(u, v, d, plan)) is not None), default=None)

    try:
        return nx.shortest_path(G, a, b, weight=weight)
    except nx.NetworkXNoPath:
        raise RouteError("no bike route between these points") from None


def _edge(G, u, v, plan):
    """The cheapest of the parallel edges from u to v that can be ridden."""
    return min((d for d in G[u][v].values() if _route_cost(u, v, d, plan) is not None),
               key=lambda d: _route_cost(u, v, d, plan))


def edge_coords(G, u, v, d):
    """[lon, lat] points of edge (u, v) with data d, from u to v."""
    if "geometry" in d:  # OSMnx edge geometries run from u to v
        return [[float(x), float(y)] for x, y in d["geometry"].coords]
    return [[float(G.nodes[n]["x"]), float(G.nodes[n]["y"])] for n in (u, v)]


@contextmanager
def route_edges(G, origin, destination, penalties):
    """Yield the edges (u, v, data) of the route find_route picks from origin to destination, both (lat, lon).

    Start and end may be temporary nodes on a split street (see _snapped_ends), which exist only inside the block.
    """
    plan = _plan(G, penalties)
    with _snapped_ends(G, origin, destination) as (a, b):
        path = _path(G, a, b, plan)
        yield [(u, v, _edge(G, u, v, plan)) for u, v in zip(path[:-1], path[1:])]


def find_route(G, origin, destination, bump_penalty=DEFAULT_BUMP_PENALTY,
               danger_penalty=DEFAULT_DANGER_PENALTY, pm_penalty=DEFAULT_PM_PENALTY,
               stop_penalty=DEFAULT_STOP_PENALTY, prefer_time=False, shade_penalty=DEFAULT_SHADE_PENALTY,
               dark_penalty=DEFAULT_DARK_PENALTY, prefer_bike_friendly=DEFAULT_PREFER_BIKE_FRIENDLY, depart_time=None,
               weight_kg=DEFAULT_WEIGHT_KG, e_bike=False, scooter=False):
    """Cheapest route from origin to destination, both (lat, lon), as a GeoJSON FeatureCollection.

    All penalties 0 give the shortest route; higher values take longer detours to avoid rough
    streets (bump_penalty), spots where cars overtook closely (danger_penalty), streets with bad
    air (pm_penalty) and streets where bikes keep stopping (stop_penalty). prefer_time weighs each
    street by its riding time at the measured speed instead of its length. With a depart_time (datetime),
    sunny streets cost extra by day (shade_penalty) and unlit streets after dark (dark_penalty).
    prefer_bike_friendly makes streets that are not bike paths, bike lanes or bike routes cost extra.
    With `scooter`, the route is for an e-scooter, pushed where it must not ride (scooter_pushes).
    """
    penalties = (bump_penalty, danger_penalty, pm_penalty, stop_penalty, prefer_time, shade_penalty, dark_penalty,
                 prefer_bike_friendly, depart_time)
    with _snapped_ends(G, origin, destination) as (a, b):
        feature = _route_feature(G, a, b, penalties, weight_kg, e_bike, scooter)
    return {"type": "FeatureCollection", "features": [feature]}


def compare_routes(G, origin, destination, bump_penalty=DEFAULT_BUMP_PENALTY,
                   danger_penalty=DEFAULT_DANGER_PENALTY, pm_penalty=DEFAULT_PM_PENALTY,
                   stop_penalty=DEFAULT_STOP_PENALTY, prefer_time=False, shade_penalty=DEFAULT_SHADE_PENALTY,
                   dark_penalty=DEFAULT_DARK_PENALTY, prefer_bike_friendly=DEFAULT_PREFER_BIKE_FRIENDLY, depart_time=None,
                   weight_kg=DEFAULT_WEIGHT_KG, e_bike=False):
    """The route from find_route next to the shortest route (by distance) at the same depart_time, with how much they differ."""
    penalties = (bump_penalty, danger_penalty, pm_penalty, stop_penalty, prefer_time, shade_penalty, dark_penalty,
                 prefer_bike_friendly, depart_time)
    with _snapped_ends(G, origin, destination) as (a, b):
        return _comparison(G, a, b, penalties, weight_kg, e_bike)


def _comparison(G, a, b, penalties, weight_kg=DEFAULT_WEIGHT_KG, e_bike=False):
    """compare_routes between graph nodes a and b."""
    route = _route_feature(G, a, b, penalties, weight_kg, e_bike)
    shortest = _route_feature(G, a, b, (0, 0, 0, 0, False, 0, 0, 0, penalties[-1]), weight_kg, e_bike)
    return {
        "route": route,
        "shortest": shortest,
        "detour_pct": round((route["properties"]["length_m"] / shortest["properties"]["length_m"] - 1) * 100, 1),
        "extra_time_pct": round((route["properties"]["duration_s"] / shortest["properties"]["duration_s"] - 1) * 100, 1),
        "same_path": route["geometry"] == shortest["geometry"],
    }


def day_routes(G, origin, destination, bump_penalty=DEFAULT_BUMP_PENALTY,
               danger_penalty=DEFAULT_DANGER_PENALTY, pm_penalty=DEFAULT_PM_PENALTY,
               stop_penalty=DEFAULT_STOP_PENALTY, prefer_time=False, shade_penalty=DEFAULT_SHADE_PENALTY,
               dark_penalty=DEFAULT_DARK_PENALTY, prefer_bike_friendly=DEFAULT_PREFER_BIKE_FRIENDLY, depart_time=None,
               weight_kg=DEFAULT_WEIGHT_KG, e_bike=False):
    """compare_routes for every departure time of one day, in periods that get the same route.

    The day is that of depart_time (today without one). Departure times are tried every DAY_STEP_MIN minutes, and
    times with the same sky() (shade slot by day, or dark) form one period, so sunrise and sunset are found to
    within DAY_STEP_MIN. Each distinct sky is routed once: a day has at most one route per shade slot plus one for
    the night, both before sunrise and after sunset.
    """
    day = local_time(depart_time).date() if depart_time else datetime.now(LOCAL_TZ).date()
    weights = (bump_penalty, danger_penalty, pm_penalty, stop_penalty, prefer_time, shade_penalty, dark_penalty,
               prefer_bike_friendly)
    times = [datetime(day.year, day.month, day.day, m // 60, m % 60, tzinfo=LOCAL_TZ) for m in range(0, 24 * 60, DAY_STEP_MIN)]
    periods = []
    for t in times:
        if periods and sky(G, t) == periods[-1][0]:
            periods[-1][2] = t
        else:
            periods.append([sky(G, t), t, t])
    compared = {}
    with _snapped_ends(G, origin, destination) as (a, b):
        for key, first, _ in periods:
            if key not in compared:
                compared[key] = _comparison(G, a, b, (*weights, first), weight_kg, e_bike)
    out = []
    for key, first, last in periods:
        end = last.replace(hour=23, minute=59) if last == times[-1] else last + (times[1] - times[0])
        out.append({"from": first.strftime("%H:%M"), "to": end.strftime("%H:%M"), **compared[key]})
    return {"date": day.isoformat(), "periods": out}
