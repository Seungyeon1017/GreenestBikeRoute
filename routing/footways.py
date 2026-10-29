"""Footways and paths routing leaves out because OSM doesn't say bikes may use them (routing.graph
keep_rideable_footways), kept as one GeoJSON feature per OSM way. Riders pick them when they report a footway bikes
ride on: the report then names the OSM way, which is what `python -m backend.reports approve` adds to
routing/rideable_ways.py's list.

Written by routing.graph whenever it builds the bike graph, so it always matches the graph in cache/.
"""
import json
import math
from pathlib import Path

from shapely import MultiLineString, Point, STRtree

DROPPED_FOOTWAYS_PATH = Path(__file__).resolve().parent.parent / "cache" / "heilbronn_dropped_footways.geojson"


def _tags(value):
    return value if isinstance(value, list) else [value]


def _coords(G, u, v, d):
    if "geometry" in d:
        return [[round(float(x), 6), round(float(y), 6)] for x, y in d["geometry"].coords]
    return [[round(float(G.nodes[n]["x"]), 6), round(float(G.nodes[n]["y"]), 6)] for n in (u, v)]


def footway_collection(G, edges):
    """The `edges` (u, v, key) of G as one Feature per OSM way: MultiLineString, `osm_way_id`, `name`, `length_m`.
    A two-way footway is two edges, one per direction: each piece counts once. Ways tagged bicycle=no are left out,
    as bikes may not ride there whatever riders report. An edge OSMnx merged from several ways goes to the first."""
    ways = {}
    for u, v, k in edges:
        d = G.edges[u, v, k]
        if "no" in _tags(d.get("bicycle")):
            continue
        way = _tags(d["osmid"])[0]
        pieces = ways.setdefault(int(way), {"name": _tags(d.get("name"))[0], "pieces": {}})["pieces"]
        pieces.setdefault((min(u, v), max(u, v)), (_coords(G, u, v, d), float(d["length"])))
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "geometry": {"type": "MultiLineString", "coordinates": [c for c, _ in w["pieces"].values()]},
         "properties": {"osm_way_id": way, "name": w["name"] if isinstance(w["name"], str) else None,
                        "length_m": round(sum(m for _, m in w["pieces"].values()), 1)}}
        for way, w in sorted(ways.items())]}


def save_footways(collection, path=DROPPED_FOOTWAYS_PATH):
    Path(path).write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")


class Footways:
    """The left-out footways, searchable by distance. `collection` as from footway_collection; by default read from
    DROPPED_FOOTWAYS_PATH (empty if the file is missing)."""

    def __init__(self, collection=None, path=DROPPED_FOOTWAYS_PATH):
        if collection is None:
            path = Path(path)
            collection = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"features": []}
        self.features = collection["features"]
        lats = [lat for f in self.features for line in f["geometry"]["coordinates"] for _, lat in line]
        self.cos_lat = math.cos(math.radians(sum(lats) / len(lats))) if lats else 1.0
        self.tree = STRtree([MultiLineString([[self._m(*p) for p in line] for line in f["geometry"]["coordinates"]])
                             for f in self.features]) if self.features else None

    def _m(self, lon, lat):
        """Equirectangular metres, plenty for the few tens of metres a tap is off."""
        return lon * 111_320 * self.cos_lat, lat * 111_320

    def nearest(self, lat, lon):
        """(feature, metres away) of the left-out footway nearest to (lat, lon), or (None, inf) if there are none."""
        if self.tree is None:
            return None, math.inf
        point = Point(self._m(lon, lat))
        i = int(self.tree.nearest(point))
        return self.features[i], self.tree.geometries[i].distance(point)

