import pytest
from routing.graph import attach_roughness, load_ml_roughness
from ml.train_imputer import extract_features, calculate_length_and_centroid


def test_calculate_length_and_centroid():
    coords = [[9.2100, 49.1400], [9.2110, 49.1400]]
    length, num_pts, c_lat, c_lon, sinuosity, dist_center = calculate_length_and_centroid(coords)
    assert length > 50  # approx 73 meters
    assert num_pts == 2
    assert abs(c_lat - 49.1400) < 0.001
    assert abs(c_lon - 9.2105) < 0.001
    assert sinuosity >= 0.99


def test_extract_features():
    props = {"osmid": "12345", "name": "Hauptstraße", "surface": "asphalt", "oneway": True}
    geom = {"type": "LineString", "coordinates": [[9.2100, 49.1400], [9.2110, 49.1400]]}
    feats = extract_features(props, geom)

    assert feats["surface"] == "asphalt"
    assert feats["oneway"] == 1
    assert feats["is_strasse"] == 1
    assert feats["is_weg"] == 0
    assert feats["length_m"] > 50


def test_load_ml_roughness():
    ml_dict = load_ml_roughness()
    assert ml_dict is not None
    assert len(ml_dict) > 10000
    sample_val = next(iter(ml_dict.values()))
    assert 0.0 <= sample_val <= 100.0


def test_attach_roughness_with_ml(toy_graph):
    # toy_graph has edges:
    # A->B: osmid=11, roughness=80
    # A->C: osmid=12, roughness=None
    # C->B: osmid=[13, 14], roughness=0
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
