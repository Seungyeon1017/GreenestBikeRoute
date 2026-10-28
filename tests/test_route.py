import pytest

from routing.graph import attach_bike_friendly, attach_danger, attach_roughness, attach_speed, attach_stop_go
from routing.route import RouteError, compare_routes, find_route
from tests.conftest import COORDS, A, B, C


def route(G, bump_penalty):
    return find_route(G, COORDS[A], COORDS[B], bump_penalty)["features"][0]


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
    assert f["properties"]["bump_penalty"] == 5


def test_compare_routes_puts_the_route_next_to_the_shortest(toy_graph):
    c = compare_routes(toy_graph, COORDS[A], COORDS[B], 10)
    assert (c["route"]["properties"]["length_m"], c["shortest"]["properties"]["length_m"]) == (140, 100)
    assert c["shortest"]["properties"]["bump_penalty"] == 0
    assert (c["detour_pct"], c["same_path"]) == (40.0, False)


def test_compare_routes_says_when_the_route_is_the_shortest(toy_graph):
    c = compare_routes(toy_graph, COORDS[A], COORDS[B], 0, 0, 0, 0)
    assert (c["detour_pct"], c["same_path"]) == (0.0, True)


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


def test_attach_stop_go(toy_graph):
    attach_stop_go(toy_graph, {11: 0.8, 13: 0.2, 14: 0.4})
    assert [d["stop_go"] for *_, d in toy_graph.edges(data=True)] == [0.8, None, pytest.approx(0.3)]


def test_stop_penalty_detours_around_stop_and_go_streets(toy_graph):
    for d in toy_graph.edges.values():
        d["roughness"] = 0.0
    attach_stop_go(toy_graph, {11: 0.9, 12: 0.1, 13: 0.1, 14: 0.1})
    assert find_route(toy_graph, COORDS[A], COORDS[B], 0, 0, 0, 0)["features"][0]["properties"]["length_m"] == 100
    f = find_route(toy_graph, COORDS[A], COORDS[B], 0, 0, 0, 2)["features"][0]  # 100 x 2.8 > 140 x 1.2
    assert (f["properties"]["length_m"], f["properties"]["mean_stop_go"]) == (140, 0.1)
    assert (f["properties"]["stop_penalty"], f["properties"]["stop_measured_share"]) == (2, 1.0)



def test_attach_speed(toy_graph):
    attach_speed(toy_graph, {11: 12.0, 13: 10.0, 14: 20.0})
    assert [d["speed_kmh"] for *_, d in toy_graph.edges(data=True)] == [12.0, None, 15.0]


def test_prefer_time_takes_the_faster_detour(toy_graph):
    for d in toy_graph.edges.values():
        d["roughness"] = 0.0
    attach_speed(toy_graph, {11: 5.0, 12: 20.0, 13: 20.0, 14: 20.0})
    p = find_route(toy_graph, COORDS[A], COORDS[B], 0, 0, 0, 0)["features"][0]["properties"]
    assert (p["length_m"], p["prefer_time"], p["duration_s"]) == (100, False, 72)  # 100 m at 5 km/h
    # 100 m at 5 km/h takes longer than 140 m at 20 km/h
    p = find_route(toy_graph, COORDS[A], COORDS[B], 0, 0, 0, 0, prefer_time=True)["features"][0]["properties"]
    assert (p["length_m"], p["prefer_time"], p["duration_s"], p["speed_measured_share"]) == (140, True, 25, 1.0)


def test_compare_routes_reports_extra_time(toy_graph):
    attach_speed(toy_graph, {11: 5.0, 12: 20.0, 13: 20.0, 14: 20.0})
    c = compare_routes(toy_graph, COORDS[A], COORDS[B], 0, 0, 0, 0, prefer_time=True)
    assert c["shortest"]["properties"]["prefer_time"] is False
    assert (c["detour_pct"], c["extra_time_pct"]) == (40.0, round((25 / 72 - 1) * 100, 1))


ON_AB = (9.2101, 49.14045)  # the bend of A->B, (lon, lat)
NEAR_CB = (9.21041, 49.14065)  # ~3 m off the middle of C->B
FAR = (9.25, 49.2)


