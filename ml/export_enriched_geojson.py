"""Export an enriched road network GeoJSON with roughness, traffic flow, highway, and surface attached.

Outputs:
  data/road_network_enriched_heilbronn.geojson
"""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

HIGHWAY_TO_SURFACE = {
    "motorway": "asphalt", "motorway_link": "asphalt",
    "trunk": "asphalt", "trunk_link": "asphalt",
    "primary": "asphalt", "primary_link": "asphalt",
    "secondary": "asphalt", "secondary_link": "asphalt",
    "tertiary": "asphalt", "tertiary_link": "asphalt",
    "unclassified": "asphalt",
    "residential": "asphalt",
    "living_street": "paving_stones",
    "service": "asphalt",
    "cycleway": "asphalt",
    "pedestrian": "paving_stones",
    "track": "gravel",
    "path": "ground",
    "footway": "paving_stones",
    "steps": "concrete",
}

def parse_ways(osmid_val):
    s = str(osmid_val).strip()
    try:
        return [int(x) for x in ast.literal_eval(s)] if s.startswith("[") else [int(s)]
    except Exception:
        return []

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

    features = roads["features"]
    counts = {"r_meas": 0, "r_est": 0, "t_meas": 0, "t_est": 0}

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

        # Roughness
        if idx in bumpy_by_idx:
            r_val = round(float(bumpy_by_idx[idx]), 2)
            r_src = "measured"
            counts["r_meas"] += 1
        else:
            est_vals = [ml_rough[w] for w in ways if w in ml_rough]
            r_val = round(sum(est_vals) / len(est_vals), 2) if est_vals else 10.0
            r_src = "estimated"
            counts["r_est"] += 1

        # Traffic flow
        if idx in tf_by_idx:
            t_val = round(float(tf_by_idx[idx]), 3)
            t_src = "measured"
            counts["t_meas"] += 1
        else:
            est_tf = [ml_tf[w] for w in ways if w in ml_tf]
            t_val = round(sum(est_tf) / len(est_tf), 3) if est_tf else 0.374
            t_src = "estimated"
            counts["t_est"] += 1

        p["highway"] = hw
        p["surface"] = surf
        p["roughness"] = r_val
        p["roughness_source"] = r_src
        p["traffic_flow"] = t_val
        p["traffic_source"] = t_src

    out_file = DATA / "road_network_enriched_heilbronn.geojson"
    print(f"Saving {len(features)} enriched road segments to {out_file}...")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(roads, f)

    print("Export Complete!")
    print(f"Roughness:    {counts['r_meas']} measured, {counts['r_est']} estimated")
    print(f"Traffic Flow: {counts['t_meas']} measured, {counts['t_est']} estimated")

if __name__ == "__main__":
    export_enriched()
