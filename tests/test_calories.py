import pytest

from routing.calories import ride_kcal, total_climb


def test_flat_ride_follows_the_met_formula():
    # 70 kg, 10.5 min on the flat: 6.8 MET * 70 kg * 0.175 h = 83.3 kcal
    assert ride_kcal(630, 0, 70) == pytest.approx(83.3, abs=0.1)


def test_climbing_adds_lifting_work():
    # 30 m up with 85 kg (rider + bike): 85 * 9.81 * 30 / 0.25 / 4184 = 23.9 kcal extra
    assert ride_kcal(630, 30, 70) - ride_kcal(630, 0, 70) == pytest.approx(23.9, abs=0.1)


def test_heavier_rider_uses_more():
    assert ride_kcal(600, 10, 90) > ride_kcal(600, 10, 60)


def test_e_bike_uses_less_mostly_on_hills():
    flat_bike, flat_e = ride_kcal(630, 0, 70), ride_kcal(630, 0, 70, e_bike=True)
    assert flat_e == pytest.approx(0.9 * flat_bike)
    # 30 m up on a 25 kg e-bike: (70 + 25) * 9.81 * 30 / 0.25 / 4184 * 0.5 = 13.4 kcal for the climb
    assert ride_kcal(630, 30, 70, e_bike=True) - flat_e == pytest.approx(13.4, abs=0.1)
    assert ride_kcal(630, 30, 70, e_bike=True) < ride_kcal(630, 30, 70)


def test_only_uphill_counts():
    assert total_climb([5.0, -3.0, 2.5, -10.0]) == 7.5
    assert ride_kcal(600, -20, 70) == ride_kcal(600, 0, 70)
