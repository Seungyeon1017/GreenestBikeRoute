import pytest
import requests
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.geocoding import MIN_INTERVAL_S, Geocoder, GeocodingUnavailable, SearchDropped, street_places
from backend.schemas import PlaceCollection


def place(name, lat, lon, category="amenity", kind="townhall"):
    return {"lat": str(lat), "lon": str(lon), "name": name, "category": category, "type": kind,
            "display_name": f"{name}, Marktplatz, Kernstadt, Heilbronn, Baden-Württemberg, 74072, Deutschland"}


RESULTS = {"rathaus": [place("Rathaus Heilbronn", 49.142788, 9.21839), place("Altes Rathaus", 49.168545, 9.201597),
                       place("Rathaus Flein", 49.100412, 9.213636)],
           "allee 40": [place("", 49.14367, 9.223382, "building", "yes")],
           "kaiserstraße": [place("Kaiserstraße", 49.1428, 9.2160, "highway", "pedestrian"),
                            place("Kaiserstraße", 49.1430, 9.2200, "highway", "pedestrian"),
                            place("Kaiserstraße", 49.1431, 9.2210, "highway", "secondary")]}


class FakeNominatim:
    """Answers from RESULTS and keeps every query it was sent; `down` makes it fail like a timeout."""

    def __init__(self):
        self.queries, self.down = [], False

    def __call__(self, q):
        self.queries.append(q)
        if self.down:
            raise requests.ConnectionError("down")
        return RESULTS.get(q.lower(), [])


class FakeClock:
    def __init__(self):
        self.now, self.slept = 100.0, []

    def __call__(self):
        return self.now

    def sleep(self, s):
        self.slept.append(s)
        self.now += s


@pytest.fixture
def nominatim():
    return FakeNominatim()


@pytest.fixture
def client(toy_graph, nominatim):
    with TestClient(create_app(graph=toy_graph, geocoder=Geocoder(fetch=nominatim, sleep=lambda s: None))) as c:
        yield c


