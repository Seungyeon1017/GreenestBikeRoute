import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.schemas import DangerCollection, FlowCollection, GradeCollection, LightingCollection, RouteCollection, \
    RouteComparison, RoughnessCollection, ScoreCollection, ShadeCollection, SpeedCollection, DayRoutes
from download_data import HEILBRONN_BBOX, overtaking_risk
from routing.costs import DEFAULT_BUMP_PENALTY, MIN_OVERTAKING_CM
from routing.graph import attach_lighting, attach_shade
from tests.conftest import COORDS, A, B, joined


@pytest.fixture
def client(toy_graph):
    with TestClient(create_app(graph=toy_graph)) as c:
        yield c


RIDER = ("weight_kg", "e_bike")  # the routes take them for their kcal; /score has no single ride


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


def test_route_has_kcal_for_the_rider(client):
    base = client.get("/route", params=params()).json()["features"][0]["properties"]["kcal"]
    heavy = client.get("/route", params={**params(), "weight_kg": 90}).json()["features"][0]["properties"]["kcal"]
    e_bike = client.get("/route", params={**params(), "e_bike": True}).json()["features"][0]["properties"]["kcal"]
    assert heavy > base > e_bike


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
    assert client.get("/route", params=params()).json()["features"][0]["properties"]["bump_penalty"] == DEFAULT_BUMP_PENALTY


def test_negative_penalty_is_invalid(client):
    assert client.get("/route", params=params(bump_penalty=-1)).status_code == 422
    assert client.get("/route", params=params(bump_penalty=11)).status_code == 422  # points go up to 10


def test_unroutable_point_is_400(client):
    r = client.get("/route", params=params(start=(48.7758, 9.1829)))
    assert r.status_code == 400
    assert "Heilbronn" in r.json()["detail"]


def test_penalty_is_documented(client):
    spec = client.get("/openapi.json").json()
    bump_penalty = next(p for p in spec["paths"]["/route"]["get"]["parameters"] if p["name"] == "bump_penalty")
    assert bump_penalty["description"].startswith("How much do you hate bumps, in points 0-10")


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
    assert set(features[0]["properties"]) == {"roughness", "name", "way", "along"}
    assert not any(f["properties"]["name"].startswith("[") for f in features if f["properties"]["name"])
    RoughnessCollection.model_validate(r.json())


def test_street_overlays_come_without_names_until_they_are_ready(client):
    client.app.state.named.clear()  # as in the live API's first ~30 s
    assert client.get("/street-names").json() == {"ready": False}
    r = client.get("/roughness")
    assert r.json()["named"] is False
    assert set(r.json()["features"][0]["properties"]) == {"roughness"}
    assert set(client.get("/score").json()["features"][0]["properties"]) == {"score", "ridden"}
    RoughnessCollection.model_validate(r.json())

    client.app.state.named.set()
    assert client.get("/street-names").json() == {"ready": True}
    r = client.get("/roughness")
    assert r.json()["named"] is True
    assert set(r.json()["features"][0]["properties"]) == {"roughness", "name", "way", "along"}


def test_overlays_are_compressed(client):
    r = client.get("/roughness", headers={"Accept-Encoding": "gzip"})
    assert r.headers["content-encoding"] == "gzip"


def test_flow_overlay(client):
    r = client.get("/flow")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/geo+json"
    features = r.json()["features"]
    assert len(features) > 7000
    assert all(0 <= f["properties"]["stop_go"] <= 1 for f in features)
    assert features[0]["geometry"]["type"] == "LineString"
    FlowCollection.model_validate(r.json())


def test_prefer_time_is_passed_through_and_off_by_default(client):
    assert client.get("/route", params=params()).json()["features"][0]["properties"]["prefer_time"] is False
    p = client.get("/route", params={**params(), "prefer_time": "true"}).json()["features"][0]["properties"]
    assert p["prefer_time"] is True and p["duration_s"] > 0


def test_speed_overlay(client):
    r = client.get("/speed")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/geo+json"
    features = r.json()["features"]
    assert len(features) > 7000
    assert all(0 <= f["properties"]["speed_kmh"] < 100 for f in features)
    assert features[0]["geometry"]["type"] == "LineString"
    SpeedCollection.model_validate(r.json())


SLOTS = ["2026-07-21T09:00+02:00", "2026-07-21T15:00+02:00"]


@pytest.fixture
def lit_client(toy_graph):
    attach_shade(toy_graph, SLOTS, {11: [0.2, 0.6], 13: [1.0, 1.0]})
    attach_lighting(toy_graph, {11: 0.96, 12: 0.0}, {11: 0.7})
    with TestClient(create_app(graph=toy_graph)) as c:
        yield c


def test_depart_time_is_passed_through_and_off_by_default(lit_client):
    p = lit_client.get("/route", params=params()).json()["features"][0]["properties"]
    assert (p["depart_time"], p["daylight"], p["shade_penalty"], p["dark_penalty"]) == (None, None, 2, 10)
    p = lit_client.get("/route", params={**params(), "depart_time": "2026-07-21T14:00", "shade_penalty": 2}).json()["features"][0]["properties"]
    assert (p["depart_time"], p["daylight"], p["shade_slot"], p["shade_penalty"]) == ("2026-07-21T14:00+02:00", True, SLOTS[1], 2)
    p = lit_client.get("/route", params={**params(), "depart_time": "2026-10-28T19:30"}).json()["features"][0]["properties"]
    assert (p["depart_time"], p["daylight"], p["mean_shade"]) == ("2026-10-28T19:30+01:00", False, None)
    RouteCollection.model_validate(lit_client.get("/route", params={**params(), "depart_time": "2026-07-21T14:00"}).json())


