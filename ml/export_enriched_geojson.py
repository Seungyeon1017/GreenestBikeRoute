"""Export an enriched road network GeoJSON with roughness, traffic flow, highway, and surface attached.

Outputs:
  data/road_network_enriched_heilbronn.geojson
"""
import ast
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data"

from ml.train_imputer import HIGHWAY_TO_SURFACE
from routing.costs import way_means

def parse_ways(osmid_val):
    s = str(osmid_val).strip()
    try:
        return [int(x) for x in ast.literal_eval(s)] if s.startswith("[") else [int(s)]
    except Exception:
        return []

def value_and_source(idx, ways, by_idx, measured_by_way, estimated_by_way, default):
    """Same priority as routing/graph.py: measured segment or OSM way, then the estimate, then the default."""
    if idx in by_idx:
        return float(by_idx[idx]), "measured"
    for source, by_way in (("measured", measured_by_way), ("estimated", estimated_by_way)):
        vals = [by_way[w] for w in ways if w in by_way]
        if vals:
            return sum(vals) / len(vals), source
    return default, "unknown"

def export_enriched():
    print("Loading datasets...")
    with open(DATA / "road_network_heilbronn.geojson") as f:
        roads = json.load(f)
    with open(DATA / "bumpy_roads_heilbronn.geojson") as f:
        bumpy = json.load(f)
    with open(DATA / "traffic_flow_heilbronn.geojson") as f:
        tf = json.load(f)

    # OSM tags cache
    osm_tags = {}
    if (DATA / "osm_tags_cache.json").exists():
        with open(DATA / "osm_tags_cache.json") as f:
            osm_tags = json.load(f)

    # ML lookup
    ml_rough = {}
    if (DATA / "ml_predicted_roughness.json").exists():
        with open(DATA / "ml_predicted_roughness.json") as f:
            ml_rough = {int(k): float(v) for k, v in json.load(f).items()}

    ml_tf = {}
    if (DATA / "ml_predicted_traffic_flow.json").exists():
        with open(DATA / "ml_predicted_traffic_flow.json") as f:
            ml_tf = {int(k): float(v) for k, v in json.load(f).items()}

    # Index maps from bumpy and tf
    bumpy_by_idx = {
        b["properties"]["id"]: b["properties"]["Normalized Roughness"]
        for b in bumpy["features"]
        if b["properties"].get("Normalized Roughness") is not None
    }
    tf_by_idx = {
        t["properties"]["road_segment"]: t["properties"]["avg_traffic_flow"]
        for t in tf["features"]
        if t["properties"].get("avg_traffic_flow") is not None
    }

    rough_by_way = way_means(bumpy["features"], "Normalized Roughness")
    tf_by_way = way_means(tf["features"], "avg_traffic_flow")

    features = roads["features"]
    r_counts, t_counts = Counter(), Counter()

    for idx, feat in enumerate(features):
        p = feat["properties"]
        ways = parse_ways(p.get("osmid"))

        # Highway & surface
        hw = "unknown"
        surf = p.get("surface")
        for w in ways:
            t = osm_tags.get(str(w), {})
            if t.get("highway"):
                hw = t["highway"]
                if not surf and t.get("surface"):
                    surf = t["surface"]
                break
        if not surf or str(surf).strip().lower() in ("none", "unknown"):
            surf = HIGHWAY_TO_SURFACE.get(hw, "unknown")

        r_val, r_src = value_and_source(idx, ways, bumpy_by_idx, rough_by_way, ml_rough, 10.0)
        t_val, t_src = value_and_source(idx, ways, tf_by_idx, tf_by_way, ml_tf, 0.374)
        r_counts[r_src] += 1
        t_counts[t_src] += 1

        p["highway"] = hw
        p["surface"] = surf
        p["roughness"] = round(r_val, 2)
        p["roughness_source"] = r_src
        p["traffic_flow"] = round(t_val, 3)
        p["traffic_source"] = t_src

    out_file = DATA / "road_network_enriched_heilbronn.geojson"
    print(f"Saving {len(features)} enriched road segments to {out_file}...")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(roads, f)

    print("Export Complete!")
    print(f"Roughness:    {dict(r_counts)}")
    print(f"Traffic Flow: {dict(t_counts)}")

if __name__ == "__main__":
    export_enriched()
