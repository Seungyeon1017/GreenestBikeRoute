"""What routing.route, routing.snap, routing.naming and routing.turns share about the graph's edges: the lock on the
shared graph, the error a route request can fail with, a plane in metres, edge lines and tags.

Group: route search.
"""
import math
import threading

from shapely import LineString

# Routing temporarily splits streets in the shared graph, so one request at a time may use it.
_GRAPH_LOCK = threading.Lock()


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


def edge_coords(G, u, v, d):
    """[lon, lat] points of edge (u, v) with data d, from u to v."""
    if "geometry" in d:  # OSMnx edge geometries run from u to v
        return [[float(x), float(y)] for x, y in d["geometry"].coords]
    return [[float(G.nodes[n]["x"]), float(G.nodes[n]["y"])] for n in (u, v)]


def _snapped(n):
    return isinstance(n, str) and n.startswith("snap-")


def _tags(d, key):
    value = d.get(key)
    return {str(v) for v in (value if isinstance(value, list) else [value])}
