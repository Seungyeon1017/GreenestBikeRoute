import pytest

from routing.score import STRESS_FACTOR, feel_factor, maxspeed_kmh, signed_factor, traffic_stress


@pytest.mark.parametrize("tags, stress", [
    ({"highway": "cycleway"}, 1),
    ({"highway": "pedestrian"}, 1),
    ({"highway": ["track", "path"]}, 1),
    ({"highway": "living_street"}, 1),
    ({"highway": "residential"}, 1),  # 30 km/h where OSM has no limit
    ({"highway": "residential", "maxspeed": "50"}, 2),
    ({"highway": "tertiary"}, 3),  # 50 km/h
    ({"highway": "tertiary", "maxspeed": "30"}, 2),
    ({"highway": "primary", "maxspeed": "50"}, 3),
    ({"highway": "primary", "maxspeed": "50", "lanes": "4"}, 4),
    ({"highway": "secondary", "maxspeed": "70"}, 4),
    ({"highway": "primary", "maxspeed": "50", "bike_lane": "lane"}, 2),
    ({"highway": "secondary", "maxspeed": "70", "bike_lane": "lane"}, 3),
    ({"highway": "primary", "maxspeed": "70", "bike_lane": "track"}, 1),
    ({"highway": "tertiary", "bike_lane": "bicycle_road"}, 1),
    ({"highway": ["residential", "primary"], "maxspeed": ["30", "50"]}, 3),  # merged: the busiest part
])
def test_traffic_stress(tags, stress):
    assert traffic_stress(tags) == stress


def test_maxspeed_reads_numbers_words_and_lists():
    assert maxspeed_kmh({"highway": "primary", "maxspeed": "DE:urban"}) == 50
    assert maxspeed_kmh({"highway": "residential", "maxspeed": "DE:zone30"}) == 30
    assert maxspeed_kmh({"highway": "track", "maxspeed": "walk"}) == 7
    assert maxspeed_kmh({"highway": "secondary", "maxspeed": ["70", "50"]}) == 70
    assert maxspeed_kmh({"highway": "secondary"}) == 50


def test_signed_factor_gives_as_much_credit_as_cost_and_stops_at_minus_one():
    worse, better = signed_factor(2, 15, 10, 20), signed_factor(2, 5, 10, 20)
    assert worse == 1.25 and better == pytest.approx(1 / 1.25)
    assert signed_factor(2, -100, 10, 20) == signed_factor(2, 0, 10, 20) == pytest.approx(1 / 1.5)
    assert signed_factor(0, 30, 10, 20) == 1


def test_feel_factor_spreads_overtaking_over_at_least_the_gps_noise():
    calm = {"highway": "residential", "length": 10.0, "roughness": None}
    assert feel_factor({**calm, "danger": 1.0}) == pytest.approx(1 + 10 * 1.0 / 50)
    assert feel_factor({**calm, "length": 200.0, "danger": 1.0}) == pytest.approx(1 + 10 * 1.0 / 200)


def test_feel_factor_counts_the_surface():
    track = {"highway": "track", "length": 100.0, "roughness": None}
    assert feel_factor({**track, "unpaved": 1.0}) == pytest.approx(2.5)  # soil or grass at the default 6 points
    assert feel_factor({**track, "unpaved": 0.25}) == pytest.approx(1.375)
    assert feel_factor({**track, "unpaved": 1.0}, unpaved_penalty=0) == 1


def test_feel_factor_uses_nearby_air_where_none_was_measured():
    street = {"highway": "residential", "length": 100.0, "roughness": None, "pm_prior": 0.5}
    assert feel_factor({**street, "pm_near": 0.555}) == pytest.approx(1.25)  # on the bad-air line: 1 + 1 x 0.25
    assert feel_factor({**street, "pm_near": 0.555, "pm_risk": 0.5}) == 1  # its own reading wins
    assert feel_factor({**street, "highway": "primary"}) == STRESS_FACTOR[3]
