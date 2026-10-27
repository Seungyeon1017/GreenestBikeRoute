from download_data import overtaking_risk
from routing.costs import DEFAULT_PM_RISK, DEFAULT_ROUGHNESS, clean_overtaking, edge_cost, edge_roughness, osm_way_ids, point_risks,     way_roughness


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
    assert edge_cost(100, 50, bump_penalty=0, pm_penalty=0) == 100
    assert edge_cost(100, 50, bump_penalty=2, pm_penalty=0) == 200
    assert edge_cost(100, bump_penalty=10, pm_penalty=0) == 100 * (1 + 10 * DEFAULT_ROUGHNESS / 100)


def test_edge_cost_danger_adds_metres_per_risk():
    assert edge_cost(100, 0, danger=1.5, danger_penalty=40, pm_penalty=0) == 160
    assert edge_cost(10, 0, danger=1.5, danger_penalty=40, pm_penalty=0) == 70  # regardless of edge length


def test_edge_cost_pm_scales_length():
    assert edge_cost(100, 0, danger_penalty=0, pm_risk=0.5, pm_penalty=2) == 200
    assert edge_cost(100, 0, danger_penalty=0, pm_penalty=1) == 100 * (1 + DEFAULT_PM_RISK)


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
