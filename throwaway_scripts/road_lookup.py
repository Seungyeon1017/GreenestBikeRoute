"""Print every attribute of one OSM way, tagged with the data source it came from.
From the repo root: python -m throwaway_scripts.road_lookup 273050550"""
import sys

from download_data import load_features
from routing.graph import load_graph

GRAPH_SOURCE = "routing graph (OSM via OSMnx)"
LAYER_SOURCE = "road_network_heilbronn"
# Attributes load_graph attaches from the ATRAI layers, so they are not OSM tags.
OVERLAY_SOURCES = {
    "roughness": "bumpy_roads_heilbronn",
    "stop_go": "traffic_flow_heilbronn",
    "danger": "danger_zones_raw_heilbronn",
    "danger_points": "danger_zones_raw_heilbronn",
    "pm_risk": "air_quality_heilbronn",
}


def print_attributes(attributes, source):
    for name, value in attributes.items():
        print(f"{name}  [{source}]")
        print(f"\t{value}")


def features_of_way(features, osm_id):
    """Every feature whose osmid is `osm_id` (a merged way can list several ids)."""
    for f in features:
        osmid = f["properties"].get("osmid")
        ids = osmid if isinstance(osmid, list) else [osmid]
        if any(str(i) == str(osm_id) for i in ids):
            yield f["properties"]


def edges_of_way(G, osm_id):
    """Every edge (one piece of the way between two junctions) whose OSM way id is `osm_id`."""
    for u, v, key, data in G.edges(keys=True, data=True):
        osmid = data.get("osmid")
        ids = osmid if isinstance(osmid, list) else [osmid]
        if any(str(i) == str(osm_id) for i in ids):
            yield u, v, key, data


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python -m throwaway_scripts.road_lookup <osm_way_id>")
    osm_id = sys.argv[1]

    layer = list(features_of_way(load_features("road_network_heilbronn"), osm_id))
    for properties in layer:
        print(f"\n== road_network_heilbronn feature ==")
        print_attributes(properties, LAYER_SOURCE)

    G = load_graph()
    found = list(edges_of_way(G, osm_id))
    if not found and not layer:
        sys.exit(f"No road with OSM id {osm_id} in the Heilbronn bike graph or road_network layer.")
    for u, v, key, data in found:
        print(f"\n== routing graph edge {u} -> {v} (key {key}) ==")
        osm = {k: v for k, v in sorted(data.items()) if k not in OVERLAY_SOURCES}
        overlays = {k: data[k] for k in sorted(OVERLAY_SOURCES) if k in data}
        print_attributes(osm, GRAPH_SOURCE)
        for name, value in overlays.items():
            print_attributes({name: value}, OVERLAY_SOURCES[name])


if __name__ == "__main__":
    main()
