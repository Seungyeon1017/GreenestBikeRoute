"""The overall score of every street for the Overview map (/score): how riding it feels, 0-100.

Its own formula, apart from routing's cost (routing.costs.edge_cost), so the map can count what routing doesn't yet:
- traffic stress from OSM (road type, speed limit, lanes, bike lane): a quiet street scores well without any ride.
- measured values better than typical earn credit, not only worse ones cost: sensors are noisy, and with costs only,
  a typical street that bikes measured looks worse than one no bike rode (where everything counts as typical).
- air of nearby measured streets (routing.graph.attach_nearby_air) where no sensor passed.
"""
import re

from routing.costs import BAD_AIR_RISK, BUMPY_ROUGHNESS, DARK_EXPONENT, DEFAULT_BUMP_PENALTY, DEFAULT_DANGER_PENALTY, \
    DEFAULT_DARK_PENALTY, DEFAULT_PM_PENALTY, DEFAULT_PM_RISK, DEFAULT_PREFER_BIKE_FRIENDLY, DEFAULT_ROUGHNESS, \
    DEFAULT_SHADE_PENALTY, DEFAULT_STOP_GO, DEFAULT_STOP_PENALTY, DEFAULT_UNPAVED_PENALTY, LIFT_WAIT_M, MEDIAN_SPEED_KMH, POINT, SNAP_M, \
    STOP_GO_HEAVY
from routing.highlights import ridden
from routing.route import _dark, _roughness, _shade, _speed_kmh, _stop_go, edge_coords, sky, street_label

# Level of traffic stress (LTS, Mekuria, Furth & Nixon 2012), from 1 (car-free or calm, fine for children) to 4
# (fast, busy roads with no room for bikes), and how much longer each makes a street feel. Riders' route choice
# (e.g. Broach, Dill & Gliebe 2012) puts a busy road without a bike lane at very roughly twice its length.
STRESS_FACTOR = {1: 1.0, 2: 1.15, 3: 1.5, 4: 2.0}
CAR_FREE = {"cycleway", "path", "footway", "pedestrian", "track", "bridleway", "steps"}
MAIN_ROADS = {"trunk", "primary", "secondary", "trunk_link", "primary_link", "secondary_link"}
# Speed limit where OSM has none: 30 km/h on residential and smaller streets (most tagged ones in Heilbronn
# are), else 50 km/h, the urban limit.
CALM_ROADS = {"residential", "unclassified", "service", "living_street", "road"}
# Words in maxspeed (e.g. "DE:urban") instead of a number.
MAXSPEED_WORDS = {"walk": 7, "living_street": 7, "zone30": 30, "zone:30": 30, "urban": 50, "rural": 100, "none": 130}
# Main roads with this many lanes (both directions) or more are stress 4 at 50 km/h.
WIDE_ROAD_LANES = 4
# Overtaking risk per metre counts over at least this length: GPS noise can't tell where along a shorter stretch a
# point was.
DANGER_MIN_M = 2 * SNAP_M


def _tags(value):
    return [str(v) for v in (value if isinstance(value, list) else [value])]


def _highways(d):
    """The OSM highway values of the edge; without a highway tag it counts as a residential street."""
    return set(_tags(d["highway"])) if d.get("highway") is not None else {"residential"}


def maxspeed_kmh(d):
    """The speed limit of the edge in km/h: the highest of its OSM maxspeed values, else the default for its road."""
    speeds = []
    for v in _tags(d.get("maxspeed")) if d.get("maxspeed") is not None else []:
        if re.fullmatch(r"\d+", v):
            speeds.append(int(v))
        else:
            speeds += [kmh for word, kmh in MAXSPEED_WORDS.items() if v.lower().endswith(word)]
    if speeds:
        return max(speeds)
    return 30 if _highways(d) <= CALM_ROADS else 50


def traffic_stress(d):
    """Level of traffic stress 1-4 of the edge, from its OSM highway, maxspeed, lanes and bike lane (see
    routing.graph.attach_bike_lanes)."""
    highways = _highways(d)
    lane = d.get("bike_lane")
    if highways <= CAR_FREE or highways <= {"living_street"} or lane == "bicycle_road":
        return 1
    kmh = maxspeed_kmh(d)
    lanes = max((int(x) for x in _tags(d.get("lanes")) if x.isdigit()), default=0)
    if highways & MAIN_ROADS:
        stress = 2 if kmh <= 30 else 4 if kmh > 50 or lanes >= WIDE_ROAD_LANES else 3
    elif highways & {"tertiary", "tertiary_link"}:
        stress = 2 if kmh <= 30 else 3 if kmh <= 50 else 4
    else:
        stress = 1 if kmh <= 30 else 2 if kmh <= 50 else 3
    if lane == "track":
        return 1  # a bike path beside the road
    if lane == "lane":
        return max(2 if kmh > 30 else 1, stress - 1)  # painted: still next to the traffic
    return stress


