"""The Heilbronn bike graph from OSM (via OSMnx), with ATRAI roughness, stop-and-go, speed and danger, shade and
street lighting on every edge."""
import json
import math
import sys
from datetime import date
from pathlib import Path

import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from shapely import LineString, STRtree, points, union_all

from download_data import load_features
from routing.costs import AIR_HOTSPOT_OFFSET, AIR_PRIOR_RIDES, CAR_HIGHWAYS, DANGER_MOVE_M, DEFAULT_PM_RISK, SNAP_M, air_scores, clean_overtaking, edge_roughness, osm_way_ids, point_risks, way_roughness, way_speed, way_stop_go
from routing.footways import DROPPED_FOOTWAYS_PATH, footway_collection, save_footways
from routing.lighting import load_light_density, load_lighting
from routing.named_roads import load_named_ways
from routing.rideable_ways import RIDEABLE_WAYS
from routing.shade import load_way_shade
from routing.shadow import load_shadow
from routing.surface import load_surface

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
# Raise when the filters or the changes to the graph below change, so every machine builds the graph again by itself.
GRAPH_VERSION = 1
# A cached graph this old is built again from the current OSM data.
GRAPH_MAX_AGE_DAYS = 30
# Written by load_graph, with the date and GRAPH_VERSION it was built with.
GRAPH_PATH = CACHE_DIR / "heilbronn_bike_rideable.graphml"
# Written next to it: the dead ends drop_orphan_stubs removed, to check them on a map.
DROPPED_STUBS_PATH = CACHE_DIR / "heilbronn_dropped_stubs.geojson"
# And the links link_sidepaths added from road ends to bike paths.
SIDEPATH_LINKS_PATH = CACHE_DIR / "heilbronn_sidepath_links.geojson"
# Written by estimation/estimate_roughness.py: roughness of unmeasured OSM ways close to measured streets.
ESTIMATED_ROUGHNESS_PATH = CACHE_DIR.parent / "data" / "custom" / "roughness_estimates_heilbronn.json"
# Written by routing/air_hotspots.py: the car roads of the clean-air plan's NO2 hotspot sections. A bike street with at
# least HOTSPOT_ALONG_SHARE of its length within HOTSPOT_ALONG_M of them runs along one (side paths, pavements), a
# street that only crosses one doesn't.
AIR_HOTSPOTS_PATH = CACHE_DIR.parent / "data" / "custom" / "air_hotspots_heilbronn.json"
HOTSPOT_ALONG_M = 15.0
HOTSPOT_ALONG_SHARE = 0.5
# attach_nearby_air: a street no air sensor passed takes the air of measured streets within this distance. 300 m
# reaches 61% of the street length (25% is measured itself); each counts 1 next to the street, 0 at the limit, and
# AIR_NEAR_PRIOR virtual streets at the prior keep one far neighbour from deciding alone.
AIR_NEAR_M = 300.0
AIR_NEAR_PRIOR = 1.0
# Bike paths, bike lanes and bike routes from OSM (Overpass query next to it), for prefer_bike_friendly.
BIKE_FRIENDLY_PATH = CACHE_DIR.parent / "data" / "custom" / "bike_friendly_streets_heilbronn.geojson"
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
# Roads bikes may not use, which BIKE_FILTER leaves out. Where a short road ends on one of them, routing is left with a
# dead end: see drop_orphan_stubs.
CUT_FILTER = ('["highway"~"^(trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|road)(_link)?$"]'
              '["bicycle"~"^(no|use_sidepath|dismount)$"]["access"!~"private"]')
STUB_M = 50  # longest dead end that drop_orphan_stubs removes
# link_sidepaths: a road that ends at a use_sidepath road links to a bike path vertex this near.
SIDEPATH_LINK_M = 20
SIDEPATH_TYPES = {"cycleway", "footway", "path", "pedestrian", "bridleway"}
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

    Returns the removed footways as routing.footways.footway_collection, for riders to report the ones bikes ride on.
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
    removed = footway_collection(G, dropped - back)
    G.remove_edges_from(dropped - back)
    G.remove_nodes_from([n for n in list(G) if G.degree(n) == 0])
    return removed


