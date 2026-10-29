import json
import sqlite3
from datetime import datetime, timedelta

import networkx as nx
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.reports import CLOSED_AT, DEFAULT_S, GRACE_S, LOCAL_TZ, MAX_S, OPEN_AT, ReportError, Reports
from backend.schemas import ClosureCollection, ClosureFeature, FootwayFeature, MappingCollection, MappingFeature,     StreetSegmentFeature
from routing.footways import Footways, footway_collection
from routing.graph import keep_rideable_footways
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


def report(reports, reporter, ip, u=A, v=B, **kwargs):
    return reports.report_closure(u, v, [11], (9.21, 49.14), reporter, ip, **kwargs)


def today(clock):
    return datetime.fromtimestamp(clock.t, LOCAL_TZ).date()


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


def test_a_lapsed_closure_is_unconfirmed_for_a_while_then_gone(reports, clock):
    for i in range(CLOSED_AT):
        report(reports, f"r{i}", f"1.1.1.{i}")
    clock.t += DEFAULT_S - 1
    assert reports.closures() == {(A, B): "closed"}
    clock.t += 2
    assert reports.closures() == {(A, B): "unconfirmed"}  # routes still avoid it; the app asks riders
    assert reports.closure_states()[(A, B)]["reports"] == 0
    clock.t += GRACE_S
    assert reports.closures() == {}


def test_a_report_lasts_until_the_day_on_the_sign(reports, clock):
    state = report(reports, "r1", "1.1.1.1", until=today(clock) + timedelta(days=14))
    clock.t += 14 * 24 * 3600
    assert reports.closures() == {(A, B): "reported"}
    assert state["expires"] == reports.closure_states()[(A, B)]["expires"]
    clock.t += 24 * 3600
    assert reports.closures() == {(A, B): "unconfirmed"}


def test_an_end_date_counts_at_most_30_days(reports, clock):
    report(reports, "r1", "1.1.1.1", until=today(clock) + timedelta(days=365))
    clock.t += MAX_S + 1
    assert reports.closures() == {(A, B): "unconfirmed"}


def test_an_end_date_in_the_past_is_refused(reports, clock):
    with pytest.raises(ReportError):
        report(reports, "r1", "1.1.1.1", until=today(clock) - timedelta(days=1))


def test_still_closed_keeps_a_closure_alive(reports, clock):
    report(reports, "r1", "1.1.1.1")
    clock.t += DEFAULT_S - 60
    report(reports, "r2", "1.1.1.2")  # "still closed"
    clock.t += DEFAULT_S - 60
    assert reports.closures() == {(A, B): "reported"}


def test_riders_saying_open_again_lift_a_closure(reports):
    for i in range(CLOSED_AT):
        report(reports, f"r{i}", f"1.1.1.{i}")
    state = report(reports, "o1", "2.2.2.1", still_closed=False)
    assert (state["status"], state["open_reports"]) == ("closed", 1)
    state = report(reports, "o2", "2.2.2.2", still_closed=False)
    assert state["status"] == "open"
    assert reports.closures() == {}
    assert report(reports, "r9", "1.1.1.9")["reports"] == 1  # a new closure starts from scratch


def test_still_closed_voids_earlier_open_answers(reports):
    report(reports, "r1", "1.1.1.1")
    report(reports, "o1", "2.2.2.1", still_closed=False)
    report(reports, "r2", "1.1.1.2")
    state = report(reports, "o2", "2.2.2.2", still_closed=False)
    assert (state["status"], state["open_reports"]) == ("reported", 1)


def test_one_rider_cannot_lift_a_closure_alone(reports):
    report(reports, "r1", "1.1.1.1")
    for i in range(OPEN_AT):
        state = report(reports, f"o{i}", "2.2.2.2", still_closed=False)
    assert state["status"] == "reported"


def test_report_files_from_before_end_dates_still_open(tmp_path, clock):
    path = tmp_path / "reports.sqlite3"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE closure_reports (id INTEGER PRIMARY KEY, created REAL NOT NULL, u INTEGER NOT NULL, "
               "v INTEGER NOT NULL, osm_way_ids TEXT NOT NULL, lon REAL NOT NULL, lat REAL NOT NULL, "
               "reporter TEXT NOT NULL, client TEXT NOT NULL, note TEXT)")
    db.execute("INSERT INTO closure_reports VALUES (1, ?, 1, 2, '[11]', 9.21, 49.14, 'r1', 'c1', 'Baustelle')", (clock.t,))
    db.commit()
    db.close()
    reports = Reports(path, clock=clock)
    assert reports.closure_states()[(1, 2)]["note"] == "Baustelle"
    report(reports, "r2", "1.1.1.2", until=today(clock) + timedelta(days=3))


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


# A footway beside the toy streets that routing leaves out, as routing.footways stores it.
FOOTWAY = {"type": "Feature", "geometry": {"type": "MultiLineString", "coordinates": [[[9.2110, 49.1400], [9.2110, 49.1409]]]},
           "properties": {"osm_way_id": 77, "name": None, "length_m": 100.0}}


@pytest.fixture
def client(toy_graph, reports):
    footways = Footways({"type": "FeatureCollection", "features": [FOOTWAY]})
    with TestClient(create_app(graph=toy_graph, reports=reports, footways=footways)) as c:
        yield c


