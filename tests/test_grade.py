import io
import zipfile

import networkx as nx
import pytest

import routing.elevation as elevation
from routing.elevation import fix_structures, ground_heights, read_xyz, structure_nodes, tile_2km
from routing.grade import NoElevationError, edge_grade, route_grade, severity
from routing.route import find_route
from routing.shade import utm32_to_lonlat
from tests.conftest import COORDS, HEIGHTS, A, B, C, joined

def test_grade_is_rise_over_length_in_travel_direction(hilly):
    assert edge_grade(hilly, A, B, hilly.edges[A, B, 0]) == pytest.approx(3.0)
    assert edge_grade(hilly, C, B, hilly.edges[C, B, 0]) == pytest.approx(-2 / 70 * 100)


def test_two_way_street_is_uphill_one_way_and_downhill_the_other(hilly):
    hilly.add_edge(C, A, osmid=12, length=70.0, roughness=None)  # the other direction of A -> C
    up, down = edge_grade(hilly, A, C, hilly.edges[A, C, 0]), edge_grade(hilly, C, A, hilly.edges[C, A, 0])
    assert up == pytest.approx(5 / 70 * 100) and down == -up


@pytest.mark.parametrize("grade, name", [
    (0, "flat"), (1.99, "flat"), (-1.99, "flat"),
    (2, "gentle"), (-3.99, "gentle"),
    (4, "noticeable"), (5.99, "noticeable"),
    (-6, "steep"), (9.99, "steep"),
    (10, "very_steep"), (-25, "very_steep"),
])
def test_severity_classes(grade, name):
    assert severity(grade) == name


def test_route_grade_follows_the_route_in_pieces(hilly):
    fc = route_grade(hilly, COORDS[A], COORDS[B], bump_penalty=10)  # the smooth detour A -> C -> B
    pieces = [(f["properties"]["severity"], f["properties"]["grade_pct"], f["properties"]["start_m"]) for f in fc["features"]]
    assert pieces == [("steep", 7.1, 0), ("gentle", -2.9, 70)]
    assert fc["features"][0]["properties"]["color"] != fc["features"][1]["properties"]["color"]
    s = fc["summary"]
    assert (s["length_m"], s["climb_m"], s["descent_m"], s["max_grade_pct"], s["max_descent_grade_pct"]) == (140, 5, 2, 7.1, -2.9)
    assert s["length_by_severity_m"] == {"flat": 0, "gentle": 70, "noticeable": 0, "steep": 70, "very_steep": 0}


@pytest.mark.parametrize("bump_penalty", [0, 10])
def test_grade_pieces_join_up_to_the_route(hilly, bump_penalty):
    route = find_route(hilly, COORDS[A], COORDS[B], bump_penalty)["features"][0]["geometry"]["coordinates"]
    assert joined(route_grade(hilly, COORDS[A], COORDS[B], bump_penalty)["features"]) == route


def test_same_class_edges_merge_into_one_piece(hilly):
    hilly.nodes[C]["elevation"] = 151.0  # A -> C +1.4 %, C -> B +2.9 %: different classes
    assert len(route_grade(hilly, COORDS[A], COORDS[B], 10)["features"]) == 2
    hilly.nodes[C]["elevation"] = 151.6  # +2.3 % and +2.0 %: both gentle uphill -> one piece
    (piece,) = route_grade(hilly, COORDS[A], COORDS[B], 10)["features"]
    assert piece["properties"]["grade_pct"] == pytest.approx(300 / 140, abs=0.05)
    assert piece["geometry"]["coordinates"] == [[9.2100, 49.1400], [9.2108, 49.1404], [9.2100, 49.1409]]


def test_uphill_and_downhill_of_the_same_class_stay_apart(hilly):
    hilly.nodes[C]["elevation"] = 155.0
    hilly.nodes[B]["elevation"] = 150.0  # A -> C +7.1 %, C -> B -7.1 %
    assert [f["properties"]["grade_pct"] for f in route_grade(hilly, COORDS[A], COORDS[B], 10)["features"]] == [7.1, -7.1]


def test_grade_does_not_change_the_route(toy_graph):
    before = find_route(toy_graph, COORDS[A], COORDS[B])
    for n, h in {**HEIGHTS, C: 300.0}.items():  # a wall on the detour
        toy_graph.nodes[n]["elevation"] = h
    assert find_route(toy_graph, COORDS[A], COORDS[B]) == before