def _stub(G, U, end):
    """(nodes, edges) of the dead end that starts at the free node `end` of the undirected U, up to the junction where it
    meets the rest of the graph (not included), or None if it is longer than STUB_M. `edges` are (u, v, key) of G."""
    nodes, edges, length = [end], [], 0.0
    while True:
        (ahead,) = [m for m in U[nodes[-1]] if m not in nodes]
        pieces = [(a, b, k, d) for a, b in ((nodes[-1], ahead), (ahead, nodes[-1])) if G.has_edge(a, b) for k, d in G[a][b].items()]
        length += min(float(d["length"]) for *_, d in pieces)  # a two-way road is two edges: count it once
        if length > STUB_M:
            return None
        edges += [(a, b, k) for a, b, k, _ in pieces]
        if U.degree(ahead) != 2:
            if U.degree(ahead) == 1:  # free at both ends: nothing else holds it
                nodes.append(ahead)
            return nodes, edges
        nodes.append(ahead)


def drop_orphan_stubs(G, cut_nodes):
    """Remove short dead-end roads that only exist because BIKE_FILTER cut off the road they ended on, from the graph.

    A stub runs at most STUB_M metres from a free end (a node with one neighbour) that lies on one of `cut_nodes`, the
    roads bikes may not use (CUT_FILTER), to the junction where it meets the rest of the graph: a service road between a
    bike path and Mannheimer Strasse. It leads nowhere now, but a trip starting next to it would snap onto it. Dead ends
    that end in OSM itself stay, as a road to a building doesn't end on a cut road. That holds for driveways and parking
    aisles too: one that only joins a bike path to a cut road is a leftover, whatever its service tag.

    Returns the removed edges as routing.footways.footway_collection, to check what was removed.
    """
    U = nx.Graph(G)
    removed = []
    for end in [n for n in U if n in cut_nodes and U.degree(n) == 1]:
        stub = _stub(G, U, end)
        if stub:
            removed += stub[1]
    collection = footway_collection(G, removed)
    G.remove_edges_from(removed)
    G.remove_nodes_from([n for n in list(G) if G.degree(n) == 0])
    return collection


def _path(d):
    """Whether the edge is a path bikes may ride beside a road: a cycleway, or a footway or path they may use
    (_allowed); not a crossing."""
    highways = set(_tags(d["highway"]))
    return highways <= SIDEPATH_TYPES and ("cycleway" in highways or _allowed(d)) and "crossing" not in _tags(d.get("footway"))


def _coords(G, u, v, d):
    return list(d["geometry"].coords) if "geometry" in d else [(G.nodes[n]["x"], G.nodes[n]["y"]) for n in (u, v)]


def _split(G, u, v, at, node):
    """Split the edges between u and v (both directions) at their vertex `at` (lon, lat), which becomes `node`."""
    G.add_node(node, x=at[0], y=at[1])
    for a, b in ((u, v), (v, u)):
        for k, d in list(G[a][b].items()) if G.has_edge(a, b) else []:
            coords = _coords(G, a, b, d)
            i = coords.index(at)
            first, second = LineString(coords[:i + 1]), LineString(coords[i:])
            share = first.length / (first.length + second.length)
            G.remove_edge(a, b, k)
            G.add_edge(a, node, **{**d, "geometry": first, "length": float(d["length"]) * share})
            G.add_edge(node, b, **{**d, "geometry": second, "length": float(d["length"]) * (1 - share)})


