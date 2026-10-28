from routing.costs import DEFAULT_ROUGHNESS, edge_cost, edge_roughness, osm_way_ids, way_means, way_roughness


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


def test_way_means_uses_the_given_property():
    features = [
        {"properties": {"osmid": "1", "avg_traffic_flow": 0.2}},
        {"properties": {"osmid": "[1, 2]", "avg_traffic_flow": 0.6}},
    ]
    assert way_means(features, "avg_traffic_flow") == {1: 0.4, 2: 0.6}


def test_edge_roughness_handles_int_list_and_unmeasured():
    rough = {1: 30, 2: 40}
    assert edge_roughness(1, rough) == 30
    assert edge_roughness([1, 2, 99], rough) == 35
    assert edge_roughness(99, rough) is None


def test_edge_cost():
    assert edge_cost(100, 50, penalty=0) == 100
    assert edge_cost(100, 50, penalty=2) == 200
    assert edge_cost(100, penalty=10) == 100 * (1 + 10 * DEFAULT_ROUGHNESS / 100)
