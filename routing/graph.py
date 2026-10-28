"""The Heilbronn bike graph from OSM (via OSMnx), with ATRAI roughness, stop-and-go, speed and danger, shade and
street lighting on every edge."""
import json
import math
from pathlib import Path

import numpy as np
import osmnx as ox
from shapely import LineString, STRtree, points

from download_data import load_features
from routing.costs import SNAP_M, air_ranks, clean_overtaking, edge_roughness, osm_way_ids, point_risks, way_roughness, way_speed, way_stop_go
from routing.lighting import load_lighting
from routing.rideable_ways import RIDEABLE_WAYS
from routing.shade import load_way_shade
from routing.shadow import load_shadow

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
# Renamed when the filter below changes, so an old cached graph isn't reused.
GRAPH_PATH = CACHE_DIR / "heilbronn_bike_rideable.graphml"
# Written by estimation/estimate_roughness.py: roughness of unmeasured OSM ways close to measured streets.
ESTIMATED_ROUGHNESS_PATH = CACHE_DIR.parent / "data" / "custom" / "roughness_estimates_heilbronn.json"
PLACE = "Heilbronn, Germany"

# OSMnx's network_type="bike" filter, with three changes:
# - leave out roads tagged bicycle=use_sidepath. They have a mandatory bike path beside them (StVO signs
#   237/240/241), so cycling on the road is illegal; that path is mapped as its own way and stays in the graph.
# - leave out bicycle=dismount ways, which can't be ridden.
# - let footways in; keep_rideable_footways then drops the ones bikes may not use.
# - let street crossings (footway=crossing) in even when tagged bicycle=no: cyclists push their bike across.
# - let short bicycle=no footways in as links between rideable places (see keep_rideable_footways).
BIKE_FILTER = (
    '["highway"]["area"!~"yes"]["access"!~"private"]'
    '["highway"!~"abandoned|bus_guideway|construction|corridor|elevator|'
    'escalator|motor|no|planned|platform|proposed|raceway|razed|'
    'rest_area|services|steps"]'
    '["bicycle"!~"no|use_sidepath|dismount"]["service"!~"private"]'
)
CROSSING_FILTER = '["highway"="footway"]["footway"="crossing"]["access"!~"private"]'
# Footways and paths with bicycle=no, which BIKE_FILTER leaves out. keep_rideable_footways keeps only the short
# ones that link two rideable places, where cyclists push their bike for a few metres.
NO_BIKE_FOOTWAY_FILTER = '["highway"~"^(footway|path)$"]["bicycle"="no"]["access"!~"private"]'
# A footway or path is rideable with one of these bicycle tags. Without a tag, bikes are not allowed on it.
BIKE_ALLOWED = {"yes", "designated", "permissive"}
FOOTWAY_TYPES = {"footway", "path"}
LINK_M = 30  # longest footway without a bicycle tag that may link two rideable places
GAP_M = 150  # longest footway without a bicycle tag that may fill a gap between two ways tagged bicycle=yes


def _allowed(d):
    """Whether bikes may use the edge: tagged bicycle=yes|designated|permissive, or listed in RIDEABLE_WAYS."""
    return bool(set(_tags(d.get("bicycle"))) & BIKE_ALLOWED) or bool(set(osm_way_ids(d["osmid"])) & RIDEABLE_WAYS.keys())


def _tags(value):
    """OSMnx merges tags of joined ways into lists; always a list."""
    return value if isinstance(value, list) else [value]


def keep_rideable_footways(G):
    """Remove footway/path edges that bikes may not use, from the graph.

    A footway or path stays if tagged bicycle=yes|designated|permissive, or listed in RIDEABLE_WAYS. Untagged ones stay only if they
    are bridge=yes ways or touch an elevator (highway=elevator node): bikes reach those bridges by lift
    (Campusbrücke) and the lift is marked on the map. Crossings (footway=crossing) always stay, as cyclists push across
    them. So do short links: footways up to LINK_M long whose both ends already touch a rideable edge, such as
    the island between two crossings or the stretch from a crossing to a bike path; cyclists push their bike
    over those. An untagged footway up to GAP_M long stays if both its ends touch ways tagged bicycle=yes, as that
    is a gap in the tagging of one path. Edges mixing footway with other highway types stay.
    """
    lifts = {n for n, d in G.nodes(data=True) if "elevator" in _tags(d.get("highway"))}
    drop = []
    for u, v, k, d in G.edges(keys=True, data=True):
        if not set(_tags(d["highway"])) <= FOOTWAY_TYPES:
            continue
        if _allowed(d):
            continue
        if "crossing" in _tags(d.get("footway")) or "yes" in _tags(d.get("bridge")) or u in lifts or v in lifts:
            continue
        drop.append((u, v, k))
    # A dropped edge comes back if it is a short link between two places that are still connected to rideable edges.
    dropped = set(drop)
    rideable = {n for u, v, k in G.edges(keys=True) if (u, v, k) not in dropped for n in (u, v)}
    signed = {n for u, v, d in G.edges(data=True) if _allowed(d) for n in (u, v)}

    # An untagged way up to GAP_M long that touches ways tagged bicycle=yes at two or more nodes is a gap in the
    # tagging of one path; the way may be split into several graph edges, so decide per OSM way.
    ways = {}
    for e in drop:
        d = G.edges[e]
        if "no" not in _tags(d.get("bicycle")) and not isinstance(d["osmid"], list):
            ways.setdefault(d["osmid"], []).append(e)
    gaps = set()
    for edges in ways.values():
        nodes = {n for u, v, k in edges for n in (u, v)}
        # A two-way footway is two edges, one per direction: count its length once.
        length = sum({(min(u, v), max(u, v)): float(G.edges[u, v, k]["length"]) for u, v, k in edges}.values())
        if length <= GAP_M and len(nodes & signed) >= 2:
            gaps.update(edges)

    def comes_back(u, v, k):
        return (u, v, k) in gaps or (float(G.edges[u, v, k]["length"]) <= LINK_M and u in rideable and v in rideable)

    back = {e for e in drop if comes_back(*e)}
    G.remove_edges_from(dropped - back)
    G.remove_nodes_from([n for n in list(G) if G.degree(n) == 0])


