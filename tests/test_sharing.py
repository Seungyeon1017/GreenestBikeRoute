import networkx as nx
import pytest
import requests
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.schemas import GeofencingCollection, SharingTrip, VehicleCollection, ZoneCollection
from backend.sharing import CACHE_S, STALE_S, Sharing, SharingUnavailable, distance_m, main
from tests.conftest import COORDS, A, B

MARKT = (49.1427, 9.2109)  # Heilbronn Marktplatz (lat, lon)


def vehicle(vid, lat, lon, type_id="bike", **extra):
    return {"vehicle_id": vid, "lat": lat, "lon": lon, "is_reserved": False, "is_disabled": False,
            "vehicle_type_id": type_id, "current_fuel_percent": 0.5, "current_range_meters": 20000.0,
            "pricing_plan_id": "plan", "rental_uris": {"android": f"https://example.org/{vid}"}, **extra}


FEEDS = {
    "system_information": {"data": {"operator": [{"text": "Dott", "language": "en"}]}},
    "vehicle_types": {"data": {"vehicle_types": [
        {"vehicle_type_id": "bike", "form_factor": "bicycle", "propulsion_type": "electric_assist"},
        {"vehicle_type_id": "scooter", "form_factor": "scooter_standing", "propulsion_type": "electric"},
        {"vehicle_type_id": "car", "form_factor": "car", "propulsion_type": "electric"}]}},
    "system_pricing_plans": {"data": {"plans": [
        {"plan_id": "plan", "currency": "EUR", "price": 1.0, "per_min_pricing": [{"start": 1, "rate": 0.44, "interval": 1}]}]}},
    "vehicle_status": {"data": {"vehicles": [
        vehicle("near", 49.1430, 9.2110),                        # ~35 m from the Marktplatz
        vehicle("far", 49.1500, 9.2200),                         # ~1 km away
        vehicle("scooter", 49.1428, 9.2109, type_id="scooter"),
        vehicle("car", 49.1428, 9.2109, type_id="car"),          # not shared here, left out
        vehicle("taken", 49.1428, 9.2109, is_reserved=True),
        vehicle("broken", 49.1428, 9.2109, is_disabled=True),
        vehicle("stuttgart", 48.7758, 9.1829),                   # outside Heilbronn
    ]}},
    "station_information": {"data": {"stations": [
        {"station_id": "z1", "name": [{"text": "Parking Zone HBF", "language": "en"}], "lat": 49.1420, "lon": 9.2070,
         "vehicle_types_capacity": [{"vehicle_type_ids": ["bike"], "count": 5}, {"vehicle_type_ids": ["scooter"], "count": 5}]}]}},
    "geofencing_zones": {"data": {"geofencing_zones": {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"rules": [  # no e-scooters parked here, e-bikes only at a parking zone
            {"vehicle_type_ids": ["scooter"], "ride_end_allowed": False, "station_parking": False},
            {"vehicle_type_ids": ["bike"], "ride_end_allowed": False, "station_parking": True}]},
         "geometry": {"type": "Polygon", "coordinates": [[[9.21, 49.142], [9.212, 49.142], [9.212, 49.144], [9.21, 49.142]]]}},
        {"type": "Feature", "properties": {"name": [{"text": "Heilbronn", "language": "en"}], "rules": [
            {"vehicle_type_ids": ["bike", "scooter"], "ride_end_allowed": True, "station_parking": False}]},
         "geometry": {"type": "Polygon", "coordinates": [[[9.1, 49.1], [9.3, 49.1], [9.3, 49.2], [9.1, 49.1]]]}}]}}},
    "station_status": {"data": {"stations": [
        {"station_id": "z1", "vehicle_types_available": [{"vehicle_type_id": "bike", "count": 3},
                                                         {"vehicle_type_id": "scooter", "count": 7}]}]}},
}


