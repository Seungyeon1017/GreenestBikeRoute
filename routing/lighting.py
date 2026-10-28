"""Street lighting per OSM way: is this street lit at night?

    python -X utf8 -m routing.lighting          # -> data/custom/lighting_heilbronn.json

Heilbronn publishes no street-lamp dataset, so this combines, in this order:

1. OSM `lit=yes/no`, where mappers have tagged it (~370 km of the ~1,900 km bike network).
2. Street lights detected in Mapillary photos (routing.mapillary_lights), snapped to the
   nearest street within SNAP_M: at least MIN_LIGHTS_PER_100M -> lit.
3. Elsewhere a rule: lit if it is a street for cars (residential, primary, ...) or has
   buildings within BUILDING_M metres along at least half of it; never for `track`.

Value per way = chance that it is lit: 1 / 0 from OSM, otherwise the share of OSM-tagged
streets in the same situation that are tagged lit=yes (see the constants below).
Combined, the three are right for ~91% of the tagged length (rule alone: ~90%), and
Mapillary turns ~300 km of guessed streets into observed ones.
Also stored: lights per 100 m from Mapillary, a rough hint of how well a street is lit.

Inputs: the OSM ways and tags OSMnx cached in cache/*.json when routing.graph built the
graph (run the API once first), the LoD2 building tiles from routing.shadow --download, and
(optional) data/custom/street_lights_mapillary.geojson.
"""
import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from routing.shade import DATA_DIR, to_xy
from routing.shadow import LOD2_DIR, load_buildings

CACHE_DIR = DATA_DIR.parent / "cache"
OUT = DATA_DIR / "custom" / "lighting_heilbronn.json"

BUILDING_M = 30.0
NEAR_SHARE = 0.5
CAR_STREETS = {"residential", "living_street", "pedestrian", "unclassified", "cycleway",
               "primary", "primary_link", "secondary", "secondary_link",
               "tertiary", "tertiary_link", "trunk", "trunk_link"}
# Measured on the OSM-tagged Heilbronn streets (length-weighted share tagged lit=yes):
# without Mapillary data
LIT_IF_RULE_SAYS_LIT = 0.91    # 268 of 295 km the rule calls lit
LIT_IF_RULE_SAYS_DARK = 0.14   # 11 of 78 km the rule calls dark
# with Mapillary data
LIT_IF_LIGHTS_SEEN = 0.96      # 248 km with >= 1 light per 200 m
LIT_IF_NOT_SEEN_RULE_LIT = 0.63   # 61 km: no light detected, rule says lit
LIT_IF_NOT_SEEN_RULE_DARK = 0.03  # 63 km: no light detected, rule says dark
MIN_LIGHTS_PER_100M = 0.5
SNAP_M = 20.0
LIGHTS = DATA_DIR / "custom" / "street_lights_mapillary.geojson"
GRID_M = 25.0


