"""Helpers for turning the ATRAI bumpy_roads data into routing costs on the OSM graph."""
import ast

# Normalized Roughness (0-100) assumed for streets no bike has measured.
# 10 is the median of the measured Heilbronn segments.
DEFAULT_ROUGHNESS = 10.0


def osm_way_ids(osmid):
    """`osmid` is a string: either "83738619" or a merged list "[439572396, 401802699]"."""
    s = str(osmid)
    return [int(x) for x in ast.literal_eval(s)] if s.startswith("[") else [int(s)]


def edge_cost(length_m, normalized_roughness=DEFAULT_ROUGHNESS, penalty=2.0):
    """Routing cost: plain length, inflated up to (1 + penalty)x on the roughest streets.

    Normalized Roughness is 0-100 in the live data (not 0-1 as the docs table says).
    """
    return length_m * (1 + penalty * normalized_roughness / 100)
