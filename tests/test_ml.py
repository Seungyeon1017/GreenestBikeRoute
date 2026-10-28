import json

import numpy as np
import pandas as pd

from ml.train_imputer import (
    HIGHWAY_TO_SURFACE, line_geometry, measured_values, neighbour_estimates, neighbour_features,
    segment_table, way_estimates,
)
from routing.costs import way_means
from routing.graph import ML_ROUGHNESS_PATH, ML_TRAFFIC_FLOW_PATH, attach_roughness, attach_traffic_flow, load_ml_roughness

LAT, LON = 49.1400, 9.2100


def road(osmid, name, coords, surface="asphalt"):
    return {"properties": {"osmid": osmid, "name": name, "surface": surface, "oneway": False, "cycleway": None},
            "geometry": {"type": "LineString", "coordinates": coords}}


def test_line_geometry():
    length, lat, lon, sinuosity = line_geometry([[9.2100, 49.1400], [9.2110, 49.1400]])
    assert 70 < length < 76
    assert abs(lat - 49.14) < 1e-9 and abs(lon - 9.2105) < 1e-9
    assert abs(sinuosity - 1) < 1e-9


def test_segment_table_features():
    t = segment_table([
        road("1", "Hauptstraße", [[LON, LAT], [LON + 0.001, LAT]]),
        road("[2, 3]", None, [[LON, LAT], [LON, LAT + 0.001]], surface="['sett', 'asphalt']"),
    ])
    assert t.street.tolist() == ["Hauptstraße", "osm:[2, 3]"]
    assert t.ways.tolist() == [[1], [2, 3]]
    assert t.surface_asphalt.tolist() == [1, 0] and t.surface_sett.tolist() == [0, 1]
    assert t.has_name.tolist() == [1, 0]


def test_highway_to_surface_mapping():
    assert HIGHWAY_TO_SURFACE["primary"] == "asphalt"
    assert HIGHWAY_TO_SURFACE["residential"] == "asphalt"
    assert HIGHWAY_TO_SURFACE["track"] == "gravel"
    assert HIGHWAY_TO_SURFACE["path"] == "ground"
    assert HIGHWAY_TO_SURFACE["living_street"] == "paving_stones"


def test_measured_values_join_by_index_and_check_osmid():
    road_osmids = ["10", "11", "12"]
    feats = [
        {"properties": {"id": 0, "osmid": "10", "v": 5.0}},
        {"properties": {"id": 1, "osmid": "99", "v": 7.0}},
        {"properties": {"id": 2, "osmid": "12", "v": None}},
        {"properties": {"id": 7, "osmid": "12", "v": 1.0}},
    ]
    assert measured_values(feats, "id", "v", road_osmids) == {0: 5.0}


def test_neighbour_features_skip_same_street_and_far_segments():
    src_lat = np.array([LAT, LAT + 0.0005, LAT + 0.0009, LAT + 0.01])
    src_lon = np.full(4, LON)
    values = np.array([100.0, 10.0, 20.0, 50.0])
    streets = np.array(["Query", "A", "B", "C"])
    out = neighbour_features(src_lat, src_lon, values, streets, np.array([LAT]), np.array([LON]), np.array(["Query"]))
    idw, median, count, nearest = out[0]
    assert count == 2
    assert 10 < idw < 15
    assert median == 15
    assert 50 < nearest < 60


def test_neighbour_estimates_trust_same_street_and_shrink_by_distance():
    # Four unmeasured segments (0-3), each ~730 m apart, with one measured segment (4-7) north of it:
    # same street 55 m away, other street 30 m, 110 m and 200 m away.
    north = [0.0005, 0.00027, 0.001, 0.0018]
    table = pd.DataFrame({
        "lat": [LAT] * 4 + [LAT + n for n in north],
        "lon": [LON + 0.01 * k for k in range(4)] * 2,
        "street": ["Q0", "Q1", "Q2", "Q3", "Q0", "Other", "Other", "Other"],
    })
    values = np.array([np.nan] * 4 + [30.0] * 4)
    est, weight = neighbour_estimates(table, np.arange(4, 8), np.arange(4), values, fallback=10.0)
    assert np.allclose(est[:3], [30.0, 24.0, 20.0]) and np.isnan(est[3])
    assert np.allclose(weight[:3], [1.0, 0.7, 0.5]) and np.isnan(weight[3])


def test_way_estimates_average_per_way_and_skip_measured_ways():
    t = pd.DataFrame({"ways": [[1], [1, 2], [3]]})
    assert way_estimates(t, [0, 1, 2], [10.0, 20.0, 5.0], measured_ways={3}) == {1: 15.0, 2: 20.0}


def test_ml_outputs_only_cover_unmeasured_ways():
    from download_data import load_features

    for path, source, key, hi in ((ML_ROUGHNESS_PATH, "bumpy_roads_heilbronn", "Normalized Roughness", 100),
                                  (ML_TRAFFIC_FLOW_PATH, "traffic_flow_heilbronn", "avg_traffic_flow", 1)):
        estimates = {int(k): v for k, v in json.loads(path.read_text()).items()}
        assert estimates and all(0 <= v <= hi for v in estimates.values())
        assert not estimates.keys() & way_means(load_features(source), key).keys()


def test_load_ml_roughness():
    ml_dict = load_ml_roughness()
    assert ml_dict
    assert all(0.0 <= v <= 100.0 for v in ml_dict.values())


def test_attach_roughness_with_ml(toy_graph):
    measured = {11: 80.0, 14: 0.0}
    ml_imputed = {12: 12.5}

    attach_roughness(toy_graph, measured, ml_way_rough=ml_imputed)

    edges = list(toy_graph.edges(data=True))
    edge_dict = {d["osmid"] if not isinstance(d["osmid"], list) else tuple(d["osmid"]): d for *_, d in edges}

    assert edge_dict[11]["roughness"] == 80.0
    assert edge_dict[11]["roughness_source"] == "measured"

    assert edge_dict[12]["roughness"] == 12.5
    assert edge_dict[12]["roughness_source"] == "ml_predicted"

    assert edge_dict[(13, 14)]["roughness"] == 0.0
    assert edge_dict[(13, 14)]["roughness_source"] == "measured"


def test_attach_traffic_flow(toy_graph):
    attach_traffic_flow(toy_graph, {11: 0.8}, ml_way_flow={13: 0.2})
    got = [(d["traffic_flow"], d["traffic_flow_source"]) for *_, d in toy_graph.edges(data=True)]
    assert got == [(0.8, "measured"), (None, "default"), (0.2, "ml_predicted")]
    assert [d["roughness"] for *_, d in toy_graph.edges(data=True)] == [80.0, None, 0.0]
