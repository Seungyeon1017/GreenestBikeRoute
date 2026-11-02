"""How the map names streets: a sidewalk, bike path or crossing without a name takes the road's it runs beside or
crosses, for routes' stretches, the street overlays and turns.

Group: route search.
"""
import ast
import math
import weakref
from collections import Counter

import shapely
from shapely import LineString, MultiLineString, Point, STRtree, line_merge

from routing.costs import MAIN_ROAD_HIGHWAYS, TERTIARY_HIGHWAYS, osm_way_ids
from routing.edges import _GRAPH_LOCK, _Plane, _edge_line, _tags, edge_coords

# Roads a sidewalk or path without a name can run beside (see _NamedRoads).
ROAD_HIGHWAYS = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
                 "living_street", "service", "motorway_link", "trunk_link", "primary_link", "secondary_link",
                 "tertiary_link"}
# Main and tertiary roads are wide (several lanes, tram tracks, parking), so their sidewalks run further from OSM's
# centre line.
WIDE_ROADS = MAIN_ROAD_HIGHWAYS | TERTIARY_HIGHWAYS
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
        self.wide = [bool(highways & WIDE_ROADS) for _, highways, *_ in roads]
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
