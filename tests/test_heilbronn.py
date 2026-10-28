"""End-to-end on the real Heilbronn graph. Skipped until cache/heilbronn_bike_rideable.graphml exists
(start the API once, or run `python -c "from routing.graph import load_graph; load_graph()"`)."""
import json

import networkx as nx
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.schemas import EXAMPLE_TRIP, RouteComparison
from routing.costs import osm_way_ids
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


def test_prefer_time_gives_a_faster_route(client):
    zero = {"bump_penalty": 0, "danger_penalty": 0, "pm_penalty": 0, "stop_penalty": 0}
    c = client.get("/route/compare", params={**TRIP, **zero, "prefer_time": "true"}).json()
    assert c["route"]["properties"]["duration_s"] < c["shortest"]["properties"]["duration_s"] * 0.95
    assert c["extra_time_pct"] < -5 < 0 < c["detour_pct"]


def test_speed_overlay_gives_measured_streets(client):
    features = client.get("/speed").json()["features"]
    assert len(features) > 7000
    assert all(f["geometry"]["type"] == "LineString" and f["properties"]["speed_kmh"] >= 0 for f in features)


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


def test_roads_with_a_mandatory_bike_path_are_left_out(client):
    """The Europaplatz roundabout and B 39 Mannheimer Straße are tagged bicycle=use_sidepath in OSM."""
    europaplatz_and_b39 = {142234373, 387411678, 387411679, 142234381, 148821228, 165419181}
    G = client.app.state.graph
    assert not any(europaplatz_and_b39 & set(osm_way_ids(d["osmid"])) for *_, d in G.edges(data=True))


def test_bike_paths_and_bridges_are_in_the_graph(client):
    """Rosenbergbrücke cycleway, Campusbrücke, a campus footway with bicycle=yes, the BUGA-Brücke and a signalised crossing tagged bicycle=no."""
    G = client.app.state.graph
    in_graph = {w for *_, d in G.edges(data=True) for w in osm_way_ids(d["osmid"])}
    assert {33498928, 443802903, 739824168, 795115713, 1413078438} <= in_graph


def test_route_from_bahnhofstrasse_crosses_at_the_start_to_reach_the_buga_bruecke(client):
    """Crossing 1413078438 and path 694954948 lead to the BUGA-Brücke, so the route needs no detour via Olgastraße."""
    r = client.get("/route", params={"from_lat": 49.142288810975934, "from_lon": 9.207969903945925,
                                     "to_lat": 49.1475, "to_lon": 9.2105}).json()
    assert r["features"][0]["properties"]["length_m"] < 1000


def test_route_can_end_on_a_one_way_street(client):
    """The snapped end point splits only the direction a one-way street has."""
    G = client.app.state.graph
    main = max(nx.strongly_connected_components(G), key=len)
    u, v, d = next((u, v, d) for u, v, d in G.edges(data=True) if u in main and v in main
                   and d.get("oneway") in (True, "True") and not G.has_edge(v, u) and "geometry" in d)
    lon, lat = d["geometry"].interpolate(0.5, normalized=True).coords[0]
    n_edges = G.number_of_edges()
    r = client.get("/route", params={"from_lat": 49.14838, "from_lon": 9.22687, "to_lat": lat, "to_lon": lon})
    assert r.status_code == 200
    assert G.number_of_edges() == n_edges


def test_hand_picked_footways_are_in_the_graph(client):
    """Footways without a bicycle tag that routing/rideable_ways.py lists, e.g. the Allee footway."""
    from routing.rideable_ways import RIDEABLE_WAYS
    G = client.app.state.graph
    in_graph = {w for *_, d in G.edges(data=True) for w in osm_way_ids(d["osmid"])}
    assert set(RIDEABLE_WAYS) <= in_graph


def test_route_from_next_to_a_cut_off_service_road_snaps_to_the_main_network(client):
    """Way 130334034 is an island (its only link, path 33921308, is not rideable): the start snaps past it."""
    r = client.get("/route", params={"from_lat": 49.13584495682357, "from_lon": 9.204933623254533,
                                     "to_lat": 49.14384658453482, "to_lon": 9.220619201660158})
    assert r.status_code == 200