def test_bad_depart_time_is_invalid(lit_client):
    assert lit_client.get("/route", params={**params(), "depart_time": "tomorrow"}).status_code == 422


def test_shade_overlay(lit_client):
    r = lit_client.get("/shade")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/geo+json"
    body = r.json()
    assert body["slots"] == SLOTS
    assert [f["properties"]["shade"] for f in body["features"]] == [[0.2, 0.6], [1.0, 1.0]]  # A -> C has no shade data
    ShadeCollection.model_validate(body)


def test_lighting_overlay(lit_client):
    r = lit_client.get("/lighting")
    assert r.status_code == 200
    features = r.json()["features"]
    unnamed = {"name": None, "way": None, "along": False}  # the toy streets have no names
    assert [f["properties"] for f in features] == [{"lit": 0.96, "lights_per_100m": 0.7, **unnamed}, {"lit": 0.0, **unnamed}]
    assert features[0]["geometry"]["type"] == "LineString"
    LightingCollection.model_validate(r.json())


def test_score_overlay_scores_how_long_streets_feel(client):
    r = client.get("/score")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/geo+json"
    body = ScoreCollection.model_validate(r.json())
    # Calm streets (no highway tag: residential, 30 km/h). C -> B (smooth) earns credit but stops at 100, A -> C
    # (default roughness) is typical: 100. A -> B (roughness 80, badness 7) feels 1 + 2 x 0.25 x 7 = 4.5x as long.
    assert [f.properties.score for f in body.features] == [100.0, 100.0, 22.2]
    assert not any(f.properties.ridden for f in body.features)  # no bike measured the toy streets


def test_score_overlay_follows_the_penalties(client):
    scores = lambda **p: [f["properties"]["score"] for f in client.get("/score", params=p).json()["features"]]
    assert scores(bump_penalty=0) == [100.0, 100.0, 100.0]
    assert scores(bump_penalty=0, danger_penalty=0, pm_penalty=0, stop_penalty=0) == [100.0, 100.0, 100.0]
    assert scores(bump_penalty=10) == [100.0, 100.0, 5.4]  # 1 + 10 x 0.25 x 7 = 18.5x
    assert client.get("/score", params={"bump_penalty": -1}).status_code == 422
    spec = client.get("/openapi.json").json()["paths"]
    names = lambda path: [p["name"] for p in spec[path]["get"]["parameters"]]
    assert names("/score") == [n for n in names("/route") if n not in RIDER][4:]  # everything but the start and end


def test_score_overlay_counts_unlit_streets_after_dark(toy_graph):
    attach_lighting(toy_graph, {12: 1.0, 13: 0.0, 14: 0.0})  # the smooth C -> B is unlit
    with TestClient(create_app(graph=toy_graph)) as c:
        scores = lambda **p: [f["properties"]["score"] for f in c.get("/score", params=p).json()["features"]]
        assert scores() == [100.0, 100.0, 22.2]
        # After dark the unlit C -> B feels 3.5x (dark_penalty 10) of its 1 / 1.5 for smoothness; A -> B, unknown
        # lighting (0.5 unlit, cubed), 1.3125x of its 4.5x.
        assert scores(depart_time="2026-10-28T19:30") == [100.0, 42.9, 16.9]
        assert c.get("/score", params={"depart_time": "tomorrow"}).status_code == 422


@pytest.fixture
def hilly_client(hilly):
    with TestClient(create_app(graph=hilly)) as c:
        yield c


def test_grade_returns_the_route_in_coloured_pieces(hilly_client):
    r = hilly_client.get("/route/grade", params=params(bump_penalty=10))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/geo+json"
    body = GradeCollection.model_validate(r.json())
    assert [(f.properties.severity, f.properties.grade_pct) for f in body.features] == [("steep", 7.1), ("gentle", -2.9)]
    assert (body.summary.climb_m, body.summary.descent_m, body.summary.max_grade_pct) == (5, 2, 7.1)
    route = hilly_client.get("/route", params=params(bump_penalty=10)).json()["features"][0]
    assert joined(r.json()["features"]) == route["geometry"]["coordinates"]
    assert body.summary.length_m == route["properties"]["length_m"]


def test_grade_takes_the_same_parameters_and_errors_as_route(hilly_client):
    spec = hilly_client.get("/openapi.json").json()["paths"]
    names = lambda path: [p["name"] for p in spec[path]["get"]["parameters"]]
    assert names("/route/grade") == names("/route")
    assert hilly_client.get("/route/grade", params=params(start=(48.7758, 9.1829))).status_code == 400
    assert hilly_client.get("/route/grade", params=params(bump_penalty=-1)).status_code == 422


def test_grade_without_elevation_data_is_503(client):
    r = client.get("/route/grade", params=params())
    assert r.status_code == 503
    assert "routing.elevation" in r.json()["detail"]


def test_day_returns_periods_of_comparisons(client):
    r = client.get("/route/day", params={**params(), "depart_time": "2026-07-21T15:00"})
    assert r.status_code == 200
    body = DayRoutes.model_validate(r.json())
    assert body.date == "2026-07-21"
    assert (r.json()["periods"][0]["from"], body.periods[-1].to) == ("00:00", "23:59")


def test_day_takes_the_same_parameters_and_errors_as_route(client):
    names = lambda path: {p["name"] for p in client.get("/openapi.json").json()["paths"][path]["get"]["parameters"]}
    assert names("/route/day") == names("/route")
    assert client.get("/route/day", params=params(start=(48.7758, 9.1829))).status_code == 400