def test_geocode_returns_candidates_best_first(client):
    r = client.get("/geocode", params={"q": "Rathaus"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/geo+json"
    body = PlaceCollection.model_validate(r.json())
    assert [f.properties.name for f in body.features] == ["Rathaus Heilbronn", "Altes Rathaus", "Rathaus Flein"]
    assert body.features[0].geometry.coordinates == (9.21839, 49.142788)
    assert body.features[0].properties.label.startswith("Rathaus Heilbronn, Marktplatz")


def test_geocode_limit(client):
    assert len(client.get("/geocode", params={"q": "Rathaus", "limit": 2}).json()["features"]) == 2


def test_address_without_a_name_has_null_name(client):
    assert client.get("/geocode", params={"q": "Allee 40"}).json()["features"][0]["properties"]["name"] is None


def test_pieces_of_one_street_are_one_candidate(client):
    features = client.get("/geocode", params={"q": "Kaiserstraße"}).json()["features"]
    assert [f["geometry"]["coordinates"] for f in features] == [[9.216, 49.1428]]


def test_no_match_is_an_empty_list(client):
    r = client.get("/geocode", params={"q": "Nirgendwo"})
    assert r.status_code == 200
    assert r.json()["features"] == []


@pytest.mark.parametrize("q", ["ab", "  a  ", ""])
def test_short_search_is_invalid(client, q):
    assert client.get("/geocode", params={"q": q}).status_code == 422


def test_bad_limit_is_invalid(client):
    assert client.get("/geocode", params={"q": "Rathaus", "limit": 11}).status_code == 422


def test_nominatim_down_is_503(client, nominatim):
    nominatim.down = True
    r = client.get("/geocode", params={"q": "Rathaus"})
    assert r.status_code == 503
    assert "try again later" in r.json()["detail"]


def test_same_search_is_cached_whatever_the_case_spaces_or_limit(client, nominatim):
    for q, limit in (("Rathaus", 5), ("  rathaus ", 2), ("RATHAUS", 10)):
        assert client.get("/geocode", params={"q": q, "limit": limit}).status_code == 200
    assert nominatim.queries == ["Rathaus"]  # sent as typed, extra spaces dropped


def test_failed_search_is_not_cached(nominatim):
    geocoder = Geocoder(fetch=nominatim, sleep=lambda s: None)
    nominatim.down = True
    with pytest.raises(GeocodingUnavailable):
        geocoder.collection("Rathaus")
    nominatim.down = False
    assert len(geocoder.collection("Rathaus")["features"]) == 3


def test_searches_are_at_least_a_second_apart(nominatim):
    clock = FakeClock()
    geocoder = Geocoder(fetch=nominatim, clock=clock, sleep=clock.sleep)
    geocoder.collection("Rathaus")
    clock.now += 0.25
    geocoder.collection("Allee 40")
    clock.now += 5
    geocoder.collection("Kaiserstraße")
    assert clock.slept == [pytest.approx(MIN_INTERVAL_S - 0.25), 0.0]


def test_search_nobody_waits_for_is_not_sent(nominatim):
    clock = FakeClock()
    geocoder = Geocoder(fetch=nominatim, clock=clock, sleep=clock.sleep)
    with pytest.raises(SearchDropped):
        geocoder.collection("Ratha", gone=lambda: True)
    assert nominatim.queries == [] and clock.slept == []  # and the next search doesn't wait for it
    geocoder.collection("Rathaus")
    assert nominatim.queries == ["Rathaus"] and clock.slept == []
    assert geocoder.collection("Rathaus", gone=lambda: True)["features"]  # cached: no need to drop it


def test_search_dropped_while_waiting_for_its_turn(nominatim):
    clock = FakeClock()
    geocoder = Geocoder(fetch=nominatim, clock=clock, sleep=clock.sleep)
    geocoder.collection("Rathaus")
    with pytest.raises(SearchDropped):  # the rider typed on during the second between searches
        geocoder.collection("Allee", gone=lambda: bool(clock.slept))
    assert nominatim.queries == ["Rathaus"]


def test_geocode_is_documented(client):
    spec = client.get("/openapi.json").json()
    get = spec["paths"]["/geocode"]["get"]
    assert get["tags"] == ["Places"]
    assert get["responses"]["200"]["content"]["application/geo+json"]["schema"] == {"$ref": "#/components/schemas/PlaceCollection"}
    assert "503" in get["responses"]


def suggested(collection):
    return [f["properties"]["name"] for f in collection["features"]]


def test_street_names_of_the_graph_complete_what_is_typed(toy_graph):
    toy_graph.edges[1, 2, 0]["name"] = "Weststraße"
    toy_graph.edges[1, 3, 0]["name"] = ["Weststraße", "Südstraße"]  # an edge merged from two ways
    toy_graph.edges[3, 2, 0]["name"] = "Am Westfriedhof"
    streets = street_places(toy_graph)
    geocoder = Geocoder(fetch=lambda q: [])
    # A name starting with it first, then one with a word starting with it; umlauts and case don't matter.
    assert suggested(geocoder.suggest("wEst", streets)) == ["Weststraße", "Am Westfriedhof"]
    assert suggested(geocoder.suggest("sudstr", streets)) == ["Südstraße"]
    assert suggested(geocoder.suggest("straße", streets)) == []  # not the middle of a word
    street = geocoder.suggest("wests", streets)["features"][0]
    assert street["properties"] == {"label": "Weststraße", "name": "Weststraße", "category": "highway",
                                    "type": "street", "local": True}
    lon, lat = street["geometry"]["coordinates"]
    assert 9.2100 <= lon <= 9.2108 and 49.1400 <= lat <= 49.1409  # one point, on the street


def test_a_street_name_used_twice_far_apart_is_suggested_once(toy_graph):
    toy_graph.add_node(8, y=49.2000, x=9.3000)
    toy_graph.add_node(9, y=49.2001, x=9.3000)
    toy_graph.add_edge(8, 9, osmid=99, length=10.0, name="Hauptstraße")
    toy_graph.edges[1, 2, 0]["name"] = "Hauptstraße"  # 100 m: the longer one
    (name, feature), = street_places(toy_graph)
    assert name == "hauptstrasse"
    assert feature["geometry"]["coordinates"][0] < 9.25


def test_places_found_before_are_suggested_and_kept_across_restarts(tmp_path, nominatim):
    path = tmp_path / "geocode.json"
    geocoder = Geocoder(fetch=nominatim, sleep=lambda s: None, cache_path=path)
    assert suggested(geocoder.suggest("rath")) == []
    geocoder.collection("Rathaus")
    assert suggested(geocoder.suggest("rath")) == ["Rathaus Flein", "Rathaus Heilbronn", "Altes Rathaus"]
    assert suggested(geocoder.suggest("altes")) == ["Altes Rathaus"]
    # A new server reads the file: the search is answered without Nominatim, the names are still known.
    again = Geocoder(fetch=nominatim, sleep=lambda s: None, cache_path=path)
    assert [f["properties"]["name"] for f in again.collection("rathaus")["features"]][0] == "Rathaus Heilbronn"
    assert nominatim.queries == ["Rathaus"] and suggested(again.suggest("flein", limit=1)) == ["Rathaus Flein"]
    assert suggested(again.suggest("rathaus f")) == ["Rathaus Flein"]


def test_api_suggest(client, toy_graph):
    toy_graph.edges[1, 2, 0]["name"] = "Weststraße"
    r = client.get("/geocode/suggest", params={"q": "Wests"})
    assert r.status_code == 200 and r.headers["content-type"] == "application/geo+json"
    assert suggested(PlaceCollection.model_validate(r.json()).model_dump()) == ["Weststraße"]
    assert r.json()["features"][0]["properties"]["local"] is True
    assert client.get("/geocode/suggest", params={"q": "W"}).status_code == 422
