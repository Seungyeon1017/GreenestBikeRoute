"""Turns for the fastest route (prefer_time): what a turn at a junction costs in riding time, by angle and road size,
and the search that counts them.

Group: route search.
"""
import math
import weakref

from routing.costs import MAIN_ROAD_HIGHWAYS, MEDIAN_SPEED_KMH, TERTIARY_HIGHWAYS
from routing.edges import _snapped, _tags
from routing.naming import PATH_KINDS, _PARTS, _street_key, street_label, way_kind
from routing.search import cheapest_path

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
ROAD_SIZES = (set(), TERTIARY_HIGHWAYS, MAIN_ROAD_HIGHWAYS)
TURN_HEADING_M = 10


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


# Per graph: {cost_per_m: (metres per degree of longitude, the lowest cost per straight-line metre of its edges)}, for
# turning_path's A* estimate.
_COST_FLOORS = weakref.WeakKeyDictionary()


def _straight_m(G, kx, u, v):
    """Straight-line metres from node u to v, on one plane for the whole graph (kx metres per degree of longitude),
    so they obey the triangle inequality, which the A* estimate needs."""
    a, b = G.nodes[u], G.nodes[v]
    return math.hypot((b["x"] - a["x"]) * kx, (b["y"] - a["y"]) * 111_320)


def _edge_floor(G, kx, u, v, d, cost_per_m):
    """What edge (u, v) costs at least per straight-line metre: its length at cost_per_m (see turning_path)."""
    straight = _straight_m(G, kx, u, v)
    return float(d["length"]) * cost_per_m(d) / straight if straight > 0 else math.inf


def _cost_floor(G, cost_per_m):
    """(kx, floor): the lowest _edge_floor of the graph's streets, not of the temporary pieces at a route's ends. With
    prefer_time, its fastest streets (some measured at 40 km/h) and the few a bit shorter than the straight line
    between their ends set it, at about 0.4: a weak estimate, but one that never overestimates."""
    floors = _COST_FLOORS.setdefault(G, {})
    if cost_per_m not in floors:
        kx = 111_320 * math.cos(math.radians(sum(y for _, y in G.nodes(data="y")) / G.number_of_nodes()))
        floors[cost_per_m] = kx, min(_edge_floor(G, kx, u, v, d, cost_per_m) for u, v, d in G.edges(data=True)
                                     if not (_snapped(u) or _snapped(v)))
    return floors[cost_per_m]


def turning_path(G, a, b, cost, cost_per_m):
    """The nodes of the cheapest route between graph nodes a and b, in which each turn at a junction costs riding time
    (see _turn_s), as metres at MEDIAN_SPEED_KMH; by A* towards b (see _cost_floor). cost(u, v, d): what edge (u, v)
    costs, in the same metres, or None where it can't be ridden; cost_per_m(d): what it costs at least per metre of
    its length (the same function every time, as the floor is kept per graph). A state (routing.search) is (junction,
    the node the rider came from), as the turn depends on it, but (node, None) elsewhere: turning costs nothing there,
    so how the rider got there doesn't matter. Raises nx.NetworkXNoPath."""
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
                costs = [(c, e) for e in parallel if (c := cost(n, v, e[0])) is not None]
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
    kx, floor = _cost_floor(G, cost_per_m)
    floor = min([floor, *(_edge_floor(G, kx, u, v, d, cost_per_m) for n in snaps
                          for u, v, d in (*G.in_edges(n, data=True), *G.out_edges(n, data=True)))])
    estimates = {}

    def estimate(n):
        if n not in estimates:
            estimates[n] = floor * _straight_m(G, kx, n, b)
        return estimates[n]

    return cheapest_path(a, b, steps, estimate)
