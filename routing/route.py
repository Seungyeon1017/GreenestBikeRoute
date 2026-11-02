"""A-to-B routing on the bike graph, returned as GeoJSON.

Group: route search.
"""
from contextlib import contextmanager
from datetime import datetime
from typing import NamedTuple
from zoneinfo import ZoneInfo

import networkx as nx
from shapely import LineString

from routing.calories import DEFAULT_WEIGHT_KG, ride_kcal, route_climb, walk_kcal
from routing.costs import BAD_AIR_RISK, BUMPY_ROUGHNESS, DARK_EXPONENT, DEFAULT_BUMP_PENALTY, DEFAULT_DANGER_PENALTY, \
    DEFAULT_DARK_PENALTY, DEFAULT_LIT, DEFAULT_PM_PENALTY, DEFAULT_PM_RISK, DEFAULT_PREFER_BIKE_FRIENDLY, DEFAULT_ROUGHNESS, \
    DEFAULT_SHADE, DEFAULT_SHADE_PENALTY, DEFAULT_STOP_GO, DEFAULT_STOP_PENALTY, DEFAULT_UNPAVED_PENALTY, \
    DIM_SHARE, LIFT_WAIT_M, MEDIAN_SPEED_KMH, \
    SHORTEST, STOP_GO_HEAVY, Penalties, edge_cost
from routing.edges import _GRAPH_LOCK, RouteError, _snapped, edge_coords
from routing.lighting import DIM_LIGHTS_PER_100M
from routing.naming import _named_roads, street_label, street_parts
from routing.shadow import sun_position
from routing.snap import _snapped_ends, segment_id
from routing.turns import turning_path

# Departure times without a time zone are Heilbronn local time.
LOCAL_TZ = ZoneInfo("Europe/Berlin")
# Sunrise and sunset: the top of the sun on the horizon, refraction included (the usual -0.833 deg).
SUNSET_ALTITUDE = -0.833
# A street users reported closed, by too few people yet to close it (backend/reports.py), costs this many times as
# much: routes ride up to this much further to avoid it, but still use it when there is no sensible way round.
REPORTED_CLOSED_FACTOR = 4
# E-scooters must not ride on footways or in pedestrian zones, even where bikes may (eKFV §10): on those a scooter
# route pushes the scooter at walking pace, so they cost and take as long as walking. Shared paths signed for bikes
# (Zeichen 240/241, bicycle=designated) are bike paths, which scooters must use.
SCOOTER_PUSH_HIGHWAYS = {"footway", "path", "pedestrian"}
WALK_KMH = 4.8
# A street counts towards a route's unpaved_m from this unpavedness on (routing.surface): compacted and worse.
UNPAVED_LINE = 0.25
# day_routes tries departure times this many minutes apart.
DAY_STEP_MIN = 15


def _roughness(d):
    return DEFAULT_ROUGHNESS if d["roughness"] is None else d["roughness"]


def _pm_risk(d):
    return d.get("pm_prior", DEFAULT_PM_RISK) if d.get("pm_risk") is None else d["pm_risk"]


def _stop_go(d):
    return DEFAULT_STOP_GO if d.get("stop_go") is None else d["stop_go"]


def _speed_kmh(d):
    return MEDIAN_SPEED_KMH if d.get("speed_kmh") is None else d["speed_kmh"]


def _shade(d, slot):
    return DEFAULT_SHADE if d.get("shade") is None else d["shade"][slot]


def _lit(d):
    return DEFAULT_LIT if d.get("lit") is None else d["lit"]


def _dim(d):
    """Whether the street is dimly lit: probably lit, but Mapillary saw few street lights on it."""
    lights = d.get("lights_per_100m")
    return lights is not None and lights < DIM_LIGHTS_PER_100M and _lit(d) >= 0.5


def _dark(d):
    """Chance the street is unlit, for routing after dark. A dimly lit street counts as unlit with chance
    DIM_SHARE ** (1 / DARK_EXPONENT) at least, so it costs DIM_SHARE of a surely dark one."""
    if _dim(d):
        return max(1 - _lit(d), DIM_SHARE ** (1 / DARK_EXPONENT))
    return 1 - _lit(d)


