"""routing/bridge_profile.py: reading a bridge deck off the DOM1 surface model."""
import networkx as nx
import numpy as np
import pytest
from shapely.geometry import LineString

from routing.bridge_profile import deck_height, runs, smooth_profile


def test_running_median_drops_a_lamp_post():
    h = np.full(100, 160.0)
    h[50:53] = 170.0  # 3 m of lamp post
    assert smooth_profile(h).max() == 160.0


def test_deck_height_keeps_the_rise_and_drops_the_offset_at_the_abutments():
    """The surface runs 157 -> 158 m with a 2 m hump; today's abutments are 156 and 157 m."""
    s = np.arange(0, 101.0)
    h = 157 + s / 100 + 2 * np.sin(np.pi * s / 100)
    assert deck_height(s, h, 50, 156.0, 157.0) == pytest.approx(156.5 + 2)
    assert deck_height(s, h, 0, 156.0, 157.0) == pytest.approx(156.0)


def test_runs_join_the_edges_from_abutment_to_abutment():
    B = nx.Graph()
    B.add_edge(1, 2, line=LineString([(0, 0), (10, 0)]))  # lines run from the smaller node id to the larger
    B.add_edge(2, 3, line=LineString([(10, 0), (30, 0)]))
    B.add_edge(7, 8, line=LineString([(0, 50), (5, 50)]))
    pieces = sorted(runs(B), key=lambda r: r[0])
    assert [(nodes, along, line.length) for nodes, line, along in pieces] == [([1, 2, 3], [0, 10, 30], 30), ([7, 8], [0, 5], 5)]