def link_sidepaths(G, sidepath_nodes, node_ids):
    """Link roads that end where BIKE_FILTER cut off a bicycle=use_sidepath road to the bike path that takes over.

    The road on is left out, and OSM rarely joins the path to it: westbound Mannheimer Strasse ends at Schaeuffelenstrasse
    with its bike path starting 11 m north. A road end is a node of `sidepath_nodes` (the use_sidepath roads) where a road
    of the graph arrives with no way on, or leaves with no way in. It gets an edge to the nearest vertex of a rideable path
    (_path) within SIDEPATH_LINK_M, in the direction(s) the road is ridden, unless that edge would cross another road. A
    vertex inside an edge becomes a node: its OSM id from `node_ids` {(lon, lat): id} of the graph before simplifying.
    The link takes the path's tags and data, and its length as the crow flies.

    Returns the added links as routing.footways.footway_collection, under the path's OSM way, to check them on a map.
    """
    lat0 = float(np.mean([y for _, y in G.nodes(data="y")]))
    roads = [(u, v, LineString(_to_metres(_coords(G, u, v, d), lat0))) for u, v, d in G.edges(data=True)
             if not set(_tags(d["highway"])) <= SIDEPATH_TYPES]
    road_tree = STRtree([line for *_, line in roads])
    vertices = {}  # (lon, lat) -> (u, v) of a path edge it lies on
    for u, v, d in G.edges(data=True):
        if _path(d):
            for c in _coords(G, u, v, d):
                vertices.setdefault(c, (u, v))
    spots = list(vertices)
    tree = STRtree(points(_to_metres(spots, lat0)))
    links = []
    for n in [n for n in G if n in sidepath_nodes]:
        ahead, behind = set(G.successors(n)), set(G.predecessors(n))
        if all(set(_tags(d["highway"])) <= SIDEPATH_TYPES for *_, d in [*G.in_edges(n, data=True), *G.out_edges(n, data=True)]):
            continue  # a path itself, not a road end
        one = len(ahead | behind) == 1
        out_link, in_link = bool(behind) and (not ahead or one), bool(ahead) and (not behind or one)
        if not (out_link or in_link):
            continue
        here = (G.nodes[n]["x"], G.nodes[n]["y"])
        at = points(_to_metres([here], lat0))[0]
        near = sorted((at.distance(tree.geometries[i]), spots[i])
                      for i in tree.query(at, predicate="dwithin", distance=SIDEPATH_LINK_M))
        for dist, spot in near:
            u, v = vertices[spot]
            if n in (u, v) or spot == here:
                continue
            line = LineString(_to_metres([here, spot], lat0))
            # Another road between the end and the path: one not at the end that meets the link short of the path.
            crossed = (roads[i] for i in road_tree.query(line, predicate="intersects"))
            if any(n not in (a, b) and line.intersection(road).distance(points(line.coords[-1])) > 1 for a, b, road in crossed):
                continue
            target = next((m for m in (u, v) if (G.nodes[m]["x"], G.nodes[m]["y"]) == spot), None)
            if target is None:
                target = node_ids[spot]
                _split(G, u, v, spot, target)
                for a, b in ((u, target), (target, v)):
                    if G.has_edge(a, b):
                        vertices.update({c: (a, b) for c in _coords(G, a, b, G.edges[a, b, 0])})
            data = next(d for *_, d in [*G.out_edges(target, data=True), *G.in_edges(target, data=True)] if _path(d))
            for a, b, ok in ((n, target, out_link), (target, n, in_link)):
                if ok:
                    coords = [here, spot] if a == n else [spot, here]
                    links.append((a, b, G.add_edge(a, b, **{**data, "geometry": LineString(coords), "length": dist})))
            break
    return footway_collection(G, links)


def build_graph(rideable, refresh=False):
    """Download the bike graph from OSM and apply the changes above. `refresh` ignores OSMnx's cached responses, to get
    the current OSM data.

    Returns the graph and the footways, links and dead ends (as routing.footways.footway_collection) left out or added,
    for the caller to write once the build worked: a failing one leaves the old files in place.
    """
    ox.settings.cache_folder = CACHE_DIR
    ox.settings.use_cache = not refresh
    ox.settings.useful_tags_way = sorted({*ox.settings.useful_tags_way, "bicycle", "footway", "service"})  # keep_rideable_footways and drop_orphan_stubs need them
    G = ox.graph_from_place(PLACE, network_type="bike", custom_filter=[BIKE_FILTER, CROSSING_FILTER, NO_BIKE_FOOTWAY_FILTER], simplify=False)
    node_ids = {(d["x"], d["y"]): n for n, d in G.nodes(data=True)}  # link_sidepaths makes some of them nodes again
    # Elevator nodes must survive simplification, as the footways only count as rideable near them.
    G = ox.simplify_graph(G, node_attrs_include=["highway"])
    footways = keep_rideable_footways(G)
    cut = ox.graph_from_place(PLACE, custom_filter=CUT_FILTER, retain_all=True, simplify=False)
    sidepath_nodes = {n for u, v, d in cut.edges(data=True) if "use_sidepath" in _tags(d.get("bicycle")) for n in (u, v)}
    # Links first: a bike path that starts on the cut road is a dead end until a road end links to it.
    links = link_sidepaths(G, sidepath_nodes, node_ids)
    stubs = drop_orphan_stubs(G, set(cut))
    G.graph.update(rideable_ways=rideable, version=GRAPH_VERSION, built=date.today().isoformat())
    return G, footways, links, stubs


def _warn_loudly(*lines):
    bar = "!" * 100
    print(*["", bar, *(f"!!! {line}" for line in lines), bar, ""], sep="\n", file=sys.stderr, flush=True)