def local_time(depart_time):
    """`depart_time` in Heilbronn local time; one without a time zone is taken as local time already."""
    return depart_time.replace(tzinfo=LOCAL_TZ) if depart_time.tzinfo is None else depart_time.astimezone(LOCAL_TZ)


def sky(G, depart_time):
    """(shade slot, dark) for a trip leaving at `depart_time` (a datetime, or None when the time doesn't matter).

    dark: the sun is below the horizon, after sunset or before sunrise on that date, so unlit streets cost extra.
    Shade slot: by day, the index into G.graph["shade_slots"] of the slot nearest the time of day (shade is
    computed for a few hours of one summer day); None at night, without a time or without shade data.
    """
    if depart_time is None:
        return None, False
    local = local_time(depart_time)
    if sun_position(local)[1] < SUNSET_ALTITUDE:
        return None, True
    slots = [datetime.fromisoformat(s) for s in G.graph.get("shade_slots", ())]
    if not slots:
        return None, False
    minutes = local.hour * 60 + local.minute
    return min(range(len(slots)), key=lambda i: abs(slots[i].hour * 60 + slots[i].minute - minutes)), False


class Plan(NamedTuple):
    """What _cost needs: the request's Penalties, their depart_time resolved by sky() into the shade `slot` and whether
    it is `dark`, and whether the route is for an e-scooter."""
    penalties: Penalties
    slot: int | None
    dark: bool
    scooter: bool = False


def _plan(G, penalties, scooter=False):
    return Plan(penalties, *sky(G, penalties.depart_time), scooter)


def scooter_pushes(d):
    """Whether an e-scooter must be pushed along the edge: a footway, path or pedestrian street not signed for bikes."""
    highways = {str(h) for h in (d["highway"] if isinstance(d.get("highway"), list) else [d.get("highway")])}
    bicycle = d.get("bicycle") if isinstance(d.get("bicycle"), list) else [d.get("bicycle")]
    return highways <= SCOOTER_PUSH_HIGHWAYS and "designated" not in bicycle


def _cost(d, plan):
    p = plan.penalties
    push = MEDIAN_SPEED_KMH / WALK_KMH if plan.scooter and scooter_pushes(d) else 1
    return push * edge_cost(d["length"], _roughness(d), p.bump_penalty,
                     d.get("danger", 0.0), p.danger_penalty, _pm_risk(d), p.pm_penalty, _stop_go(d), p.stop_penalty,
                     lift_ends=d.get("lift_start", False) + d.get("lift_end", False),
                     speed_kmh=_speed_kmh(d) if p.prefer_time else MEDIAN_SPEED_KMH,
                     sun=0.0 if plan.slot is None else 1 - _shade(d, plan.slot), shade_penalty=p.shade_penalty,
                     dark=_dark(d) if plan.dark else 0.0, dark_penalty=p.dark_penalty,
                     bike_friendly=d.get("bike_friendly", False), prefer_bike_friendly=p.prefer_bike_friendly,
                     unpaved=d.get("unpaved", 0.0), unpaved_penalty=p.unpaved_penalty)


def route_duration(G, edges, scooter=False):
    """Expected riding time in s of a route given as (u, v, data) edges: speed_map per street (unmeasured streets at
    the median speed), plus waiting for each lift at the median speed. With `scooter`, pushed edges (scooter_pushes)
    at walking pace."""
    lifts = sum(1 for _, n, _ in edges[:-1] if "elevator" in str(G.nodes[n].get("highway")))
    duration = lifts * LIFT_WAIT_M / (MEDIAN_SPEED_KMH / 3.6)
    for _, _, d in edges:
        kmh = WALK_KMH if scooter and scooter_pushes(d) else _speed_kmh(d)
        duration += float(d["length"]) / (kmh / 3.6)
    return duration


# Fields of a stretch (see _stretches) that are length-weighted means over its edges with data.
_STRETCH_MEANS = ("roughness", "pm_risk", "stop_go", "speed_kmh", "shade", "lit", "unpaved")


