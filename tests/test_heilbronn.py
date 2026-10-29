"""End-to-end on the real Heilbronn graph. Skipped until cache/heilbronn_bike_rideable.graphml exists
(start the API once, or run `python -c "from routing.graph import load_graph; load_graph()"`)."""
import json

import networkx as nx
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.schemas import EXAMPLE_TRIP, GradeCollection, RouteComparison, TourCollection
from routing.costs import osm_way_ids
from routing.elevation import OUT as ELEVATION_PATH
from routing.graph import GRAPH_PATH, load_graph
from tests.conftest import joined

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
    smooth = client.get("/route", params={**TRIP, **ONLY_BUMPS, "bump_penalty": 8}).json()["features"][0]
    assert smooth["properties"]["length_m"] > shortest["properties"]["length_m"]
    assert smooth["properties"]["mean_roughness"] < shortest["properties"]["mean_roughness"]


def test_hating_close_overtaking_passes_fewer_danger_spots(client):
    zero = {"bump_penalty": 0, "danger_penalty": 0, "pm_penalty": 0, "stop_penalty": 0}
    shortest = client.get("/route", params={**TRIP, **zero}).json()["features"][0]["properties"]
    safe = client.get("/route", params={**TRIP, **zero, "danger_penalty": 25}).json()["features"][0]["properties"]
    assert safe["danger_points"] < shortest["danger_points"] / 2
    assert safe["length_m"] < shortest["length_m"] * 1.05



# Raising one dislike once sent routes back towards the shortest route: stop-and-go is about the same on most streets,
# so it inflated every street alike, and a high prefer_bike_friendly drowned the other dislikes.
SLIDER_TRIPS = [TRIP, {"from_lat": 49.1428, "from_lon": 9.2188, "to_lat": 49.1206, "to_lon": 9.2050}]


@pytest.mark.parametrize("trip", SLIDER_TRIPS)
@pytest.mark.parametrize("penalty, metres", [("stop_penalty", "stop_go_m"), ("bump_penalty", "bumpy_m"),
                                             ("pm_penalty", "bad_air_m")])
def test_raising_a_dislike_rides_less_of_it_and_never_drifts_back_to_the_shortest_route(client, trip, penalty, metres):
    def compare(value):
        return client.get("/route/compare", params={**trip, penalty: value}).json()
    low, high = compare(0), compare(10)
    assert high["route"]["properties"][metres] <= low["route"]["properties"][metres]
    assert high["detour_pct"] >= low["detour_pct"]


@pytest.mark.parametrize("trip", SLIDER_TRIPS)
def test_preferring_bike_paths_keeps_the_route_smoother_than_the_shortest(client, trip):
    """Factors multiply: even at prefer_bike_friendly 10 the default dislike of bumps still steers the route."""
    c = client.get("/route/compare", params={**trip, "prefer_bike_friendly": 10}).json()
    assert c["route"]["properties"]["bike_friendly_m"] > c["shortest"]["properties"]["bike_friendly_m"]
    assert c["route"]["properties"]["bumpy_m"] < c["shortest"]["properties"]["bumpy_m"]

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
    smooth = client.get("/route", params={**trip, **zero, "stop_penalty": 4}).json()["features"][0]["properties"]
    assert smooth["stop_go_m"] < shortest["stop_go_m"] / 2
    assert smooth["length_m"] < shortest["length_m"] * 1.15


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
        real_props, example_props = dict(real[key]["properties"]), dict(example[key]["properties"])
        assert real_props.pop("segments")[:2] == example_props.pop("segments")
        assert real_props == example_props
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


def test_route_can_end_next_to_a_way_with_parallel_edges(client):
    """Way 32927311 has a 2 m stub parallel to its long edge; splitting the stub at the point made a 500."""
    r = client.get("/route/compare", params={"from_lat": 49.13980383591573, "from_lon": 9.208045005798342,
                                             "to_lat": 49.13531584034481, "to_lon": 9.202290567660226})
    assert r.status_code == 200


needs_elevation = pytest.mark.skipif(not ELEVATION_PATH.exists(), reason="no elevation file: run python -m routing.elevation")
ZERO = {"bump_penalty": 0, "danger_penalty": 0, "pm_penalty": 0, "stop_penalty": 0}


@needs_elevation
@pytest.mark.parametrize("trip, penalties", [
    (TRIP, {}), (TRIP, ZERO), (TRIP, {"danger_penalty": 100}),
    ({"from_lat": 49.16, "from_lon": 9.215, "to_lat": 49.135, "to_lon": 9.235}, {"stop_penalty": 10}),
    ({"from_lat": 49.1415, "from_lon": 9.205, "to_lat": 49.1405, "to_lon": 9.231}, {}),  # across the Neckar
])
def test_grade_route_is_exactly_the_route(client, trip, penalties):
    route = client.get("/route", params={**trip, **penalties}).json()["features"][0]
    grade = client.get("/route/grade", params={**trip, **penalties}).json()
    assert joined(grade["features"]) == route["geometry"]["coordinates"]
    assert grade["summary"]["length_m"] == route["properties"]["length_m"]


