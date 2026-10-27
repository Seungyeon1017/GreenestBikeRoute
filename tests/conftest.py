gitimport networkx as nx
import pytest
from shapely.geometry import LineString

# Three corners ~100 m apart in Heilbronn:  A -> B is direct but bumpy,
# A -> C -> B is a 40% longer detour on smooth / unmeasured streets.
A, B, C = 1, 2, 3
COORDS = {A: (49.1400, 9.2100), B: (49.1409, 9.2100), C: (49.1404, 9.2108)}  # (lat, lon)


@pytest.fixture
def toy_graph():
    G = nx.MultiDiGraph(crs="epsg:4326")
    for n, (lat, lon) in COORDS.items():
        G.add_node(n, y=lat, x=lon)
    bend = LineString([(9.2100, 49.1400), (9.2101, 49.14045), (9.2100, 49.1409)])
    G.add_edge(A, B, osmid=11, length=100.0, roughness=80.0, geometry=bend)
    G.add_edge(A, C, osmid=12, length=70.0, roughness=None)  # unmeasured -> default roughness
    G.add_edge(C, B, osmid=[13, 14], length=70.0, roughness=0.0)
    return G
