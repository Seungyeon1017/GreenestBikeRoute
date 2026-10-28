"""Helpers for turning the ATRAI bumpy_roads, danger_zones, air_quality, traffic_flow and speed_map data, plus shade
and street lighting, into routing costs on the OSM graph."""
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

# air_quality: air score 0-1 (see air_scores) sampled every ~20 m along rides, averaged per street by ride
# (see AIR_PRIOR_RIDES), which keeps street values within ~0.44-0.58 (5-95%). Unmeasured streets get 0.5, a typical
# reading. Streets agree only weakly between bikes (rank correlation ~0.24 between halves of the bike sensors,
# ~0.39 between halves of the days), so the default penalty is kept mild.
DEFAULT_PM_RISK = 0.5
DEFAULT_PM_PENALTY = 0.5

# air_scores: a reading this far above its ride's median (in weighted log ratio to the senseBox:home
# background) scores 1, as far below scores 0. 0.3 is about 1.35x the ride's usual air; ~10% of rows reach it.
AIR_SPREAD = 0.3

# A street's air is the mean over the rides that passed it (each ride's readings averaged first: they share one
# sensor, one moment and one weather), pulled towards DEFAULT_PM_RISK by AIR_PRIOR_RIDES virtual rides. A third of
# the measured streets have a single ride. Predicting held-out rides (other bikes, or other days), plain point means
# do 25-30% worse than no air data at all; 8 rides does best, slightly better than no data (1% by bike, 3.5% by day).
AIR_PRIOR_RIDES = 8
# Streets along the clean-air plan's NO2 hotspots (routing.air_hotspots) start this much above DEFAULT_PM_RISK, before
# any ride: the difference between their measured mean (0.557) and other streets' (0.530). Within the same ride, bikes
# read +0.06 higher there than on other main roads (181 rides). Predicting held-out rides, it beats 0.5 for them in
# 26-28 of 30 splits (-2 to -2.6% error there); a regression on road class, traffic nearby, buildings and trees did not.
AIR_HOTSPOT_OFFSET = 0.025

# Rides (one device, one day) with fewer rows can't say what is typical for them; ~0.1% of rows.
MIN_RIDE_POINTS = 20

# The PM weights of danger_zones_PM's Risk Index (0.20, 0.15, 0.10, 0.05) without its overtaking
# part, scaled to sum to 1. Overtaking is already counted through danger_zones_raw.
PM_WEIGHTS = {"Finedust PM1": 0.4, "Finedust PM2.5": 0.3, "Finedust PM4": 0.2, "Finedust PM10": 0.1}

# traffic_flow: avg_traffic_flow 0-1 per segment, 1 = cyclists roll freely, 0 = slow or stop-and-go
# (traffic lights, congestion). Routing uses stop_go = 1 - flow, length-scaled like roughness.
# Half the segments have 7 or fewer points and are noisy, so each way's points-weighted mean is
# pulled towards the city median by FLOW_PRIOR_POINTS virtual points at that median.
# Median flow is ~0.37, so unmeasured streets get stop_go 0.63.
MEDIAN_FLOW = 0.37
FLOW_PRIOR_POINTS = 5
DEFAULT_STOP_GO = 1 - MEDIAN_FLOW
# Way means span ~0.5-0.85 stop_go (5-95%), narrower than air ranks, so a mild default still
# trades a short detour for streets where bikes don't keep stopping.
DEFAULT_STOP_PENALTY = 0.5
# Waiting for a lift and getting in and out, as metres of riding at stop_penalty 1 (about 25 s at 15 km/h).
LIFT_WAIT_M = 100

