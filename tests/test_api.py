import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.schemas import DangerCollection, FlowCollection, RouteCollection, RouteComparison, RoughnessCollection
from download_data import HEILBRONN_BBOX, overtaking_risk
from routing.costs import MIN_OVERTAKING_CM
from tests.conftest import COORDS, A, B


@pytest.fixture
def client(toy_graph):
    with TestClient(create_app(graph=toy_graph)) as c:
        yield c


def params(bump_penalty=None, start=COORDS[A]):
    p = {"from_lat": start[0], "from_lon": start[1], "to_lat": COORDS[B][0], "to_lon": COORDS[B][1]}
    if bump_penalty is not None:
        p["bump_penalty"] = bump_penalty
    return p


def test_route_returns_geojson(client):
    r = client.get("/route", params=params(bump_penalty=0))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/geo+json"
    assert r.json()["features"][0]["properties"]["length_m"] == 100


def test_route_matches_the_documented_schema(client):
    RouteCollection.model_validate(client.get("/route", params=params()).json())


def test_compare_returns_route_and_shortest(client):
    r = client.get("/route/compare", params=params(bump_penalty=10))
    assert r.status_code == 200
    body = RouteComparison.model_validate(r.json())
    assert (body.route.properties.length_m, body.shortest.properties.length_m, body.detour_pct) == (140, 100, 40.0)


def test_compare_takes_the_same_parameters_and_errors_as_route(client):
    spec = client.get("/openapi.json").json()["paths"]
    names = lambda path: [p["name"] for p in spec[path]["get"]["parameters"]]
    assert names("/route/compare") == names("/route")
    assert client.get("/route/compare", params=params(start=(48.7758, 9.1829))).status_code == 400


def test_docs_show_a_geojson_linestring(client):
    spec = client.get("/openapi.json").json()
    ok = spec["paths"]["/route"]["get"]["responses"]["200"]["content"]
    assert ok["application/geo+json"]["schema"] == {"$ref": "#/components/schemas/RouteCollection"}
    assert spec["components"]["schemas"]["LineString"]["properties"]["type"]["const"] == "LineString"


def test_penalty_changes_the_route(client):
    assert client.get("/route", params=params(bump_penalty=10)).json()["features"][0]["properties"]["length_m"] == 140


def test_default_penalty_is_used(client):
    assert client.get("/route", params=params()).json()["features"][0]["properties"]["bump_penalty"] == 10


def test_negative_penalty_is_invalid(client):
    assert client.get("/route", params=params(bump_penalty=-1)).status_code == 422


def test_unroutable_point_is_400(client):
    r = client.get("/route", params=params(start=(48.7758, 9.1829)))
    assert r.status_code == 400
    assert "Heilbronn" in r.json()["detail"]


def test_penalty_is_documented(client):
    spec = client.get("/openapi.json").json()
    bump_penalty = next(p for p in spec["paths"]["/route"]["get"]["parameters"] if p["name"] == "bump_penalty")
    assert bump_penalty["description"] == "How much do you hate bumps"


def test_danger_penalties_are_passed_through(client):
    p = client.get("/route", params={**params(), "danger_penalty": 70, "pm_penalty": 3, "stop_penalty": 2}).json()["features"][0]["properties"]
    assert (p["danger_penalty"], p["pm_penalty"], p["stop_penalty"]) == (70, 3, 2)


def test_danger_overlay(client):
    r = client.get("/danger")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/geo+json"
    features = r.json()["features"]
    assert len(features) > 3000
    west, south, east, north = HEILBRONN_BBOX
    assert all(west <= f["geometry"]["coordinates"][0] <= east and south <= f["geometry"]["coordinates"][1] <= north
               for f in features)  # no rides from Karlsruhe, Munich, ...
    assert all(f["properties"]["risk"] < overtaking_risk(1, MIN_OVERTAKING_CM) for f in features)  # all over 25 cm
    assert features[0]["geometry"]["type"] == "Point"
    assert set(features[0]["properties"]) == {"risk"}
    DangerCollection.model_validate(r.json())


def test_roughness_overlay(client):
    r = client.get("/roughness")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/geo+json"
    features = r.json()["features"]
    assert len(features) > 9000
    assert set(features[0]["properties"]) == {"roughness"}
    RoughnessCollection.model_validate(r.json())


def test_flow_overlay(client):
    r = client.get("/flow")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/geo+json"
    features = r.json()["features"]
    assert len(features) > 7000
    assert all(0 <= f["properties"]["stop_go"] <= 1 for f in features)
    assert features[0]["geometry"]["type"] == "LineString"
    FlowCollection.model_validate(r.json())
