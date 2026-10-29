from datetime import datetime, timezone

import networkx as nx
import pytest

from routing import graph
from routing.calories import DEFAULT_WEIGHT_KG, ride_kcal, walk_kcal
from routing.costs import AIR_HOTSPOT_OFFSET, AIR_PRIOR_RIDES
from routing.graph import attach_bike_friendly, attach_danger, attach_lighting, attach_roughness, attach_shade, attach_speed, attach_stop_go
from routing.route import WALK_KMH, RouteError, compare_routes, day_routes, find_route, sky
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


def test_start_on_a_merged_two_way_street_can_leave_both_ways(toy_graph):
    # OSMnx lists merged way ids in riding order, so the way back lists them reversed.
    toy_graph.add_edge(B, C, osmid=[14, 13], length=70.0, roughness=0.0)
    mid_cb = (49.14065, 9.2104)
    for end in (B, C):
        assert find_route(toy_graph, mid_cb, COORDS[end], 0, 0, 0, 0)["features"][0]["properties"]["length_m"] == 35


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


def test_climb_m_is_null_without_elevation(toy_graph):
    assert route(toy_graph, 0)["properties"]["climb_m"] is None


def test_climb_m_and_kcal_count_the_ascent(hilly):
    p = route(hilly, 10)["properties"]  # the detour A -> C -> B climbs 5 m
    assert p["climb_m"] == 5
    assert p["kcal"] == pytest.approx(ride_kcal(p["duration_s"], 5, DEFAULT_WEIGHT_KG), abs=0.2)


def test_kcal_follows_the_rider_and_the_bike(toy_graph):
    p = route(toy_graph, 0)["properties"]
    # the toy graph has no elevation, so the climb counts as 0
    assert p["kcal"] == pytest.approx(ride_kcal(p["duration_s"], 0, DEFAULT_WEIGHT_KG), abs=0.1)
    heavy = find_route(toy_graph, COORDS[A], COORDS[B], 0, weight_kg=90)["features"][0]["properties"]
    e_bike = find_route(toy_graph, COORDS[A], COORDS[B], 0, e_bike=True)["features"][0]["properties"]
    assert heavy["kcal"] > p["kcal"] and e_bike["kcal"] < p["kcal"]


def test_compare_routes_reports_extra_time(toy_graph):
    attach_speed(toy_graph, {11: 5.0, 12: 20.0, 13: 20.0, 14: 20.0})
    c = compare_routes(toy_graph, COORDS[A], COORDS[B], 0, 0, 0, 0, prefer_time=True)
    assert c["shortest"]["properties"]["prefer_time"] is False
    assert (c["detour_pct"], c["extra_time_pct"]) == (40.0, round((25 / 72 - 1) * 100, 1))


ON_AB = (9.2101, 49.14045)  # the bend of A->B, (lon, lat)
NEAR_CB = (9.21041, 49.14065)  # ~3 m off the middle of C->B
FAR = (9.25, 49.2)


def test_attach_danger_snaps_points_to_the_nearest_street(toy_graph):
    attach_danger(toy_graph, ([ON_AB, ON_AB, FAR], [0.5, 0.75, 1.0]), ([NEAR_CB, NEAR_CB], [0.2, 0.4], ["r1", "r2"]))
    ab, ac, cb = (toy_graph.edges[e] for e in ((A, B, 0), (A, C, 0), (C, B, 0)))
    assert (ab["danger"], ab["danger_points"], ab["pm_risk"]) == (1.25, 2, None)
    assert (ac["danger"], ac["danger_points"], ac["pm_risk"]) == (0, 0, None)
    assert cb["danger_points"] == 0 and cb["pm_rides"] == 2
    assert cb["pm_risk"] == pytest.approx((0.2 + 0.4 + AIR_PRIOR_RIDES * 0.5) / (2 + AIR_PRIOR_RIDES))


