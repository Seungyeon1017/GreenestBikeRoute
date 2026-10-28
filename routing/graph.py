"""The Heilbronn bike graph from OSM (via OSMnx), with ATRAI roughness and traffic flow on every edge."""
import json
from pathlib import Path

import osmnx as ox

from download_data import load_features
from routing.costs import edge_roughness, way_means, way_roughness

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
GRAPH_PATH = CACHE_DIR / "heilbronn_bike.graphml"
PLACE = "Heilbronn, Germany"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
# Written by ml/train_imputer.py: estimates for unmeasured ways close to measured streets only.
ML_ROUGHNESS_PATH = DATA_DIR / "ml_predicted_roughness.json"
ML_TRAFFIC_FLOW_PATH = DATA_DIR / "ml_predicted_traffic_flow.json"


def load_ml_values(path):
    """{osm way id: estimate} from an ml/train_imputer.py output, or None if missing or unreadable."""
    p = Path(path)
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                return {int(k): float(v) for k, v in json.load(f).items()}
        except Exception:
            return None
    return None


def load_ml_roughness(path=ML_ROUGHNESS_PATH):
    """Load precomputed ML way roughness predictions if available."""
    return load_ml_values(path)


def load_graph(path=GRAPH_PATH, use_ml=True):
    """Load the bike graph from cache/, downloading it from OSM the first time (~2 min).

    Delete the .graphml file to pick up newer OSM data.
    """
    path = Path(path)
    if path.exists():
        G = ox.load_graphml(path)
    else:
        ox.settings.cache_folder = CACHE_DIR
        G = ox.graph_from_place(PLACE, network_type="bike")
        ox.save_graphml(G, path)
    attach_roughness(G, way_roughness(load_features("bumpy_roads_heilbronn")),
                     ml_way_rough=load_ml_roughness() if use_ml else None)
    attach_traffic_flow(G, way_means(load_features("traffic_flow_heilbronn"), "avg_traffic_flow"),
                        ml_way_flow=load_ml_values(ML_TRAFFIC_FLOW_PATH) if use_ml else None)
    return G


def _attach(G, attr, measured_by_way, estimated_by_way):
    """Set edge `attr` (None if unknown) and `<attr>_source`: "measured", "ml_predicted" or "default"."""
    for _, _, d in G.edges(data=True):
        measured = edge_roughness(d["osmid"], measured_by_way)
        if measured is not None:
            d[attr] = measured
            d[f"{attr}_source"] = "measured"
        elif estimated_by_way and (estimate := edge_roughness(d["osmid"], estimated_by_way)) is not None:
            d[attr] = estimate
            d[f"{attr}_source"] = "ml_predicted"
        else:
            d[attr] = None
            d[f"{attr}_source"] = "default"


def attach_roughness(G, way_rough, ml_way_rough=None):
    """Set edge attribute `roughness` (0-100, or None where no bike has measured it).

    If `ml_way_rough` is provided, unmeasured streets use the ML predicted roughness.
    """
    _attach(G, "roughness", way_rough, ml_way_rough)


def attach_traffic_flow(G, way_flow, ml_way_flow=None):
    """Set edge attribute `traffic_flow` (0-1, or None where unknown), like attach_roughness."""
    _attach(G, "traffic_flow", way_flow, ml_way_flow)
