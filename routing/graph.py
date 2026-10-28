"""The Heilbronn bike graph from OSM (via OSMnx), with ATRAI roughness, stop-and-go and danger on every edge."""
import math
from pathlib import Path

import numpy as np
import osmnx as ox
from shapely import LineString, STRtree, points

from download_data import load_features
from routing.costs import SNAP_M, air_ranks, clean_overtaking, edge_roughness, point_risks, way_roughness, way_stop_go

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
# Renamed when the filter below changes, so an old cached graph isn't reused.
GRAPH_PATH = CACHE_DIR / "heilbronn_bike_legal.graphml"
PLACE = "Heilbronn, Germany"

# OSMnx's network_type="bike" filter, plus: leave out roads tagged bicycle=use_sidepath.
# They have a mandatory bike path beside them (StVO signs 237/240/241), so cycling on the road is
# illegal; that path is mapped as its own way and stays in the graph.
BIKE_FILTER = (
    '["highway"]["area"!~"yes"]["access"!~"private"]'
    '["highway"!~"abandoned|bus_guideway|construction|corridor|elevator|'
    'escalator|footway|motor|no|planned|platform|proposed|raceway|razed|'
    'rest_area|services|steps"]'
    '["bicycle"!~"no|use_sidepath"]["service"!~"private"]'
)


def load_graph(path=GRAPH_PATH):
    """Load the bike graph from cache/, downloading it from OSM the first time (~2 min).

    Delete the .graphml file to pick up newer OSM data.
    """
    path = Path(path)
    if path.exists():
        G = ox.load_graphml(path)
    else:
        ox.settings.cache_folder = CACHE_DIR
        G = ox.graph_from_place(PLACE, network_type="bike", custom_filter=BIKE_FILTER)
        ox.save_graphml(G, path)
    attach_roughness(G, way_roughness(load_features("bumpy_roads_heilbronn")))
    attach_stop_go(G, way_stop_go(load_features("traffic_flow_heilbronn")))
    attach_danger(G, point_risks(clean_overtaking(load_features("danger_zones_raw_heilbronn")), "Risk Index Overtaking"),
                  air_ranks(load_features("air_quality_heilbronn")))
    return G


def attach_roughness(G, way_rough):
    """Set edge attribute `roughness` (0-100, or None where no bike has measured it)."""
    for _, _, d in G.edges(data=True):
        d["roughness"] = edge_roughness(d["osmid"], way_rough)


def attach_stop_go(G, way_stop):
    """Set edge attribute `stop_go` (0-1, or None where no bike has measured it)."""
    for _, _, d in G.edges(data=True):
        d["stop_go"] = edge_roughness(d["osmid"], way_stop)


def _to_metres(lonlat, lat0):
    """Equirectangular projection around latitude lat0; good to well under 1% across a city."""
    xy = np.asarray(lonlat, dtype=float).reshape(-1, 2)
    return np.column_stack([xy[:, 0] * math.cos(math.radians(lat0)), xy[:, 1]]) * 111_320


def _streets(G, lat0):
    """Each street once, as a line in metres, with the directed edges (u, v, key) that run along it.

    A two-way street is two edges with the same geometry, one per direction.
    """
    streets = {}
    for u, v, k, d in G.edges(keys=True, data=True):
        street = (min(u, v), max(u, v), round(float(d["length"]), 1))
        if street not in streets:
            coords = d["geometry"].coords if "geometry" in d else [(G.nodes[n]["x"], G.nodes[n]["y"]) for n in (u, v)]
            streets[street] = (LineString(_to_metres(list(coords), lat0)), [])
        streets[street][1].append((u, v, k))
    return list(streets.values())


def snap_to_streets(lines, lonlat, lat0, max_m=SNAP_M):
    """For each point, the index of the nearest line within max_m metres, or -1."""
    snapped = np.full(len(lonlat), -1)
    if len(lonlat):
        point_idx, line_idx = STRtree(lines).query_nearest(points(_to_metres(lonlat, lat0)), max_distance=max_m)
        snapped[point_idx] = line_idx
    return snapped


def attach_danger(G, overtaking, pm):
    """Snap the overtaking and PM points to their nearest street and set edge attributes:
    `danger` (summed Risk Index Overtaking), `danger_points` (how many) and
    `pm_risk` (mean air rank of the PM points, or None where none was measured).

    `overtaking` and `pm` are (lon/lat list, risk list) pairs from point_risks.
    """
    lat0 = float(np.mean([y for _, y in G.nodes(data="y")]))
    streets = _streets(G, lat0)
    lines = [line for line, _ in streets]

    def per_street(lonlat, risks):
        snapped = snap_to_streets(lines, lonlat, lat0)
        hit = snapped >= 0
        n = np.bincount(snapped[hit], minlength=len(lines))
        total = np.bincount(snapped[hit], weights=np.asarray(risks, dtype=float)[hit], minlength=len(lines))
        return n, total

    danger_n, danger_sum = per_street(*overtaking)
    pm_n, pm_sum = per_street(*pm)
    for i, (_, edges) in enumerate(streets):
        for u, v, k in edges:
            d = G.edges[u, v, k]
            d["danger"] = float(danger_sum[i])
            d["danger_points"] = int(danger_n[i])
            d["pm_risk"] = float(pm_sum[i] / pm_n[i]) if pm_n[i] else None