def test_attach_danger_counts_each_ride_once_and_pulls_few_rides_towards_typical(toy_graph):
    # r1 passed with three readings, r2 with one: two rides, each worth the same
    attach_danger(toy_graph, ([], []), ([NEAR_CB] * 4, [0.2, 0.3, 0.4, 0.9], ["r1", "r1", "r1", "r2"]))
    cb = toy_graph.edges[C, B, 0]
    assert cb["pm_rides"] == 2
    assert cb["pm_risk"] == pytest.approx((0.3 + 0.9 + AIR_PRIOR_RIDES * 0.5) / (2 + AIR_PRIOR_RIDES))
    attach_danger(toy_graph, ([], []), ([NEAR_CB], [1.0], ["r1"]))
    assert toy_graph.edges[C, B, 0]["pm_risk"] == pytest.approx(0.5 + 0.5 / (1 + AIR_PRIOR_RIDES))  # one ride: barely moves


def test_attach_danger_covers_both_directions_of_a_street(toy_graph):
    toy_graph.add_edge(B, A, osmid=11, length=100.0, roughness=80.0,
                       geometry=toy_graph.edges[A, B, 0]["geometry"].reverse())
    attach_danger(toy_graph, ([ON_AB], [1.0]), ([], [], []))
    assert toy_graph.edges[A, B, 0]["danger"] == toy_graph.edges[B, A, 0]["danger"] == 1.0


def test_attach_danger_starts_streets_along_a_hotspot_road_above_typical(toy_graph):
    along_cb = [(9.2108, 49.14042), (9.2100, 49.14092)]  # 3 m beside C->B
    attach_danger(toy_graph, ([], []), ([NEAR_CB], [0.9], ["r1"]), [along_cb])
    ab, cb = toy_graph.edges[A, B, 0], toy_graph.edges[C, B, 0]
    assert ab["pm_prior"] == 0.5 and ab["pm_risk"] is None
    assert cb["pm_prior"] == 0.5 + AIR_HOTSPOT_OFFSET
    assert cb["pm_risk"] == pytest.approx((0.9 + AIR_PRIOR_RIDES * (0.5 + AIR_HOTSPOT_OFFSET)) / (1 + AIR_PRIOR_RIDES))


def test_attach_danger_does_not_mark_streets_that_only_cross_a_hotspot_road(toy_graph):
    crossing_ab = [(9.2094, 49.1404), (9.2106, 49.1404)]
    attach_danger(toy_graph, ([], []), ([], [], []), [crossing_ab])
    assert toy_graph.edges[A, B, 0]["pm_prior"] == 0.5


def test_unmeasured_streets_cost_their_prior(toy_graph):
    for d in toy_graph.edges.values():
        d["roughness"] = 0.0
    attach_danger(toy_graph, ([], []), ([], [], []))
    toy_graph.edges[A, B, 0]["pm_prior"] = 5.0  # unmeasured, but a bad prior: worth a 40 m detour at pm_penalty 1
    assert find_route(toy_graph, COORDS[A], COORDS[B], 0, 0, 1, 0)["features"][0]["properties"]["length_m"] == 140


def test_danger_penalty_detours_around_overtaking_spots(toy_graph):
    for d in toy_graph.edges.values():
        d["roughness"] = 0.0
    attach_danger(toy_graph, ([ON_AB], [1.0]), ([], [], []))
    shortest = find_route(toy_graph, COORDS[A], COORDS[B], 0, 0, 0, 0)["features"][0]["properties"]
    assert (shortest["length_m"], shortest["danger_points"], shortest["danger_risk"]) == (100, 1, 1.0)
    # 1 risk x 50 m outweighs the 40 m detour
    safe = find_route(toy_graph, COORDS[A], COORDS[B], 0, 50, 0, 0)["features"][0]["properties"]
    assert (safe["length_m"], safe["danger_points"], safe["danger_penalty"]) == (140, 0, 50)


def test_pm_penalty_detours_around_polluted_streets(toy_graph, monkeypatch):
    monkeypatch.setattr(graph, "AIR_PRIOR_RIDES", 0)  # take the readings as they are
    for d in toy_graph.edges.values():
        d["roughness"] = 0.0
    attach_danger(toy_graph, ([], []), ([ON_AB, NEAR_CB], [0.9, 0.1], ["r1", "r1"]))
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


