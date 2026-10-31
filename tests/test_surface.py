import pytest

from routing.surface import unpaved


@pytest.mark.parametrize("tags, value", [
    ({"highway": "track", "tracktype": "grade1"}, 0.0),  # a paved farm road
    ({"highway": "track", "tracktype": "grade2"}, 0.25),
    ({"highway": "track", "tracktype": "grade3"}, 0.5),
    ({"highway": "track", "tracktype": "grade5"}, 1.0),
    ({"highway": "track", "tracktype": "grade4", "surface": "asphalt"}, 0.0),  # surface wins over tracktype
    ({"highway": "path", "surface": "fine_gravel"}, 0.25),  # a park path
    ({"highway": "residential", "surface": "cobblestone"}, 0.5),
    ({"highway": "path", "surface": "grass"}, 1.0),
    ({"highway": "path", "surface": "dirt;grass"}, 1.0),  # the first of several
    ({"highway": "track"}, 0.5),  # a track with neither tag
    ({"highway": "residential"}, None),  # nothing says: counts as paved
])
def test_unpaved(tags, value):
    assert unpaved(tags) == value
