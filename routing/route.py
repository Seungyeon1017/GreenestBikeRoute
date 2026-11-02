"""A-to-B routing on the bike graph, returned as GeoJSON."""
import ast
import math
import threading
import weakref
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import networkx as nx
import shapely
from shapely import LineString, MultiLineString, Point, STRtree, line_merge
from shapely.ops import substring

from routing.calories import DEFAULT_WEIGHT_KG, ride_kcal, route_climb, walk_kcal
from routing.costs import BAD_AIR_RISK, BUMPY_ROUGHNESS, DARK_EXPONENT, DEFAULT_BUMP_PENALTY, DEFAULT_DANGER_PENALTY, \
    DEFAULT_DARK_PENALTY, DEFAULT_LIT, DEFAULT_PM_PENALTY, DEFAULT_PM_RISK, DEFAULT_PREFER_BIKE_FRIENDLY, DEFAULT_ROUGHNESS, \
    DEFAULT_SHADE, DEFAULT_SHADE_PENALTY, DEFAULT_STOP_GO, DEFAULT_STOP_PENALTY, DEFAULT_UNPAVED_PENALTY, \
    DIM_SHARE, LIFT_WAIT_M, MEDIAN_SPEED_KMH, \
    STOP_GO_HEAVY, edge_cost, osm_way_ids