def test_attach_danger_snaps_points_to_the_nearest_street(toy_graph):
    attach_danger(toy_graph, ([ON_AB, ON_AB, FAR], [0.5, 0.75, 1.0]), ([NEAR_CB, NEAR_CB], [0.2, 0.4]))
    ab, ac, cb = (toy_graph.edges[e] for e in ((A, B, 0), (A, C, 0), (C, B, 0)))
    assert (ab["danger"], ab["danger_points"], ab["pm_risk"]) == (1.25, 2, None)
    assert (ac["danger"], ac["danger_points"], ac["pm_risk"]) == (0, 0, None)
    assert cb["danger_points"] == 0 and cb["pm_risk"] == pytest.approx(0.3)


def test_attach_danger_covers_both_directions_of_a_street(toy_graph):
    toy_graph.add_edge(B, A, osmid=11, length=100.0, roughness=80.0,
                       geometry=toy_graph.edges[A, B, 0]["geometry"].reverse())
    attach_danger(toy_graph, ([ON_AB], [1.0]), ([], []))
    assert toy_graph.edges[A, B, 0]["danger"] == toy_graph.edges[B, A, 0]["danger"] == 1.0


def test_danger_penalty_detours_around_overtaking_spots(toy_graph):
    for d in toy_graph.edges.values():
        d["roughness"] = 0.0
    attach_danger(toy_graph, ([ON_AB], [1.0]), ([], []))
    shortest = find_route(toy_graph, COORDS[A], COORDS[B], 0, 0, 0, 0)["features"][0]["properties"]
    assert (shortest["length_m"], shortest["danger_points"], shortest["danger_risk"]) == (100, 1, 1.0)
    # 1 risk x 50 m outweighs the 40 m detour
    safe = find_route(toy_graph, COORDS[A], COORDS[B], 0, 50, 0, 0)["features"][0]["properties"]
    assert (safe["length_m"], safe["danger_points"], safe["danger_penalty"]) == (140, 0, 50)


def test_pm_penalty_detours_around_polluted_streets(toy_graph):
    for d in toy_graph.edges.values():
        d["roughness"] = 0.0
    attach_danger(toy_graph, ([], []), ([ON_AB, NEAR_CB], [0.9, 0.1]))
    assert find_route(toy_graph, COORDS[A], COORDS[B], 0, 0, 0)["features"][0]["properties"]["length_m"] == 100
    f = find_route(toy_graph, COORDS[A], COORDS[B], 0, 0, 10, 0)["features"][0]
    assert f["properties"]["length_m"] == 140
    assert f["properties"]["mean_pm_risk"] == 0.1  # A->C is unmeasured
    assert f["properties"]["pm_measured_share"] == 0.5


def test_attach_roughness_marks_measured_estimated_and_unknown(toy_graph):
    attach_roughness(toy_graph, {11: 80.0, 14: 0.0}, {12: 12.5})
    got = [(d["roughness"], d["roughness_source"]) for *_, d in toy_graph.edges(data=True)]
    assert got == [(80.0, "measured"), (12.5, "estimated"), (0.0, "measured")]

    attach_roughness(toy_graph, {11: 80.0, 14: 0.0})
    assert [d["roughness_source"] for *_, d in toy_graph.edges(data=True)] == ["measured", "unknown", "measured"]


def test_route_reports_estimated_share_apart_from_measured(toy_graph):
    attach_roughness(toy_graph, {11: 80.0, 14: 0.0}, {12: 12.5})
    p = find_route(toy_graph, COORDS[A], COORDS[B], 10, 0, 0, 0)["features"][0]["properties"]
    assert p["length_m"] == 140  # A -> C (estimated) -> B (measured)
    assert (p["measured_share"], p["estimated_share"]) == (0.5, 0.5)
    assert p["mean_roughness"] == 0  # over the measured part only


def test_prefer_bike_friendly_detours_onto_bike_friendly_streets(toy_graph):
    attach_bike_friendly(toy_graph, {12, 13})  # A->C and C->B (osmid [13, 14]) are bike lanes, A->B is not
    zero = {"bump_penalty": 0, "danger_penalty": 0, "pm_penalty": 0, "stop_penalty": 0}
    assert find_route(toy_graph, COORDS[A], COORDS[B], **zero)["features"][0]["properties"]["length_m"] == 100
    f = find_route(toy_graph, COORDS[A], COORDS[B], **zero, prefer_bike_friendly=1)["features"][0]
    assert f["properties"]["length_m"] == 140
    assert f["properties"]["prefer_bike_friendly"] == 1