def test_report_a_closure(client):
    r = client.post("/reports/closures", json={"lat": 49.14045, "lon": 9.2101, "reporter_id": "r1", "note": "Baustelle"})
    assert r.status_code == 201
    body = ClosureFeature.model_validate(r.json())
    assert (body.properties.segment, body.properties.status, body.properties.reports) == (f"{A}-{B}", "reported", 1)
    ClosureCollection.model_validate(client.get("/reports/closures").json())
    assert len(client.get("/reports/closures").json()["features"]) == 1


def test_preview_the_segment_a_click_would_report(client, reports):
    r = client.get("/reports/segment", params={"lat": 49.14045, "lon": 9.2101})
    assert r.status_code == 200
    body = StreetSegmentFeature.model_validate(r.json())
    assert (body.properties.segment, body.properties.osm_way_ids, body.properties.status) == (f"{A}-{B}", [11], None)
    assert len(body.geometry.coordinates) == 3  # the whole bend, junction to junction
    report(reports, "r1", "1.1.1.1")
    assert client.get("/reports/segment", params={"lat": 49.14045, "lon": 9.2101}).json()["properties"]["status"] == "reported"
    assert client.get("/reports/segment", params={"lat": 49.15, "lon": 9.25}).status_code == 400


def test_report_a_closure_on_a_picked_segment(client):
    for segment in (f"{A}-{C}", f"{C}-{A}"):  # either order of the junctions
        r = client.post("/reports/closures", json={"segment": segment, "reporter_id": segment})
        assert r.status_code == 201
        assert r.json()["properties"]["segment"] == f"{A}-{C}"
    assert r.json()["properties"]["status"] == "reported"  # one network: the second report doesn't count again


def test_a_closure_needs_a_segment_or_a_point(client):
    assert client.post("/reports/closures", json={"segment": f"{A}-99"}).status_code == 400  # not a street
    assert client.post("/reports/closures", json={"segment": "Allee"}).status_code == 422
    assert client.post("/reports/closures", json={"lat": 49.14}).status_code == 422
    assert client.post("/reports/closures", json={}).status_code == 422


def test_a_closure_far_from_every_street_is_refused(client):
    assert client.post("/reports/closures", json={"lat": 49.15, "lon": 9.25}).status_code == 400


def test_report_a_closure_until_a_date(client, clock):
    until = (today(clock) + timedelta(days=5)).isoformat()
    r = client.post("/reports/closures", json={"lat": 49.14045, "lon": 9.2101, "until": until})
    assert r.status_code == 201
    assert r.json()["properties"]["expires"][:10] == until
    past = (today(clock) - timedelta(days=1)).isoformat()
    assert client.post("/reports/closures", json={"lat": 49.14045, "lon": 9.2101, "until": past}).status_code == 400


def test_answer_still_closed_or_open(client, reports):
    report(reports, "r1", "1.1.1.1")
    r = client.post(f"/reports/closures/{A}-{B}/confirm", json={"still_closed": True, "reporter_id": "r2"})
    assert r.status_code == 200
    assert ClosureFeature.model_validate(r.json()).properties.reports == 2
    r = client.post(f"/reports/closures/{A}-{B}/confirm", json={"still_closed": False, "reporter_id": "r3"})
    assert r.json()["properties"]["open_reports"] == 1


def test_answering_on_a_street_without_a_closure_is_404(client):
    assert client.post(f"/reports/closures/{A}-{C}/confirm", json={"still_closed": True}).status_code == 404
    assert client.post("/reports/closures/nonsense/confirm", json={"still_closed": True}).status_code == 404


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


def test_pick_the_left_out_footway_near_a_click(client):
    r = client.get("/reports/footway", params={"lat": 49.1404, "lon": 9.21105})
    assert r.status_code == 200
    assert FootwayFeature.model_validate(r.json()).properties.osm_way_id == 77
    assert client.get("/reports/footway", params={"lat": 49.1404, "lon": 9.2200}).status_code == 404


def test_footways_left_out_of_routing_are_kept_per_way():
    G = nx.MultiDiGraph(crs="epsg:4326")
    for n, (x, y) in {1: (9.2100, 49.1400), 2: (9.2100, 49.1404), 3: (9.2100, 49.1409), 4: (9.2105, 49.1404)}.items():
        G.add_node(n, x=x, y=y)
    G.add_edge(1, 2, osmid=11, highway="residential", length=45.0)
    # Footway 21 in two pieces, both directions, no bicycle tag: left out, kept as one way.
    for u, v in ((2, 3), (3, 2)):
        G.add_edge(u, v, osmid=21, highway="footway", length=55.0)
    G.add_edge(3, 4, osmid=21, highway="footway", length=60.0)
    G.add_edge(2, 4, osmid=22, highway="footway", bicycle="no", length=40.0)  # bikes may not: not reportable
    removed = keep_rideable_footways(G)
    assert set(G.edges()) == {(1, 2)}
    assert [(f["properties"]["osm_way_id"], len(f["geometry"]["coordinates"]), f["properties"]["length_m"])
            for f in removed["features"]] == [(21, 2, 115.0)]
    assert footway_collection(G, []) == {"type": "FeatureCollection", "features": []}