class FakeFeed:
    """GBFS feeds from FEEDS; counts calls and can be switched off."""

    def __init__(self):
        self.calls, self.down = 0, False

    def __call__(self, system, feed):
        self.calls += 1
        if self.down:
            raise requests.ConnectionError("feed down")
        return FEEDS[feed]


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_only_free_bikes_and_scooters_in_heilbronn_are_listed():
    vehicles = Sharing(fetch=FakeFeed()).collection("vehicles")["features"]
    assert sorted((f["properties"]["vehicle_id"], f["properties"]["vehicle"]) for f in vehicles) == [
        ("far", "bike"), ("near", "bike"), ("scooter", "scooter")]
    p = next(f["properties"] for f in vehicles if f["properties"]["vehicle_id"] == "near")
    assert (p["provider"], p["electric"], p["battery_pct"], p["range_m"]) == ("Dott", True, 50, 20000.0)
    assert p["price"] == "€1.00 to unlock + €0.44/min"
    assert p["rent_url"].startswith("https://example.org/")


@pytest.mark.parametrize("vehicle, want", [("bike", ["far", "near"]), ("scooter", ["scooter"])])
def test_filter_by_vehicle(vehicle, want):
    fc = Sharing(fetch=FakeFeed()).collection("vehicles", vehicle=vehicle)
    assert sorted(f["properties"]["vehicle_id"] for f in fc["features"]) == want


def test_zones_count_bikes_and_scooters_apart():
    (zone,) = Sharing(fetch=FakeFeed()).collection("zones")["features"]
    assert zone["properties"] == {"provider": "Dott", "name": "Parking Zone HBF", "bikes_available": 3,
                                  "scooters_available": 7, "bike_capacity": 5, "scooter_capacity": 5}


def test_near_sorts_by_distance_and_limits():
    fc = Sharing(fetch=FakeFeed()).collection("vehicles", near=MARKT, limit=1, vehicle="bike")
    (f,) = fc["features"]
    assert f["properties"]["vehicle_id"] == "near" and 20 < f["properties"]["distance_m"] < 50


def test_distance():
    assert distance_m(49.0, 9.0, 49.01, 9.0) == pytest.approx(1112, abs=2)  # 0.01 deg of latitude


def test_snapshot_is_cached_then_refetched():
    feed, clock = FakeFeed(), Clock()
    bs = Sharing(fetch=feed, clock=clock)
    bs.collection("vehicles")
    calls = feed.calls
    clock.t = CACHE_S - 1
    bs.collection("zones")
    assert feed.calls == calls  # same snapshot
    clock.t = CACHE_S + 1
    bs.collection("vehicles")
    assert feed.calls > calls


def test_feed_down_serves_the_last_snapshot_for_a_while():
    feed, clock = FakeFeed(), Clock()
    bs = Sharing(fetch=feed, clock=clock)
    first = bs.collection("vehicles")
    feed.down = True
    clock.t = CACHE_S + 1
    assert bs.collection("vehicles") == first
    clock.t = STALE_S + 1
    with pytest.raises(SharingUnavailable):
        bs.collection("vehicles")


@pytest.fixture
def saved(tmp_path):
    """The geofencing file from `python -m backend.sharing`, made from FEEDS."""
    path = tmp_path / "geofencing.json"
    main(["--out", str(path)], fetch=FakeFeed())
    return path


def test_saved_file_has_the_geofencing_zones_in_feed_order(saved):
    zones = Sharing(fetch=FakeFeed(), saved=saved).collection("geofencing")["features"]
    assert [(f["properties"]["order"], f["properties"]["bike"], f["properties"]["scooter"], f["properties"]["name"])
            for f in zones] == [(0, "parking_zone", "no", None), (1, "anywhere", "anywhere", "Heilbronn")]


def test_without_a_saved_file_there_are_no_geofencing_zones():
    assert Sharing(fetch=FakeFeed(), saved=None).snapshot()["geofencing"] is None


# ------------------------------------------------------------- API --------

@pytest.fixture
def feed():
    return FakeFeed()


@pytest.fixture
def client(toy_graph, feed, saved):
    with TestClient(create_app(graph=toy_graph, sharing=Sharing(fetch=feed, saved=saved), walk_graph=walk_graph())) as c:
        yield c


