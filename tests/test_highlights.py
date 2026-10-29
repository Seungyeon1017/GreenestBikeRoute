import networkx as nx
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.schemas import GreenStreetCollection
from routing.graph import attach_shade
from routing.highlights import MIN_RIDDEN_M, greenest_streets, ridden

# Four nodes on a line in Heilbronn, ~110 m apart; each street is one two-way edge.
NODES = {1: (49.1400, 9.2100), 2: (49.1410, 9.2100), 3: (49.1420, 9.2100), 4: (49.1430, 9.2100), 5: (49.1440, 9.2100)}


def street(G, u, v, osmid, name, **data):
    """A two-way street: one edge per direction, as OSMnx has them."""
    d = {"osmid": osmid, "name": name, "length": 200.0, "roughness_source": "unknown", "speed_kmh": None,
         "stop_go": None, "pm_rides": 0, "pm_prior": 0.5, "pm_risk": None, "trees": None, "bike_friendly": False, **data}
    G.add_edge(u, v, **d)
    G.add_edge(v, u, **d)


@pytest.fixture
def streets():
    G = nx.MultiDiGraph(crs="epsg:4326")
    for n, (lat, lon) in NODES.items():
        G.add_node(n, y=lat, x=lon)
    street(G, 1, 2, 21, "Allee", speed_kmh=16.0, trees=0.6, bike_friendly=True, pm_rides=4, pm_risk=0.46)
    street(G, 2, 3, 22, "Kaiserstraße", roughness_source="measured", trees=0.1, pm_rides=9, pm_risk=0.56)
    street(G, 3, 4, 23, "Parkweg", trees=0.9, bike_friendly=True)  # leafy, but no bike has ridden it
    street(G, 4, 5, 24, "Stummel", stop_go=0.5, length=MIN_RIDDEN_M - 1, trees=0.9)  # ridden, too little of it
    return G


def test_only_ridden_edges_count():
    assert ridden({"speed_kmh": 12.0})
    assert ridden({"roughness_source": "measured"})
    assert ridden({"pm_rides": 2})
    assert not ridden({"roughness_source": "estimated", "speed_kmh": None, "stop_go": None, "pm_rides": 0})


def test_ranks_ridden_streets_greenest_first(streets):
    ranked = greenest_streets(streets)
    names = [f["properties"]["name"] for f in ranked["features"]]
    assert names == ["Allee", "Kaiserstraße"]  # Parkweg was never ridden, Stummel is too short
    assert ranked["total"] == 2
    allee = ranked["features"][0]["properties"]
    assert allee["rank"] == 1 and allee["ridden_m"] == 200 and allee["air_rides"] == 4
    assert allee["tree_cover"] == 0.6 and allee["bike_friendly_share"] == 1.0
    assert allee["green_score"] > ranked["features"][1]["properties"]["green_score"]


def test_two_way_street_counts_once(streets):
    allee = greenest_streets(streets)["features"][0]
    assert len(allee["geometry"]["coordinates"]) == 1


def test_unmeasured_air_counts_at_its_prior(streets):
    streets.edges[1, 2, 0]["pm_risk"] = streets.edges[2, 1, 0]["pm_risk"] = None
    assert greenest_streets(streets)["features"][0]["properties"]["pm_risk"] == 0.5


def test_attach_shade_sets_tree_canopy(streets):
    attach_shade(streets, ["12:00"], {21: [0.3]}, {21: 0.7, 22: 0.2})
    assert streets.edges[1, 2, 0]["trees"] == 0.7
    assert streets.edges[3, 4, 0]["trees"] is None


def test_greenest_streets_endpoint(streets):
    with TestClient(create_app(graph=streets)) as c:
        r = c.get("/highlights/greenest-streets", params={"limit": 1})
    assert r.status_code == 200
    body = GreenStreetCollection.model_validate(r.json())
    assert body.total == 2 and [f.properties.name for f in body.features] == ["Allee"]