def test_start_in_the_middle_of_a_street_gets_an_interpolated_height(hilly):
    """The start splits A -> C (150 -> 155 m) halfway, so it is at 152.5 m; the graph is restored afterwards."""
    edges = hilly.number_of_edges()
    halfway = ((COORDS[A][0] + COORDS[C][0]) / 2, (COORDS[A][1] + COORDS[C][1]) / 2)
    fc = route_grade(hilly, halfway, COORDS[B], bump_penalty=10)
    assert fc["summary"]["start_elevation_m"] == 152.5
    assert fc["features"][0]["properties"]["rise_m"] == 2.5
    assert hilly.number_of_edges() == edges and "snap-start" not in hilly


def test_missing_elevation_is_reported(toy_graph):
    with pytest.raises(NoElevationError):
        route_grade(toy_graph, COORDS[A], COORDS[B])


# ------------------------------------------------------------ bridges -----

def bridge_graph():
    """Left bank L (160 m) -- bridge over the river via P1, P2 -- right bank R (166 m); the terrain under
    P1 and P2 is the river at 150 m. X and Y are normal streets on each bank."""
    G = nx.MultiDiGraph()
    L, P1, P2, R, X, Y = "L", "P1", "P2", "R", "X", "Y"
    for u, v, length, tags in [(X, L, 50, {}), (L, P1, 10, {"bridge": "yes"}), (P1, P2, 20, {"bridge": "yes"}),
                               (P2, R, 30, {"bridge": "yes"}), (R, Y, 50, {})]:
        G.add_edge(u, v, length=length, **tags)
        G.add_edge(v, u, length=length, **tags)
    return G, {X: 158.0, L: 160.0, P1: 150.0, P2: 150.0, R: 166.0, Y: 167.0}


def test_bridge_nodes_are_interpolated_between_the_abutments():
    G, heights = bridge_graph()
    assert structure_nodes(G) == {"P1", "P2"}
    fixed = fix_structures(G, heights)
    assert set(fixed) == {"P1", "P2"}
    # straight line from L (160 m) to R (166 m) over 60 m
    assert heights["P1"] == pytest.approx(161.0) and heights["P2"] == pytest.approx(163.0)
    assert (heights["L"], heights["R"]) == (160.0, 166.0)


def test_tunnel_nodes_are_interpolated_too():
    G, heights = bridge_graph()
    for _, _, d in G.edges(data=True):
        if d.pop("bridge", None):
            d["tunnel"] = "yes"
    heights["P1"] = heights["P2"] = 190.0  # the hill above the tunnel
    fix_structures(G, heights)
    assert heights["P1"] == pytest.approx(161.0)


def test_bridge_no_is_a_normal_street():
    G, heights = bridge_graph()
    for _, _, d in G.edges(data=True):
        if "bridge" in d:
            d["bridge"] = "no"
    assert structure_nodes(G) == set() and fix_structures(G, heights) == {}


# ------------------------------------------------------------ DGM1 files --

def test_tile_naming_matches_lgl():
    # south-west corner, odd east km, even north km
    assert tile_2km(515_000.5, 5_442_999.5) == (515, 5442)
    assert tile_2km(516_999.0, 5_443_999.0) == (515, 5442)
    assert tile_2km(514_200.0, 5_441_100.0) == (513, 5440)


def test_xyz_rows_run_north_to_south(monkeypatch, tmp_path):
    # A 2 x 2 m "tile" in the same layout as a 1000 x 1000 m DGM1 file.
    monkeypatch.setattr(elevation, "CELLS", 2)
    text = "515000.50 5442999.50 10\n515001.50 5442999.50 11\n515000.50 5442998.50 12\n515001.50 5442998.50 13\n"
    west, north, h = read_xyz(io.StringIO(text))
    assert (west, north) == (515000, 5443000) and h.tolist() == [[10, 11], [12, 13]]

    path = tmp_path / "dgm1_32_515_5442_2_bw.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("dgm1_32_515_5442_1_bw_2024.xyz", text)
    G = nx.MultiDiGraph()
    for n, (e, no) in {"nw": (515000.3, 5442999.8), "se": (515001.6, 5442998.2)}.items():
        lon, lat = utm32_to_lonlat(e, no)
        G.add_node(n, x=lon, y=lat)
    assert ground_heights(G, [path]) == {"nw": 10.0, "se": 13.0}
