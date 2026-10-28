import networkx as nx
import pytest

from routing.calories import walk_kcal
from routing.route import RouteError, find_route
from routing.sharing_trip import WALK_MAX_M, ParkingRules, WalkNetwork, plan_sharing_trip
from tests.conftest import COORDS, A, B

ZERO = (0, 0, 0, 0, False, 0, 0, 0, None)  # all penalties 0: the shortest ride


@pytest.fixture
def walk():
    """A straight walking street from A to B (100 m) with a corner in the middle, both ways."""
    G = nx.MultiDiGraph(crs="epsg:4326")
    mid = ((COORDS[A][0] + COORDS[B][0]) / 2, COORDS[A][1])
    for n, (lat, lon) in {"wa": COORDS[A], "wm": mid, "wb": COORDS[B]}.items():
        G.add_node(n, y=lat, x=lon)
    for u, v in (("wa", "wm"), ("wm", "wb")):
        G.add_edge(u, v, length=50.0)
        G.add_edge(v, u, length=50.0)
    return WalkNetwork(G)


def point(lat, lon, **props):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": props}


def bike(vid, lat, lon, kind="bike", range_m=20000.0, electric=True):
    return point(lat, lon, vehicle=kind, vehicle_id=vid, battery_pct=50, range_m=range_m, provider="Dott", electric=electric)


ZONE_AT_B = point(*COORDS[B], name="Zone B", bikes_available=1, scooters_available=0)


def box(south, west, north, east, order, **rules):
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"provider": "Dott", "name": None, "order": order, **rules}}


# Dott's whole area last: a ride may end anywhere in it.
AREA = box(49.13, 9.20, 49.15, 9.22, 9, bike="anywhere", scooter="anywhere")
# A no-parking zone around B (the destination), as Dott has around pedestrian zones.
NO_PARKING_AT_B = box(49.1407, 9.2095, 49.1411, 9.2105, 0, bike="no", scooter="no")


def test_parking_rules_take_the_first_zone_and_refuse_outside_all():
    rules = ParkingRules([NO_PARKING_AT_B, AREA])
    assert rules.rule("bike", *COORDS[B]) == "no"
    assert rules.rule("bike", *COORDS[A]) == "anywhere"
    assert rules.rule("bike", 48.7758, 9.1829) == "no"  # Stuttgart, outside Dott's area
    assert ParkingRules([box(49.1407, 9.2095, 49.1411, 9.2105, 0, scooter="no"), AREA]).rule("bike", *COORDS[B]) == "anywhere"


def test_ride_kcal_is_for_a_pedelec_and_only_pushing_on_a_scooter(toy_graph, walk):
    def kcal(vehicle, **kw):
        trip = plan_sharing_trip(toy_graph, walk, [vehicle], [], COORDS[A], COORDS[B], ZERO, geofencing=[AREA], **kw)
        return trip["legs"][1]["properties"]["kcal"]
    route = lambda **kw: find_route(toy_graph, COORDS[A], COORDS[B], *ZERO, **kw)["features"][0]["properties"]["kcal"]
    assert kcal(bike("e", *COORDS[A])) == route(e_bike=True) < route()
    assert kcal(bike("p", *COORDS[A], electric=False)) == route()
    assert kcal(bike("e", *COORDS[A]), weight_kg=90) == route(e_bike=True, weight_kg=90)
    assert kcal(bike("s", *COORDS[A], kind="scooter")) == 0  # rides round, pushes nowhere


def test_walks_count_and_add_up_to_the_trip_kcal(toy_graph, walk):
    mid = ((COORDS[A][0] + COORDS[B][0]) / 2, COORDS[A][1])
    trip = plan_sharing_trip(toy_graph, walk, [bike("mid", *mid)], [], COORDS[A], COORDS[B], ZERO, geofencing=[AREA])
    first, ride, last = (leg["properties"] for leg in trip["legs"])
    assert first["kcal"] == round(walk_kcal(first["duration_s"]), 1) > 0
    assert trip["kcal"] == round(first["kcal"] + ride["kcal"] + last["kcal"], 1)


def test_free_floating_ride_ends_at_the_destination(toy_graph, walk):
    trip = plan_sharing_trip(toy_graph, walk, [bike("near", *COORDS[A])], [ZONE_AT_B], COORDS[A], COORDS[B], ZERO,
                             geofencing=[AREA])
    assert trip["zone"] is None
    assert trip["return_point"]["properties"] == {"rule": "anywhere", "at_destination": True, "name": None}
    assert trip["legs"][2]["properties"]["length_m"] == 0


