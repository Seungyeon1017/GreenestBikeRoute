"""Putting a route's start and end points on the graph: each on the nearest street of the main network, split there
for the time of the route.

Group: route search.
"""
import weakref
from contextlib import contextmanager

import networkx as nx
import shapely
from shapely import Point, STRtree
from shapely.ops import substring

from routing.costs import osm_way_ids
from routing.edges import _GRAPH_LOCK, RouteError, _Plane, _edge_line

# Start/end points further than this from any street are treated as outside Heilbronn.
MAX_SNAP_M = 500


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


def nearest_street(G, lat, lon):
    """The street of the main network nearest to (lat, lon): (u, v, data, metres away)."""
    with _GRAPH_LOCK:
        (u, v, _, d), dist, _ = _nearest_edge(G, _snap_index(G), lat, lon)
    return u, v, d, dist
