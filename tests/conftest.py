import networkx as nx
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


# Ground heights for /route/grade: A -> B +3 % (gentle), A -> C +7.1 % (steep), C -> B -2.9 % (gentle, downhill).
HEIGHTS = {A: 150.0, B: 153.0, C: 155.0}


@pytest.fixture
def hilly(toy_graph):
    for n, h in HEIGHTS.items():
        toy_graph.nodes[n]["elevation"] = h
    return toy_graph


def joined(features):
    """The LineStrings of consecutive features as one line, without repeating the joints."""
    coords = []
    for f in features:
        pts = f["geometry"]["coordinates"]
        coords.extend(pts if not coords else pts[1:])
    return coords
