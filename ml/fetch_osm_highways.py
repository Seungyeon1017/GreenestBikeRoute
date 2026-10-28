"""Fetch OSM highway & surface tags for the 11,011 ways in road_network_heilbronn via official OSM API.

Outputs:
  data/osm_tags_cache.json: {way_id: {"highway": ..., "surface": ...}}
"""
import ast
import json
import time
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ROAD_NET_PATH = DATA_DIR / "road_network_heilbronn.geojson"
OUTPUT_PATH = DATA_DIR / "osm_tags_cache.json"

def parse_osm_ids(osmid_val):
    s = str(osmid_val).strip()
    if s.startswith("[") and s.endswith("]"):
        try:
            return [int(x) for x in ast.literal_eval(s)]
        except Exception:
            return []
    try:
        return [int(s)]
    except ValueError:
        return []

def collect_unique_ways():
    with open(ROAD_NET_PATH, "r", encoding="utf-8") as f:
        roads = json.load(f)["features"]
    unique_ways = set()
    for feat in roads:
        for w in parse_osm_ids(feat["properties"].get("osmid")):
            unique_ways.add(w)
    return sorted(unique_ways)

def fetch_batch(way_batch):
    url = f"https://api.openstreetmap.org/api/0.6/ways?ways={','.join(map(str, way_batch))}"
    req = urllib.request.Request(url, headers={"User-Agent": "GreenestBikeRouteResearch/1.0 (contact: github.com)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        xml_data = resp.read()
    root = ET.fromstring(xml_data)
    results = {}
    for way in root.findall("way"):
        wid = str(way.get("id"))
        tags = {t.get("k"): t.get("v") for t in way.findall("tag")}
        results[wid] = {
            "highway": tags.get("highway"),
            "surface": tags.get("surface"),
            "name": tags.get("name"),
            "cycleway": tags.get("cycleway"),
        }
    return results

def main():
    ways = collect_unique_ways()
    print(f"Total unique OSM ways: {len(ways)}")
    
    existing = {}
    if OUTPUT_PATH.exists():
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
            print(f"Loaded {len(existing)} existing cached way tags.")
        except Exception:
            pass
            
    needed = [w for w in ways if str(w) not in existing]
    print(f"Ways remaining to fetch: {len(needed)}")
    
    batch_size = 200
    total_batches = (len(needed) + batch_size - 1) // batch_size
    
    for idx, i in enumerate(range(0, len(needed), batch_size), 1):
        batch = needed[i:i + batch_size]
        try:
            res = fetch_batch(batch)
            existing.update(res)
            print(f"[{idx}/{total_batches}] Fetched {len(res)} ways. Total cached: {len(existing)}")
        except Exception as e:
            print(f"Error on batch {idx}: {e}, waiting 2s...")
            time.sleep(2)
            try:
                res = fetch_batch(batch)
                existing.update(res)
                print(f"[{idx}/{total_batches}] Retry success. Total cached: {len(existing)}")
            except Exception as e2:
                print(f"Failed batch {idx} again: {e2}")
        time.sleep(0.3)
        
        # Save incrementally every 10 batches
        if idx % 10 == 0:
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(existing, f)
                
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)
    print(f"Complete! Saved {len(existing)} ways to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