def load_graph(path=GRAPH_PATH):
    """Load the bike graph from cache/, downloading it from OSM the first time (~2 min).

    Delete the .graphml file to pick up newer OSM data.
    """
    path = Path(path)
    if path.exists():
        G = ox.load_graphml(path)
    else:
        ox.settings.cache_folder = CACHE_DIR
        ox.settings.useful_tags_way = sorted({*ox.settings.useful_tags_way, "bicycle", "footway"})  # keep_rideable_footways needs them
        G = ox.graph_from_place(PLACE, network_type="bike", custom_filter=[BIKE_FILTER, CROSSING_FILTER, NO_BIKE_FOOTWAY_FILTER], simplify=False)
        # Elevator nodes must survive simplification, as the footways only count as rideable near them.
        G = ox.simplify_graph(G, node_attrs_include=["highway"])
        keep_rideable_footways(G)
        ox.save_graphml(G, path)
    attach_lifts(G)
    attach_roughness(G, way_roughness(load_features("bumpy_roads_heilbronn")), load_estimates())
    attach_stop_go(G, way_stop_go(load_features("traffic_flow_heilbronn")))
    attach_speed(G, way_speed(load_features("speed_map_heilbronn")))
    attach_danger(G, point_risks(clean_overtaking(load_features("danger_zones_raw_heilbronn")), "Risk Index Overtaking"),
                  air_ranks(load_features("air_quality_heilbronn")))
    attach_shade(G, *load_shadow(), load_way_shade())
    attach_lighting(G, load_lighting())
    return G


def attach_lifts(G):
    """Set edge attributes `lift_start` and `lift_end`: whether the edge's first / last node is a lift
    (highway=elevator), so routing can charge for waiting for it."""
    lifts = {n for n, d in G.nodes(data=True) if "elevator" in _tags(d.get("highway"))}
    for u, v, d in G.edges(data=True):
        d["lift_start"] = u in lifts
        d["lift_end"] = v in lifts


def load_estimates(path=ESTIMATED_ROUGHNESS_PATH):
    """{OSM way id: estimated roughness} from estimation/estimate_roughness.py, or {} if the file is missing."""
    path = Path(path)
    return {int(k): v for k, v in json.loads(path.read_text()).items()} if path.exists() else {}


def attach_roughness(G, way_rough, estimated=None):
    """Set edge attributes `roughness` (0-100, or None where unknown) and `roughness_source`:
    "measured", "estimated" (from nearby measured streets, see estimation/README.md) or "unknown".
    """
    for _, _, d in G.edges(data=True):
        d["roughness"] = edge_roughness(d["osmid"], way_rough)
        d["roughness_source"] = "measured"
        if d["roughness"] is None:
            d["roughness"] = edge_roughness(d["osmid"], estimated or {})
            d["roughness_source"] = "unknown" if d["roughness"] is None else "estimated"


def attach_stop_go(G, way_stop):
    """Set edge attribute `stop_go` (0-1, or None where no bike has measured it)."""
    for _, _, d in G.edges(data=True):
        d["stop_go"] = edge_roughness(d["osmid"], way_stop)


def attach_speed(G, way_kmh):
    """Set edge attribute `speed_kmh` (measured cyclist speed, or None where no bike has measured it).
    Both directions of a street get the same value: speed_map is per segment, not per direction."""
    for _, _, d in G.edges(data=True):
        d["speed_kmh"] = edge_roughness(d["osmid"], way_kmh)


def attach_shade(G, slots, way_shadow, way_tree_shade=None):
    """Set edge attribute `shade`: a list with the share in shade (0-1) per time slot of `slots` (stored as
    G.graph["shade_slots"]), from routing.shadow; where a way has no shadow value, its static tree shade from
    routing.shade for every slot; None where neither is known.
    """
    G.graph["shade_slots"] = list(slots)
    for _, _, d in G.edges(data=True):
        ids = d["osmid"] if isinstance(d["osmid"], list) else [d["osmid"]]
        per_way = [way_shadow[i] if i in way_shadow else [way_tree_shade[i]] * len(slots)
                   for i in ids if i in way_shadow or i in (way_tree_shade or {})]
        d["shade"] = [sum(s) / len(per_way) for s in zip(*per_way)] if per_way else None


def attach_lighting(G, way_lit):
    """Set edge attribute `lit` (chance the street is lit at night, 0-1, or None where unknown) from routing.lighting."""
    for _, _, d in G.edges(data=True):
        d["lit"] = edge_roughness(d["osmid"], way_lit)


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
