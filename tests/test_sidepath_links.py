import networkx as nx
import pytest
from shapely import LineString

from routing.graph import drop_orphan_stubs, link_sidepaths

LAT = 49.14
M = 1 / 111_320  # about a metre of latitude, in degrees


def graph(*ways):
    """Ways (osmid, [(node, x metres, y metres), ...], tags, two_way) as a simplified MultiDiGraph: nodes at the ends,
    the points between them as geometry (their OSM node ids in the returned {(x, y): id})."""
    G, ids = nx.MultiDiGraph(crs="epsg:4326"), {}
    lon = lambda x: 9.21 + x * M / 0.6547  # cos(49.14°)
    for osmid, points, tags, two_way in ways:
        coords = [(lon(x), LAT + y * M) for _, x, y in points]
        ids.update({c: n for (n, *_), c in zip(points, coords)})
        for (n, *_), (x, y) in zip(points[::len(points) - 1], coords[::len(coords) - 1]):
            G.add_node(n, x=x, y=y)
        length = LineString([(x, y) for _, x, y in points]).length
        a, b = points[0][0], points[-1][0]
        G.add_edge(a, b, osmid=osmid, length=length, geometry=LineString(coords), **tags)
        if two_way:
            G.add_edge(b, a, osmid=osmid, length=length, geometry=LineString(coords[::-1]), **tags)
    return G, ids


ROAD = {"highway": "primary", "name": "Mannheimer Straße"}
PATH = {"highway": "cycleway", "bicycle": "designated"}


def test_a_one_way_road_ending_at_a_sidepath_road_links_on_to_the_path():
    G, ids = graph(
        (1, [(1, -100, 0), (2, 0, 0)], ROAD, False),  # one way west to east; beyond 2 the road is use_sidepath
        (9, [(10, -50, 11), (11, 2, 11), (12, 80, 11)], PATH, True),  # the bike path 11 m north, past 2
    )
    links = link_sidepaths(G, sidepath_nodes={2}, node_ids=ids)
    assert nx.has_path(G, 1, 12) and nx.has_path(G, 1, 10)
    assert {(u, v) for u, v in G.edges() if 2 in (u, v)} == {(1, 2), (2, 11)}  # ridden one way only
    assert G.edges[2, 11, 0]["length"] == pytest.approx(11, abs=0.2)
    # The path is split at the vertex the link reaches; the link takes the path's tags.
    assert {(u, v) for u, v in G.edges() if 9 == G.edges[u, v, 0]["osmid"] and 2 not in (u, v)} == {(10, 11), (11, 10), (11, 12), (12, 11)}
    assert G.edges[2, 11, 0]["highway"] == "cycleway"
    assert G.edges[10, 11, 0]["length"] + G.edges[11, 12, 0]["length"] == pytest.approx(130)
    assert [f["properties"]["osm_way_id"] for f in links["features"]] == [9]


def test_a_two_way_road_end_links_both_ways():
    G, ids = graph(
        (1, [(1, -100, 0), (2, 0, 0)], ROAD, True),
        (9, [(10, -50, 11), (11, 2, 11), (12, 80, 11)], PATH, True),
    )
    link_sidepaths(G, sidepath_nodes={2}, node_ids=ids)
    assert G.has_edge(2, 11) and G.has_edge(11, 2)


def test_a_path_too_far_away_or_across_another_road_is_not_linked():
    far, ids = graph(
        (1, [(1, -100, 0), (2, 0, 0)], ROAD, False),
        (9, [(10, -50, 25), (12, 80, 25)], PATH, True),
    )
    across, ids2 = graph(
        (1, [(1, -100, 0), (2, 0, 0)], ROAD, False),
        (5, [(5, -50, 6), (6, 50, 6)], {"highway": "residential"}, True),  # a road between the end and the path
        (9, [(10, -50, 12), (11, 0, 12), (12, 80, 12)], PATH, True),
    )
    for G, node_ids in ((far, ids), (across, ids2)):
        edges = set(G.edges(keys=True))
        assert link_sidepaths(G, sidepath_nodes={2}, node_ids=node_ids)["features"] == []
        assert set(G.edges(keys=True)) == edges


def test_a_road_that_goes_on_is_not_linked():
    G, ids = graph(
        (1, [(1, -100, 0), (2, 0, 0)], ROAD, False),
        (2, [(2, 0, 0), (3, 0, -50)], {"highway": "residential"}, True),  # turns off at 2: not a dead end
        (9, [(10, -50, 11), (11, 2, 11), (12, 80, 11)], PATH, True),
    )
    assert link_sidepaths(G, sidepath_nodes={2}, node_ids=ids)["features"] == []


def test_a_bike_path_starting_on_the_cut_road_is_linked_before_stubs_go():
    G, ids = graph(
        (1, [(1, -100, 0), (2, 0, 0)], ROAD, False),
        (8, [(3, -8, 8), (4, -8, 20)], PATH, True),  # starts on the use_sidepath road (3), 11 m from the road end
        (9, [(4, -8, 20), (12, 80, 20)], PATH, True),
    )
    link_sidepaths(G, sidepath_nodes={2, 3}, node_ids=ids)
    drop_orphan_stubs(G, cut_nodes={2, 3})
    assert nx.shortest_path(G, 1, 12) == [1, 2, 3, 4, 12]
