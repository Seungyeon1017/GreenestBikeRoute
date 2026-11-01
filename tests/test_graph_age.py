from datetime import date, timedelta

import networkx as nx

from routing.graph import _age_days


def test_age_counts_from_the_recorded_build_date(tmp_path):
    G = nx.MultiDiGraph(built=(date.today() - timedelta(days=40)).isoformat())
    assert _age_days(G, tmp_path / "missing.graphml") == 40


def test_age_of_a_graph_without_a_date_counts_from_its_file(tmp_path):
    path = tmp_path / "g.graphml"
    path.write_text("")
    assert _age_days(nx.MultiDiGraph(), path) == 0
