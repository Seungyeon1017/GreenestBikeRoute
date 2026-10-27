"""Helpers for turning the ATRAI bumpy_roads and danger_zones data into routing costs on the OSM graph."""
import ast

import numpy as np
import pandas as pd

# Normalized Roughness (0-100) assumed for streets no bike has measured.
# 10 is the median of the measured Heilbronn segments.
DEFAULT_ROUGHNESS = 10.0

# "How much do you hate bumps". Roughness clusters around 10, so a bump_penalty of 2
# barely changes routes; around 10 trades a ~1-2% detour for smoother streets.
DEFAULT_BUMP_PENALTY = 10.0

# A danger point counts for its nearest street when within this distance (GPS noise).
# Catches ~90% of the points inside the city; the rest are mostly rides outside Heilbronn.
SNAP_M = 25.0

# danger_zones_raw: points where a car overtook a bike, Risk Index Overtaking 0-1. They add up,
# so this is the detour in metres you'd ride to pass one fewer full-risk overtaking spot.
# Spots cluster on a few main roads: 25 already avoids most of them for a few % detour.
DEFAULT_DANGER_PENALTY = 25.0

# Readings of 25 cm or less are ignored (see "Which overtaking readings count" in routing/README.md).
# 25 cm is also where the overtaking_distance dataset starts counting.
MIN_OVERTAKING_CM = 25.0

# air_quality: air rank 0-1 within its ride (see air_ranks) sampled every ~20 m along
# rides, so it is averaged per street like roughness. Unmeasured streets get 0.5, a typical reading.
# Street means span ~0.13-0.87, but streets agree only weakly between days (correlation ~0.17),
# so the default penalty is kept mild.
DEFAULT_PM_RISK = 0.5
DEFAULT_PM_PENALTY = 0.5

# Rides (one device, one day) with fewer rows can't say what is typical for them; ~0.1% of rows.
MIN_RIDE_POINTS = 20

# The PM weights of danger_zones_PM's Risk Index (0.20, 0.15, 0.10, 0.05) without its overtaking
# part, scaled to sum to 1. Overtaking is already counted through danger_zones_raw.
PM_WEIGHTS = {"Finedust PM1": 0.4, "Finedust PM2.5": 0.3, "Finedust PM4": 0.2, "Finedust PM10": 0.1}


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


def clean_overtaking(features):
    """The danger_zones_raw rows routing counts: a measured distance over MIN_OVERTAKING_CM.

    Readings of 25 cm or less and rows with no distance (0 or missing) are left out.
    """
    return [f for f in features if (f["properties"]["Overtaking Distance"] or 0) > MIN_OVERTAKING_CM]


def air_risks(features):
    """(lon, lat) and air Risk Index (0-1) of every air_quality row: each PM value divided
    by its maximum over `features`, weighted by PM_WEIGHTS. The rows are free of spikes already
    (see download_data.clean_pm_rows), so the maximum is a real reading.
    """
    if not features:
        return [], []
    pm = np.array([[f["properties"][k] for k in PM_WEIGHTS] for f in features], dtype=float)
    risk = (pm / pm.max(axis=0)) @ np.array(list(PM_WEIGHTS.values()))
    return [tuple(f["geometry"]["coordinates"]) for f in features], risk.tolist()


def air_ranks(features):
    """(lon, lat) and air rank (0-1) of every air_quality row in a ride of at least
    MIN_RIDE_POINTS rows: where its air_risks value falls within its ride (same device, same day).
    0.5 is a typical reading for that ride, so weather and sensor offsets drop out.
    """
    lonlat, risk = air_risks(features)
    rides = pd.Series([f["properties"]["boxId"] + f["properties"]["createdAt"][:10] for f in features], dtype=object)
    by_ride = pd.Series(risk, dtype=float).groupby(rides)
    size = by_ride.transform("size")
    rank = (by_ride.rank() - 0.5) / size
    keep = (size >= MIN_RIDE_POINTS).to_numpy()
    return [p for p, k in zip(lonlat, keep) if k], rank[keep].tolist()


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