def test_ride_ends_outside_a_no_parking_zone_at_the_destination(toy_graph, walk):
    trip = plan_sharing_trip(toy_graph, walk, [bike("near", *COORDS[A])], [], COORDS[A], COORDS[B], ZERO,
                             geofencing=[NO_PARKING_AT_B, AREA])
    lon, lat = trip["return_point"]["geometry"]["coordinates"]
    assert ParkingRules([NO_PARKING_AT_B, AREA]).rule("bike", lat, lon) == "anywhere"
    assert not trip["return_point"]["properties"]["at_destination"]
    assert trip["legs"][2]["properties"]["length_m"] > 0  # walk on from where it was left


def test_park_in_zone_ends_at_a_parking_zone(toy_graph, walk):
    trip = plan_sharing_trip(toy_graph, walk, [bike("near", *COORDS[A])], [ZONE_AT_B], COORDS[A], COORDS[B], ZERO,
                             park_in_zone=True, geofencing=[AREA])
    assert trip["zone"]["properties"]["name"] == "Zone B"
    assert trip["return_point"]["properties"]["rule"] == "parking_zone"


def test_walks_to_the_nearest_vehicle_and_rides_to_the_zone_without_geofencing(toy_graph, walk):
    vehicles = [bike("far", COORDS[B][0] - 0.0002, COORDS[B][1]), bike("near", *COORDS[A])]
    trip = plan_sharing_trip(toy_graph, walk, vehicles, [ZONE_AT_B], COORDS[A], COORDS[B], ZERO)  # feed down: zones only
    assert trip["vehicle"]["properties"]["vehicle_id"] == "near"
    assert trip["zone"]["properties"]["name"] == "Zone B"
    assert [leg["properties"]["mode"] for leg in trip["legs"]] == ["walk", "bike", "walk"]
    assert trip["ride_m"] == 100
    assert trip["walk_m"] == pytest.approx(0, abs=1)
    assert trip["duration_s"] == sum(leg["properties"]["duration_s"] for leg in trip["legs"])


def test_walk_follows_the_walking_network(toy_graph, walk):
    mid = ((COORDS[A][0] + COORDS[B][0]) / 2, COORDS[A][1])
    trip = plan_sharing_trip(toy_graph, walk, [bike("mid", *mid)], [], COORDS[A], COORDS[B], ZERO, geofencing=[AREA])
    first = trip["legs"][0]
    assert first["properties"]["length_m"] == pytest.approx(50, rel=0.02)
    assert [mid[1], mid[0]] == first["geometry"]["coordinates"][-1]


def test_vehicle_with_too_little_range_is_skipped(toy_graph, walk):
    vehicles = [bike("empty", *COORDS[A], range_m=500.0), bike("full", COORDS[A][0] + 0.0001, COORDS[A][1])]
    trip = plan_sharing_trip(toy_graph, walk, vehicles, [], COORDS[A], COORDS[B], ZERO, geofencing=[AREA])
    assert trip["vehicle"]["properties"]["vehicle_id"] == "full"


def test_only_the_requested_kind_and_only_within_walking_reach(toy_graph, walk):
    vehicles = [bike("b", *COORDS[A]), bike("s", *COORDS[A], kind="scooter")]
    trip = plan_sharing_trip(toy_graph, walk, vehicles, [], COORDS[A], COORDS[B], ZERO, vehicle="scooter", geofencing=[AREA])
    assert (trip["vehicle"]["properties"]["vehicle_id"], trip["legs"][1]["properties"]["mode"]) == ("s", "scooter")
    off_network = bike("off", COORDS[A][0] - 0.01, COORDS[A][1])  # ~1.1 km south, beyond WALK_MAX_M
    assert WALK_MAX_M < 1100
    with pytest.raises(RouteError, match="no free e-bike"):
        plan_sharing_trip(toy_graph, walk, [off_network], [], COORDS[A], COORDS[B], ZERO, vehicle="bike", geofencing=[AREA])
    with pytest.raises(RouteError, match="may be left"):  # nowhere to park: all of it a no-parking zone
        plan_sharing_trip(toy_graph, walk, [bike("b", *COORDS[A])], [], COORDS[A], COORDS[B], ZERO,
                          geofencing=[box(49.13, 9.20, 49.15, 9.22, 0, bike="no")])
