import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from tests.conftest import COORDS, A, B


@pytest.fixture
def client(toy_graph):
    with TestClient(create_app(graph=toy_graph)) as c:
        yield c


def params(penalty=None, start=COORDS[A]):
    p = {"from_lat": start[0], "from_lon": start[1], "to_lat": COORDS[B][0], "to_lon": COORDS[B][1]}
    if penalty is not None:
        p["penalty"] = penalty
    return p


def test_route_returns_geojson(client):
    r = client.get("/route", params=params(penalty=0))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/geo+json"
    assert r.json()["features"][0]["properties"]["length_m"] == 100


def test_penalty_changes_the_route(client):
    assert client.get("/route", params=params(penalty=10)).json()["features"][0]["properties"]["length_m"] == 140


def test_default_penalty_is_used(client):
    assert client.get("/route", params=params()).json()["features"][0]["properties"]["penalty"] == 10


def test_negative_penalty_is_invalid(client):
    assert client.get("/route", params=params(penalty=-1)).status_code == 422


def test_unroutable_point_is_400(client):
    r = client.get("/route", params=params(start=(48.7758, 9.1829)))
    assert r.status_code == 400
    assert "Heilbronn" in r.json()["detail"]


def test_penalty_is_documented(client):
    spec = client.get("/openapi.json").json()
    penalty = next(p for p in spec["paths"]["/route"]["get"]["parameters"] if p["name"] == "penalty")
    assert penalty["description"] == "How much do you hate bumps"