def _edge_facts(G, u, v, d, slot, dark, scooter, label=None, danger_points=True):
    """What a stretch shows for one edge (or one part of it, named `label`, see street_parts): street name, kind of
    way, the measured values (None where unknown) and `flags`, the bad or good things it counts towards (the route's
    bumpy_m, danger_points, ... with the same thresholds). Without `danger_points` the edge's close-overtaking spots
    are left out, for its parts after the first: where along it they are isn't known."""
    facts = {
        **(label or street_label(G, u, v, d)),
        "roughness": d["roughness"],
        "danger_points": int(d.get("danger_points", 0)) if danger_points else 0,
        "pm_risk": d.get("pm_risk"),
        "stop_go": d.get("stop_go"),
        "speed_kmh": d.get("speed_kmh"),
        "shade": d["shade"][slot] if slot is not None and d.get("shade") is not None else None,
        "lit": d.get("lit"),
        "dim": _dim(d),
        "bike_friendly": bool(d.get("bike_friendly")),
        "unpaved": d.get("unpaved", 0.0),
        "pushed": bool(scooter and scooter_pushes(d)),
    }
    flags = [key for key, bad in (
        ("bumpy_m", facts["roughness"] is not None and facts["roughness"] >= BUMPY_ROUGHNESS),
        ("danger_points", facts["danger_points"] > 0),
        ("bad_air_m", facts["pm_risk"] is not None and facts["pm_risk"] >= BAD_AIR_RISK),
        ("stop_go_m", facts["stop_go"] is not None and facts["stop_go"] >= STOP_GO_HEAVY),
        ("sunny_m", facts["shade"] is not None and facts["shade"] < 0.5),
        ("unlit_m", dark and facts["lit"] is not None and facts["lit"] < 0.5),
        ("dim_m", dark and facts["dim"]),
        ("bike_friendly_m", facts["bike_friendly"]),
        ("unpaved_m", facts["unpaved"] >= UNPAVED_LINE),
    ) if bad]
    return {**facts, "flags": flags}


def _stretches(pieces):
    """The route as stretches for the map: runs of consecutive edges on the same street with the same flags, from
    `pieces` [(first coordinate index, last coordinate index, length, _edge_facts, segment_id)]. Values are
    length-weighted over the edges with data. Unnamed ways are told apart by their kind; a sidewalk joins the road it
    runs beside, and then the stretch has no single `way`. `segments` are the street segments it rides, for reporting
    the stretch closed."""
    out, start_m = [], 0.0
    for first, last, length, facts, segment in pieces:
        prev = out[-1] if out else None
        key = (facts["name"] or facts["way"], facts["flags"], facts["pushed"])
        if prev is None or (prev["name"] or prev["way"], prev["flags"], prev["pushed"]) != key:
            prev = {"from_index": first, "start_m": start_m, "length_m": 0.0, "name": facts["name"], "way": facts["way"],
                    "along": facts["along"], "across": facts.get("across", False), "danger_points": 0,
                    "bike_friendly": facts["bike_friendly"],
                    "pushed": facts["pushed"], "flags": facts["flags"], "segments": [],
                    "_sums": {k: [0.0, 0.0] for k in _STRETCH_MEANS}}
            out.append(prev)
        elif prev["way"] != facts["way"]:
            prev["way"] = None
        prev["along"] = prev["along"] and facts["along"]
        prev["across"] = prev["across"] and facts.get("across", False)
        prev["to_index"] = last
        prev["length_m"] += length
        if segment not in prev["segments"]:
            prev["segments"].append(segment)
        prev["danger_points"] += facts["danger_points"]
        for k in _STRETCH_MEANS:
            if facts[k] is not None:
                prev["_sums"][k][0] += float(facts[k]) * length
                prev["_sums"][k][1] += length
        start_m += length
    means = [{k: round(total / known, 3) if known else None for k, (total, known) in s.pop("_sums").items()} for s in out]
    return [{"from_index": s["from_index"], "to_index": s["to_index"], "start_m": round(s["start_m"], 1),
             "length_m": round(s["length_m"], 1), "name": s["name"], "way": s["way"], "along": s["along"],
             "across": s["across"],
             "flags": s["flags"], "roughness": m["roughness"],
             "danger_points": s["danger_points"], "pm_risk": m["pm_risk"], "stop_go": m["stop_go"],
             "speed_kmh": m["speed_kmh"], "shade": m["shade"], "lit": m["lit"], "bike_friendly": s["bike_friendly"],
             "unpaved": m["unpaved"], "pushed": s["pushed"], "segments": s["segments"]} for s, m in zip(out, means)]


