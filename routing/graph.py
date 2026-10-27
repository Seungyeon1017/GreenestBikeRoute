"""The Heilbronn bike graph from OSM (via OSMnx), with ATRAI roughness on every edge."""
from pathlib import Path

import osmnx as ox

from download_data import load_features
from routing.costs import edge_roughness, way_roughness

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
GRAPH_PATH = CACHE_DIR / "heilbronn_bike.graphml"
PLACE = "Heilbronn, Germany"


def load_graph(path=GRAPH_PATH):
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
    attach_roughness(G, way_roughness(load_features("bumpy_roads_heilbronn")))
    return G


def attach_roughness(G, way_rough):
    """Set edge attribute `roughness` (0-100, or None where no bike has measured it)."""
    for _, _, d in G.edges(data=True):
        d["roughness"] = edge_roughness(d["osmid"], way_rough)
