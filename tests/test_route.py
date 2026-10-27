import pytest

from routing.graph import attach_roughness
from routing.route import RouteError, find_route
from tests.conftest import COORDS, A, B


def route(G, penalty):
    return find_route(G, COORDS[A], COORDS[B], penalty)["features"][0]


def test_penalty_zero_is_shortest_route(toy_graph):
    f = route(toy_graph, 0)
    assert f["properties"]["length_m"] == 100
    # follows the edge geometry, including its bend, from A to B
    assert f["geometry"]["coordinates"] == [[9.2100, 49.1400], [9.2101, 49.14045], [9.2100, 49.1409]]


def test_high_penalty_detours_around_bumps(toy_graph):
    f = route(toy_graph, 10)
    assert f["properties"]["length_m"] == 140
    # edges without geometry become straight lines between their corners, joined without repeats
    assert f["geometry"]["coordinates"] == [[9.2100, 49.1400], [9.2108, 49.1404], [9.2100, 49.1409]]
    assert f["properties"]["mean_roughness"] == 0  # only C->B was measured
    assert f["properties"]["measured_share"] == 0.5


def test_parallel_edges_use_the_cheapest(toy_graph):
    toy_graph.add_edge(A, B, osmid=15, length=110.0, roughness=0.0)
    assert route(toy_graph, 10)["properties"]["length_m"] == 110


def test_result_is_geojson_feature_collection(toy_graph):
    fc = find_route(toy_graph, COORDS[A], COORDS[B], 5)
    assert fc["type"] == "FeatureCollection"
    (f,) = fc["features"]
    assert f["type"] == "Feature" and f["geometry"]["type"] == "LineString"
    assert f["properties"]["penalty"] == 5


def test_point_far_from_streets_is_rejected(toy_graph):
    with pytest.raises(RouteError, match="start point"):
        find_route(toy_graph, (48.7758, 9.1829), COORDS[B])  # Stuttgart


def test_same_start_and_end_is_rejected(toy_graph):
    with pytest.raises(RouteError, match="same"):
        find_route(toy_graph, COORDS[A], COORDS[A])


def test_no_path_is_rejected(toy_graph):
    with pytest.raises(RouteError, match="no bike route"):
        find_route(toy_graph, COORDS[B], COORDS[A])  # all edges are one-way towards B


def test_attach_roughness(toy_graph):
    attach_roughness(toy_graph, {11: 50, 14: 20})
    assert [d["roughness"] for *_, d in toy_graph.edges(data=True)] == [50, None, 20]