def _metres(edges, share=lambda d: True):
    """Metres of a route's `edges` [(u, v, data)], each counting share(data) of its length: 0-1, or a bool."""
    return sum(float(d["length"]) * share(d) for *_, d in edges)  # numpy floats when loaded from GraphML


def _mean(edges, value):
    """(The length-weighted mean of value(data) over the edges where it isn't None, None if there are none; the metres
    of those edges.)"""
    known = [(float(d["length"]), x) for *_, d in edges if (x := value(d)) is not None]
    metres = sum(m for m, _ in known)
    return (sum(x * m for m, x in known) / metres if metres else None), metres


def _line(G, edges, plan):
    """The route's line, [lon, lat] points without repeating the joints, and its pieces for _stretches: one per edge,
    or per name on an edge merged from ways with different names."""
    coords, pieces = [], []
    for u, v, d in edges:
        pts = edge_coords(G, u, v, d)
        first = max(len(coords) - 1, 0)
        coords.extend(pts if not coords else pts[1:])
        parts = street_parts(G, u, v, d)
        part_m = [_named_roads(G).plane.to_m(LineString(pts[a:b + 1])).length for a, b, _ in parts] \
            if len(parts) > 1 else [1.0]
        for k, ((a, b, label), metres) in enumerate(zip(parts, part_m)):
            pieces.append((first + a, first + b, float(d["length"]) * metres / sum(part_m),
                           _edge_facts(G, u, v, d, plan.slot, plan.dark, plan.scooter, label, danger_points=k == 0),
                           d.get("segment") or segment_id(u, v)))
    return coords, pieces