SLOTS = ["2026-07-21T09:00+02:00", "2026-07-21T12:00+02:00", "2026-07-21T15:00+02:00", "2026-07-21T18:00+02:00"]
SUMMER_AFTERNOON = datetime(2026, 7, 21, 15, 0)
SUMMER_NIGHT = datetime(2026, 7, 21, 23, 0)


def test_attach_shade_falls_back_to_tree_shade(toy_graph):
    attach_shade(toy_graph, SLOTS, {11: [0.1, 0.2, 0.3, 0.4], 13: [1.0, 1.0, 1.0, 1.0]}, {12: 0.5, 14: 0.0})
    assert toy_graph.graph["shade_slots"] == SLOTS
    assert [d["shade"] for *_, d in toy_graph.edges(data=True)] == [[0.1, 0.2, 0.3, 0.4], [0.5] * 4, [0.5] * 4]
    attach_shade(toy_graph, SLOTS, {})
    assert [d["shade"] for *_, d in toy_graph.edges(data=True)] == [None, None, None]


def test_attach_lighting(toy_graph):
    attach_lighting(toy_graph, {11: 1.0, 13: 0.2, 14: 0.4})
    assert [d["lit"] for *_, d in toy_graph.edges(data=True)] == [1.0, None, pytest.approx(0.3)]


@pytest.mark.parametrize("when, expected", [
    (None, (None, False)),                                   # no departure time: neither counts
    (datetime(2026, 7, 21, 13, 20), (1, False)),             # nearest slot 12:00
    (datetime(2026, 7, 21, 13, 31, tzinfo=timezone.utc), (2, False)),  # 15:31 local -> 15:00
    (datetime(2026, 7, 21, 6, 0), (0, False)),               # sun up since ~05:40
    (datetime(2026, 7, 21, 5, 0), (None, True)),             # before sunrise
    (datetime(2026, 12, 21, 17, 0), (None, True)),           # winter sunset ~16:30
    (datetime(2026, 12, 21, 16, 0), (2, False)),             # still light: nearest slot 15:00
])
def test_sky_picks_daylight_and_the_nearest_shade_slot(toy_graph, when, expected):
    toy_graph.graph["shade_slots"] = SLOTS
    assert sky(toy_graph, when) == expected


@pytest.fixture
def sunny_unlit_shortcut(toy_graph):
    """The direct street A -> B is sunny and unlit; the 40 % longer detour via C is shaded and lit."""
    for d in toy_graph.edges.values():
        d["roughness"] = 0.0
    attach_shade(toy_graph, SLOTS, {11: [0.0] * 4, 12: [1.0] * 4, 13: [1.0] * 4, 14: [1.0] * 4})
    attach_lighting(toy_graph, {11: 0.0, 12: 1.0, 13: 1.0, 14: 1.0})
    return toy_graph


def route_props(G, **kw):
    return find_route(G, COORDS[A], COORDS[B], 0, 0, 0, 0, **kw)["features"][0]["properties"]


def test_shade_penalty_detours_into_the_shade_by_day_only(sunny_unlit_shortcut):
    G = sunny_unlit_shortcut
    p = route_props(G, shade_penalty=4, dark_penalty=0, depart_time=SUMMER_AFTERNOON)  # 100 x 2 > 140
    assert (p["length_m"], p["daylight"], p["shade_slot"], p["mean_shade"]) == (140, True, SLOTS[2], 1.0)
    p = route_props(G, shade_penalty=4, dark_penalty=0, depart_time=SUMMER_NIGHT)
    assert (p["length_m"], p["daylight"], p["shade_slot"], p["mean_shade"]) == (100, False, None, None)


def test_dark_penalty_detours_onto_lit_streets_after_dark_only(sunny_unlit_shortcut):
    G = sunny_unlit_shortcut
    p = route_props(G, shade_penalty=0, dark_penalty=4, depart_time=SUMMER_NIGHT)
    assert (p["length_m"], p["mean_lit"], p["lit_known_share"]) == (140, 1.0, 1.0)
    assert route_props(G, shade_penalty=0, dark_penalty=4, depart_time=SUMMER_AFTERNOON)["length_m"] == 100


