"""Suggested rides (Vorgeschlagene Radtouren) for the Highlights tab: four themed tours through Heilbronn, each a chain
of hand-picked stops routed leg by leg with its own penalties, so the theme comes from both where it goes and what it
avoids on the way."""
import math
from datetime import datetime

from routing.costs import DEFAULT_BUMP_PENALTY, DEFAULT_DANGER_PENALTY, DEFAULT_DARK_PENALTY, DEFAULT_PM_PENALTY, \
    DEFAULT_PREFER_BIKE_FRIENDLY, DEFAULT_SHADE_PENALTY, DEFAULT_STOP_PENALTY
from routing.calories import ride_kcal, total_climb
from routing.route import LOCAL_TZ, edge_coords, route_duration, route_edges, street_name

# Shade counts only by day, so the green tour is planned for a summer afternoon: then street trees and park crowns
# make a street cheaper (buildings too, but the stops keep it in the parks).
SUMMER_AFTERNOON = datetime(2026, 7, 1, 15, 0, tzinfo=LOCAL_TZ)

# id: (stops as (name, lat, lon), the penalties that differ from DEFAULTS). A tour that ends where it
# started is a loop. Each stop sits on the line of the finished tour (a loop's start on its ring), so the stops shape
# the route and the tour has no spurs to cut.
TOURS = {
    # The plane trees of the Neckar bank, the Stadtgarten, tree-lined Karl- and Pfühlstraße, the Pfühlpark and the
    # Trappensee: over half of it under tree crowns.
    "scenicGreen": ([
        ("Neckarbogen", 49.14727, 9.21156),
        ("Obere Neckarstraße", 49.14100, 9.21551),
        ("Stadtgarten", 49.14216, 9.22498),
        ("Pfühlpark", 49.14004, 9.24122),
        ("Trappensee", 49.13922, 9.25405),
    ], {"shade_penalty": 8, "pm_penalty": 3, "prefer_bike_friendly": 2, "depart_time": SUMMER_AFTERNOON}),
    # A loop from the edge of the old town through the side streets of the Südstadt to the Wertwiesenpark and back on
    # the bike path along the Neckar: stop-and-go, close overtakes and bad air cost a lot more than usual.
    "quietEscape": ([
        ("Rosenbergstraße", 49.13871, 9.21467),
        ("Südstadt", 49.13311, 9.22066),
        ("Wertwiesenpark", 49.12454, 9.19811),
        ("Badstraße", 49.13710, 9.21171),
        ("Rosenbergstraße", 49.13871, 9.21467),
    ], {"stop_penalty": 6, "danger_penalty": 40, "pm_penalty": 4, "prefer_bike_friendly": 5}),
    # The Neckar cycle path upstream: from the Neckarbogen along the old town bank and the Badstraße to the
    # Wertwiesenpark and on along the river to the Horkheim lock. Three quarters of it within 80 m of the water.
    "riverside": ([
        ("Neckarbogen", 49.14727, 9.21156),
        ("Altstadtufer", 49.14229, 9.21630),
        ("Badstraße", 49.13710, 9.21171),
        ("Wertwiesenpark", 49.12428, 9.19771),
        ("Neckarufer Sontheim", 49.11967, 9.18106),
        ("Schleuse Horkheim", 49.11771, 9.16632),
    ], {"prefer_bike_friendly": 4}),
    # A loop out at the eastern edge of town: from the Trappensee up the Kirschenallee to the Waldheide by the
    # Stadtwald and back down the Böckinger Hangweg.
    "nature": ([
        ("Trappensee", 49.13687, 9.25586),
        ("Kirschenallee", 49.13355, 9.27183),
        ("Waldheide", 49.12612, 9.27085),
        ("Böckinger Hangweg", 49.12805, 9.25988),
        ("Trappensee", 49.13687, 9.25586),
    ], {"bump_penalty": 1, "prefer_bike_friendly": 2}),
}

# The route penalties in route_edges' order, at their defaults.
DEFAULTS = {"bump_penalty": DEFAULT_BUMP_PENALTY, "danger_penalty": DEFAULT_DANGER_PENALTY,
            "pm_penalty": DEFAULT_PM_PENALTY, "stop_penalty": DEFAULT_STOP_PENALTY, "prefer_time": False,
            "shade_penalty": DEFAULT_SHADE_PENALTY, "dark_penalty": DEFAULT_DARK_PENALTY,
            "prefer_bike_friendly": DEFAULT_PREFER_BIKE_FRIENDLY, "depart_time": None}

