"""Write data/road_network_enriched_heilbronn.geojson: every road segment with the roughness and
stop-and-go the router uses and where each value comes from, for Kepler.gl or QGIS.

    uv run python ml/export_enriched_geojson.py

roughness_source: measured / estimated (ml/estimate_roughness.py) / unknown (router uses the median, 10)
stop_go_source:   measured / unknown (router uses 0.63, see routing/README.md)
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from download_data import load_features
from routing.costs import DEFAULT_ROUGHNESS, DEFAULT_STOP_GO, osm_way_ids, way_roughness, way_stop_go
from routing.graph import load_estimates

OUT = ROOT / "data" / "road_network_enriched_heilbronn.geojson"


def value_and_source(idx, ways, by_idx, measured_by_way, estimated_by_way, default):
    """Same priority as routing/graph.py: measured segment or OSM way, then the estimate, then the default."""
    if idx in by_idx:
        return float(by_idx[idx]), "measured"
    for source, by_way in (("measured", measured_by_way), ("estimated", estimated_by_way)):
        vals = [by_way[w] for w in ways if w in by_way]
        if vals:
            return sum(vals) / len(vals), source
    return default, "unknown"


def main():
    roads = load_features("road_network_heilbronn")
    bumpy = load_features("bumpy_roads_heilbronn")
    rough_by_idx = {f["properties"]["id"]: f["properties"]["Normalized Roughness"]
                    for f in bumpy if f["properties"].get("Normalized Roughness") is not None}
    rough_by_way, estimated = way_roughness(bumpy), load_estimates()
    stop_by_way = way_stop_go(load_features("traffic_flow_heilbronn"))

    counts = {"roughness": Counter(), "stop_go": Counter()}
    for idx, f in enumerate(roads):
        p = f["properties"]
        ways = osm_way_ids(p["osmid"])
        rough, rough_src = value_and_source(idx, ways, rough_by_idx, rough_by_way, estimated, DEFAULT_ROUGHNESS)
        stop, stop_src = value_and_source(idx, ways, {}, stop_by_way, {}, DEFAULT_STOP_GO)
        p.update(roughness=round(rough, 2), roughness_source=rough_src, stop_go=round(stop, 3), stop_go_source=stop_src)
        counts["roughness"][rough_src] += 1
        counts["stop_go"][stop_src] += 1

    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": roads}))
    print(f"Wrote {len(roads)} road segments to {OUT.relative_to(ROOT)}")
    for name, c in counts.items():
        print(f"  {name:9} {dict(c)}")


if __name__ == "__main__":
    main()
