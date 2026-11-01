import networkx as nx

from routing.graph import drop_orphan_stubs


def street_graph(*roads):
    """Two-way roads (osmid, u, v, length, extra tags) as a MultiDiGraph; nodes sit on a line, only their ids matter."""
    G = nx.MultiDiGraph(crs="epsg:4326")
    for osmid, u, v, length, tags in roads:
        for a, b in ((u, v), (v, u)):
            for n in (a, b):
                G.add_node(n, x=9.21 + n * 1e-4, y=49.14)
            G.add_edge(a, b, osmid=osmid, highway=tags.pop("highway", "service"), length=length, **tags)
    return G


def test_a_short_road_between_a_bike_path_and_a_cut_road_is_removed():
    G = street_graph(
        (1, 1, 2, 60.0, {"highway": "path", "bicycle": "designated"}),
        (2, 2, 3, 60.0, {"highway": "path", "bicycle": "designated"}),
        (3, 2, 4, 12.0, {}),  # 4 lies on a use_sidepath road, which the graph left out
    )
    removed = drop_orphan_stubs(G, cut_nodes={4})
    assert {(u, v) for u, v, _ in G.edges(keys=True)} == {(1, 2), (2, 1), (2, 3), (3, 2)}
    assert 4 not in G
    assert [(f["properties"]["osm_way_id"], f["properties"]["length_m"]) for f in removed["features"]] == [(3, 12.0)]


def test_dead_ends_that_are_not_left_over_from_a_cut_road_stay():
    G = street_graph(
        (1, 1, 2, 60.0, {"highway": "residential"}),
        (2, 2, 3, 60.0, {"highway": "residential"}),
        (3, 2, 4, 12.0, {}),  # a dead end in OSM itself, e.g. to a building: 4 isn't on a cut road
        (4, 3, 5, 20.0, {"service": "driveway"}),  # a driveway to a building: 5 isn't on a cut road
        (5, 3, 6, 200.0, {}),  # too long to be a leftover
    )
    removed = drop_orphan_stubs(G, cut_nodes={6})
    assert G.number_of_edges() == 10
    assert removed["features"] == []


def test_the_whole_stub_goes_and_the_junction_stays():
    G = street_graph(
        (1, 1, 2, 60.0, {"highway": "residential"}),
        (2, 2, 3, 60.0, {"highway": "residential"}),
        (3, 2, 4, 10.0, {}),
        (4, 4, 5, 15.0, {}),  # 5 is on a cut road; 4 only links the two pieces
        (5, 6, 7, 8.0, {}),  # hangs by nothing else, one end on a cut road
    )
    removed = drop_orphan_stubs(G, cut_nodes={5, 6})
    assert set(G) == {1, 2, 3}
    assert sorted(f["properties"]["osm_way_id"] for f in removed["features"]) == [3, 4, 5]


def test_a_driveway_or_parking_aisle_joining_a_bike_path_to_a_cut_road_is_removed():
    G = street_graph(
        (1, 1, 2, 60.0, {"highway": "path", "bicycle": "designated"}),
        (2, 2, 3, 60.0, {"highway": "path", "bicycle": "designated"}),
        (3, 2, 4, 7.0, {"service": "driveway"}),
        (4, 2, 5, 8.0, {"service": "parking_aisle"}),
    )
    removed = drop_orphan_stubs(G, cut_nodes={4, 5})
    assert set(G) == {1, 2, 3}
    assert sorted(f["properties"]["osm_way_id"] for f in removed["features"]) == [3, 4]
