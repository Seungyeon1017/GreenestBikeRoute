"""Helpers for turning the ATRAI bumpy_roads and danger_zones data into routing costs on the OSM graph."""
import ast

# Normalized Roughness (0-100) assumed for streets no bike has measured.
# 10 is the median of the measured Heilbronn segments.
DEFAULT_ROUGHNESS = 10.0

# "How much do you hate bumps". Roughness clusters around 10, so a bump_penalty of 2
# barely changes routes; around 10 trades a ~1-2% detour for smoother streets.
DEFAULT_BUMP_PENALTY = 10.0

# A danger point counts for its nearest street when within this distance (GPS noise).
# Catches ~90% of the points inside the city; the rest are mostly rides outside Heilbronn.
SNAP_M = 25.0

# danger_zones: points where a car overtook a bike, Risk Index Overtaking 0-1. They add up,
# so this is the detour in metres you'd ride to pass one fewer full-risk overtaking spot.
# Spots cluster on a few main roads: 25 already avoids most of them for a few % detour.
DEFAULT_DANGER_PENALTY = 25.0

# danger_zones_PM: Risk Index 0-1 (traffic + air quality) sampled every ~20 m along rides,
# so it is averaged per street like roughness. The default for unmeasured streets is the
# median of the measured Heilbronn streets. Street means only span ~0.24-0.40, so the
# penalty needs to be fairly high (5-20) before routes change much.
DEFAULT_PM_RISK = 0.33
DEFAULT_PM_PENALTY = 2.0


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


def point_risks(features, risk_key):
    """(lon, lat) and risk of every danger_zones point that has a risk value."""
    keep = [f for f in features if f["properties"].get(risk_key) is not None]
    return [tuple(f["geometry"]["coordinates"]) for f in keep], [f["properties"][risk_key] for f in keep]


def edge_cost(length_m, normalized_roughness=DEFAULT_ROUGHNESS, bump_penalty=DEFAULT_BUMP_PENALTY,
              danger=0.0, danger_penalty=DEFAULT_DANGER_PENALTY,
              pm_risk=DEFAULT_PM_RISK, pm_penalty=DEFAULT_PM_PENALTY):
    """Routing cost: plain length, inflated on rough and polluted streets, plus a fixed
    `danger_penalty` metres per unit of overtaking risk (`danger` = summed risk on the edge).

    Normalized Roughness is 0-100 in the live data (not 0-1 as the docs table says).
    """
    return length_m * (1 + bump_penalty * normalized_roughness / 100 + pm_penalty * pm_risk) + danger_penalty * danger
