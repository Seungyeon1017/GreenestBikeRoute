import pytest

from download_data import overtaking_risk
from routing import costs
from routing.costs import DEFAULT_PM_RISK, DEFAULT_ROUGHNESS, DEFAULT_STOP_GO, FLOW_PRIOR_POINTS, MEDIAN_FLOW, MIN_RIDE_POINTS, \
    air_ranks, air_risks, clean_overtaking, edge_cost, edge_roughness, osm_way_ids, point_risks, way_roughness, way_stop_go


def test_osm_way_ids_single_and_merged():
    assert osm_way_ids("83738619") == [83738619]
    assert osm_way_ids("[439572396, 401802699]") == [439572396, 401802699]


def test_way_roughness_averages_segments_and_splits_merged_ids():
    features = [
        {"properties": {"osmid": "1", "Normalized Roughness": 20}},
        {"properties": {"osmid": "[1, 2]", "Normalized Roughness": 40}},
        {"properties": {"osmid": "3", "Normalized Roughness": None}},
    ]
    assert way_roughness(features) == {1: 30, 2: 40}


def test_edge_roughness_handles_int_list_and_unmeasured():
    rough = {1: 30, 2: 40}
    assert edge_roughness(1, rough) == 30
    assert edge_roughness([1, 2, 99], rough) == 35
    assert edge_roughness(99, rough) is None


def test_edge_cost():
    assert edge_cost(100, 50, bump_penalty=0, pm_penalty=0, stop_penalty=0) == 100
    assert edge_cost(100, 50, bump_penalty=2, pm_penalty=0, stop_penalty=0) == 200
    assert edge_cost(100, bump_penalty=10, pm_penalty=0, stop_penalty=0) == 100 * (1 + 10 * DEFAULT_ROUGHNESS / 100)


def test_edge_cost_danger_adds_metres_per_risk():
    assert edge_cost(100, 0, danger=1.5, danger_penalty=40, pm_penalty=0, stop_penalty=0) == 160
    assert edge_cost(10, 0, danger=1.5, danger_penalty=40, pm_penalty=0, stop_penalty=0) == 70  # regardless of edge length


def test_edge_cost_pm_scales_length():
    assert edge_cost(100, 0, danger_penalty=0, pm_risk=0.5, pm_penalty=2, stop_penalty=0) == 200
    assert edge_cost(100, 0, danger_penalty=0, pm_penalty=1, stop_penalty=0) == 100 * (1 + DEFAULT_PM_RISK)


def test_edge_cost_stop_go_scales_length():
    assert edge_cost(100, 0, danger_penalty=0, pm_penalty=0, stop_go=0.5, stop_penalty=2) == 200
    assert edge_cost(100, 0, danger_penalty=0, pm_penalty=0, stop_penalty=1) == pytest.approx(100 * (1 + DEFAULT_STOP_GO))


def flow(osmid, value, n):
    return {"properties": {"osmid": osmid, "avg_traffic_flow": value, "points_in_segment": n}}


def test_way_stop_go_weights_by_points_and_pulls_sparse_ways_to_the_median():
    k = FLOW_PRIOR_POINTS
    stop = way_stop_go([flow("1", 1.0, 1), flow("[1, 2]", 0.0, 1000), flow("3", None, 5)])
    assert stop[1] == pytest.approx(1 - (1 + k * MEDIAN_FLOW) / (1001 + k))  # the busy segment dominates
    assert stop[2] == pytest.approx(1 - k * MEDIAN_FLOW / (1000 + k))
    assert 3 not in stop
    sparse = way_stop_go([flow("4", 1.0, 1)])[4]
    assert 0 < sparse < DEFAULT_STOP_GO  # one free-rolling point moves it only a bit


def test_point_risks_skips_missing_values():
    features = [
        {"geometry": {"coordinates": [9.2, 49.1]}, "properties": {"Risk Index": 0.4}},
        {"geometry": {"coordinates": [9.3, 49.2]}, "properties": {"Risk Index": None}},
    ]
    assert point_risks(features, "Risk Index") == ([(9.2, 49.1)], [0.4])


def raw_overtake(cm):
    return {"geometry": {"coordinates": [9.2, 49.14]},
            "properties": {"Overtaking Distance": cm, "Risk Index Overtaking": overtaking_risk(1, cm) if cm else None}}


def test_clean_overtaking_drops_readings_of_25_cm_or_less_and_missing_distances():
    kept = clean_overtaking([raw_overtake(cm) for cm in (None, 0, 10, 25, 26, 100)])
    assert [f["properties"]["Overtaking Distance"] for f in kept] == [26, 100]


def pm(pm1, pm25, pm4, pm10, lonlat=(9.2, 49.14)):
    return {"geometry": {"coordinates": list(lonlat)},
            "properties": {"Finedust PM1": pm1, "Finedust PM2.5": pm25, "Finedust PM4": pm4, "Finedust PM10": pm10}}


def test_air_risks_normalises_each_pm_by_its_maximum():
    lonlat, risk = air_risks([pm(10, 20, 30, 40, lonlat=(9.1, 49.1)), pm(5, 20, 15, 0)])
    assert lonlat == [(9.1, 49.1), (9.2, 49.14)]
    assert risk == pytest.approx([1.0, 0.4 * 0.5 + 0.3 * 1 + 0.2 * 0.5 + 0])
    assert air_risks([]) == ([], [])


def ride_row(box, day, value):
    f = pm(value, value, value, value)
    f["properties"].update(boxId=box, createdAt=f"2026-06-{day}T08:00:00.000")
    return f


def test_air_ranks_compare_each_reading_with_its_own_ride(monkeypatch):
    monkeypatch.setattr(costs, "MIN_RIDE_POINTS", 3)
    smoggy = [ride_row("a", "01", v) for v in (30, 20, 40)]
    clean = [ride_row("a", "02", v) for v in (2, 4, 3)]  # same device, next day: the weather drops out
    _, rank = air_ranks(smoggy + clean)
    assert rank == pytest.approx([1 / 2, 1 / 6, 5 / 6, 1 / 6, 5 / 6, 1 / 2])


def test_air_ranks_skip_short_rides():
    assert air_ranks([ride_row("a", "01", 3) for _ in range(MIN_RIDE_POINTS - 1)]) == ([], [])
    assert air_ranks([]) == ([], [])
