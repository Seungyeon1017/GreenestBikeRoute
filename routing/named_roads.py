"""Named ways in Heilbronn from OSM, to name streets on the map and in route stretches.

- The bike graph leaves out roads bikes may not ride (e.g. most of Mannheimer Straße), but their sidewalks are in it
  and should still take the road's name (routing.route._NamedRoads).
- A graph edge or ATRAI segment merged from several ways has several names, in no particular order: the way that
  covers most of the line names it (routing.route._main_way).

Run `python -m routing.named_roads` to download them again (data/custom/named_roads_heilbronn.overpassql via the
Overpass API).
"""
import json
from pathlib import Path

import requests

DATA = Path(__file__).resolve().parent.parent / "data" / "custom"
QUERY = DATA / "named_roads_heilbronn.overpassql"
OUT = DATA / "named_roads_heilbronn.geojson"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def to_geojson(overpass):
    """Overpass `out geom` JSON as GeoJSON LineStrings with the way's `name`, `highway` and `footway` tags."""
    features = [
        {"type": "Feature", "id": f"way/{w['id']}",
         "geometry": {"type": "LineString", "coordinates": [[round(p["lon"], 6), round(p["lat"], 6)] for p in w["geometry"]]},
         "properties": {k: w["tags"][k] for k in ("name", "highway", "footway") if k in w["tags"]}}
        for w in overpass["elements"] if w["type"] == "way" and len(w.get("geometry", [])) >= 2
    ]
    return {"type": "FeatureCollection", "features": features}


def load_named_ways(path=OUT):
    """{OSM way id: (name, tags {highway, footway}, [(lon, lat), ...])}, or {} if the file is missing."""
    path = Path(path)
    if not path.exists():
        return {}
    return {int(f["id"].split("/")[1]): (f["properties"]["name"],
                                         {k: v for k, v in f["properties"].items() if k != "name"},
                                         f["geometry"]["coordinates"])
            for f in json.loads(path.read_text(encoding="utf-8"))["features"]}


def main():
    query = "\n".join(line for line in QUERY.read_text(encoding="utf-8").splitlines() if not line.startswith("//"))
    # Overpass refuses requests without a User-Agent (406).
    response = requests.post(OVERPASS_URL, data={"data": query}, headers={"User-Agent": "GreenestBikeRoute"}, timeout=180)
    response.raise_for_status()
    collection = to_geojson(response.json())
    OUT.write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{OUT.name}: {len(collection['features'])} ways")


if __name__ == "__main__":
    main()
