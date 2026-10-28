import math
import pytest

from download_data import overtaking_risk
from routing import costs
from routing.costs import BAD_AIR_RISK, BUMPY_ROUGHNESS, DEFAULT_PM_RISK, DEFAULT_ROUGHNESS, DEFAULT_STOP_GO, FLOW_PRIOR_POINTS,     MEDIAN_FLOW, MEDIAN_SPEED_KMH, STOP_GO_HEAVY, AIR_SPREAD, MIN_RIDE_POINTS, MIN_SPEED_KMH, SPEED_PRIOR_POINTS, air_scores,     badness, clean_overtaking, edge_cost, edge_roughness, osm_way_ids, point_risks, way_roughness, way_speed, way_stop_go


def test_osm_way_ids_single_and_merged():
    assert osm_way_ids("83738619") == [83738619]
    assert osm_way_ids("[439572396, 401802699]") == [439572396, 401802699]


def test_way_roughness_averages_segments_and_splits_merged_ids():
    features = [
        {"properties": {"osmid": "1", "Normalized Roughness": 20}},
        {"properties": {"osmid": "[1, 2]", "Normalized Roughness": 40}},
        {"properties": {"osmid": "3", "Normalized Roughness": None}},
    ]
    assert way_roughness(features) == {1: 30, 2: 40}


def test_edge_roughness_handles_int_list_and_unmeasured():
    rough = {1: 30, 2: 40}
    assert edge_roughness(1, rough) == 30
    assert edge_roughness([1, 2, 99], rough) == 35
    assert edge_roughness(99, rough) is None


ZERO = {"bump_penalty": 0, "danger_penalty": 0, "pm_penalty": 0, "stop_penalty": 0}


def test_badness_is_0_up_to_typical_1_on_the_bad_line_and_more_beyond():
    assert badness(5, 10, 20) == 0
    assert badness(10, 10, 20) == 0
    assert badness(15, 10, 20) == 0.5
    assert badness(40, 10, 20) == 3


def test_edge_cost_bumps_cost_only_above_typical():
    assert edge_cost(100, 50, **ZERO) == 100
    assert edge_cost(100, DEFAULT_ROUGHNESS, **{**ZERO, "bump_penalty": 5}) == 100  # typical: no extra
    assert edge_cost(100, BUMPY_ROUGHNESS, **{**ZERO, "bump_penalty": 2}) == 300  # bad line: 1 + penalty


def test_edge_cost_danger_adds_metres_per_risk():
    assert edge_cost(100, 0, danger=1.5, danger_penalty=40, pm_penalty=0, stop_penalty=0) == 160
    assert edge_cost(10, 0, danger=1.5, danger_penalty=40, pm_penalty=0, stop_penalty=0) == 70  # regardless of edge length


def test_edge_cost_air_and_stop_go_cost_only_above_typical():
    assert edge_cost(100, 0, **{**ZERO, "pm_penalty": 5}, pm_risk=DEFAULT_PM_RISK) == 100
    assert edge_cost(100, 0, **{**ZERO, "pm_penalty": 2}, pm_risk=BAD_AIR_RISK) == pytest.approx(300)
    assert edge_cost(100, 0, **{**ZERO, "stop_penalty": 5}, stop_go=DEFAULT_STOP_GO) == 100
    assert edge_cost(100, 0, **{**ZERO, "stop_penalty": 2}, stop_go=STOP_GO_HEAVY) == pytest.approx(300)


def test_edge_cost_sun_and_dark_scale_length():
    assert edge_cost(100, 0, **ZERO, sun=0.5, shade_penalty=2) == 200
    assert edge_cost(100, 0, **ZERO, dark=0.25, dark_penalty=4) == 200
    # Without a departure time the router passes sun = dark = 0: the penalties change nothing.
    assert edge_cost(100, 0, **ZERO, shade_penalty=5, dark_penalty=5) == 100


def test_edge_cost_factors_multiply_so_one_penalty_does_not_drown_another():
    """Raising one penalty keeps the cost ratio two streets get from another: a high prefer_bike_friendly still
    tells a bumpy street from a smooth one as much as without it (with a sum it would barely)."""
    def ratio(**kw):
        return edge_cost(100, BUMPY_ROUGHNESS, **kw) / edge_cost(100, DEFAULT_ROUGHNESS, **kw)
    assert ratio(**{**ZERO, "bump_penalty": 1}) == pytest.approx(2)
    assert ratio(**{**ZERO, "bump_penalty": 1}, prefer_bike_friendly=5) == pytest.approx(2)
    assert ratio(**{**ZERO, "bump_penalty": 1, "stop_penalty": 5}, stop_go=STOP_GO_HEAVY) == pytest.approx(2)


def test_edge_cost_danger_keeps_its_weight_under_other_penalties():
    """The overtaking metres are scaled by the street's factor too, so they count as much next to its length."""
    plain = edge_cost(100, 0, danger=1, danger_penalty=50, pm_penalty=0, stop_penalty=0)
    disliked = edge_cost(100, 0, danger=1, danger_penalty=50, pm_penalty=0, stop_penalty=0, prefer_bike_friendly=3)
    assert disliked / plain == pytest.approx(4)


def flow(osmid, value, n):
    return {"properties": {"osmid": osmid, "avg_traffic_flow": value, "points_in_segment": n}}


def test_way_stop_go_weights_by_points_and_pulls_sparse_ways_to_the_median():
    k = FLOW_PRIOR_POINTS
    stop = way_stop_go([flow("1", 1.0, 1), flow("[1, 2]", 0.0, 1000), flow("3", None, 5)])
    assert stop[1] == pytest.approx(1 - (1 + k * MEDIAN_FLOW) / (1001 + k))  # the busy segment dominates
    assert stop[2] == pytest.approx(1 - k * MEDIAN_FLOW / (1000 + k))
    assert 3 not in stop
    sparse = way_stop_go([flow("4", 1.0, 1)])[4]
    assert 0 < sparse < DEFAULT_STOP_GO  # one free-rolling point moves it only a bit