def load_osm_ways(cache_dir=CACHE_DIR):
    """{way_id: (tags, [(lon, lat), ...])} from every OSMnx Overpass response cached in cache_dir."""
    nodes, ways = {}, {}
    for path in sorted(Path(cache_dir).glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        elements = data.get("elements") if isinstance(data, dict) else None
        if not elements:
            continue
        for e in elements:
            if e.get("type") == "node":
                nodes[e["id"]] = (e["lon"], e["lat"])
        for e in elements:
            if e.get("type") == "way" and "highway" in e.get("tags", {}):
                ways[e["id"]] = (e["tags"], e["nodes"])
    return {w: (tags, [nodes[n] for n in ids if n in nodes]) for w, (tags, ids) in ways.items()}


class BuildingNearby:
    """Is any building footprint vertex within BUILDING_M of a point?"""

    def __init__(self, buildings):
        self.grid = defaultdict(list)
        for ring, _ in buildings:
            for x, y in ring:
                self.grid[(int(x // GRID_M), int(y // GRID_M))].append((x, y))

    def __call__(self, x, y, r=BUILDING_M):
        cx, cy, k = int(x // GRID_M), int(y // GRID_M), int(r // GRID_M) + 1
        for dx in range(-k, k + 1):
            for dy in range(-k, k + 1):
                for bx, by in self.grid.get((cx + dx, cy + dy), ()):
                    if (bx - x) ** 2 + (by - y) ** 2 <= r * r:
                        return True
        return False


def rule_says_lit(highway, near_share):
    if highway == "track":
        return False
    return highway in CAR_STREETS or near_share >= NEAR_SHARE


def _dist_to_segment(px, py, a, b):
    (ax, ay), (bx, by) = a, b
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def lights_per_way(osm_ways, lights_lonlat, snap_m=SNAP_M):
    """{way_id: number of lights} snapping each light to the nearest way segment within snap_m."""
    grid, segs = defaultdict(list), []
    cell = 30.0
    for w, (_, coords) in osm_ways.items():
        xy = [to_xy(lon, lat) for lon, lat in coords]
        for a, b in zip(xy, xy[1:]):
            k = len(segs)
            segs.append((w, a, b))
            for cx in range(int(min(a[0], b[0]) // cell), int(max(a[0], b[0]) // cell) + 1):
                for cy in range(int(min(a[1], b[1]) // cell), int(max(a[1], b[1]) // cell) + 1):
                    grid[(cx, cy)].append(k)
    counts = Counter()
    for lon, lat in lights_lonlat:
        x, y = to_xy(lon, lat)
        cx, cy = int(x // cell), int(y // cell)
        best, way = snap_m, None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for k in grid.get((cx + dx, cy + dy), ()):
                    d = _dist_to_segment(x, y, segs[k][1], segs[k][2])
                    if d <= best:
                        best, way = d, segs[k][0]
        if way is not None:
            counts[way] += 1
    return counts


def way_lighting(osm_ways, near, light_counts=None):
    """{way_id: (chance lit 0-1, "osm" | "mapillary" | "rule")} and the length (m) of each way.

    light_counts: {way_id: Mapillary lights on it}, or None when there is no Mapillary data.
    """
    out, lengths = {}, {}
    for w, (tags, coords) in osm_ways.items():
        if len(coords) < 2:
            continue
        xy = [to_xy(lon, lat) for lon, lat in coords]
        lengths[w] = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(xy, xy[1:]))
        lit = tags.get("lit")
        if lit in ("yes", "24/7", "automatic", "sunset-sunrise"):
            out[w] = (1.0, "osm")
            continue
        if lit in ("no", "disused"):
            out[w] = (0.0, "osm")
            continue
        if light_counts is not None and lengths[w] > 0 and \
                100 * light_counts.get(w, 0) / lengths[w] >= MIN_LIGHTS_PER_100M:
            out[w] = (LIT_IF_LIGHTS_SEEN, "mapillary")
            continue
        share = sum(near(x, y) for x, y in xy) / len(xy)
        says_lit = rule_says_lit(tags.get("highway"), share)
        if light_counts is None:
            out[w] = (LIT_IF_RULE_SAYS_LIT if says_lit else LIT_IF_RULE_SAYS_DARK, "rule")
        else:
            out[w] = (LIT_IF_NOT_SEEN_RULE_LIT if says_lit else LIT_IF_NOT_SEEN_RULE_DARK, "rule")
    return out, lengths


def load_lighting(path=OUT):
    """{way_id: chance lit 0-1} as written by main()."""
    return {int(k): v for k, v in json.loads(Path(path).read_text())["ways"].items()}


def load_light_density(path=OUT):
    """{way_id: Mapillary street lights per 100 m} (ways with at least one detected light)."""
    return {int(k): v for k, v in json.loads(Path(path).read_text()).get("lights_per_100m", {}).items()}


def edge_lit(osmid, ways, default=0.5):
    """Mean chance (0-1) that the OSM ways of a graph edge are lit; `default` if none is known."""
    ids = osmid if isinstance(osmid, list) else [osmid]
    known = [ways[i] for i in ids if i in ways]
    return sum(known) / len(known) if known else default


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, default=CACHE_DIR, help="folder with OSMnx's cached Overpass responses")
    ap.add_argument("--lights", type=Path, default=LIGHTS, help="Mapillary street lights GeoJSON (optional)")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    osm_ways = load_osm_ways(args.cache)
    if not osm_ways:
        raise SystemExit(f"No OSM ways in {args.cache}: start the API once (routing.graph caches OSM there)")
    zips = sorted(LOD2_DIR.glob("LoD2_*.zip")) + sorted(DATA_DIR.glob("LoD2_*.zip"))
    if not zips:
        raise SystemExit("No LoD2 tiles: run  python -X utf8 -m routing.shadow --download  first")
    buildings, _ = load_buildings(zips)
    print(f"{len(osm_ways):,} OSM ways, {len(buildings):,} building footprints")

    counts = None
    if args.lights.exists():
        lights = [f["geometry"]["coordinates"] for f in json.loads(args.lights.read_text())["features"]]
        counts = lights_per_way(osm_ways, lights)
        print(f"{len(lights):,} Mapillary lights, {sum(counts.values()):,} within {SNAP_M:.0f} m of a street")
    else:
        print(f"No {args.lights.name}: OSM tags + rule only (run routing.mapillary_lights to add it)")

    lighting, lengths = way_lighting(osm_ways, BuildingNearby(buildings), counts)
    density = {w: round(100 * c / lengths[w], 2) for w, c in (counts or {}).items() if lengths.get(w, 0) > 0}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "about": "chance each OSM way is lit at night: 1/0 from OSM lit=*, 0.96 if Mapillary saw >= 1 light "
                 "per 200 m, else 0.63/0.03 (0.91/0.14 without Mapillary) from the road-type + buildings rule",
        "source": "OpenStreetMap contributors (ODbL); Mapillary (CC BY-SA 4.0); LGL BW LoD2 (dl-de/by-2-0)",
        "ways": {str(w): v for w, (v, _) in lighting.items()},
        "lights_per_100m": {str(w): v for w, v in density.items()},
    }))
    km = Counter()
    for w, (v, src) in lighting.items():
        km[(src, v >= 0.5)] += lengths[w] / 1000
    print(f"{len(lighting):,} OSM ways -> {args.out}")
    for (src, lit), v in sorted(km.items()):
        print(f"  {src:9s} {'lit ' if lit else 'dark'}: {v:6.0f} km")


if __name__ == "__main__":
    main()
