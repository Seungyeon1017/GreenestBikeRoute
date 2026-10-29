"""The greenest streets of Heilbronn (Grünste Straßen) for the Highlights tab: named streets bikes have ridden,
ranked by street trees, clean air and bike paths."""
from routing.costs import DEFAULT_PM_RISK
from routing.route import edge_coords, street_name

# A street counts only where ATRAI bikes rode it: its edges with a bike measurement (roughness, speed, stop-and-go or
# air), and only with at least MIN_RIDDEN_M of them, so a few metres of a crossing street don't rank.
MIN_RIDDEN_M = 150.0
# The green score (0-100) is a weighted mean of three shares, each 0-1 (higher = greener):
# - trees: street-tree canopy (routing.shade) over TREES_FULL; half a street under crowns is as green as it gets
#   (13% of the qualifying streets reach it, the median has 0.15).
# - air: pm_risk from AIR_BAD (0) to AIR_CLEAN (1), the 95% and 5% of measured streets (see DEFAULT_PM_RISK); a
#   street no air sensor passed counts at its prior. Weighted less: streets agree only weakly between bikes.
# - bike_friendly: share of its length on bike paths, bike lanes or bike routes.
TREES_FULL = 0.5
AIR_CLEAN, AIR_BAD = 0.44, 0.58
WEIGHTS = {"trees": 0.5, "air": 0.3, "bike_friendly": 0.2}


def ridden(d):
    """Whether ATRAI bikes measured the edge: they rode it."""
    return (d.get("roughness_source") == "measured" or d.get("speed_kmh") is not None or d.get("stop_go") is not None
            or bool(d.get("pm_rides")))


def _share(value, zero, one):
    return min(1.0, max(0.0, (value - zero) / (one - zero)))


def greenest_streets(G, limit=None):
    """The ridden named streets (see ridden, MIN_RIDDEN_M) as GeoJSON MultiLineStrings of their ridden edges, greenest
    first, with `rank`, `name`, `green_score` 0-100 and what it is made of (length-weighted over the ridden edges).
    A way without a name (a sidewalk, a bike path) counts for the road it runs beside (street_name)."""
    streets, seen = {}, set()
    for u, v, d in G.edges(data=True):
        edge = (min(u, v), max(u, v), str(d["osmid"]), round(float(d["length"]), 1))
        if edge in seen or not ridden(d):
            continue
        seen.add(edge)
        name = street_name(G, u, v, d)
        if not name:
            continue
        length = float(d["length"])
        pm = d.get("pm_risk") if d.get("pm_risk") is not None else d.get("pm_prior", DEFAULT_PM_RISK)
        s = streets.setdefault(name, {"length": 0.0, "trees": 0.0, "pm": 0.0, "bike": 0.0, "rides": 0, "lines": []})
        s["length"] += length
        s["trees"] += length * (d.get("trees") or 0.0)
        s["pm"] += length * pm
        s["bike"] += length * bool(d.get("bike_friendly"))
        s["rides"] = max(s["rides"], int(d.get("pm_rides") or 0))
        s["lines"].append([[round(x, 6), round(y, 6)] for x, y in edge_coords(G, u, v, d)])

    features = []
    for name, s in streets.items():
        if s["length"] < MIN_RIDDEN_M:
            continue
        trees, pm, bike = s["trees"] / s["length"], s["pm"] / s["length"], s["bike"] / s["length"]
        shares = {"trees": _share(trees, 0, TREES_FULL), "air": _share(pm, AIR_BAD, AIR_CLEAN), "bike_friendly": bike}
        score = 100 * sum(WEIGHTS[k] * shares[k] for k in WEIGHTS)
        features.append({"type": "Feature", "geometry": {"type": "MultiLineString", "coordinates": s["lines"]},
                         "properties": {"name": name, "green_score": round(score, 1), "tree_cover": round(trees, 3),
                                        "pm_risk": round(pm, 3), "bike_friendly_share": round(bike, 2),
                                        "ridden_m": round(s["length"]), "air_rides": s["rides"]}})
    features.sort(key=lambda f: (-f["properties"]["green_score"], f["properties"]["name"]))
    for rank, f in enumerate(features, 1):
        f["properties"] = {"rank": rank, **f["properties"]}
    return {"type": "FeatureCollection", "features": features[:limit], "total": len(features)}
