"""Helpers for turning the ATRAI bumpy_roads data into routing costs on the OSM graph."""
import ast

# Normalized Roughness (0-100) assumed for streets no bike has measured.
# 10 is the median of the measured Heilbronn segments.
DEFAULT_ROUGHNESS = 10.0

# "How much do you hate bumps". Roughness clusters around 10, so a penalty of 2
# barely changes routes; around 10 trades a ~1-2% detour for smoother streets.
DEFAULT_PENALTY = 10.0


def osm_way_ids(osmid):
    """`osmid` is a string: either "83738619" or a merged list "[439572396, 401802699]"."""
    s = str(osmid)
    return [int(x) for x in ast.literal_eval(s)] if s.startswith("[") else [int(s)]


def way_roughness(bumpy_features):
    """Mean Normalized Roughness per OSM way id, from the bumpy_roads_heilbronn features."""
    values = {}
    for f in bumpy_features:
        p = f["properties"]
        if p.get("Normalized Roughness") is None:
            continue
        for way in osm_way_ids(p["osmid"]):
            values.setdefault(way, []).append(p["Normalized Roughness"])
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