def test_point_risks_skips_missing_values():
    features = [
        {"geometry": {"coordinates": [9.2, 49.1]}, "properties": {"Risk Index": 0.4}},
        {"geometry": {"coordinates": [9.3, 49.2]}, "properties": {"Risk Index": None}},
    ]
    assert point_risks(features, "Risk Index") == ([(9.2, 49.1)], [0.4])


def raw_overtake(cm):
    return {"geometry": {"coordinates": [9.2, 49.14]},
            "properties": {"Overtaking Distance": cm, "Risk Index Overtaking": overtaking_risk(1, cm) if cm else None}}


def test_clean_overtaking_drops_readings_of_25_cm_or_less_and_missing_distances():
    kept = clean_overtaking([raw_overtake(cm) for cm in (None, 0, 10, 25, 26, 100)])
    assert [f["properties"]["Overtaking Distance"] for f in kept] == [26, 100]


def ride_row(box, day, value, hour="08"):
    return {"geometry": {"coordinates": [9.2, 49.14]},
            "properties": {"boxId": box, "createdAt": f"2026-06-{day}T{hour}:00:00.000",
                           **{k: value for k in ("Finedust PM1", "Finedust PM2.5", "Finedust PM4", "Finedust PM10")}}}


def background(day, value, hour="08"):
    return {"properties": {"hour": f"2026-06-{day}T{hour}",
                           **{k: value for k in ("Finedust PM1", "Finedust PM2.5", "Finedust PM4", "Finedust PM10")}}}


def test_air_scores_compare_each_reading_with_its_own_ride(monkeypatch):
    monkeypatch.setattr(costs, "MIN_RIDE_POINTS", 3)
    smoggy = [ride_row("a", "01", v) for v in (24, 19, 29)]
    clean = [ride_row("a", "02", v) for v in (3, 2, 5)]  # same device, next day: the weather drops out
    _, score, rides = air_scores(smoggy + clean, [background("01", 19), background("02", 1)])
    assert rides == ["a2026-06-01"] * 3 + ["a2026-06-02"] * 3
    assert score == pytest.approx([0.5, 0.5 - math.log(25 / 20) / (2 * AIR_SPREAD), 0.5 + math.log(30 / 25) / (2 * AIR_SPREAD),
                                   0.5, 0.5 - math.log(4 / 3) / (2 * AIR_SPREAD), 1.0])  # 6/4 is beyond AIR_SPREAD


def test_air_scores_take_out_how_the_background_changes_within_a_ride(monkeypatch):
    monkeypatch.setattr(costs, "MIN_RIDE_POINTS", 3)
    # the whole region got twice as smoggy at 09: a reading twice as high is just as usual
    ride = [ride_row("a", "01", 9, "08"), ride_row("a", "01", 19, "09"), ride_row("a", "01", 9, "08")]
    _, score, _ = air_scores(ride, [background("01", 9, "08"), background("01", 19, "09")])
    assert score == pytest.approx([0.5, 0.5, 0.5])


def test_air_scores_skip_short_rides_and_hours_without_a_background():
    bg = [background("01", 3)]
    assert air_scores([ride_row("a", "01", 3) for _ in range(MIN_RIDE_POINTS - 1)], bg) == ([], [], [])
    lonlat, _, _ = air_scores([ride_row("a", "01", 3) for _ in range(MIN_RIDE_POINTS)] + [ride_row("a", "01", 3, "09")], bg)
    assert len(lonlat) == MIN_RIDE_POINTS
    assert air_scores([], bg) == ([], [], [])


def test_lift_costs_stop_penalty_times_100_m_per_ride_through():
    """Each of the two edges meeting at a lift carries half."""
    assert edge_cost(10, **ZERO, lift_ends=1) == 10
    one_edge = edge_cost(10, **{**ZERO, "stop_penalty": 2}, stop_go=0, lift_ends=1)
    assert one_edge == 10 + 2 * 100 / 2


def test_edge_cost_speed_turns_length_into_time():
    zero = {"bump_penalty": 0, "pm_penalty": 0, "stop_penalty": 0}
    assert edge_cost(100, 0, **zero, danger_penalty=0) == 100  # the median speed by default: plain length
    assert edge_cost(100, 0, **zero, speed_kmh=MEDIAN_SPEED_KMH / 2) == pytest.approx(200)
    # danger stays metres per risk, whatever the speed
    assert edge_cost(100, 0, **zero, danger=1, danger_penalty=40, speed_kmh=MEDIAN_SPEED_KMH * 2) == pytest.approx(90)


def speed(osmid, kmh, n):
    return {"properties": {"osmid": osmid, "avg_speed[km/h]": kmh, "points_in_segment": n}}


def test_way_speed_weights_by_points_pulls_to_the_median_and_has_a_floor():
    k = SPEED_PRIOR_POINTS
    kmh = way_speed([speed("1", 30.0, 1000), speed("[1, 2]", 10.0, 10), speed("3", None, 5), speed("4", 0.0, 500)])
    assert kmh[1] == pytest.approx((30 * 1000 + 10 * 10 + k * MEDIAN_SPEED_KMH) / (1010 + k))
    assert kmh[2] == pytest.approx((10 * 10 + k * MEDIAN_SPEED_KMH) / (10 + k))
    assert 3 not in kmh
    assert kmh[4] == MIN_SPEED_KMH