def _age_days(G, path):
    """Days since the graph was built from OSM; for one cached before the date was recorded, since its file changed."""
    try:
        built = date.fromisoformat(G.graph["built"])
    except (KeyError, ValueError):
        built = date.fromtimestamp(path.stat().st_mtime)
    return (date.today() - built).days


def load_graph(path=GRAPH_PATH, footways_path=DROPPED_FOOTWAYS_PATH, stubs_path=DROPPED_STUBS_PATH,
               links_path=SIDEPATH_LINKS_PATH):
    """Load the bike graph from cache/, downloading it from OSM the first time (~2 min).

    It is built again by itself when GRAPH_VERSION or RIDEABLE_WAYS (e.g. an approved user report) changed, as they decide
    what the graph holds, and when the footways it left out (`footways_path`, see routing.footways), the dead ends it
    removed (`stubs_path`) or the links it added to bike paths (`links_path`) are missing. Once it is GRAPH_MAX_AGE_DAYS
    old it is built again from the current OSM data; if that fails (Overpass down), the old graph stays in use.
    """
    path, footways_path, stubs_path, links_path = Path(path), Path(footways_path), Path(stubs_path), Path(links_path)
    rideable = ",".join(map(str, sorted(RIDEABLE_WAYS)))
    G = ox.load_graphml(path) if path.exists() else None
    if G is not None and "rideable_ways" not in G.graph:
        # Cached before the list was recorded, when it held only the hand-picked ways: record it.
        G.graph["rideable_ways"] = rideable
        ox.save_graphml(G, path)
    outdated = (G is None or G.graph["rideable_ways"] != rideable or G.graph.get("version") != str(GRAPH_VERSION)
                or not footways_path.exists() or not stubs_path.exists() or not links_path.exists())
    if outdated and G is not None:
        _warn_loudly("The graph logic changed (GRAPH_VERSION, the hand-picked ways or a check file): rebuilding the graph.",
                     "This reuses the OSM responses cached in cache/*.json, so it does NOT pick up newer OSM data.",
                     "Consider a fresh rebuild: delete cache/*.json and cache/heilbronn_bike_rideable.graphml.")
    if outdated or _age_days(G, path) >= GRAPH_MAX_AGE_DAYS:
        try:
            built, footways, links, stubs = build_graph(rideable, refresh=not outdated)
        except Exception as e:
            if outdated:
                raise
            print(f"Could not refresh the graph from OSM, keeping the one from {G.graph.get('built', 'earlier')}: {e}")
        else:
            G = built
            save_footways(footways, footways_path)
            save_footways(links, links_path)
            save_footways(stubs, stubs_path)
            ox.save_graphml(G, path)
    attach_lifts(G)
    attach_roughness(G, way_roughness(load_features("bumpy_roads_heilbronn")), load_estimates())
    attach_stop_go(G, way_stop_go(load_features("traffic_flow_heilbronn")))
    attach_speed(G, way_speed(load_features("speed_map_heilbronn")))
    attach_danger(G, point_risks(clean_overtaking(load_features("danger_zones_raw_heilbronn")), "Risk Index Overtaking"),
                  air_scores(load_features("air_quality_heilbronn"), load_features("air_background_heilbronn")),
                  load_hotspot_roads())
    attach_shade(G, *load_shadow(), load_way_shade())
    attach_lighting(G, load_lighting(), load_light_density())
    attach_bike_friendly(G, load_bike_friendly_ways())
    attach_bike_lanes(G, load_bike_lanes())
    attach_surface(G, load_surface())
    attach_nearby_air(G)
    G.graph["named_ways"] = load_named_ways()  # to name streets on the map and in stretches (routing.route)
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