from routing.lighting import DIM_LIGHTS_PER_100M
from routing.search import cheapest_path
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
# A street counts towards a route's unpaved_m from this unpavedness on (routing.surface): compacted and worse.
UNPAVED_LINE = 0.25
# day_routes tries departure times this many minutes apart.
DAY_STEP_MIN = 15
# With prefer_time, turning at a junction (a node with 3+ neighbours) costs riding time (see _turn_s): at 90 degrees
# TURN_S to the right and LEFT_TURN_S to the left, across oncoming traffic, by road size (ROAD_SIZES: small, tertiary,
# main road). Without it, small speed differences between streets send the fastest route zig-zagging through side
# streets to save seconds, with a corner to find at every turn. A street's heading at a junction is taken over its
# TURN_HEADING_M nearest it.
# The time lost against riding on at the median 15.7 km/h, braking at 1.5 m/s^2 and speeding up at 1 m/s^2: taking a
# 90-degree corner of 5 m radius at 10 km/h loses ~1.5 s, stopping and setting off again at once ~3.6 s. A small street
# is the first; a bigger road, where the rider more often gives way, nears the second; a left turn, across oncoming
# traffic, more so. Waiting at traffic lights isn't counted.
TURN_DEG = 30
TURN_S = (1.5, 2, 3)
LEFT_TURN_S = (2, 3, 4)
ROAD_SIZES = (set(), {"tertiary", "tertiary_link"},
              {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link"})
TURN_HEADING_M = 10


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
        self.size = _size(G)
        self.lat0 = sum(y for _, y in G.nodes(data="y")) / G.number_of_nodes()
        main = max(nx.weakly_connected_components(G), key=len)
        self.edges = [(u, v, k) for u, v, k in G.edges(keys=True) if u in main and v in main]
        plane = _Plane(self.lat0)
        scale = (plane.cos_lat * plane.scale, plane.scale)
        lines = shapely.transform([_edge_line(G, u, v, G.edges[u, v, k]) for u, v, k in self.edges], lambda xy: xy * scale)
        self.tree = STRtree(lines)


# One _SnapIndex per graph; a graph whose node or edge count changed gets a new one.
_SNAP_INDEXES = weakref.WeakKeyDictionary()


def _size(G):
    """(nodes, edges) of G. networkx counts a multigraph's edges through its degree view, ~0.1 s on Heilbronn for
    every route; counting the adjacency dicts directly is ~20x faster."""
    if G.is_directed() and G.is_multigraph():
        return G.number_of_nodes(), sum(len(keys) for nbrs in G._succ.values() for keys in nbrs.values())
    return G.number_of_nodes(), G.number_of_edges()


def _snap_index(G):
    index = _SNAP_INDEXES.get(G)
    if index is None or index.size != _size(G):
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


def _dim(d):
    """Whether the street is dimly lit: probably lit, but Mapillary saw few street lights on it."""
    lights = d.get("lights_per_100m")
    return lights is not None and lights < DIM_LIGHTS_PER_100M and _lit(d) >= 0.5


def _dark(d):
    """Chance the street is unlit, for routing after dark. A dimly lit street counts as unlit with chance
    DIM_SHARE ** (1 / DARK_EXPONENT) at least, so it costs DIM_SHARE of a surely dark one."""
    if _dim(d):
        return max(1 - _lit(d), DIM_SHARE ** (1 / DARK_EXPONENT))
    return 1 - _lit(d)


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
        unpaved_penalty, slot, dark, scooter = plan
    push = MEDIAN_SPEED_KMH / WALK_KMH if scooter and scooter_pushes(d) else 1
    return push * edge_cost(d["length"], _roughness(d), bump_penalty,
                     d.get("danger", 0.0), danger_penalty, _pm_risk(d), pm_penalty, _stop_go(d), stop_penalty,
                     lift_ends=d.get("lift_start", False) + d.get("lift_end", False),
                     speed_kmh=_speed_kmh(d) if prefer_time else MEDIAN_SPEED_KMH,
                     sun=0.0 if slot is None else 1 - _shade(d, slot), shade_penalty=shade_penalty,
                     dark=_dark(d) if dark else 0.0, dark_penalty=dark_penalty,
                     bike_friendly=d.get("bike_friendly", False), prefer_bike_friendly=prefer_bike_friendly,
                     unpaved=d.get("unpaved", 0.0), unpaved_penalty=unpaved_penalty)


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


# Roads a sidewalk or path without a name can run beside (see _NamedRoads).
ROAD_HIGHWAYS = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
                 "living_street", "service", "motorway_link", "trunk_link", "primary_link", "secondary_link",
                 "tertiary_link"}
# Main roads are wide (several lanes, tram tracks, parking), so their sidewalks run further from OSM's centre line.
MAIN_ROADS = {"motorway", "trunk", "primary", "secondary", "tertiary", "motorway_link", "trunk_link", "primary_link",
              "secondary_link", "tertiary_link"}
# Only sidewalks and paths without a name (PATH_KINDS) take the name of a road, and crossings that of the road they
# cross: a farm track, access road or slip road along a road isn't part of it. A way on another level than the road (a
# footbridge over it, a tunnel under it; _levels) isn't beside it. A path runs beside a named road where it
# is within ALONG_M of it (MAIN_ALONG_M of a main road), not past where the road ends (a path across Austraße isn't
# beside Goppeltstraße starting on its far side), and heads the same way (either direction) to within ALONG_DEG,
# checked every ALONG_STEP_M (at most ALONG_POINTS times, spread evenly). It takes the name of the road it runs beside
# for most of its length, if that is at least MIN_ALONG_SHARE of it. A crossing takes the road it crosses within
# CROSSING_M. A path whose OSM way passes through a named road (or runs from one carriageway of it to another), and
# that heads across it as near for as much of its length, is `across` that road: when it runs beside no road, or only beside that one (the bike path over Mannheimer
# Straße west of Schaeuffelenstraße, beside a slip road of it).
ALONG_M = 20
MAIN_ALONG_M = 30
ALONG_DEG = 25
ALONG_STEP_M = 2
ALONG_POINTS = 25
MIN_ALONG_SHARE = 0.5
CROSSING_M = 3
# A way shorter than CORNER_M beside two roads for about as much of it (to within CORNER_MARGIN of its length), e.g.
# a sidewalk round a corner, is named after both: "A / B".
CORNER_M = 15
CORNER_MARGIN = 0.1
# The kind of way a stretch is on, from its OSM tags, in this order; "link" for a slip road (highway=*_link); null for
# an ordinary road.
WAY_KINDS = ("crossing", "sidewalk", "cycleway", "footway", "path", "track", "service", "pedestrian")
# Sidewalks and paths: the ways that take the name of the road they run beside, unless another of them runs between.
PATH_KINDS = {"sidewalk", "footway", "path", "cycleway"}


def _tags(d, key):
    value = d.get(key)
    return {str(v) for v in (value if isinstance(value, list) else [value])}


def _levels(d):
    """The levels above the ground a way is on, from its OSM layer, bridge and tunnel tags (one merged from several ways
    may be on several): a bridge is 1 and a tunnel -1 without a layer, any other way 0."""
    levels = set()
    for layer in _tags(d, "layer"):
        try:
            levels.add(int(layer))
        except ValueError:
            pass
    if not levels:
        if _tags(d, "bridge") - {"None", "no"}:
            levels.add(1)
        if _tags(d, "tunnel") - {"None", "no"}:
            levels.add(-1)
    return levels or {0}


def _structure(d):
    """"bridge" or "tunnel" if the way (its tags `d`) is one, else None."""
    for structure in ("bridge", "tunnel"):
        if _tags(d, structure) - {"None", "no"}:
            return structure
    return None


def way_kind(d):
    """What kind of way the edge is (WAY_KINDS, or "link" for a slip road), from highway=* and footway=*; None for an
    ordinary road."""
    tags = _tags(d, "highway") | _tags(d, "footway")
    kind = next((kind for kind in WAY_KINDS if kind in tags), None)
    return "link" if kind is None and any(t.endswith("_link") for t in _tags(d, "highway")) else kind


class _NamedRoads:
    """The named roads (ROAD_HIGHWAYS) as lines in metres around the graph's mean latitude, in an STRtree: the graph's
    with one name (one merged from several ways may run beside a path under either), plus every OSM road of
    G.graph["named_ways"] (routing.named_roads) with its own name, also those bikes may not ride that the graph
    leaves out. And the graph's sidewalks and paths (PATH_KINDS), to see whether one runs between a way and a road."""

    def __init__(self, G):
        self.plane = _Plane(sum(y for _, y in G.nodes(data="y")) / G.number_of_nodes())
        roads = [(d["name"], _tags(d, "highway"), _levels(d), _edge_line(G, u, v, d)) for u, v, d in G.edges(data=True)
                 if isinstance(d.get("name"), str) and d["name"] and _tags(d, "highway") & ROAD_HIGHWAYS]
        roads += [(name, _tags(tags, "highway"), _levels(tags), LineString(coords))
                  for name, tags, coords in G.graph.get("named_ways", {}).values()
                  if _tags(tags, "highway") & ROAD_HIGHWAYS]
        self.names = [name for name, *_ in roads]
        self.wide = [bool(highways & MAIN_ROADS) for _, highways, *_ in roads]
        self.levels = [levels for _, _, levels, _ in roads]
        self.lines = [self.plane.to_m(line) for *_, line in roads]
        self.tree = STRtree(self.lines)
        # Per line, whether the street ends at its first / last point: an end of the lines of its name joined (the
        # same road comes as a graph edge per direction and as an OSM way), where no other one goes on.
        by_name = {}
        for name, line in zip(self.names, self.lines):
            by_name.setdefault(name, []).append(line)
        street_ends = {}
        for name, lines in by_name.items():
            union = shapely.unary_union(lines)
            ends = Counter(c for part in getattr(union, "geoms", [union]) for c in (part.coords[0], part.coords[-1]))
            street_ends[name] = shapely.MultiPoint([c for c, n in ends.items() if n == 1])
        self.open_ends = [tuple(street_ends[name].distance(Point(c)) < 1 for c in (line.coords[0], line.coords[-1]))
                          for name, line in zip(self.names, self.lines)]
        paths = {(min(u, v), max(u, v), str(d["osmid"])): _edge_line(G, u, v, d) for u, v, d in G.edges(data=True)
                 if not isinstance(u, str) and not isinstance(v, str) and way_kind(d) in PATH_KINDS}
        self.paths = [self.plane.to_m(line) for line in paths.values()]
        self.path_tree = STRtree(self.paths)
        # Each path's OSM way as a whole (the graph's edges of it), to see whether it passes through a road.
        pieces = {}
        for (_, _, osmid), line in zip(paths, self.paths):
            for i in osm_way_ids(osmid):
                pieces.setdefault(i, []).append(line)
        self.ways = {osmid: line_merge(MultiLineString(lines)) for osmid, lines in pieces.items()}

    def along(self, line, way=None, levels=None):
        """Name of the road a way of kind `way` (way_kind) on `levels` (_levels) runs beside, line (lon, lat), or for a
        crossing the road it crosses; "A / B" for a short piece beside two roads alike; None if none. A way on another
        level than a road (a footbridge over it, a tunnel under it) isn't beside it."""
        line = self.plane.to_m(line)
        if way == "crossing":
            found = self.tree.query(line, predicate="dwithin", distance=CROSSING_M)
            return min(((line.distance(self.lines[i]), self.names[i]) for i in found), default=(0, None))[1]
        found = self.tree.query(line, predicate="dwithin", distance=MAIN_ALONG_M)
        if levels is not None:
            found = [i for i in found if levels & self.levels[i]]
        if not len(found):
            return None
        n = min(max(round(line.length / ALONG_STEP_M), 2), ALONG_POINTS)
        points = [line.interpolate(k / n, normalized=True) for k in range(n + 1)]
        beside, metres = {}, {}
        for p in points:
            heading, near = _heading(line, p), {}
            for i in found:
                road, dist = self.lines[i], self.lines[i].distance(p)
                if dist > (MAIN_ALONG_M if self.wide[i] else ALONG_M) or self._past_end(i, p):
                    continue
                turn = abs(heading - _heading(road, p)) % 180
                if min(turn, 180 - turn) <= ALONG_DEG:
                    near[self.names[i]] = min(near.get(self.names[i], dist), dist)
            for name, dist in near.items():
                beside[name] = beside.get(name, 0) + 1
                metres[name] = metres.get(name, 0.0) + dist
        ranked = sorted(beside, key=lambda name: (-beside[name], metres[name], name))
        if not ranked:
            return None
        name = ranked[0]
        if beside[name] < len(points) * MIN_ALONG_SHARE:
            return None
        if self._path_between(line, [self.lines[i] for i in found if self.names[i] == name]):
            return None
        if line.length < CORNER_M and len(ranked) > 1 and beside[ranked[1]] >= beside[name] - CORNER_MARGIN * len(points):
            return f"{name} / {ranked[1]}"
        return name

    def across(self, line, ids, levels=None):
        """Name of the road a path, line (lon, lat) of OSM ways `ids` on `levels`, crosses: its way passes through the
        road, or runs from one carriageway of it to another (both its ends on the road; Austraße's platforms), and at
        least MIN_ALONG_SHARE of the line is within ALONG_M of it (MAIN_ALONG_M of a main road) heading across it (more
        than ALONG_DEG off its way). None if none; the nearest if several."""
        ways = [self.ways[i] for i in ids if i in self.ways]
        if not ways:
            return None
        line = self.plane.to_m(line)
        n = min(max(round(line.length / ALONG_STEP_M), 2), ALONG_POINTS)
        points = [line.interpolate(k / n, normalized=True) for k in range(n + 1)]
        roads = {i for way in ways for i in self.tree.query(way, predicate="crosses")}
        for way in ways:
            for part in getattr(way, "geoms", [way]):
                ends = [set(self.tree.query(Point(c), predicate="dwithin", distance=1)) for c in (part.coords[0], part.coords[-1])]
                both = {self.names[i] for i in ends[0]} & {self.names[i] for i in ends[1]}
                roads |= {i for i in ends[0] | ends[1] if self.names[i] in both}
        crossed = []
        for i in roads:
            if levels is not None and not levels & self.levels[i]:
                continue
            road, limit, hits, metres = self.lines[i], MAIN_ALONG_M if self.wide[i] else ALONG_M, 0, 0.0
            for p in points:
                turn = abs(_heading(line, p) - _heading(road, p)) % 180
                dist = road.distance(p)
                if dist <= limit and min(turn, 180 - turn) > ALONG_DEG:
                    hits, metres = hits + 1, metres + dist
            if hits >= len(points) * MIN_ALONG_SHARE:
                crossed.append((metres / hits, self.names[i]))
        return min(crossed, default=(0, None))[1]

    def _path_between(self, line, roads):
        """Whether another sidewalk or path (heading the road's way) runs between `line` and the nearest of `roads`
        (all in metres) at each of the points checked along it, and at least two: then it is a path of its own."""
        hits = checks = 0
        for f in (0.25, 0.5, 0.75):
            p = line.interpolate(f, normalized=True)
            road = min(roads, key=lambda r: r.distance(p))
            q = road.interpolate(road.project(p))
            if p.distance(q) < 4:
                continue  # no room for a path between
            checks += 1
            gap = LineString([p, q])
            for j in self.path_tree.query(gap, predicate="intersects"):
                crossing = self.paths[j].intersection(gap)
                at = crossing if crossing.geom_type == "Point" else crossing.representative_point()
                if at.distance(p) < 1.5:
                    continue  # the way itself, or a path joining it there
                turn = abs(_heading(self.paths[j], at) - _heading(road, q)) % 180
                if min(turn, 180 - turn) <= ALONG_DEG:
                    hits += 1
                    break
        return checks >= 2 and hits == checks

    def _past_end(self, i, p):
        """Whether point `p` (metres) lies past an end of road line i where the street ends: no other line of its name
        goes on from there. Its nearest point is that end, so it isn't beside the street but before it."""
        road = self.lines[i]
        at = road.project(p)
        return (at <= 0 and self.open_ends[i][0]) or (at >= road.length and self.open_ends[i][1])


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
_STRETCH_MEANS = ("roughness", "pm_risk", "stop_go", "speed_kmh", "shade", "lit", "unpaved")


def street_name(G, u, v, d):
    """The street name of edge (u, v); a way without one (a sidewalk, a bike path) takes the name of the road it runs
    beside or, for a crossing, crosses. None if there is neither."""
    return street_label(G, u, v, d)["name"]


def _label(G, name, way, line, tags=None, ids=()):
    """How the map names a line (lon, lat) of OSM ways `ids` with its own `name` and kind `way`, from OSM tags `tags`
    (None: unknown): a sidewalk or path (PATH_KINDS) without a name takes the road's it runs beside, on its level
    (_levels), a crossing the road's it crosses (`along`); a path across a road (_NamedRoads.across) beside no other
    takes that road's (`along` and `across`); other ways keep none. `structure` ("bridge" or "tunnel") only on one that
    is."""
    levels = None if tags is None else _levels(tags)
    beside = None if name or (way not in PATH_KINDS and way != "crossing") else _named_roads(G).along(line, way, levels)
    across = None if name or way not in PATH_KINDS else _named_roads(G).across(line, ids, levels)
    if across and beside not in (None, across):
        across = None
    structure = None if tags is None else _structure(tags)
    return {"name": name or across or beside, "way": way, "along": bool(beside or across),
            **({"across": True} if across else {}), **({"structure": structure} if structure else {})}


def _names(d):
    """An edge's OSM names: one merged from several ways has a list (in ATRAI data its "['a', 'b']")."""
    name = d.get("name")
    if isinstance(name, str) and name.startswith("["):
        name = ast.literal_eval(name)
    return [n for n in (name if isinstance(name, list) else [name]) if n]


# How far (m) a line's vertices may lie from the OSM way they come from: the same points, rounded. A step of a line
# whose vertices aren't OSM's (ATRAI cuts its own) takes the nearest of its ways within NEAR_WAY_M of its middle.
ON_WAY_M = 1
NEAR_WAY_M = 5


def _way_runs(G, ids, coords):
    """A line [(lon, lat)] merged from OSM ways `ids`, cut where one way ends and the next begins (a vertex of the
    line): [(first vertex, last vertex, name, way kind)], name None on a way without one (not in G.graph["named_ways"],
    routing.named_roads). None if none of the ways is known."""
    known = G.graph.get("named_ways", {})
    plane = _named_roads(G).plane
    ways = [(known[i][0], way_kind(known[i][1]), plane.to_m(LineString(known[i][2]))) for i in ids if i in known]
    if not ways:
        return None
    points = [Point(plane.to_m_point(*c)) for c in coords]
    runs = []
    for k, (a, b) in enumerate(zip(points[:-1], points[1:])):
        mid = Point((a.x + b.x) / 2, (a.y + b.y) / 2)
        on = [(line.distance(mid), name, kind) for name, kind, line in ways
              if max(line.distance(a), line.distance(b), line.distance(mid)) <= ON_WAY_M]
        if not on:  # a dataset that cut the line elsewhere (ATRAI): the nearest of its ways, if that close
            on = [(line.distance(mid), name, kind) for name, kind, line in ways if line.distance(mid) <= NEAR_WAY_M]
        name, kind = min(on, key=lambda o: o[0])[1:] if on else (None, None)
        if runs and runs[-1][2:] == [name, kind]:
            runs[-1][1] = k + 1
        else:
            runs.append([k, k + 1, name, kind])
    return [tuple(run) for run in runs]


def _parts(G, d, ids, coords):
    """street_parts of a line [(lon, lat)] with tags `d` from OSM ways `ids`."""
    names = _names(d)
    if len(set(names)) > 1:
        runs = _way_runs(G, ids, coords)
        if runs:
            return [(a, b, _label(G, name, kind or way_kind(d), LineString(coords[a:b + 1]), d, ids))
                    for a, b, name, kind in runs]
    return [(0, len(coords) - 1, _label(G, names[0] if names else None, way_kind(d), LineString(coords), d, ids))]


# street_parts per graph and edge, for the overlays (and every /score) that name all ~22,000 streets: ~10 s once.
_PARTS = weakref.WeakKeyDictionary()


def _street_key(u, v, d):
    """An edge's key in _PARTS: once per street, from its lower node to its higher one (a two-way street is two edges,
    the same line reversed); with the tags it is named from, so a renamed street isn't served its old name."""
    return (min(u, v), max(u, v), str(d["osmid"]), round(float(d["length"]), 1),
            *(str(d.get(k)) for k in ("name", "highway", "footway", "bridge", "tunnel", "layer")))


def street_parts(G, u, v, d):
    """How the map names edge (u, v), as route stretches: [(first vertex, last vertex, label)] of edge_coords, one
    part per name. A label has `name`, its OSM name; `way`, its kind (way_kind); and `along`: a way without a name (a
    sidewalk, a bike path) takes the name of the road it runs beside or, for a crossing, crosses. An edge merged from
    ways with different names is cut where one ends. Kept per edge, except for the pieces of a street split at a
    route's start or end."""
    coords = edge_coords(G, u, v, d)
    if isinstance(u, str) or isinstance(v, str):
        return _parts(G, d, osm_way_ids(d["osmid"]), coords)
    cache = _PARTS.setdefault(G, {})
    street = _street_key(u, v, d)
    forward = u < v
    if street not in cache:
        cache[street] = _parts(G, d, osm_way_ids(d["osmid"]), coords if forward else coords[::-1])
    if forward:
        return cache[street]
    last = len(coords) - 1
    return [(last - b, last - a, label) for a, b, label in reversed(cache[street])]


def name_streets(G):
    """street_parts of every street, ahead of the overlays and routes that ask for them (~15 s on Heilbronn): e.g. in a
    background thread at startup. The edges are listed under the graph lock, as routes add and remove their ends."""
    with _GRAPH_LOCK:
        edges = [(u, v, d) for u, v, d in G.edges(data=True) if not isinstance(u, str) and not isinstance(v, str)]
    for u, v, d in edges:
        street_parts(G, u, v, d)


def _longest(G, coords, parts):
    plane = _named_roads(G).plane
    return max(parts, key=lambda part: plane.to_m(LineString(coords[part[0]:part[1] + 1])).length)[2]


def street_label(G, u, v, d):
    """The label (see street_parts) of the longest part of edge (u, v): for what names the edge as a whole."""
    parts = street_parts(G, u, v, d)
    return parts[0][2] if len(parts) == 1 else _longest(G, edge_coords(G, u, v, d), parts)


def street_lines(G, u, v, d, named=True):
    """Edge (u, v) as map lines, one per name: [(coordinates [[lon, lat]] rounded to 6 places, label)]. Not `named`:
    the whole edge as one line with an empty label, without naming it (name_streets may not have yet)."""
    coords = [[round(x, 6), round(y, 6)] for x, y in edge_coords(G, u, v, d)]
    if not named:
        return [(coords, {})]
    return [(coords[a:b + 1], label) for a, b, label in street_parts(G, u, v, d)]


# The first graph edge of each OSM way, per graph, for way_parts.
_WAYS = weakref.WeakKeyDictionary()


def way_parts(G, osmid, coords, name=None):
    """street_parts for a line of another OSM-based dataset (an ATRAI segment, an Overpass way): OSM way `osmid` (an
    id, or ATRAI's "[id, id]" string) at `coords` [(lon, lat)]. Name and kind come from that way (G.graph["named_ways"]
    and the graph's edges of it), else the dataset's own `name` (also "['a', 'b']"); a line merged from several ways
    with different names is cut where one ends."""
    ways = _WAYS.get(G)
    if ways is None:
        ways = _WAYS[G] = {}
        for *_, d in G.edges(data=True):
            for i in osm_way_ids(d["osmid"]):
                ways.setdefault(i, d)
    ids = osm_way_ids(osmid)
    kind = next((way_kind(ways[i]) for i in ids if i in ways), None)
    if len(ids) > 1:
        runs = _way_runs(G, ids, coords)
        if runs and len({run[2] for run in runs}) > 1:
            first = next((ways[i] for i in ids if i in ways), None)
            return [(a, b, _label(G, n, k or kind, LineString(coords[a:b + 1]), first, ids)) for a, b, n, k in runs]
    named = G.graph.get("named_ways", {})
    known = next((named[i] for i in ids if i in named), None)
    d = next((ways[i] for i in ids if i in ways), None)
    tags = known[1] if known else d
    if known:
        own, kind = known[0], way_kind(known[1])
    elif d is not None:
        # A graph edge merged from several ways: its name is this way's too if they all have the same one; else this
        # may be an unnamed one among them.
        names = set(_names(d))
        own = names.pop() if len(names) == 1 else None
    else:
        own = (_names({"name": name}) or [None])[0]
    return [(0, len(coords) - 1, _label(G, own, kind, LineString(coords), tags, ids))]


def way_label(G, osmid, coords, name=None, named=True):
    """The label (see street_parts) of the longest part of way_parts: for what names the line as a whole. Not `named`:
    an empty one, without naming it."""
    if not named:
        return {}
    parts = way_parts(G, osmid, coords, name)
    return parts[0][2] if len(parts) == 1 else _longest(G, coords, parts)


def way_lines(G, osmid, coords, name=None, named=True):
    """way_parts as map lines: [(coordinates, label)], one per name. Not `named`: the whole line with an empty label."""
    if not named:
        return [(coords, {})]
    return [(coords[a:b + 1], label) for a, b, label in way_parts(G, osmid, coords, name)]


def _edge_facts(G, u, v, d, slot, dark, scooter, label=None, danger_points=True):
    """What a stretch shows for one edge (or one part of it, named `label`, see street_parts): street name, kind of
    way, the measured values (None where unknown) and `flags`, the bad or good things it counts towards (the route's
    bumpy_m, danger_points, ... with the same thresholds). Without `danger_points` the edge's close-overtaking spots
    are left out, for its parts after the first: where along it they are isn't known."""
    facts = {
        **(label or street_label(G, u, v, d)),
        "roughness": d["roughness"],
        "danger_points": int(d.get("danger_points", 0)) if danger_points else 0,
        "pm_risk": d.get("pm_risk"),
        "stop_go": d.get("stop_go"),
        "speed_kmh": d.get("speed_kmh"),
        "shade": d["shade"][slot] if slot is not None and d.get("shade") is not None else None,
        "lit": d.get("lit"),
        "dim": _dim(d),
        "bike_friendly": bool(d.get("bike_friendly")),
        "unpaved": d.get("unpaved", 0.0),
        "pushed": bool(scooter and scooter_pushes(d)),
    }
    flags = [key for key, bad in (
        ("bumpy_m", facts["roughness"] is not None and facts["roughness"] >= BUMPY_ROUGHNESS),
        ("danger_points", facts["danger_points"] > 0),
        ("bad_air_m", facts["pm_risk"] is not None and facts["pm_risk"] >= BAD_AIR_RISK),
        ("stop_go_m", facts["stop_go"] is not None and facts["stop_go"] >= STOP_GO_HEAVY),
        ("sunny_m", facts["shade"] is not None and facts["shade"] < 0.5),
        ("unlit_m", dark and facts["lit"] is not None and facts["lit"] < 0.5),
        ("dim_m", dark and facts["dim"]),
        ("bike_friendly_m", facts["bike_friendly"]),
        ("unpaved_m", facts["unpaved"] >= UNPAVED_LINE),
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
                    "along": facts["along"], "across": facts.get("across", False), "danger_points": 0,
                    "bike_friendly": facts["bike_friendly"],
                    "pushed": facts["pushed"], "flags": facts["flags"], "segments": [],
                    "_sums": {k: [0.0, 0.0] for k in _STRETCH_MEANS}}
            out.append(prev)
        elif prev["way"] != facts["way"]:
            prev["way"] = None
        prev["along"] = prev["along"] and facts["along"]
        prev["across"] = prev["across"] and facts.get("across", False)
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
             "across": s["across"],
             "flags": s["flags"], "roughness": m["roughness"],
             "danger_points": s["danger_points"], "pm_risk": m["pm_risk"], "stop_go": m["stop_go"],
             "speed_kmh": m["speed_kmh"], "shade": m["shade"], "lit": m["lit"], "bike_friendly": s["bike_friendly"],
             "unpaved": m["unpaved"], "pushed": s["pushed"], "segments": s["segments"]} for s, m in zip(out, means)]