def walk_graph():
    """A walking street from the toy graph's A to B, both ways."""
    G = nx.MultiDiGraph(crs="epsg:4326")
    for n, (lat, lon) in {"wa": COORDS[A], "wb": COORDS[B]}.items():
        G.add_node(n, y=lat, x=lon)
    G.add_edge("wa", "wb", length=100.0)
    G.add_edge("wb", "wa", length=100.0)
    return G


def test_sharing_endpoint(client):
    r = client.get("/sharing")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/geo+json"
    body = VehicleCollection.model_validate(r.json())
    assert len(body.features) == 3 and "MobiData BW" in body.attribution
    assert [f["properties"]["vehicle"] for f in client.get("/sharing", params={"vehicle": "scooter"}).json()["features"]] == ["scooter"]
    assert client.get("/sharing", params={"vehicle": "car"}).status_code == 422


def test_sharing_near_the_start(client):
    r = client.get("/sharing", params={"near_lat": MARKT[0], "near_lon": MARKT[1], "limit": 2}).json()
    assert [f["properties"]["vehicle_id"] for f in r["features"]] == ["scooter", "near"]  # scooter ~10 m, bike ~35 m
    assert client.get("/sharing", params={"near_lat": MARKT[0]}).status_code == 422  # lon missing
    assert client.get("/sharing", params={"limit": 0}).status_code == 422


def test_zones_endpoint(client):
    body = ZoneCollection.model_validate(client.get("/sharing/zones").json())
    p = body.features[0].properties
    assert (p.bikes_available, p.scooters_available) == (3, 7)


def test_feed_down_is_503(client, feed):
    feed.down = True
    r = client.get("/sharing")
    assert r.status_code == 503 and "unavailable" in r.json()["detail"]


def test_sharing_is_documented_under_its_own_tag(client):
    spec = client.get("/openapi.json").json()
    assert spec["paths"]["/sharing"]["get"]["tags"] == ["Sharing"]
    assert spec["paths"]["/sharing/zones"]["get"]["tags"] == ["Sharing"]


def trip_params(start=COORDS[A], **extra):
    return {"from_lat": start[0], "from_lon": start[1], "to_lat": COORDS[B][0], "to_lon": COORDS[B][1], **extra}


def test_sharing_trip(client, feed, monkeypatch):
    # The toy graph is ~600 m from the fake feed's vehicles: put a bike and a scooter at the start.
    monkeypatch.setitem(FEEDS, "vehicle_status", {"data": {"vehicles": [
        vehicle("bike-at-a", *COORDS[A]), vehicle("scooter-at-a", *COORDS[A], type_id="scooter")]}})
    r = client.get("/route/sharing", params=trip_params(vehicle="bike"))
    assert r.status_code == 200, r.text
    trip = SharingTrip.model_validate(r.json())
    assert trip.vehicle.properties.vehicle_id == "bike-at-a"
    assert [leg.properties.mode for leg in trip.legs] == ["walk", "bike", "walk"]
    assert r.json()["attribution"].startswith("MobiData BW")
    assert client.get("/route/sharing", params=trip_params(vehicle="scooter")).json()["legs"][1]["properties"]["mode"] == "scooter"


def test_sharing_trip_without_a_vehicle_nearby_is_400(client, monkeypatch):
    monkeypatch.setitem(FEEDS, "vehicle_status", {"data": {"vehicles": [vehicle("far", 49.1600, 9.2100)]}})  # ~2 km north
    r = client.get("/route/sharing", params=trip_params())
    assert r.status_code == 400
    assert "no free e-bike or e-scooter" in r.json()["detail"]


def test_sharing_trip_with_the_feed_down_is_503(client, feed):
    feed.down = True
    assert client.get("/route/sharing", params=trip_params()).status_code == 503


def test_geofencing_endpoint(client):
    r = client.get("/sharing/geofencing")
    assert r.status_code == 200
    body = GeofencingCollection.model_validate(r.json())
    assert [f.properties.order for f in body.features] == [0, 1]
