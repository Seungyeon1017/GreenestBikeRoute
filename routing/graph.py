"""The Heilbronn bike graph from OSM (via OSMnx), with ATRAI roughness on every edge."""
import json
from pathlib import Path

import osmnx as ox

from download_data import load_features
from routing.costs import edge_roughness, way_roughness

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
GRAPH_PATH = CACHE_DIR / "heilbronn_bike.graphml"
PLACE = "Heilbronn, Germany"
ML_ROUGHNESS_PATH = Path(__file__).resolve().parent.parent / "data" / "ml_predicted_roughness.json"


def load_ml_roughness(path=ML_ROUGHNESS_PATH):
    """Load precomputed ML way roughness predictions if available."""
    p = Path(path)
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                return {int(k): float(v) for k, v in json.load(f).items()}
        except Exception:
            return None
    return None


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
    ml_rough = load_ml_roughness() if use_ml else None
    attach_roughness(G, way_roughness(load_features("bumpy_roads_heilbronn")), ml_way_rough=ml_rough)
    return G


def attach_roughness(G, way_rough, ml_way_rough=None):
    """Set edge attribute `roughness` (0-100, or None where no bike has measured it).

    If `ml_way_rough` is provided, unmeasured streets use the ML predicted roughness.
    """
    for _, _, d in G.edges(data=True):
        measured = edge_roughness(d["osmid"], way_rough)
        if measured is not None:
            d["roughness"] = measured
            d["roughness_source"] = "measured"
        elif ml_way_rough and (ml_val := edge_roughness(d["osmid"], ml_way_rough)) is not None:
            d["roughness"] = ml_val
            d["roughness_source"] = "ml_predicted"
        else:
            d["roughness"] = None
            d["roughness_source"] = "default"