def _steps(G, a, b, penalties):
    """The route from a to b, both (lat, lon), as steps from one point of its line to the next, each with its share
    (by distance) of its edge's length, riding time and rise, and the edge's trees, whether bike-friendly and street
    name. Point by point, so a street split at a stop still matches the same street ridden whole. Taken while the
    split edges at a and b exist (route_edges)."""
    from routing.grade import NoElevationError, edge_parts  # needs the graph stack (osmnx)
    steps = []
    with route_edges(G, a, b, penalties) as edges:
        for u, v, d in edges:
            try:
                rise = sum(rise for _, rise, _ in edge_parts(G, u, v, d))
            except NoElevationError:
                rise = 0.0
            points = [(round(x, 6), round(y, 6)) for x, y in edge_coords(G, u, v, d)]
            pieces = [(p, q, math.dist(p, q)) for p, q in zip(points, points[1:]) if p != q]
            span = sum(dist for _, _, dist in pieces) or 1.0
            length, duration = float(d["length"]), route_duration(G, [(u, v, d)])
            for p, q, dist in pieces:
                share = dist / span
                steps.append({"coords": (p, q), "length": length * share, "duration": duration * share,
                              "rise": rise * share, "trees": d.get("trees") or 0.0,
                              "bike_friendly": bool(d.get("bike_friendly")), "name": street_name(G, u, v, d)})
    return steps


# A loop's way out to its ring and back is cut only while it is at most this share of the tour.
MAX_STEM_SHARE = 0.25


def _without_spurs(steps, loop):
    """steps without the out-and-back spurs: a piece followed by the same piece back cancels with it, repeatedly, so a
    stop just off the way leaves no branch (the tour turns where the spur left it). On a loop, the stem too: the way
    from the start out to the ring that is ridden back at the end, so the loop starts and ends on the ring. Cut as long
    as the loop shares a way out and back, but never more than MAX_STEM_SHARE of it in all."""
    kept = []
    for step in steps:
        if kept and step["coords"] == kept[-1]["coords"][::-1]:
            kept.pop()
        else:
            kept.append(step)
    total, cut = sum(step["length"] for step in kept), True
    while loop and cut:
        cut = False
        for k, step in enumerate(kept):
            m = next((m for m in range(len(kept) - 1, k, -1) if kept[m]["coords"] == step["coords"][::-1]), None)
            if m is None:
                continue
            while k + 1 < m - 1 and kept[k + 1]["coords"] == kept[m - 1]["coords"][::-1]:
                k, m = k + 1, m - 1
            cut_so_far = total - sum(step["length"] for step in kept)
            if cut_so_far + sum(step["length"] for step in kept[:k + 1] + kept[m:]) <= MAX_STEM_SHARE * total:
                kept, cut = kept[k + 1:m], True
            break
    return kept


def plan_tour(G, tour_id):
    """The tour as one GeoJSON Feature: a LineString over all legs without out-and-back spurs (_without_spurs), with
    `stops` [{name, lon, lat}], `loop`, length_m, duration_s, climb_m, kcal, bike_friendly_m, `tree_share` (length
    share under street-tree crowns), `bike_friendly_share` and the streets it follows in order (`streets`, each once;
    paths beside a road count for that road, other unnamed paths are left out)."""
    stops, penalties = TOURS[tour_id]
    penalties, loop = tuple({**DEFAULTS, **penalties}.values()), stops[0] == stops[-1]
    steps = _without_spurs([step for (_, *a), (_, *b) in zip(stops[:-1], stops[1:])
                            for step in _steps(G, tuple(a), tuple(b), penalties)], loop)
    coords = [list(steps[0]["coords"][0])] + [list(step["coords"][1]) for step in steps]
    length = sum(step["length"] for step in steps)
    duration = sum(step["duration"] for step in steps)
    climb = total_climb(step["rise"] for step in steps)
    bike_friendly = sum(step["length"] for step in steps if step["bike_friendly"])
    streets = list(dict.fromkeys(step["name"] for step in steps if step["name"]))
    return {"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords}, "properties": {
        "id": tour_id,
        "stops": [{"name": name, "lon": lon, "lat": lat} for name, lat, lon in stops],
        "loop": loop,
        "length_m": round(length, 1),
        "duration_s": round(duration),
        "climb_m": round(climb, 1),
        "kcal": round(ride_kcal(duration, climb), 1),
        "bike_friendly_m": round(bike_friendly),
        "tree_share": round(sum(step["length"] * step["trees"] for step in steps) / length, 2),
        "bike_friendly_share": round(bike_friendly / length, 2),
        "streets": streets,
    }}


def plan_tours(G):
    """All TOURS as a GeoJSON FeatureCollection, in TOURS order."""
    return {"type": "FeatureCollection", "features": [plan_tour(G, tour_id) for tour_id in TOURS]}
