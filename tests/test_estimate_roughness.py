"""ml/estimate_roughness.py. Needs the ml dependency group: uv run --group ml pytest"""
import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from download_data import load_features
from ml.estimate_roughness import measured_values, neighbour_estimates, segment_table, way_estimates
from routing.costs import way_roughness
from routing.graph import load_estimates

LAT, LON = 49.1400, 9.2100


def test_segment_table_names_ways_and_position():
    t = segment_table([
        {"properties": {"osmid": "1", "name": "Hauptstraße"},
         "geometry": {"type": "LineString", "coordinates": [[LON, LAT], [LON + 0.001, LAT]]}},
        {"properties": {"osmid": "[2, 3]", "name": None},
         "geometry": {"type": "LineString", "coordinates": [[LON, LAT], [LON, LAT + 0.001]]}},
    ])
    assert t.street.tolist() == ["Hauptstraße", "osm:[2, 3]"]
    assert t.ways.tolist() == [[1], [2, 3]]
    assert np.allclose(t.lat, [LAT, LAT + 0.0005]) and np.allclose(t.lon, [LON + 0.0005, LON])


def test_measured_values_join_by_index_and_check_osmid():
    road_osmids = ["10", "11", "12"]
    feats = [
        {"properties": {"id": 0, "osmid": "10", "v": 5.0}},
        {"properties": {"id": 1, "osmid": "99", "v": 7.0}},
        {"properties": {"id": 2, "osmid": "12", "v": None}},
        {"properties": {"id": 7, "osmid": "12", "v": 1.0}},
    ]
    assert measured_values(feats, "id", "v", road_osmids) == {0: 5.0}


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


def test_estimates_file_only_covers_unmeasured_ways():
    estimates = load_estimates()
    assert estimates and all(0 <= v <= 100 for v in estimates.values())
    assert not estimates.keys() & way_roughness(load_features("bumpy_roads_heilbronn")).keys()