# speed_map: avg_speed[km/h] per segment, the speed bikes were measured at, waits included (5-95%: 4.5-26 km/h).
# Aggregated per way like traffic_flow: points-weighted, pulled towards the city median by SPEED_PRIOR_POINTS.
# Used only when a route prefers time: the base cost becomes length x MEDIAN_SPEED_KMH / speed, i.e. metres
# ridden at the median speed, so danger_penalty and lifts keep meaning metres. Unmeasured streets get the median.
MEDIAN_SPEED_KMH = 15.7
SPEED_PRIOR_POINTS = 5
# Ways measured slower are raised to walking pace: segments of ~2 km/h with hundreds of points are bikes pushed
# or waiting, and would otherwise cost like a street 3x+ as long.
MIN_SPEED_KMH = 5.0

# Shade (routing.shadow): share of a street in building or tree shadow, 0-1, per time slot of a summer day.
# Used only by day (sun above the horizon at the departure time): routing uses sun = 1 - shade, length-scaled
# like roughness. Most streets get little shade (median ~0.05 at noon, ~0.16 at 09 and 18), so unknown streets get 0.1.
DEFAULT_SHADE = 0.1
# Over 30 random trips of 1.5 km or more at 15:00, shade_penalty 0.5 changes 23 routes for a 0.5% mean detour
# (mean shade 0.18 -> 0.21); 2 gives a 3% detour for 0.26.
DEFAULT_SHADE_PENALTY = 0.5
# Street lighting (routing.lighting): chance a street is lit at night, 0-1. Used only after dark (sun below the
# horizon at the departure time): routing uses dark = 1 - lit, length-scaled. Unknown streets get 0.5.
DEFAULT_LIT = 0.5
# Over the same trips at 21:00, dark_penalty 1 changes 26 of 30 routes for a 3% mean detour, raising the
# length-weighted chance of being lit from 0.80 to 0.91; 2 adds little more (0.92 for a 4% detour).
DEFAULT_DARK_PENALTY = 1.0


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
    Also used for stop_go (any per-way value).
    """
    ids = osmid if isinstance(osmid, list) else [osmid]
    measured = [way_rough[i] for i in ids if i in way_rough]
    return sum(measured) / len(measured) if measured else None


def way_stop_go(flow_features):
    """stop_go (1 - avg_traffic_flow, 0-1) per OSM way id from the traffic_flow_heilbronn features:
    the points-weighted mean flow, pulled towards MEDIAN_FLOW by FLOW_PRIOR_POINTS.
    """
    sums = {}
    for f in flow_features:
        p = f["properties"]
        if p.get("avg_traffic_flow") is None or not p.get("points_in_segment"):
            continue
        for way in osm_way_ids(p["osmid"]):
            flow, n = sums.get(way, (0.0, 0))
            sums[way] = (flow + p["avg_traffic_flow"] * p["points_in_segment"], n + p["points_in_segment"])
    return {way: 1 - (flow + FLOW_PRIOR_POINTS * MEDIAN_FLOW) / (n + FLOW_PRIOR_POINTS)
            for way, (flow, n) in sums.items()}


def way_speed(speed_features):
    """Cyclist speed in km/h per OSM way id from the speed_map_heilbronn features: the points-weighted mean
    speed, pulled towards MEDIAN_SPEED_KMH by SPEED_PRIOR_POINTS, at least MIN_SPEED_KMH.
    """
    sums = {}
    for f in speed_features:
        p = f["properties"]
        if p.get("avg_speed[km/h]") is None or not p.get("points_in_segment"):
            continue
        for way in osm_way_ids(p["osmid"]):
            speed, n = sums.get(way, (0.0, 0))
            sums[way] = (speed + p["avg_speed[km/h]"] * p["points_in_segment"], n + p["points_in_segment"])
    return {way: max(MIN_SPEED_KMH, (speed + SPEED_PRIOR_POINTS * MEDIAN_SPEED_KMH) / (n + SPEED_PRIOR_POINTS))
            for way, (speed, n) in sums.items()}


def clean_overtaking(features):
    """The danger_zones_raw rows routing counts: a measured distance over MIN_OVERTAKING_CM.

    Readings of 25 cm or less and rows with no distance (0 or missing) are left out.
    """
    return [f for f in features if (f["properties"]["Overtaking Distance"] or 0) > MIN_OVERTAKING_CM]


def air_scores(features, background):
    """(lon, lat), air score (0-1) and ride id of every air_quality row in a ride of at least MIN_RIDE_POINTS rows
    with a background at its hour; 0.5 is typical, higher is worse. A ride is one device on one day.

    `background` is air_background_heilbronn: the median fine dust of the senseBox:home stations per hour.
    Each row's log ratio to that hour, weighted by PM_WEIGHTS, takes out how the air of the whole region
    changes, also within a ride. Its ride's median is then subtracted, which takes out the bike sensor's
    offset. Last, the result is scaled to 0-1: AIR_SPREAD above the ride's median is 1, as far below is 0.
    """
    bg = {f["properties"]["hour"]: [f["properties"][k] for k in PM_WEIGHTS] for f in background}
    rows = [f for f in features if f["properties"]["createdAt"][:13] in bg]
    if not rows:
        return [], [], []
    pm = np.array([[f["properties"][k] for k in PM_WEIGHTS] for f in rows], dtype=float)
    ref = np.array([bg[f["properties"]["createdAt"][:13]] for f in rows], dtype=float)
    ratio = pd.Series(np.log((pm + 1) / (ref + 1)) @ np.array(list(PM_WEIGHTS.values())))
    rides = pd.Series([f["properties"]["boxId"] + f["properties"]["createdAt"][:10] for f in rows], dtype=object)
    by_ride = ratio.groupby(rides)
    keep = (by_ride.transform("size") >= MIN_RIDE_POINTS).to_numpy()
    score = (ratio - by_ride.transform("median"))[keep]
    return ([tuple(f["geometry"]["coordinates"]) for f, k in zip(rows, keep) if k],
            np.clip(0.5 + score / (2 * AIR_SPREAD), 0, 1).tolist(), rides[keep].tolist())


def point_risks(features, risk_key):
    """(lon, lat) and risk of every danger_zones point that has a risk value."""
    keep = [f for f in features if f["properties"].get(risk_key) is not None]
    return [tuple(f["geometry"]["coordinates"]) for f in keep], [f["properties"][risk_key] for f in keep]


def edge_cost(length_m, normalized_roughness=DEFAULT_ROUGHNESS, bump_penalty=DEFAULT_BUMP_PENALTY,
              danger=0.0, danger_penalty=DEFAULT_DANGER_PENALTY,
              pm_risk=DEFAULT_PM_RISK, pm_penalty=DEFAULT_PM_PENALTY,
              stop_go=DEFAULT_STOP_GO, stop_penalty=DEFAULT_STOP_PENALTY, lift_ends=0, speed_kmh=MEDIAN_SPEED_KMH,
              sun=0.0, shade_penalty=DEFAULT_SHADE_PENALTY, dark=0.0, dark_penalty=DEFAULT_DARK_PENALTY):
    """Routing cost: plain length, inflated on rough, polluted, stop-and-go, sunny (`sun`, by day) and unlit
    (`dark`, at night) streets, plus a fixed
    `danger_penalty` metres per unit of overtaking risk (`danger` = summed risk on the edge) and a fixed
    `stop_penalty * LIFT_WAIT_M` metres per lift ridden through. A lift sits where two edges meet, so each
    edge ending at one (`lift_ends` = 0, 1 or 2) carries half of it.

    `speed_kmh` turns length into riding time, as metres at MEDIAN_SPEED_KMH: a street ridden at half the
    median speed costs twice its length. The default (the median) leaves the length as it is.

    Normalized Roughness is 0-100, in the live data and the ATRAI docs.
    """
    base = length_m * (MEDIAN_SPEED_KMH / speed_kmh)
    return (base * (1 + bump_penalty * normalized_roughness / 100 + pm_penalty * pm_risk + stop_penalty * stop_go
                    + shade_penalty * sun + dark_penalty * dark)
            + danger_penalty * danger + stop_penalty * LIFT_WAIT_M * lift_ends / 2)
