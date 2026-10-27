"""End-to-end on the real Heilbronn graph. Skipped until cache/heilbronn_bike.graphml exists
(start the API once, or run `python -c "from routing.graph import load_graph; load_graph()"`)."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from routing.graph import GRAPH_PATH, load_graph

pytestmark = pytest.mark.skipif(not GRAPH_PATH.exists(), reason="Heilbronn graph not cached yet")

# A trip across the south-east of the city where the shortest route is rough.
TRIP = {"from_lat": 49.14838, "from_lon": 9.22687, "to_lat": 49.1262, "to_lon": 9.22439}


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(graph=load_graph())) as c:
        yield c


def test_hating_bumps_gives_a_smoother_longer_route(client):
    shortest = client.get("/route", params={**TRIP, "penalty": 0}).json()["features"][0]
    smooth = client.get("/route", params={**TRIP, "penalty": 10}).json()["features"][0]
    assert smooth["properties"]["length_m"] > shortest["properties"]["length_m"]
    assert smooth["properties"]["mean_roughness"] < shortest["properties"]["mean_roughness"]


def test_route_starts_and_ends_near_the_requested_points(client):
    coords = client.get("/route", params=TRIP).json()["features"][0]["geometry"]["coordinates"]
    assert len(coords) > 10
    for (lon, lat), (want_lat, want_lon) in ((coords[0], (TRIP["from_lat"], TRIP["from_lon"])),
                                            (coords[-1], (TRIP["to_lat"], TRIP["to_lon"]))):
        assert abs(lat - want_lat) < 0.001 and abs(lon - want_lon) < 0.001


def test_response_is_plain_json(client):
    json.dumps(client.get("/route", params=TRIP).json())  # no numpy types leak out
