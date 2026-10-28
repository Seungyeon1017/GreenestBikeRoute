import pytest

from routing.lighting import (LIT_IF_RULE_SAYS_DARK, LIT_IF_RULE_SAYS_LIT, BuildingNearby, edge_lit,
                              rule_says_lit, way_lighting)
from routing.shade import LAT0, LON0, M_PER_DEG_LAT

# Two points 100 m apart, going north from the projection origin.
LINE = [(LON0, LAT0), (LON0, LAT0 + 100 / M_PER_DEG_LAT)]
HOUSE = [([(5, 0), (15, 0), (15, 100), (5, 100), (5, 0)], 8.0)]  # 5 m east of the line


@pytest.mark.parametrize("highway, near, lit", [
    ("residential", 0.0, True),   # car streets are lit
    ("path", 1.0, True),          # a path between houses is lit
    ("path", 0.0, False),         # a path in the open is not
    ("track", 1.0, False),        # field/forest tracks never
])
def test_rule(highway, near, lit):
    assert rule_says_lit(highway, near) is lit


def test_osm_tag_wins_over_the_rule():
    ways = {1: ({"highway": "track", "lit": "yes"}, LINE),
            2: ({"highway": "residential", "lit": "no"}, LINE),
            3: ({"highway": "path"}, LINE)}
    near_house = BuildingNearby(HOUSE)
    out, lengths = way_lighting(ways, near_house)
    assert out[1] == (1.0, "osm") and out[2] == (0.0, "osm")
    assert out[3] == (LIT_IF_RULE_SAYS_LIT, "rule")
    assert lengths[3] == pytest.approx(100, abs=1)
    out, _ = way_lighting({3: ways[3]}, BuildingNearby([]))
    assert out[3] == (LIT_IF_RULE_SAYS_DARK, "rule")


def test_mapillary_lights_mark_a_way_as_lit():
    from routing.lighting import LIT_IF_LIGHTS_SEEN, LIT_IF_NOT_SEEN_RULE_DARK, lights_per_way
    ways = {3: ({"highway": "path"}, LINE)}
    lon0, lat0 = LINE[0]
    on_path = (lon0, lat0 + 50 / M_PER_DEG_LAT)          # 50 m along, on the path
    far_away = (lon0 + 0.01, lat0)                         # ~700 m east
    counts = lights_per_way(ways, [on_path, far_away])
    assert counts == {3: 1}                                # 1 light on 100 m = 1 per 100 m
    out, _ = way_lighting(ways, BuildingNearby([]), counts)
    assert out[3] == (LIT_IF_LIGHTS_SEEN, "mapillary")
    out, _ = way_lighting(ways, BuildingNearby([]), {})   # Mapillary data, but no light here
    assert out[3] == (LIT_IF_NOT_SEEN_RULE_DARK, "rule")


def test_edge_lit():
    ways = {1: 1.0, 2: 0.0}
    assert edge_lit([1, 2], ways) == pytest.approx(0.5)
    assert edge_lit(1, ways) == 1.0
    assert edge_lit(9, ways, default=0.3) == 0.3