def test_without_depart_time_shade_and_lighting_change_nothing(sunny_unlit_shortcut):
    p = route_props(sunny_unlit_shortcut, shade_penalty=10, dark_penalty=10)
    assert (p["length_m"], p["depart_time"], p["daylight"], p["mean_shade"], p["mean_lit"]) == (100, None, None, None, 0.0)


def test_compare_routes_plans_the_shortest_route_for_the_same_time(sunny_unlit_shortcut):
    r = compare_routes(sunny_unlit_shortcut, COORDS[A], COORDS[B], 0, 0, 0, 0, shade_penalty=4, depart_time=SUMMER_AFTERNOON)
    assert r["shortest"]["properties"]["depart_time"] == "2026-07-21T15:00+02:00"
    assert (r["shortest"]["properties"]["mean_shade"], r["route"]["properties"]["mean_shade"]) == (0.0, 1.0)


def test_prefer_bike_friendly_detours_onto_bike_friendly_streets(toy_graph):
    attach_bike_friendly(toy_graph, {12, 13})  # A->C and C->B (osmid [13, 14]) are bike lanes, A->B is not
    zero = {"bump_penalty": 0, "danger_penalty": 0, "pm_penalty": 0, "stop_penalty": 0}
    assert find_route(toy_graph, COORDS[A], COORDS[B], **zero)["features"][0]["properties"]["length_m"] == 100
    f = find_route(toy_graph, COORDS[A], COORDS[B], **zero, prefer_bike_friendly=4)["features"][0]
    assert f["properties"]["length_m"] == 140
    assert f["properties"]["prefer_bike_friendly"] == 4


def test_route_reports_metres_on_bad_streets(toy_graph):
    attach_bike_friendly(toy_graph, {12})
    p = route_props(toy_graph)  # A -> B, roughness 80
    assert (p["bumpy_m"], p["bike_friendly_m"], p["sunny_m"], p["unlit_m"], p["pushed_m"]) == (100, 0, None, None, 0)
    p = find_route(toy_graph, COORDS[A], COORDS[B], 50, 0, 0, 0)["features"][0]["properties"]  # via C
    assert (p["bumpy_m"], p["bike_friendly_m"]) == (0, 70)


def test_route_reports_sunny_metres_by_day_and_unlit_metres_after_dark(sunny_unlit_shortcut):
    G = sunny_unlit_shortcut
    p = route_props(G, shade_penalty=0, depart_time=SUMMER_AFTERNOON)
    assert (p["sunny_m"], p["unlit_m"]) == (100, None)
    p = route_props(G, dark_penalty=0, depart_time=SUMMER_NIGHT)
    assert (p["sunny_m"], p["unlit_m"]) == (None, 100)


def test_scooter_kcal_counts_only_pushing(toy_graph):
    for d in toy_graph.edges.values():
        d.update(roughness=0.0, highway="footway", bicycle="yes")  # every street a footway: push all the way
    p = find_route(toy_graph, COORDS[A], COORDS[B], 0, 0, 0, 0, scooter=True)["features"][0]["properties"]
    assert p["pushed_m"] == p["length_m"]
    assert p["kcal"] == pytest.approx(walk_kcal(p["length_m"] / (WALK_KMH / 3.6)), abs=0.1)


def test_scooter_is_pushed_on_footways_not_signed_for_bikes(toy_graph):
    for d in toy_graph.edges.values():
        d["roughness"] = 0.0
    toy_graph.edges[A, B, 0].update(highway="footway", bicycle="yes")  # Gehweg, Radfahrer frei
    bike = route_props(toy_graph)
    assert (bike["length_m"], bike["pushed_m"]) == (100, 0)
    scooter = find_route(toy_graph, COORDS[A], COORDS[B], 0, 0, 0, 0, scooter=True)["features"][0]["properties"]
    assert (scooter["length_m"], scooter["pushed_m"]) == (140, 0)  # riding round beats pushing 100 m
    toy_graph.edges[A, B, 0]["bicycle"] = "designated"  # Zeichen 240: a shared path scooters must use
    assert find_route(toy_graph, COORDS[A], COORDS[B], 0, 0, 0, 0, scooter=True)["features"][0]["properties"]["length_m"] == 100


