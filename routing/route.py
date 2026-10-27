"""A-to-B routing on the bike graph, returned as GeoJSON."""
import networkx as nx
import numpy as np
import osmnx as ox

from routing.costs import DEFAULT_BUMP_PENALTY, DEFAULT_DANGER_PENALTY, DEFAULT_PM_PENALTY, DEFAULT_PM_RISK,     DEFAULT_ROUGHNESS, edge_cost

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


def _pm_risk(d):
    return DEFAULT_PM_RISK if d.get("pm_risk") is None else d["pm_risk"]


def _cost(d, penalties):
    bump_penalty, danger_penalty, pm_penalty = penalties
    return edge_cost(d["length"], _roughness(d), bump_penalty,
                     d.get("danger", 0.0), danger_penalty, _pm_risk(d), pm_penalty)


def find_route(G, origin, destination, bump_penalty=DEFAULT_BUMP_PENALTY,
               danger_penalty=DEFAULT_DANGER_PENALTY, pm_penalty=DEFAULT_PM_PENALTY):
    """Cheapest route from origin to destination, both (lat, lon), as a GeoJSON FeatureCollection.

    All penalties 0 give the shortest route; higher values take longer detours to avoid rough
    streets (bump_penalty), spots where cars overtook closely (danger_penalty) and streets with heavy
    traffic and bad air (pm_penalty).
    """
    penalties = (bump_penalty, danger_penalty, pm_penalty)
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
        return min(_cost(d, penalties) for d in parallel.values())

    try:
        path = nx.shortest_path(G, a, b, weight=weight)
    except nx.NetworkXNoPath:
        raise RouteError("no bike route between these points") from None

    coords, length, rough_len, measured_len = [], 0.0, 0.0, 0.0
    danger, danger_points, pm_len, pm_measured_len = 0.0, 0, 0.0, 0.0
    for u, v in zip(path[:-1], path[1:]):
        d = min(G[u][v].values(), key=lambda d: _cost(d, penalties))
        if "geometry" in d:  # OSMnx edge geometries run from u to v
            pts = [[float(x), float(y)] for x, y in d["geometry"].coords]
        else:
            pts = [[float(G.nodes[n]["x"]), float(G.nodes[n]["y"])] for n in (u, v)]
        coords.extend(pts if not coords else pts[1:])
        edge_len = float(d["length"])  # numpy float when loaded from GraphML
        length += edge_len
        if d["roughness"] is not None:
            measured_len += edge_len
            rough_len += d["roughness"] * edge_len
        danger += d.get("danger", 0.0)
        danger_points += d.get("danger_points", 0)
        if d.get("pm_risk") is not None:
            pm_measured_len += edge_len
            pm_len += d["pm_risk"] * edge_len

    properties = {
        "bump_penalty": bump_penalty,
        "danger_penalty": danger_penalty,
        "pm_penalty": pm_penalty,
        "length_m": round(length, 1),
        # Length-weighted over the measured part of the route only.
        "mean_roughness": round(rough_len / measured_len, 1) if measured_len else None,
        "measured_share": round(measured_len / length, 2),
        # Overtaking spots (danger_zones) on the route and their summed Risk Index Overtaking.
        "danger_points": danger_points,
        "danger_risk": round(danger, 2),
        # Length-weighted over the part of the route with danger_zones_PM measurements.
        "mean_pm_risk": round(pm_len / pm_measured_len, 3) if pm_measured_len else None,
        "pm_measured_share": round(pm_measured_len / length, 2),
    }
    feature = {"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords}, "properties": properties}
    return {"type": "FeatureCollection", "features": [feature]}
