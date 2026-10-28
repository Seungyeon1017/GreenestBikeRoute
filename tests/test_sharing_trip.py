import networkx as nx
import pytest

from routing.route import RouteError
from routing.sharing_trip import WALK_MAX_M, WalkNetwork, plan_sharing_trip
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


def bike(vid, lat, lon, kind="bike", range_m=20000.0):
    return point(lat, lon, vehicle=kind, vehicle_id=vid, battery_pct=50, range_m=range_m, provider="Dott")


ZONE_AT_B = point(*COORDS[B], name="Zone B", bikes_available=1, scooters_available=0)


def test_walks_to_the_nearest_vehicle_and_rides_to_the_zone(toy_graph, walk):
    vehicles = [bike("far", COORDS[B][0] - 0.0002, COORDS[B][1]), bike("near", *COORDS[A])]
    trip = plan_sharing_trip(toy_graph, walk, vehicles, [ZONE_AT_B], COORDS[A], COORDS[B], ZERO)
    assert trip["vehicle"]["properties"]["vehicle_id"] == "near"
    assert trip["zone"]["properties"]["name"] == "Zone B"
    assert [leg["properties"]["mode"] for leg in trip["legs"]] == ["walk", "bike", "walk"]
    assert trip["ride_m"] == 100
    assert trip["walk_m"] == pytest.approx(0, abs=1)
    assert trip["duration_s"] == sum(leg["properties"]["duration_s"] for leg in trip["legs"])


def test_walk_follows_the_walking_network(toy_graph, walk):
    mid = ((COORDS[A][0] + COORDS[B][0]) / 2, COORDS[A][1])
    trip = plan_sharing_trip(toy_graph, walk, [bike("mid", *mid)], [], COORDS[A], COORDS[B], ZERO)
    first = trip["legs"][0]
    assert first["properties"]["length_m"] == pytest.approx(50, rel=0.02)
    assert [mid[1], mid[0]] == first["geometry"]["coordinates"][-1]
    assert trip["zone"] is None  # no zone: the ride ends at the destination


def test_vehicle_with_too_little_range_is_skipped(toy_graph, walk):
    vehicles = [bike("empty", *COORDS[A], range_m=500.0), bike("full", COORDS[A][0] + 0.0001, COORDS[A][1])]
    trip = plan_sharing_trip(toy_graph, walk, vehicles, [], COORDS[A], COORDS[B], ZERO)
    assert trip["vehicle"]["properties"]["vehicle_id"] == "full"


def test_only_the_requested_kind_and_only_within_walking_reach(toy_graph, walk):
    vehicles = [bike("b", *COORDS[A]), bike("s", *COORDS[A], kind="scooter")]
    trip = plan_sharing_trip(toy_graph, walk, vehicles, [], COORDS[A], COORDS[B], ZERO, vehicle="scooter")
    assert (trip["vehicle"]["properties"]["vehicle_id"], trip["legs"][1]["properties"]["mode"]) == ("s", "scooter")
    off_network = bike("off", COORDS[A][0] - 0.01, COORDS[A][1])  # ~1.1 km south, beyond WALK_MAX_M
    assert WALK_MAX_M < 1100
    with pytest.raises(RouteError, match="no free e-bike"):
        plan_sharing_trip(toy_graph, walk, [off_network], [], COORDS[A], COORDS[B], ZERO, vehicle="bike")