def test_day_routes_split_the_day_by_sky(sunny_unlit_shortcut):
    day = day_routes(sunny_unlit_shortcut, COORDS[A], COORDS[B], 0, 0, 0, 0, shade_penalty=4, dark_penalty=0,
                     depart_time=SUMMER_AFTERNOON)
    periods = day["periods"]
    assert day["date"] == "2026-07-21"
    assert (periods[0]["from"], periods[-1]["to"]) == ("00:00", "23:59")
    assert all(a["to"] == b["from"] for a, b in zip(periods[:-1], periods[1:]))
    slots = [p["route"]["properties"]["shade_slot"] for p in periods]
    assert slots == [None, *SLOTS, None]  # night, the four shade slots, night
    # By day the sunny shortcut is avoided, after dark (dark_penalty 0) it is taken.
    assert [p["route"]["properties"]["length_m"] for p in periods] == [100, 140, 140, 140, 140, 100]
    assert [p["same_path"] for p in periods] == [True, False, False, False, False, True]


def test_segments_cover_the_route_with_its_flags(toy_graph):
    toy_graph.edges[C, B, 0]["name"] = "Oststraße"
    f = find_route(toy_graph, COORDS[A], COORDS[B], 10)["features"][0]  # the detour A -> C -> B
    segments = f["properties"]["segments"]
    assert [(s["from_index"], s["to_index"], s["start_m"], s["name"]) for s in segments] == [(0, 1, 0, None), (1, 2, 70, "Oststraße")]
    assert segments[0]["roughness"] is None and segments[1]["roughness"] == 0
    # Unnamed streets with the same flags make one stretch, length-weighted over the measured part.
    del toy_graph.edges[C, B, 0]["name"]
    merged = find_route(toy_graph, COORDS[A], COORDS[B], 10)["features"][0]["properties"]["segments"]
    assert [(s["to_index"], s["length_m"], s["roughness"]) for s in merged] == [(2, 140, 0)]
    shortest = find_route(toy_graph, COORDS[A], COORDS[B], 0)["features"][0]["properties"]["segments"]
    assert [(s["to_index"], s["flags"], s["roughness"]) for s in shortest] == [(2, ["bumpy_m"], 80)]


def test_a_sidewalk_without_a_name_is_named_after_the_road_beside_it():
    G = nx.MultiDiGraph(crs="epsg:4326")
    points = {"r1": (49.1400, 9.2100), "r2": (49.1400, 9.2120), "s1": (49.14009, 9.2100), "s2": (49.14009, 9.2120),
              "p1": (49.1420, 9.2100), "p2": (49.1420, 9.2120)}
    for n, (lat, lon) in points.items():
        G.add_node(n, y=lat, x=lon)
    for a, b, osmid, tags in (("r1", "r2", 1, {"name": "Allee", "highway": "residential"}),
                              ("s1", "s2", 2, {"highway": "footway", "footway": "sidewalk"}),
                              ("p1", "p2", 3, {"highway": "path"}),  # 220 m away: no road beside it
                              ("s2", "p2", 4, {"highway": "path"})):  # leaves the road at a right angle
        for u, v in ((a, b), (b, a)):
            G.add_edge(u, v, osmid=osmid, length=146.0, roughness=None, **tags)

    def segments(start, end):
        f = find_route(G, points[start], points[end], 0)["features"][0]
        return [(s["name"], s["way"], s["along"]) for s in f["properties"]["segments"]]

    assert segments("s1", "s2") == [("Allee", "sidewalk", True)]
    assert segments("s1", "p1") == [("Allee", "sidewalk", True), (None, "path", False)]