def _route_feature(G, a, b, penalties, weight_kg=DEFAULT_WEIGHT_KG, e_bike=False, scooter=False):
    """The cheapest route between graph nodes a and b for `penalties` (the six penalties, prefer_time,
    prefer_bike_friendly, unpaved_penalty and depart_time), as one GeoJSON Feature. kcal is for a rider of
    weight_kg; for an e-scooter with `scooter`."""
    bump_penalty, danger_penalty, pm_penalty, stop_penalty, prefer_time, shade_penalty, dark_penalty, prefer_bike_friendly, \
        unpaved_penalty, depart_time = penalties
    plan = _plan(G, penalties, scooter)
    slot, dark = plan[-3:-1]
    path = _path(G, a, b, plan)

    lifts = sum(1 for n in path[1:-1] if "elevator" in str(G.nodes[n].get("highway")))
    coords, length, rough_len, measured_len, estimated_len = [], 0.0, 0.0, 0.0, 0.0
    danger, danger_points, pm_len, pm_measured_len = 0.0, 0, 0.0, 0.0
    stop_len, stop_measured_len = 0.0, 0.0
    shade_len, shade_known_len, lit_len, lit_known_len = 0.0, 0.0, 0.0, 0.0
    bumpy_m, bad_air_m, stop_go_m, sunny_m, unlit_m, dim_m, bike_friendly_m, pushed_m = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    unpaved_m = 0.0
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
        # One piece per name: an edge merged from ways with different names makes a stretch of each.
        parts = street_parts(G, u, v, d)
        part_m = [_named_roads(G).plane.to_m(LineString(pts[a:b + 1])).length for a, b, _ in parts] \
            if len(parts) > 1 else [1.0]
        for k, ((a, b, label), metres) in enumerate(zip(parts, part_m)):
            pieces.append((first + a, first + b, edge_len * metres / sum(part_m),
                           _edge_facts(G, u, v, d, slot, dark, scooter, label, danger_points=k == 0),
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
        if _dim(d):
            dim_m += edge_len
        if d.get("bike_friendly"):
            bike_friendly_m += edge_len
        if d.get("unpaved", 0.0) >= UNPAVED_LINE:
            unpaved_m += edge_len
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
        "unpaved_penalty": unpaved_penalty,
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
        # Metres on dimly lit streets after dark (probably lit, but few street lights seen); null otherwise.
        "dim_m": round(dim_m) if dark else None,
        # Metres on bike paths, bike lanes and bike routes (/bike-friendly-streets).
        "bike_friendly_m": round(bike_friendly_m),
        # Metres on unpaved streets: gravel, compacted, cobblestones, soil or grass (routing.surface, from OSM).
        "unpaved_m": round(unpaved_m),
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
        if plan[4]:  # prefer_time
            return _turning_path(G, a, b, plan)
        return nx.shortest_path(G, a, b, weight=weight)
    except nx.NetworkXNoPath:
        raise RouteError("no bike route between these points") from None


def _end_heading(G, u, v, d, at_end):
    """Direction in degrees in which edge u->v leaves u (or, `at_end`, reaches v), over TURN_HEADING_M."""
    # Plain maths, not shapely: a search computes this for a lot of edges. Towards the first point of the line at least
    # TURN_HEADING_M away (or its other end), in equirectangular metres.
    coords = list(d["geometry"].coords) if "geometry" in d else [(G.nodes[n]["x"], G.nodes[n]["y"]) for n in (u, v)]
    if at_end:
        coords = coords[::-1]
    (x0, y0), kx = coords[0], math.cos(math.radians(coords[0][1]))
    for x, y in coords[1:]:
        dx, dy = (x - x0) * kx, y - y0
        if math.hypot(dx, dy) * 111_320 >= TURN_HEADING_M:
            break
    heading = math.degrees(math.atan2(dy, dx))
    return heading + 180 if at_end else heading  # measured from v backwards


# Per graph: {road name: its ROAD_SIZES size, the biggest along it}.
_NAME_SIZES = weakref.WeakKeyDictionary()


def _highway_size(highways):
    return max((size for size, kinds in enumerate(ROAD_SIZES) if highways & kinds), default=0)


def _road_size(G, u, v, d, wait=True):
    """How big the road of edge (u, v) is, 0-2 (see ROAD_SIZES): its own highway or that of a road of its name; for a
    bike path, sidewalk or crossing without a name, the road it runs beside or crosses (street_label). Not `wait`: None
    for one of those that isn't named yet (name_streets), as naming them all takes ~15 s."""
    names = _tags(d, "name") - {"None"}
    if not names and (way_kind(d) in PATH_KINDS or way_kind(d) == "crossing"):
        if not wait and (_snapped(u) or _snapped(v) or _street_key(u, v, d) not in _PARTS.get(G, {})):
            return None
        names = {street_label(G, u, v, d)["name"]}
    if G not in _NAME_SIZES:
        sizes = {}
        for name, highways in [(d["name"], _tags(d, "highway")) for *_, d in G.edges(data=True) if isinstance(d.get("name"), str)] \
                + [(name, _tags(tags, "highway")) for name, tags, _ in G.graph.get("named_ways", {}).values()]:
            sizes[name] = max(sizes.get(name, 0), _highway_size(highways))
        _NAME_SIZES[G] = sizes
    return max([_highway_size(_tags(d, "highway")), *(_NAME_SIZES[G].get(name, 0) for name in names)])


def _turn_s(angle, size_in, size_out):
    """Riding time in s a turn by `angle` degrees (> 0: to the left) costs at a junction, from a road of size_in into one
    of size_out: TURN_S / LEFT_TURN_S at 90 degrees, in proportion to the angle (twice as much to turn back), nothing
    under TURN_DEG. A right turn by the road it turns into; a left turn, across the traffic, by the bigger road."""
    angle = 180 - (180 - angle) % 360  # -180 < angle <= 180: turning back counts as to the left
    if abs(angle) < TURN_DEG:
        return 0.0
    if angle > 0:
        return LEFT_TURN_S[max(size_in, size_out)] * abs(angle) / 90
    return TURN_S[size_out] * -angle / 90


# Per graph: {node: _turn_streets}, kept across searches, as the streets don't change; not for the temporary start
# and end points and their neighbours, whose streets they split, nor before their bike paths are named.
_TURN_STREETS = weakref.WeakKeyDictionary()


def _is_junction(G, n):
    return not _snapped(n) and len(set(G.successors(n)) | set(G.predecessors(n))) >= 3


def _turn_streets(G, n):
    """The streets leaving n, as [(v, whether v is a junction, [(data, heading leaving n, heading reaching v, road
    size) of each parallel edge n->v])], and whether that is final: False while a bike path or crossing among them
    isn't named yet (_road_size), which counts as its own size until then."""
    streets, final = [], True
    for v, parallel in G[n].items():
        edges = []
        for d in parallel.values():
            size = _road_size(G, n, v, d, wait=False)
            if size is None:
                size, final = _highway_size(_tags(d, "highway")), False
            edges.append((d, _end_heading(G, n, v, d, False), _end_heading(G, n, v, d, True), size))
        streets.append((v, _is_junction(G, v), edges))
    return streets, final


# Per graph: (metres per degree of longitude, the lowest _cost per straight-line metre of its edges at the measured
# speeds), for _turning_path's A* estimate.
_COST_FLOORS = weakref.WeakKeyDictionary()


def _straight_m(G, kx, u, v):
    """Straight-line metres from node u to v, on one plane for the whole graph (kx metres per degree of longitude),
    so they obey the triangle inequality, which the A* estimate needs."""
    a, b = G.nodes[u], G.nodes[v]
    return math.hypot((b["x"] - a["x"]) * kx, (b["y"] - a["y"]) * 111_320)


def _edge_floor(G, kx, u, v, d):
    """What edge (u, v) costs at least per straight-line metre with prefer_time: its length at its measured speed, as
    every other part of _cost and the turns only add to it."""
    straight = _straight_m(G, kx, u, v)
    return float(d["length"]) * MEDIAN_SPEED_KMH / _speed_kmh(d) / straight if straight > 0 else math.inf


def _cost_floor(G):
    """(kx, floor): the lowest _edge_floor of the graph's streets, not of the temporary pieces at a route's ends. Its
    fastest streets (some measured at 40 km/h) and the few a bit shorter than the straight line between their ends
    set it, at about 0.4: a weak estimate, but one that never overestimates."""
    if G not in _COST_FLOORS:
        kx = 111_320 * math.cos(math.radians(sum(y for _, y in G.nodes(data="y")) / G.number_of_nodes()))
        _COST_FLOORS[G] = kx, min(_edge_floor(G, kx, u, v, d) for u, v, d in G.edges(data=True)
                                  if not (_snapped(u) or _snapped(v)))
    return _COST_FLOORS[G]


def _turning_path(G, a, b, plan):
    """_path for prefer_time, in which each turn at a junction can cost riding time (see _turn_s), as metres at
    MEDIAN_SPEED_KMH like _cost; by A* towards b (see _cost_floor). A state (routing.search) is (junction, the node the rider came from), as the turn
    depends on it, but (node, None) elsewhere: turning costs nothing there, so how the rider got there doesn't matter."""
    static = _TURN_STREETS.setdefault(G, {})
    snaps = [n for n in ("snap-start", "snap-end") if n in G]
    split = {m for n in snaps for m in (*G.successors(n), *G.predecessors(n), n)}
    m_per_s = MEDIAN_SPEED_KMH / 3.6
    leaving = {}

    def streets_from(n):
        """(v, cost, heading leaving n, heading reaching v, road size, whether v is a junction) of the cheapest
        parallel edge to each neighbour v that can be ridden."""
        if n not in leaving:
            if n in static and n not in split:
                streets = static[n]
            else:
                streets, final = _turn_streets(G, n)
                if final and n not in split:
                    static[n] = streets
            out = []
            for v, junction, parallel in streets:
                costs = [(c, e) for e in parallel if (c := _route_cost(n, v, e[0], plan)) is not None]
                if costs:
                    c, (_, start, end, size) = min(costs, key=lambda ce: ce[0])
                    out.append((v, c, start, end, size, junction))
            leaving[n] = out
        return leaving[n]

    def steps(state, arrival):  # arrival: heading and road size on arrival at a junction
        n = state[0]
        for v, c, start, end, size, junction in streets_from(n):
            if arrival is not None:
                c += _turn_s(start - arrival[0], arrival[1], size) * m_per_s
            yield ((v, n), c, (end, size)) if junction else ((v, None), c, None)

    # A*: what is left costs at least the straight line to b at the floor; the pieces of the streets split for the
    # ends count too.
    kx, floor = _cost_floor(G)
    floor = min([floor, *(_edge_floor(G, kx, u, v, d) for n in snaps
                          for u, v, d in (*G.in_edges(n, data=True), *G.out_edges(n, data=True)))])
    estimates = {}

    def estimate(n):
        if n not in estimates:
            estimates[n] = floor * _straight_m(G, kx, n, b)
        return estimates[n]

    return cheapest_path(a, b, steps, estimate)


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
               dark_penalty=DEFAULT_DARK_PENALTY, prefer_bike_friendly=DEFAULT_PREFER_BIKE_FRIENDLY,
               unpaved_penalty=DEFAULT_UNPAVED_PENALTY, depart_time=None,
               weight_kg=DEFAULT_WEIGHT_KG, e_bike=False, scooter=False):
    """Cheapest route from origin to destination, both (lat, lon), as a GeoJSON FeatureCollection.

    All penalties 0 give the shortest route; higher values take longer detours to avoid rough
    streets (bump_penalty), spots where cars overtook closely (danger_penalty), streets with bad
    air (pm_penalty) and streets where bikes keep stopping (stop_penalty). prefer_time weighs each
    street by its riding time at the measured speed instead of its length. With a depart_time (datetime),
    sunny streets cost extra by day (shade_penalty) and unlit streets after dark (dark_penalty).
    prefer_bike_friendly makes streets that are not bike paths, bike lanes or bike routes cost extra, and
    unpaved_penalty gravel, soil and grass (routing.surface).
    With `scooter`, the route is for an e-scooter, pushed where it must not ride (scooter_pushes).
    """
    penalties = (bump_penalty, danger_penalty, pm_penalty, stop_penalty, prefer_time, shade_penalty, dark_penalty,
                 prefer_bike_friendly, unpaved_penalty, depart_time)
    with _snapped_ends(G, origin, destination) as (a, b):
        feature = _route_feature(G, a, b, penalties, weight_kg, e_bike, scooter)
    return {"type": "FeatureCollection", "features": [feature]}


def compare_routes(G, origin, destination, bump_penalty=DEFAULT_BUMP_PENALTY,
                   danger_penalty=DEFAULT_DANGER_PENALTY, pm_penalty=DEFAULT_PM_PENALTY,
                   stop_penalty=DEFAULT_STOP_PENALTY, prefer_time=False, shade_penalty=DEFAULT_SHADE_PENALTY,
                   dark_penalty=DEFAULT_DARK_PENALTY, prefer_bike_friendly=DEFAULT_PREFER_BIKE_FRIENDLY,
                   unpaved_penalty=DEFAULT_UNPAVED_PENALTY, depart_time=None,
                   weight_kg=DEFAULT_WEIGHT_KG, e_bike=False):
    """The route from find_route next to the shortest route (by distance) at the same depart_time, with how much they differ."""
    penalties = (bump_penalty, danger_penalty, pm_penalty, stop_penalty, prefer_time, shade_penalty, dark_penalty,
                 prefer_bike_friendly, unpaved_penalty, depart_time)
    with _snapped_ends(G, origin, destination) as (a, b):
        return _comparison(G, a, b, penalties, weight_kg, e_bike)


def _comparison(G, a, b, penalties, weight_kg=DEFAULT_WEIGHT_KG, e_bike=False):
    """compare_routes between graph nodes a and b."""
    route = _route_feature(G, a, b, penalties, weight_kg, e_bike)
    shortest = _route_feature(G, a, b, (0, 0, 0, 0, False, 0, 0, 0, 0, penalties[-1]), weight_kg, e_bike)
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
               dark_penalty=DEFAULT_DARK_PENALTY, prefer_bike_friendly=DEFAULT_PREFER_BIKE_FRIENDLY,
               unpaved_penalty=DEFAULT_UNPAVED_PENALTY, depart_time=None,
               weight_kg=DEFAULT_WEIGHT_KG, e_bike=False):
    """compare_routes for every departure time of one day, in periods that get the same route.

    The day is that of depart_time (today without one). Departure times are tried every DAY_STEP_MIN minutes, and
    times with the same sky() (shade slot by day, or dark) form one period, so sunrise and sunset are found to
    within DAY_STEP_MIN. Each distinct sky is routed once: a day has at most one route per shade slot plus one for
    the night, both before sunrise and after sunset.
    """
    day = local_time(depart_time).date() if depart_time else datetime.now(LOCAL_TZ).date()
    weights = (bump_penalty, danger_penalty, pm_penalty, stop_penalty, prefer_time, shade_penalty, dark_penalty,
               prefer_bike_friendly, unpaved_penalty)
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