def _route_feature(G, a, b, penalties, weight_kg=DEFAULT_WEIGHT_KG, e_bike=False, scooter=False):
    """The cheapest route between graph nodes a and b for `penalties` (Penalties), as one GeoJSON Feature. kcal is for
    a rider of weight_kg; for an e-scooter with `scooter`."""
    plan = _plan(G, penalties, scooter)
    slot, dark, depart_time = plan.slot, plan.dark, penalties.depart_time
    path = _path(G, a, b, plan)
    edges = [(u, v, _edge(G, u, v, plan)) for u, v in zip(path[:-1], path[1:])]
    coords, pieces = _line(G, edges, plan)
    length = _metres(edges)
    duration, climb = route_duration(G, edges, scooter), route_climb(G, edges)
    pushed_m = _metres(edges, lambda d: scooter and scooter_pushes(d))
    mean_roughness, measured_m = _mean(edges, lambda d: None if d.get("roughness_source") == "estimated" else d["roughness"])
    mean_pm_risk, pm_measured_m = _mean(edges, lambda d: d.get("pm_risk"))
    mean_stop_go, stop_measured_m = _mean(edges, lambda d: d.get("stop_go"))
    mean_shade, _ = _mean(edges, lambda d: None if slot is None or d.get("shade") is None else d["shade"][slot])
    mean_lit, lit_known_m = _mean(edges, lambda d: d.get("lit"))

    properties = {
        **penalties._asdict(),
        "depart_time": local_time(depart_time).isoformat(timespec="minutes") if depart_time else None,
        # Sun above the horizon at depart_time (null without one): shade counts by day, lighting after dark.
        "daylight": None if depart_time is None else not dark,
        "shade_slot": G.graph["shade_slots"][slot] if slot is not None else None,
        "length_m": round(length, 1),
        # Expected riding time from speed_map (unmeasured streets at the median speed), lifts included.
        "duration_s": round(duration),
        # Total ascent, bridge humps included (null without elevation data), and the rough energy use for it
        # and the riding time, see routing/calories.py. On an e-scooter only pushing it counts, as walking.
        "climb_m": None if climb is None else round(climb, 1),
        "kcal": round(walk_kcal(pushed_m / (WALK_KMH / 3.6), weight_kg) if scooter
                      else ride_kcal(duration, climb or 0.0, weight_kg, e_bike), 1),
        "speed_measured_share": round(_metres(edges, lambda d: d.get("speed_kmh") is not None) / length, 2),
        # Length-weighted over the measured part of the route only.
        "mean_roughness": None if mean_roughness is None else round(mean_roughness, 1),
        "measured_share": round(measured_m / length, 2),
        # Roughness estimated from nearby measured streets (estimation/README.md); the rest of the route is unknown.
        "estimated_share": round(_metres(edges, lambda d: d.get("roughness_source") == "estimated") / length, 2),
        # Overtaking spots (danger_zones) on the route and their summed Risk Index Overtaking.
        "danger_points": sum(d.get("danger_points", 0) for *_, d in edges),
        "danger_risk": round(sum(d.get("danger", 0.0) for *_, d in edges), 2),
        # Length-weighted over the part of the route with air_quality measurements.
        "mean_pm_risk": None if mean_pm_risk is None else round(mean_pm_risk, 3),
        "pm_measured_share": round(pm_measured_m / length, 2),
        # Length-weighted over the part of the route with traffic_flow measurements.
        "mean_stop_go": None if mean_stop_go is None else round(mean_stop_go, 3),
        "stop_measured_share": round(stop_measured_m / length, 2),
        # Length-weighted share in shade at shade_slot, over the part of the route with shade data; null unless by day.
        "mean_shade": None if mean_shade is None else round(mean_shade, 3),
        "shade_known_share": round(_metres(edges, lambda d: d.get("shade") is not None) / length, 2),
        # Length-weighted chance the streets are lit at night, over the part of the route with lighting data.
        "mean_lit": None if mean_lit is None else round(mean_lit, 3),
        "lit_known_share": round(lit_known_m / length, 2),
        # Lifts the route rides through; each costs stop_penalty x 25 m.
        "lifts": sum(1 for n in path[1:-1] if "elevator" in str(G.nodes[n].get("highway"))),
        # Streets on the route that users reported closed (backend/reports.py) and that it still rides.
        "reported_closures": len({str(d["osmid"]) for *_, d in edges if d.get("closure")}),
        # Metres on bad streets (the worst tenth of measured street length for that factor), to compare routes by.
        "bumpy_m": round(_metres(edges, lambda d: d["roughness"] is not None and d["roughness"] >= BUMPY_ROUGHNESS)),
        "bad_air_m": round(_metres(edges, lambda d: d.get("pm_risk") is not None and d["pm_risk"] >= BAD_AIR_RISK)),
        "stop_go_m": round(_metres(edges, lambda d: d.get("stop_go") is not None and d["stop_go"] >= STOP_GO_HEAVY)),
        # Metres in the sun by day / on probably unlit streets after dark (share not in shade / not lit, over the
        # streets with data); null at other times.
        "sunny_m": round(_metres(edges, lambda d: 0.0 if d.get("shade") is None else 1 - d["shade"][slot]))
                   if slot is not None else None,
        "unlit_m": round(_metres(edges, lambda d: 0.0 if d.get("lit") is None else 1 - d["lit"])) if dark else None,
        # Metres on dimly lit streets after dark (probably lit, but few street lights seen); null otherwise.
        "dim_m": round(_metres(edges, _dim)) if dark else None,
        # Metres on bike paths, bike lanes and bike routes (/bike-friendly-streets).
        "bike_friendly_m": round(_metres(edges, lambda d: bool(d.get("bike_friendly")))),
        # Metres on unpaved streets: gravel, compacted, cobblestones, soil or grass (routing.surface, from OSM).
        "unpaved_m": round(_metres(edges, lambda d: d.get("unpaved", 0.0) >= UNPAVED_LINE)),
        # Metres an e-scooter is pushed (footways and pedestrian streets); 0 for bikes.
        "pushed_m": round(pushed_m),
        # The route as stretches with what is measured on them, to show when the rider points at the line.
        "segments": _stretches(pieces),
    }
    return {"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords}, "properties": properties}


def set_closures(G, closures):
    """Set edge attribute `closure` ("closed", or "reported" / "unconfirmed", which only cost more) on the streets in
    `closures`, {(u, v): status}, in both directions, and remove it from every other street. Streets no longer in G
    are skipped."""
    closures = dict(closures)
    with _GRAPH_LOCK:
        if G.graph.get("closures") == closures:
            return
        for u, v in G.graph.get("closures", {}):
            for a, b in ((u, v), (v, u)):
                for d in (G.get_edge_data(a, b) or {}).values():
                    d.pop("closure", None)
        for (u, v), status in closures.items():
            for a, b in ((u, v), (v, u)):
                for d in (G.get_edge_data(a, b) or {}).values():
                    d["closure"] = status
        G.graph["closures"] = closures


def _route_cost(u, v, d, plan):
    """_cost, REPORTED_CLOSED_FACTOR times as much on a street reported closed; None (can't be ridden) on a closed
    street, except its piece up to a start or end point on it, so places on a closed street can still be reached."""
    closure = d.get("closure")
    if closure == "closed" and not (_snapped(u) or _snapped(v)):
        return None
    return _cost(d, plan) * (REPORTED_CLOSED_FACTOR if closure else 1)


def _min_cost_per_m(d):
    """What _route_cost costs at least per metre of an edge with prefer_time: its length at its measured speed; every
    other part of _cost and a closure only add to it. For routing.turns' A* estimate."""
    return MEDIAN_SPEED_KMH / _speed_kmh(d)


def _path(G, a, b, plan):
    """The nodes of the cheapest route between graph nodes a and b for `plan` (see _plan)."""
    # MultiDiGraph: between two nodes there can be parallel edges; use the cheapest. None hides a closed street.
    def weight(u, v, parallel):
        return min((c for d in parallel.values() if (c := _route_cost(u, v, d, plan)) is not None), default=None)

    try:
        if plan.penalties.prefer_time:
            return turning_path(G, a, b, lambda u, v, d: _route_cost(u, v, d, plan), _min_cost_per_m)
        return nx.shortest_path(G, a, b, weight=weight)
    except nx.NetworkXNoPath:
        raise RouteError("no bike route between these points") from None


def _edge(G, u, v, plan):
    """The cheapest of the parallel edges from u to v that can be ridden."""
    return min((d for d in G[u][v].values() if _route_cost(u, v, d, plan) is not None),
               key=lambda d: _route_cost(u, v, d, plan))


@contextmanager
def route_edges(G, origin, destination, penalties):
    """Yield the edges (u, v, data) of the route find_route picks from origin to destination, both (lat, lon), for
    `penalties` (Penalties).

    Start and end may be temporary nodes on a split street (see routing.snap._snapped_ends), which exist only inside
    the block.
    """
    plan = _plan(G, penalties)
    with _snapped_ends(G, origin, destination) as (a, b):
        path = _path(G, a, b, plan)
        yield [(u, v, _edge(G, u, v, plan)) for u, v in zip(path[:-1], path[1:])]


def find_route(G, origin, destination, bump_penalty=DEFAULT_BUMP_PENALTY,
               danger_penalty=DEFAULT_DANGER_PENALTY, pm_penalty=DEFAULT_PM_PENALTY,
               stop_penalty=DEFAULT_STOP_PENALTY, prefer_time=False, shade_penalty=DEFAULT_SHADE_PENALTY,
               dark_penalty=DEFAULT_DARK_PENALTY, prefer_bike_friendly=DEFAULT_PREFER_BIKE_FRIENDLY,
               unpaved_penalty=DEFAULT_UNPAVED_PENALTY, depart_time=None,
               weight_kg=DEFAULT_WEIGHT_KG, e_bike=False, scooter=False):
    """Cheapest route from origin to destination, both (lat, lon), as a GeoJSON FeatureCollection.

    All penalties 0 give the shortest route; higher values take longer detours to avoid rough
    streets (bump_penalty), spots where cars overtook closely (danger_penalty), streets with bad
    air (pm_penalty) and streets where bikes keep stopping (stop_penalty). prefer_time weighs each
    street by its riding time at the measured speed instead of its length. With a depart_time (datetime),
    sunny streets cost extra by day (shade_penalty) and unlit streets after dark (dark_penalty).
    prefer_bike_friendly makes streets that are not bike paths, bike lanes or bike routes cost extra, and
    unpaved_penalty gravel, soil and grass (routing.surface).
    With `scooter`, the route is for an e-scooter, pushed where it must not ride (scooter_pushes).
    """
    penalties = Penalties(bump_penalty, danger_penalty, pm_penalty, stop_penalty, prefer_time, shade_penalty,
                          dark_penalty, prefer_bike_friendly, unpaved_penalty, depart_time)
    with _snapped_ends(G, origin, destination) as (a, b):
        feature = _route_feature(G, a, b, penalties, weight_kg, e_bike, scooter)
    return {"type": "FeatureCollection", "features": [feature]}


def compare_routes(G, origin, destination, bump_penalty=DEFAULT_BUMP_PENALTY,
                   danger_penalty=DEFAULT_DANGER_PENALTY, pm_penalty=DEFAULT_PM_PENALTY,
                   stop_penalty=DEFAULT_STOP_PENALTY, prefer_time=False, shade_penalty=DEFAULT_SHADE_PENALTY,
                   dark_penalty=DEFAULT_DARK_PENALTY, prefer_bike_friendly=DEFAULT_PREFER_BIKE_FRIENDLY,
                   unpaved_penalty=DEFAULT_UNPAVED_PENALTY, depart_time=None,
                   weight_kg=DEFAULT_WEIGHT_KG, e_bike=False):
    """The route from find_route next to the shortest route (by distance) at the same depart_time, with how much they differ."""
    penalties = Penalties(bump_penalty, danger_penalty, pm_penalty, stop_penalty, prefer_time, shade_penalty,
                          dark_penalty, prefer_bike_friendly, unpaved_penalty, depart_time)
    with _snapped_ends(G, origin, destination) as (a, b):
        return _comparison(G, a, b, penalties, weight_kg, e_bike)


def _comparison(G, a, b, penalties, weight_kg=DEFAULT_WEIGHT_KG, e_bike=False):
    """compare_routes between graph nodes a and b."""
    route = _route_feature(G, a, b, penalties, weight_kg, e_bike)
    shortest = _route_feature(G, a, b, SHORTEST._replace(depart_time=penalties.depart_time), weight_kg, e_bike)
    return {
        "route": route,
        "shortest": shortest,
        "detour_pct": round((route["properties"]["length_m"] / shortest["properties"]["length_m"] - 1) * 100, 1),
        "extra_time_pct": round((route["properties"]["duration_s"] / shortest["properties"]["duration_s"] - 1) * 100, 1),
        "same_path": route["geometry"] == shortest["geometry"],
    }


def day_routes(G, origin, destination, bump_penalty=DEFAULT_BUMP_PENALTY,
               danger_penalty=DEFAULT_DANGER_PENALTY, pm_penalty=DEFAULT_PM_PENALTY,
               stop_penalty=DEFAULT_STOP_PENALTY, prefer_time=False, shade_penalty=DEFAULT_SHADE_PENALTY,
               dark_penalty=DEFAULT_DARK_PENALTY, prefer_bike_friendly=DEFAULT_PREFER_BIKE_FRIENDLY,
               unpaved_penalty=DEFAULT_UNPAVED_PENALTY, depart_time=None,
               weight_kg=DEFAULT_WEIGHT_KG, e_bike=False):
    """compare_routes for every departure time of one day, in periods that get the same route.

    The day is that of depart_time (today without one). Departure times are tried every DAY_STEP_MIN minutes, and
    times with the same sky() (shade slot by day, or dark) form one period, so sunrise and sunset are found to
    within DAY_STEP_MIN. Each distinct sky is routed once: a day has at most one route per shade slot plus one for
    the night, both before sunrise and after sunset.
    """
    day = local_time(depart_time).date() if depart_time else datetime.now(LOCAL_TZ).date()
    penalties = Penalties(bump_penalty, danger_penalty, pm_penalty, stop_penalty, prefer_time, shade_penalty,
                          dark_penalty, prefer_bike_friendly, unpaved_penalty)
    times =[datetime(day.year, day.month, day.day, m // 60, m % 60, tzinfo=LOCAL_TZ) for m in range(0, 24 * 60, DAY_STEP_MIN)]
    periods = []
    for t in times:
        if periods and sky(G, t) == periods[-1][0]:
            periods[-1][2] = t
        else:
            periods.append([sky(G, t), t, t])
    compared = {}
    with _snapped_ends(G, origin, destination) as (a, b):
        for key, first, _ in periods:
            if key not in compared:
                compared[key] = _comparison(G, a, b, penalties._replace(depart_time=first), weight_kg, e_bike)
    out = []
    for key, first, last in periods:
        end = last.replace(hour=23, minute=59) if last == times[-1] else last + (times[1] - times[0])
        out.append({"from": first.strftime("%H:%M"), "to": end.strftime("%H:%M"), **compared[key]})
    return {"date": day.isoformat(), "periods": out}
