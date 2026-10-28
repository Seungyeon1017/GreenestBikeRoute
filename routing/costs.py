"""Helpers for turning the ATRAI bumpy_roads data into routing costs on the OSM graph."""
import ast

# Normalized Roughness (0-100) assumed for streets no bike has measured.
# 10 is the median of the measured Heilbronn segments.
DEFAULT_ROUGHNESS = 10.0

# ATRAI avg_traffic_flow (0-1) assumed for streets without a measurement or nearby estimate.
# 0.37 is the median of the measured Heilbronn segments. Not used in edge_cost yet.
DEFAULT_TRAFFIC_FLOW = 0.37

# "How much do you hate bumps". Roughness clusters around 10, so a penalty of 2
# barely changes routes; around 10 trades a ~1-2% detour for smoother streets.
DEFAULT_PENALTY = 10.0


def osm_way_ids(osmid):
    """`osmid` is a string: either "83738619" or a merged list "[439572396, 401802699]"."""
    s = str(osmid)
    return [int(x) for x in ast.literal_eval(s)] if s.startswith("[") else [int(s)]


def way_roughness(bumpy_features):
    """Mean Normalized Roughness per OSM way id, from the bumpy_roads_heilbronn features."""
    return way_means(bumpy_features, "Normalized Roughness")


def way_means(features, value_key):
    """Mean of property `value_key` per OSM way id; merged-way features count for each of their ways."""
    values = {}
    for f in features:
        p = f["properties"]
        if p.get(value_key) is None:
            continue
        for way in osm_way_ids(p["osmid"]):
            values.setdefault(way, []).append(p[value_key])
    return {way: sum(v) / len(v) for way, v in values.items()}


def edge_roughness(osmid, way_rough):
    """Mean roughness of the OSM ways a graph edge is made of, or None if none was measured.

    OSMnx gives `osmid` as an int, or a list of ints when it merged several ways into one edge.
    """
    ids = osmid if isinstance(osmid, list) else [osmid]
    measured = [way_rough[i] for i in ids if i in way_rough]
    return sum(measured) / len(measured) if measured else None


def edge_cost(length_m, normalized_roughness=DEFAULT_ROUGHNESS, penalty=DEFAULT_PENALTY):
    """Routing cost: plain length, inflated up to (1 + penalty)x on the roughest streets.

    Normalized Roughness is 0-100 in the live data (not 0-1 as the docs table says).
    """
    return length_m * (1 + penalty * normalized_roughness / 100)
