import json

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.reports import CLOSED_AT, WINDOW_S, ReportError, Reports
from backend.schemas import ClosureCollection, ClosureFeature, MappingCollection, MappingFeature
from routing.rideable_ways import load_rideable_ways
from routing.route import RouteError, find_route, set_closures
from tests.conftest import COORDS, A, B, C


class Clock:
    def __init__(self):
        self.t = 1_800_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def reports(clock):
    return Reports(":memory:", clock=clock)


def report(reports, reporter, ip, u=A, v=B):
    return reports.report_closure(u, v, [11], (9.21, 49.14), reporter, ip)


def test_one_report_marks_a_street_reported(reports):
    state = report(reports, "r1", "1.1.1.1")
    assert (state["status"], state["reports"], state["osm_way_ids"]) == ("reported", 1, [11])
    assert reports.closures() == {(A, B): "reported"}


def test_independent_reports_close_a_street(reports):
    for i in range(CLOSED_AT):
        state = report(reports, f"r{i}", f"1.1.1.{i}")
    assert (state["status"], state["reports"]) == ("closed", CLOSED_AT)


def test_one_rider_or_one_network_counts_once(reports):
    for _ in range(CLOSED_AT):
        report(reports, "same-rider", "1.1.1.1")
    for i in range(CLOSED_AT):
        state = report(reports, f"new-id-{i}", "2.2.2.2")  # a new id per report, from one network
    assert state["reports"] == 2


def test_both_directions_are_one_segment(reports):
    report(reports, "r1", "1.1.1.1", A, B)
    report(reports, "r2", "1.1.1.2", B, A)
    assert reports.closure_states()[(A, B)]["reports"] == 2


def test_reports_expire(reports, clock):
    for i in range(CLOSED_AT):
        report(reports, f"r{i}", f"1.1.1.{i}")
    clock.t += WINDOW_S - 1
    assert reports.closures() == {(A, B): "closed"}
    clock.t += 2
    assert reports.closures() == {}


def test_a_reported_street_is_avoided_if_the_detour_is_short(toy_graph):
    trip = (COORDS[A], COORDS[B])
    assert find_route(toy_graph, *trip, bump_penalty=0)["features"][0]["properties"]["length_m"] == 100
    set_closures(toy_graph, {(A, B): "reported"})
    p = find_route(toy_graph, *trip, bump_penalty=0)["features"][0]["properties"]
    assert (p["length_m"], p["reported_closures"]) == (140, 0)


def test_a_reported_street_is_still_ridden_without_a_sensible_way_round(toy_graph):
    set_closures(toy_graph, {(A, B): "reported", (A, C): "reported", (B, C): "reported"})
    p = find_route(toy_graph, COORDS[A], COORDS[B], bump_penalty=0)["features"][0]["properties"]
    assert (p["length_m"], p["reported_closures"]) == (100, 1)


def test_a_closed_street_is_not_ridden(toy_graph):
    set_closures(toy_graph, {(A, C): "reported", (A, B): "closed"})
    assert find_route(toy_graph, COORDS[A], COORDS[B], bump_penalty=0)["features"][0]["properties"]["length_m"] == 140
    set_closures(toy_graph, {(A, C): "closed", (A, B): "closed"})
    with pytest.raises(RouteError):
        find_route(toy_graph, COORDS[A], COORDS[B])


def test_a_place_on_a_closed_street_can_still_be_reached(toy_graph):
    set_closures(toy_graph, {(A, B): "closed"})
    halfway = (49.14045, 9.2101)  # on the bend of A -> B
    assert find_route(toy_graph, COORDS[A], halfway, bump_penalty=0)["features"][0]["properties"]["length_m"] < 100


def test_closures_are_cleared(toy_graph):
    set_closures(toy_graph, {(A, B): "closed"})
    set_closures(toy_graph, {})
    assert not any("closure" in d for *_, d in toy_graph.edges(data=True))


@pytest.fixture
def client(toy_graph, reports):
    with TestClient(create_app(graph=toy_graph, reports=reports)) as c:
        yield c


def test_report_a_closure(client):
    r = client.post("/reports/closures", json={"lat": 49.14045, "lon": 9.2101, "reporter_id": "r1", "note": "Baustelle"})
    assert r.status_code == 201
    body = ClosureFeature.model_validate(r.json())
    assert (body.properties.segment, body.properties.status, body.properties.reports) == (f"{A}-{B}", "reported", 1)
    ClosureCollection.model_validate(client.get("/reports/closures").json())
    assert len(client.get("/reports/closures").json()["features"]) == 1


def test_a_closure_far_from_every_street_is_refused(client):
    assert client.post("/reports/closures", json={"lat": 49.15, "lon": 9.25}).status_code == 400


def test_routes_use_the_reports(client, reports):
    params = {"from_lat": COORDS[A][0], "from_lon": COORDS[A][1], "to_lat": COORDS[B][0], "to_lon": COORDS[B][1],
              "bump_penalty": 0}
    assert client.get("/route", params=params).json()["features"][0]["properties"]["length_m"] == 100
    for i in range(CLOSED_AT):
        report(reports, f"r{i}", f"1.1.1.{i}")
    assert client.get("/route", params=params).json()["features"][0]["properties"]["length_m"] == 140


def test_report_a_rideable_footway(client):
    r = client.post("/reports/mapping", json={"lat": 49.1404, "lon": 9.2108, "kind": "rideable", "osm_way_id": 123,
                                              "note": "signed for bikes"})
    assert r.status_code == 201
    assert MappingFeature.model_validate(r.json()).properties.status == "pending"
    listed = MappingCollection.model_validate(client.get("/reports/mapping").json())
    assert [f.properties.osm_way_id for f in listed.features] == [123]
    assert client.get("/reports/mapping", params={"status": "approved"}).json()["features"] == []


def test_mapping_report_kind_is_checked(client):
    assert client.post("/reports/mapping", json={"lat": 49.14, "lon": 9.21, "kind": "blocked"}).status_code == 422


def test_approving_a_rideable_report_adds_the_way(reports, tmp_path):
    path = tmp_path / "rideable_ways.json"
    path.write_text(json.dumps({"286359672": "Allee"}))
    stored = reports.report_mapping("rideable", (9.21, 49.14), "r1", "1.1.1.1", note="signed for bikes")
    with pytest.raises(ReportError):
        reports.approve_mapping(stored["id"], rideable_path=path)  # no way id yet
    approved = reports.approve_mapping(stored["id"], way_id=123, rideable_path=path)
    assert (approved["status"], approved["osm_way_id"]) == ("approved", 123)
    assert load_rideable_ways(path) == {123: f"signed for bikes (user report {stored['id']})", 286359672: "Allee"}
    assert reports.mapping_reports() == []


def test_rejecting_leaves_the_list_alone(reports, tmp_path):
    path = tmp_path / "rideable_ways.json"
    stored = reports.report_mapping("rideable", (9.21, 49.14), "r1", "1.1.1.1", osm_way_id=5, note="x")
    assert reports.reject_mapping(stored["id"])["status"] == "rejected"
    assert not path.exists()