@needs_elevation
def test_grade_docs_example_is_a_real_response(client):
    """The /route/grade example in /docs is what the example trip returns (its first pieces and the summary)."""
    example = GradeCollection.model_config["json_schema_extra"]["example"]
    real = client.get("/route/grade", params=TRIP).json()
    assert real["summary"] == example["summary"]
    assert real["features"][:len(example["features"])] == example["features"]


@needs_elevation
def test_neckar_bridge_has_no_grade_spike(client):
    """Kaiserstraße crosses the Neckar on three bridge edges. The terrain model under the two middle nodes is
    about 4 m below the deck, which made a fake -11.3 %, -1.9 %, +8.8 % on the way east."""
    G = client.app.state.graph
    west, middle, east = G.nodes[392616596], G.nodes[393412335], G.nodes[817445456]
    assert min(west["elevation"], east["elevation"]) <= middle["elevation"] <= max(west["elevation"], east["elevation"])
    trip = {"from_lat": 49.1422, "from_lon": 9.2120, "to_lat": 49.1426, "to_lon": 9.2190}
    grade = client.get("/route/grade", params=trip).json()
    assert [middle["x"], middle["y"]] in joined(grade["features"])  # the route does cross the bridge
    assert grade["summary"]["max_grade_pct"] < 4 and grade["summary"]["max_descent_grade_pct"] > -4
    assert all(f["properties"]["severity"] in ("flat", "gentle") for f in grade["features"])


@needs_elevation
def test_humped_bridge_shows_its_climb(client):
    """Erwin-Fuchs-Brücke rises about 5 m above its abutments (data/custom/bridge_decks.json). Interpolated
    straight between them, its deck read -1.1 % and +1.8 % on the way east; now the route climbs onto it and
    down again, about 10 m in all with the ramp."""
    G = client.app.state.graph
    assert G.nodes[148083098]["elevation"] > max(G.nodes[21725964]["elevation"], G.nodes[21725975]["elevation"])
    trip = {"from_lat": 49.1330, "from_lon": 9.1925, "to_lat": 49.1330, "to_lon": 9.2060, **ZERO}
    grade = client.get("/route/grade", params=trip).json()
    assert [G.nodes[148083098]["x"], G.nodes[148083098]["y"]] in joined(grade["features"])  # it does cross the bridge
    pieces = [(f["properties"]["grade_pct"], f["properties"]["length_m"]) for f in grade["features"]]
    # onto the deck (at least 100 m over 3 %), then straight down from the crest
    assert any(g >= 3 and length >= 100 and after <= -2.5 for (g, length), (after, _) in zip(pieces, pieces[1:]))
    assert grade["summary"]["climb_m"] >= 9


def test_suggested_tours_keep_their_theme(client):
    """Each tour is routed stop to stop and does what its card says: the green one mostly under trees, the quiet loop
    and the riverside one almost all on bike paths, the nature one out east with a climb."""
    body = TourCollection.model_validate(client.get("/highlights/tours").json())
    tours = {f.properties.id: f.properties for f in body.features}
    assert tours["scenicGreen"].tree_share >= 0.45
    assert tours["quietEscape"].loop and tours["quietEscape"].bike_friendly_share >= 0.9
    assert tours["riverside"].bike_friendly_share >= 0.9 and "Neckarhalde" in tours["riverside"].streets
    assert tours["nature"].loop and "Kirschenallee" in tours["nature"].streets and tours["nature"].climb_m >= 100
    assert all(4000 < t.length_m < 8000 for t in tours.values())


def test_suggested_tours_are_simple_lines_through_their_stops(client):
    """No street ridden twice (no spurs or stems), and every stop is on the line, so the map shows one plain line."""
    for f in client.get("/highlights/tours").json()["features"]:
        line = [tuple(p) for p in f["geometry"]["coordinates"]]
        pieces = [frozenset(piece) for piece in zip(line, line[1:])]
        assert len(pieces) == len(set(pieces)), f["properties"]["id"]
        for stop in f["properties"]["stops"]:
            metres = min(((x - stop["lon"]) * 65600) ** 2 + ((y - stop["lat"]) * 111200) ** 2 for x, y in line) ** 0.5
            assert metres < 20, (f["properties"]["id"], stop["name"])
        assert (line[0] == line[-1]) == f["properties"]["loop"]