def signed_factor(penalty, value, typical, bad):
    """1 + penalty x POINT x badness on a street worse than typical (as routing), and the inverse for one as much
    better: noise then averages out instead of only adding cost. The credit stops at badness -1."""
    b = (value - typical) / (bad - typical)
    if b >= 0:
        return 1 + penalty * POINT * b
    return 1 / (1 + penalty * POINT * min(-b, 1))


def _air(d):
    if d.get("pm_risk") is not None:
        return d["pm_risk"]
    return d["pm_near"] if d.get("pm_near") is not None else d.get("pm_prior", DEFAULT_PM_RISK)


def feel_factor(d, bump_penalty=DEFAULT_BUMP_PENALTY, danger_penalty=DEFAULT_DANGER_PENALTY,
                pm_penalty=DEFAULT_PM_PENALTY, stop_penalty=DEFAULT_STOP_PENALTY, prefer_time=False,
                shade_penalty=DEFAULT_SHADE_PENALTY, dark_penalty=DEFAULT_DARK_PENALTY,
                prefer_bike_friendly=DEFAULT_PREFER_BIKE_FRIENDLY, unpaved_penalty=DEFAULT_UNPAVED_PENALTY, slot=None,
                dark=False):
    """How many times its length the edge feels to ride: 1 on a calm, typical street. Traffic stress times signed
    factors for roughness, air and stop-and-go, plus overtaking risk per metre (danger_penalty metres each, as
    routing), plus by day sun and after dark unlit streets, like routing; prefer_time, prefer_bike_friendly and the
    surface (unpaved_penalty, routing.surface) as routing too. Below 1 where a calm street measures better than typical."""
    length = max(float(d["length"]), 1.0)
    factor = (STRESS_FACTOR[traffic_stress(d)]
              * signed_factor(bump_penalty, _roughness(d), DEFAULT_ROUGHNESS, BUMPY_ROUGHNESS)
              * signed_factor(pm_penalty, _air(d), DEFAULT_PM_RISK, BAD_AIR_RISK)
              * signed_factor(stop_penalty, _stop_go(d), DEFAULT_STOP_GO, STOP_GO_HEAVY)
              * (1 + shade_penalty * POINT * (0.0 if slot is None else 1 - _shade(d, slot)))
              * (1 + dark_penalty * POINT * (_dark(d) ** DARK_EXPONENT if dark else 0.0))
              * (1 + (0 if d.get("bike_friendly", False) else prefer_bike_friendly * POINT))
              * (1 + unpaved_penalty * POINT * d.get("unpaved", 0.0))
              * (MEDIAN_SPEED_KMH / _speed_kmh(d) if prefer_time else 1))
    lifts = d.get("lift_start", False) + d.get("lift_end", False)
    return (factor * (1 + danger_penalty * d.get("danger", 0.0) / max(length, DANGER_MIN_M))
            + stop_penalty * POINT * LIFT_WAIT_M * lifts / 2 / length)


def street_scores(G, bump_penalty=DEFAULT_BUMP_PENALTY, danger_penalty=DEFAULT_DANGER_PENALTY,
                  pm_penalty=DEFAULT_PM_PENALTY, stop_penalty=DEFAULT_STOP_PENALTY, prefer_time=False,
                  shade_penalty=DEFAULT_SHADE_PENALTY, dark_penalty=DEFAULT_DARK_PENALTY,
                  prefer_bike_friendly=DEFAULT_PREFER_BIKE_FRIENDLY, unpaved_penalty=DEFAULT_UNPAVED_PENALTY,
                  depart_time=None):
    """Each street once (a two-way street is two edges) as a GeoJSON LineString with `score` 0-100:
    100 / feel_factor, at most 100. 100 = rides like a calm, typical street (or better), 50 = feels twice its length,
    25 = four times. The same in every city and for every street, not a rank: a good street doesn't lose points
    because others are better. `ridden` says whether ATRAI bikes measured it (routing.highlights.ridden); without,
    the score comes from OSM (traffic stress), nearby air and estimates only. `name`, `way` and `along` as
    routing.route.street_label."""
    slot, dark = sky(G, depart_time)
    weights = (bump_penalty, danger_penalty, pm_penalty, stop_penalty, prefer_time, shade_penalty, dark_penalty,
               prefer_bike_friendly, unpaved_penalty, slot, dark)
    streets = {}
    for u, v, d in G.edges(data=True):
        street = (min(u, v), max(u, v), str(d["osmid"]), round(float(d["length"]), 1))
        f = feel_factor(d, *weights)
        if street not in streets or f < streets[street][0]:
            streets[street] = (f, u, v, d)
    features = [
        {"type": "Feature",
         "geometry": {"type": "LineString", "coordinates": [[round(x, 6), round(y, 6)] for x, y in edge_coords(G, u, v, d)]},
         "properties": {"score": round(min(100.0, 100 / f), 1), "ridden": ridden(d), **street_label(G, u, v, d)}}
        for f, u, v, d in sorted(streets.values(), key=lambda s: s[0])
    ]
    return {"type": "FeatureCollection", "features": features}
