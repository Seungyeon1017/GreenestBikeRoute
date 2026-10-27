"""A-to-B routing on the bike graph, returned as GeoJSON."""
import networkx as nx
import numpy as np
import osmnx as ox

from routing.costs import DEFAULT_PENALTY, DEFAULT_ROUGHNESS, edge_cost

# Start/end points further than this from any street are treated as outside Heilbronn.
MAX_SNAP_M = 500


class RouteError(ValueError):
    """The request can't be routed (point off the map, no connection, ...)."""


def nearest_node(G, lat, lon):
    """The graph node closest to (lat, lon) and its distance in metres."""
    nodes = list(G.nodes)
    ys = np.array([G.nodes[n]["y"] for n in nodes])
    xs = np.array([G.nodes[n]["x"] for n in nodes])
    dist = ox.distance.great_circle(lat, lon, ys, xs)
    i = int(np.argmin(dist))
    return nodes[i], float(dist[i])


def _roughness(d):
    return DEFAULT_ROUGHNESS if d["roughness"] is None else d["roughness"]


def _cost(d, penalty):
    return edge_cost(d["length"], _roughness(d), penalty)


def find_route(G, origin, destination, penalty=DEFAULT_PENALTY):
    """Cheapest route from origin to destination, both (lat, lon), as a GeoJSON FeatureCollection.

    penalty=0 gives the shortest route; higher values take longer detours to avoid rough streets.
    """
    ends = []
    for label, (lat, lon) in (("start", origin), ("end", destination)):
        node, dist = nearest_node(G, lat, lon)
        if dist > MAX_SNAP_M:
            raise RouteError(f"{label} point is {dist:.0f} m from the nearest Heilbronn street")
        ends.append(node)
    a, b = ends
    if a == b:
        raise RouteError("start and end snap to the same street corner")

    # MultiDiGraph: between two nodes there can be parallel edges; use the cheapest.
    def weight(u, v, parallel):
        return min(_cost(d, penalty) for d in parallel.values())

    try:
        path = nx.shortest_path(G, a, b, weight=weight)
    except nx.NetworkXNoPath:
        raise RouteError("no bike route between these points") from None

    coords, length, rough_len, measured_len, ml_len = [], 0.0, 0.0, 0.0, 0.0
    for u, v in zip(path[:-1], path[1:]):
        d = min(G[u][v].values(), key=lambda d: _cost(d, penalty))
        if "geometry" in d:  # OSMnx edge geometries run from u to v
            pts = [[float(x), float(y)] for x, y in d["geometry"].coords]
        else:
            pts = [[float(G.nodes[n]["x"]), float(G.nodes[n]["y"])] for n in (u, v)]
        coords.extend(pts if not coords else pts[1:])
        edge_len = float(d["length"])  # numpy float when loaded from GraphML
        length += edge_len
        source = d.get("roughness_source")
        if d["roughness"] is not None:
            if source == "ml_predicted":
                ml_len += edge_len
            else:
                measured_len += edge_len
                rough_len += d["roughness"] * edge_len

    properties = {
        "penalty": penalty,
        "length_m": round(length, 1),
        # Length-weighted over the measured part of the route only.
        "mean_roughness": round(rough_len / measured_len, 1) if measured_len else None,
        "measured_share": round(measured_len / length, 2),
        "ml_share": round(ml_len / length, 2),
    }
    feature = {"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords}, "properties": properties}
    return {"type": "FeatureCollection", "features": [feature]}