def load_hotspot_roads(path=AIR_HOTSPOTS_PATH):
    """[(lon, lat), ...] lines of the clean-air plan's NO2 hotspot roads (routing/air_hotspots.py), or [] if the file is missing."""
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8"))["roads"] if path.exists() else []


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
    routing.shade for every slot; None where neither is known. Also `trees`: the street-tree canopy alone (0-1, or None
    where unknown), for the greenest streets (routing.highlights).
    """
    G.graph["shade_slots"] = list(slots)
    for _, _, d in G.edges(data=True):
        d["trees"] = edge_roughness(d["osmid"], way_tree_shade or {})
        ids = d["osmid"] if isinstance(d["osmid"], list) else [d["osmid"]]
        per_way = [way_shadow[i] if i in way_shadow else [way_tree_shade[i]] * len(slots)
                   for i in ids if i in way_shadow or i in (way_tree_shade or {})]
        d["shade"] = [sum(s) / len(per_way) for s in zip(*per_way)] if per_way else None


def load_bike_friendly_ways(path=BIKE_FRIENDLY_PATH):
    """OSM way ids of the bike-friendly streets ("way/123" -> 123), or an empty set if the file is missing."""
    path = Path(path)
    if not path.exists():
        return set()
    return {int(f["id"].split("/")[1]) for f in json.loads(path.read_text(encoding="utf-8"))["features"]}


def attach_bike_friendly(G, ways):
    """Set edge attribute `bike_friendly`: whether any OSM way the edge is made of is in `ways`."""
    for _, _, d in G.edges(data=True):
        d["bike_friendly"] = any(i in ways for i in osm_way_ids(d["osmid"]))


def load_bike_lanes(path=BIKE_FRIENDLY_PATH):
    """What the bike-friendly roads give bikes, per OSM way id: "bicycle_road" (Fahrradstraße), "track" (a bike
    path along the road, tagged on the road) or "lane" (painted). Bike routes, shared lanes and ways mapped as their
    own bike path are left out. Empty if the file is missing."""
    path = Path(path)
    if not path.exists():
        return {}
    lanes = {}
    for f in json.loads(path.read_text(encoding="utf-8"))["features"]:
        p = f["properties"]
        tags = {p.get(k) for k in ("cycleway", "cycleway:both", "cycleway:left", "cycleway:right")}
        kind = "bicycle_road" if p.get("bicycle_road") == "yes" else "track" if "track" in tags else "lane" if "lane" in tags else None
        if kind:
            lanes[int(f["id"].split("/")[1])] = kind
    return lanes


def attach_bike_lanes(G, lanes):
    """Set edge attribute `bike_lane`: the best of load_bike_lanes' kinds among the OSM ways of the edge, or None."""
    best = ("bicycle_road", "track", "lane")
    for _, _, d in G.edges(data=True):
        kinds = {lanes.get(i) for i in osm_way_ids(d["osmid"])}
        d["bike_lane"] = next((k for k in best if k in kinds), None)


def attach_nearby_air(G):
    """Set edge attribute `pm_near` on streets no air sensor passed (`pm_risk` None): the measured streets within
    AIR_NEAR_M, weighted by how close they are (1 next to it, 0 at AIR_NEAR_M), pulled towards the street's own
    `pm_prior` by AIR_NEAR_PRIOR. Air spreads over an area, not along one street. None with no measured street near.
    Only for the overall score (routing.score); routing leaves unmeasured streets at their prior."""
    lat0 = float(np.mean([y for _, y in G.nodes(data="y")]))
    streets = _streets(G, lat0)
    first = [G.edges[edges[0]] for _, edges in streets]
    measured = [i for i, d in enumerate(first) if d.get("pm_risk") is not None]
    near = {}
    if measured:
        tree = STRtree([streets[i][0] for i in measured])
        todo = [i for i, d in enumerate(first) if d.get("pm_risk") is None]
        pairs = tree.query([streets[i][0] for i in todo], predicate="dwithin", distance=AIR_NEAR_M)
        for t, m in zip(*pairs):
            i, j = todo[t], measured[m]
            w = 1 - streets[i][0].distance(streets[j][0]) / AIR_NEAR_M
            s, n = near.get(i, (0.0, 0.0))
            near[i] = (s + w * first[j]["pm_risk"], n + w)
    for i, (_, edges) in enumerate(streets):
        for e in edges:
            d = G.edges[e]
            if i in near:
                s, n = near[i]
                d["pm_near"] = float((s + AIR_NEAR_PRIOR * d.get("pm_prior", DEFAULT_PM_RISK)) / (n + AIR_NEAR_PRIOR))
            else:
                d["pm_near"] = None


def attach_surface(G, way_unpaved):
    """Set edge attribute `unpaved` (0 paved to 1 soil or grass, routing.surface): the mean over the OSM ways of the
    edge, ways not in `way_unpaved` counting as paved."""
    for _, _, d in G.edges(data=True):
        ids = osm_way_ids(d["osmid"])
        d["unpaved"] = sum(way_unpaved.get(i, 0.0) for i in ids) / len(ids)


