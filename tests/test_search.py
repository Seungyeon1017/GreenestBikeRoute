import math

import networkx as nx
import pytest

from routing.search import cheapest_path

# Corners of a square 0-1-2 / 0-3-2 plus a long way round 0-4-2, (x, y) in metres.
XY = {0: (0, 0), 1: (100, 0), 2: (100, 100), 3: (0, 100), 4: (300, 300)}
EDGES = {(0, 1): 100, (1, 2): 100, (0, 3): 100, (3, 2): 110, (0, 4): 425, (4, 2): 285}


def steps_by_node(state, info):
    for (u, v), cost in EDGES.items():
        if u == state[0]:
            yield (v, None), cost, None


def straight(n, goal=2):
    return math.dist(XY[n], XY[goal])


def test_dijkstra_finds_the_cheapest_path():
    assert cheapest_path(0, 2, steps_by_node) == [0, 1, 2]


def test_a_star_finds_the_same_path():
    assert cheapest_path(0, 2, steps_by_node, straight) == [0, 1, 2]


def test_a_star_skips_what_cannot_be_cheaper():
    expanded = []

    def counted(state, info):
        expanded.append(state[0])
        return steps_by_node(state, info)

    cheapest_path(0, 2, counted, straight)
    assert 4 not in expanded  # 425 m away, already more than the whole 200 m path


def test_info_from_the_step_reaches_the_next():
    # A state per (node, came from): turning at 1 costs 50, so 0-3-2 wins although 0-1-2 is shorter.
    def turning(state, info):
        for (u, v), cost in EDGES.items():
            if u == state[0]:
                yield (v, u), cost + (50 if info == "at 1" else 0), f"at {v}"
    assert cheapest_path(0, 2, turning) == [0, 3, 2]


def test_no_path_raises():
    with pytest.raises(nx.NetworkXNoPath):
        cheapest_path(2, 0, steps_by_node)
