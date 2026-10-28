"""Grade along a route, for display only: it is never part of the route cost (see routing/README.md, "Grade").

Grade of an edge = rise in the travel direction / edge length, from the node heights of
routing.elevation. A two-way street is two edges, so it is uphill one way and downhill the other.
"""
from routing.costs import DEFAULT_BUMP_PENALTY, DEFAULT_DANGER_PENALTY, DEFAULT_DARK_PENALTY, DEFAULT_PM_PENALTY, \
    DEFAULT_PREFER_BIKE_FRIENDLY, DEFAULT_SHADE_PENALTY, DEFAULT_STOP_PENALTY
from routing.route import edge_coords, route_edges

# Severity on the absolute grade in %: (upper bound, name, colour). Bounds belong to the steeper class.
SEVERITIES = [
    (2, "flat", "#4caf50"),
    (4, "gentle", "#c0ca33"),
    (6, "noticeable", "#f2c94c"),
    (10, "steep", "#f2994a"),
    (float("inf"), "very_steep", "#d63b3b"),
]
COLORS = {name: color for _, name, color in SEVERITIES}


class NoElevationError(LookupError):
    """The graph has no heights for (part of) the route: run python -m routing.elevation."""


def severity(grade_pct):
    """Class name of a grade in % (sign ignored): flat < 2 <= gentle < 4 <= noticeable < 6 <= steep < 10 <= very_steep."""
    return next(name for bound, name, _ in SEVERITIES if abs(grade_pct) < bound)


def node_height(G, n):
    """Height of node n in m. A node without one, such as a route's start or end splitting a street, gets the
    distance-weighted mean of its neighbours: the straight line between the ends of the street it splits."""
    h = G.nodes[n].get("elevation")
    if h is not None:
        return h
    near = {}  # neighbour -> distance
    for a, b, d in [*G.in_edges(n, data=True), *G.out_edges(n, data=True)]:
        m = a if b == n else b
        if G.nodes[m].get("elevation") is not None:
            near[m] = min(near.get(m, float("inf")), float(d["length"]))
    if not near:
        raise NoElevationError("no elevation data for this route: run python -m routing.elevation")
    if 0 in near.values():
        return next(G.nodes[m]["elevation"] for m, dist in near.items() if dist == 0)
    weights = {m: 1 / dist for m, dist in near.items()}
    return sum(w * G.nodes[m]["elevation"] for m, w in weights.items()) / sum(weights.values())


def edge_rise(G, u, v):
    """Height gain in m from u to v (negative downhill)."""
    return node_height(G, v) - node_height(G, u)


def grade_pct(rise, length):
    return 100 * rise / length if length else 0.0


def edge_grade(G, u, v, d):
    """Signed grade in % of edge (u, v) with data d, in the direction u -> v."""
    return grade_pct(edge_rise(G, u, v), float(d["length"]))


def _direction(grade_pct):
    return 0 if severity(grade_pct) == "flat" else (1 if grade_pct > 0 else -1)


def grade_pieces(G, edges):
    """Runs of consecutive edges with the same severity and direction (up/down), as GeoJSON Features."""
    runs = []  # [key, coords, length, rise, start_m]
    along = 0.0
    for u, v, d in edges:
        length, rise = float(d["length"]), edge_rise(G, u, v)
        grade = grade_pct(rise, length)
        key = (severity(grade), _direction(grade))
        pts = edge_coords(G, u, v, d)
        if runs and runs[-1][0] == key:
            run = runs[-1]
            run[1].extend(pts[1:])
            run[2] += length
            run[3] += rise
        else:
            runs.append([key, pts, length, rise, along])
        along += length

    features = []
    for (name, _), coords, length, rise, start in runs:
        features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords}, "properties": {
            "grade_pct": round(grade_pct(rise, length), 1),
            "severity": name,
            "color": COLORS[name],
            "length_m": round(length, 1),
            "rise_m": round(rise, 1),
            "start_m": round(start, 1),
        }})
    return features


def grade_summary(G, edges):
    """Totals over the route: length, climb and descent, steepest pieces, length per severity."""
    length = climb = descent = 0.0
    max_up = max_down = 0.0
    by_severity = {name: 0.0 for _, name, _ in SEVERITIES}
    for u, v, d in edges:
        edge_len, rise = float(d["length"]), edge_rise(G, u, v)
        grade = grade_pct(rise, edge_len)
        length += edge_len
        climb += max(rise, 0)
        descent += max(-rise, 0)
        max_up, max_down = max(max_up, grade), min(max_down, grade)
        by_severity[severity(grade)] += edge_len
    start, end = node_height(G, edges[0][0]), node_height(G, edges[-1][1])
    return {
        "length_m": round(length, 1),
        "climb_m": round(climb, 1),
        "descent_m": round(descent, 1),
        "start_elevation_m": round(start, 1),
        "end_elevation_m": round(end, 1),
        "max_grade_pct": round(max_up, 1),
        "max_descent_grade_pct": round(max_down, 1),
        "length_by_severity_m": {k: round(v, 1) for k, v in by_severity.items()},
    }


def route_grade(G, origin, destination, bump_penalty=DEFAULT_BUMP_PENALTY, danger_penalty=DEFAULT_DANGER_PENALTY,
                pm_penalty=DEFAULT_PM_PENALTY, stop_penalty=DEFAULT_STOP_PENALTY, prefer_time=False,
                shade_penalty=DEFAULT_SHADE_PENALTY, dark_penalty=DEFAULT_DARK_PENALTY,
                prefer_bike_friendly=DEFAULT_PREFER_BIKE_FRIENDLY, depart_time=None):
    """The route find_route picks, as a FeatureCollection of pieces coloured by grade, plus route totals."""
    penalties = (bump_penalty, danger_penalty, pm_penalty, stop_penalty, prefer_time, shade_penalty, dark_penalty,
                 prefer_bike_friendly, depart_time)
    with route_edges(G, origin, destination, penalties) as edges:
        return {"type": "FeatureCollection", "features": grade_pieces(G, edges), "summary": grade_summary(G, edges)}