def attach_lighting(G, way_lit, way_lights=None):
    """Set edge attributes `lit` (chance the street is lit at night, 0-1, or None where unknown) and
    `lights_per_100m` (Mapillary street lights per 100 m, or None where none was seen) from routing.lighting."""
    for _, _, d in G.edges(data=True):
        d["lit"] = edge_roughness(d["osmid"], way_lit)
        d["lights_per_100m"] = edge_roughness(d["osmid"], way_lights or {})


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


def _car_street(d):
    """Whether cars drive on the edge (CAR_HIGHWAYS, or no highway tag)."""
    h = d.get("highway")
    return h is None or bool({str(x) for x in (h if isinstance(h, list) else [h])} & CAR_HIGHWAYS)


def attach_danger(G, overtaking, pm, hotspot_roads=()):
    """Snap the overtaking and PM points to their nearest street and set edge attributes:
    `danger` (summed Risk Index Overtaking; 0 on car-free ways, see CAR_HIGHWAYS and DANGER_MOVE_M), `danger_points` (how many),
    `pm_prior` (air score before any ride: DEFAULT_PM_RISK, plus AIR_HOTSPOT_OFFSET on a street that runs along
    one of `hotspot_roads`, [(lon, lat), ...] lines), `pm_risk` (air score, or None where none was measured) and `pm_rides` (how many rides
    measured it). `pm_risk` is the mean over rides of each ride's mean score on the street, pulled towards
    `pm_prior` by AIR_PRIOR_RIDES virtual rides: a street one bike passed once stays close to its prior.

    `overtaking` is a (lon/lat list, risk list) pair from point_risks, `pm` the (lon/lat, score, ride) lists of air_scores.
    """
    lat0 = float(np.mean([y for _, y in G.nodes(data="y")]))
    streets = _streets(G, lat0)
    lines = [line for line, _ in streets]

    car = np.array([_car_street(G.edges[edges[0]]) for _, edges in streets], dtype=bool)
    car_streets = np.flatnonzero(car)

    def snap_overtaking(lonlat):
        """Street index per point (-1: none): a point whose nearest street is car-free moves to the nearest car street
        within DANGER_MOVE_M, else it is dropped."""
        snapped = snap_to_streets(lines, lonlat, lat0)
        free = (snapped >= 0) & ~car[snapped]
        if free.any():
            moved = np.full(int(free.sum()), -1)
            if len(car_streets):
                moved = snap_to_streets([lines[i] for i in car_streets], np.asarray(lonlat)[free], lat0, DANGER_MOVE_M)
            snapped[free] = np.where(moved >= 0, car_streets[moved], -1)
        return snapped

    def per_street(lonlat, risks, snap=lambda lonlat: snap_to_streets(lines, lonlat, lat0)):
        snapped = snap(lonlat)
        hit = snapped >= 0
        n = np.bincount(snapped[hit], minlength=len(lines))
        total = np.bincount(snapped[hit], weights=np.asarray(risks, dtype=float)[hit], minlength=len(lines))
        return n, total

    danger_n, danger_sum = per_street(*overtaking, snap=snap_overtaking)
    pm_lonlat, pm_score, pm_ride = pm
    pm_street = snap_to_streets(lines, pm_lonlat, lat0)
    per_ride = pd.DataFrame({"street": pm_street, "ride": pm_ride, "score": pm_score}, columns=["street", "ride", "score"])
    per_ride = per_ride[pm_street >= 0].groupby(["street", "ride"]).score.mean().groupby(level=0)
    pm_n, pm_sum = per_ride.size(), per_ride.sum()
    hot = np.zeros(len(lines), bool)
    if len(hotspot_roads):
        zone = union_all([LineString(_to_metres(r, lat0)).buffer(HOTSPOT_ALONG_M) for r in hotspot_roads])
        for i in STRtree(lines).query(zone, predicate="intersects"):
            hot[i] = lines[i].intersection(zone).length >= HOTSPOT_ALONG_SHARE * lines[i].length
    for i, (_, edges) in enumerate(streets):
        for u, v, k in edges:
            d = G.edges[u, v, k]
            d["danger"] = float(danger_sum[i])
            d["danger_points"] = int(danger_n[i])
            d["pm_prior"] = DEFAULT_PM_RISK + AIR_HOTSPOT_OFFSET * bool(hot[i])
            n = int(pm_n.get(i, 0))
            d["pm_risk"] = float((pm_sum[i] + AIR_PRIOR_RIDES * d["pm_prior"]) / (n + AIR_PRIOR_RIDES)) if n else None
            d["pm_rides"] = n
