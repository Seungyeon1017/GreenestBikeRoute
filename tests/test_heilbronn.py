"""End-to-end on the real Heilbronn graph. Skipped until cache/heilbronn_bike.graphml exists
(start the API once, or run `python -c "from routing.graph import load_graph; load_graph()"`)."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.schemas import EXAMPLE_TRIP, RouteComparison
from routing.graph import GRAPH_PATH, load_graph

pytestmark = pytest.mark.skipif(not GRAPH_PATH.exists(), reason="Heilbronn graph not cached yet")

# A trip across the south-east of the city where the shortest route is rough.
TRIP = EXAMPLE_TRIP


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(graph=load_graph())) as c:
        yield c


ONLY_BUMPS = {"danger_penalty": 0, "pm_penalty": 0, "stop_penalty": 0}


def test_hating_bumps_gives_a_smoother_longer_route(client):
    shortest = client.get("/route", params={**TRIP, **ONLY_BUMPS, "bump_penalty": 0}).json()["features"][0]
    smooth = client.get("/route", params={**TRIP, **ONLY_BUMPS, "bump_penalty": 10}).json()["features"][0]
    assert smooth["properties"]["length_m"] > shortest["properties"]["length_m"]
    assert smooth["properties"]["mean_roughness"] < shortest["properties"]["mean_roughness"]


def test_hating_close_overtaking_passes_fewer_danger_spots(client):
    zero = {"bump_penalty": 0, "danger_penalty": 0, "pm_penalty": 0, "stop_penalty": 0}
    shortest = client.get("/route", params={**TRIP, **zero}).json()["features"][0]["properties"]
    safe = client.get("/route", params={**TRIP, **zero, "danger_penalty": 25}).json()["features"][0]["properties"]
    assert safe["danger_points"] < shortest["danger_points"] / 2
    assert safe["length_m"] < shortest["length_m"] * 1.05


def test_air_overlay_gives_ranked_points(client):
    r = client.get("/air")
    features = r.json()["features"]
    assert r.status_code == 200 and len(features) > 100
    assert all(f["geometry"]["type"] == "Point" and 0 <= f["properties"]["air"] <= 1 for f in features)


def test_hating_stop_and_go_gives_a_more_free_flowing_route(client):
    # A north-to-south-east trip where the shortest route runs through stop-and-go streets.
    trip = {"from_lat": 49.16, "from_lon": 9.215, "to_lat": 49.135, "to_lon": 9.235}
    zero = {"bump_penalty": 0, "danger_penalty": 0, "pm_penalty": 0, "stop_penalty": 0}
    shortest = client.get("/route", params={**trip, **zero}).json()["features"][0]["properties"]
    smooth = client.get("/route", params={**trip, **zero, "stop_penalty": 5}).json()["features"][0]["properties"]
    assert smooth["mean_stop_go"] < shortest["mean_stop_go"]
    assert smooth["length_m"] < shortest["length_m"] * 1.05


def test_route_starts_and_ends_near_the_requested_points(client):
    coords = client.get("/route", params=TRIP).json()["features"][0]["geometry"]["coordinates"]
    assert len(coords) > 10
    for (lon, lat), (want_lat, want_lon) in ((coords[0], (TRIP["from_lat"], TRIP["from_lon"])),
                                            (coords[-1], (TRIP["to_lat"], TRIP["to_lon"]))):
        assert abs(lat - want_lat) < 0.001 and abs(lon - want_lon) < 0.001


def test_response_is_plain_json(client):
    json.dumps(client.get("/route", params=TRIP).json())  # no numpy types leak out


def test_docs_example_is_a_real_response(client):
    """The /route and /route/compare examples in /docs are what the example trip returns."""
    example = RouteComparison.model_config["json_schema_extra"]["example"]
    real = client.get("/route/compare", params=TRIP).json()
    for key in ("route", "shortest"):
        assert real[key]["properties"] == example[key]["properties"]
        coords = real[key]["geometry"]["coordinates"]
        assert example[key]["geometry"]["coordinates"] == [coords[0], coords[len(coords) // 2], coords[-1]]
    assert (real["detour_pct"], real["same_path"]) == (example["detour_pct"], example["same_path"])
