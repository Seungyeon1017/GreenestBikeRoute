import math
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import routing.shadow as shadow
from routing.shade import utm32_to_lonlat
from routing.shadow import CEST, BuildingIndex, TreeIndex, edge_shadow, slot_index, sun_position, toward_sun


def test_sun_highest_at_solar_noon_on_solstice():
    # Heilbronn, 21 June: max altitude = 90 - 49.14 + 23.44 = 64.3 deg, due south.
    start = datetime(2026, 6, 21, 10, 0, tzinfo=timezone.utc)
    alt, az = max((sun_position(start + timedelta(minutes=m))[::-1]) for m in range(240))
    assert alt == pytest.approx(64.3, abs=0.2)
    assert az == pytest.approx(180, abs=1)


def test_sun_rises_in_the_east_and_sets_in_the_west():
    az9, alt9 = sun_position(datetime(2026, 7, 21, 9, tzinfo=CEST))
    az18, alt18 = sun_position(datetime(2026, 7, 21, 18, tzinfo=CEST))
    assert 60 < az9 < 120 and 240 < az18 < 300
    assert 20 < alt9 < 40 and 20 < alt18 < 40


# A 20 x 20 m, 10 m high box centred at (0, 0); sun from the south at 45 deg -> 10 m shadow to the north.
BOX = BuildingIndex([([(-10, -10), (10, -10), (10, 10), (-10, 10), (-10, -10)], 10.0)])
SOUTH = toward_sun(180)


@pytest.mark.parametrize("y, shaded", [(0, True), (12, True), (19, True), (21, False), (-12, False)])
def test_building_shadow_falls_away_from_the_sun(y, shaded):
    assert BOX.shades(0, y, *SOUTH, 1.0) is shaded


def test_lower_sun_casts_a_longer_shadow():
    assert not BOX.shades(0, 25, *SOUTH, math.tan(math.radians(45)))
    assert BOX.shades(0, 25, *SOUTH, math.tan(math.radians(20)))  # 10 m / tan 20 = 27 m


@pytest.mark.parametrize("y, shaded", [(4, True), (9.5, True), (14, False), (-6, False)])
def test_tree_crown_shades_the_side_away_from_the_sun(y, shaded):
    trees = TreeIndex([(0, 0, 3)])  # crown radius 3 m
    c = s = math.sqrt(0.5)          # sun from the south at 45 deg
    assert trees.shades(0, y, 0, -c, s, 1.0) is shaded


def test_utm_round_trip():
    east, north = shadow.lonlat_to_utm32(9.2186, 49.1427)  # Marktplatz
    assert (east, north) == (pytest.approx(515943, abs=2), pytest.approx(5443342, abs=2))
    lon, lat = utm32_to_lonlat(east, north)
    assert (lon, lat) == (pytest.approx(9.2186, abs=1e-7), pytest.approx(49.1427, abs=1e-7))


def test_tiles_are_named_by_odd_east_and_even_north_km():
    street = {"geometry": {"coordinates": [[9.2186, 49.1427], [9.2100, 49.1420]]}}
    assert shadow.tiles_for_roads([street]) == [(515, 5442)]


def test_download_skips_existing_and_missing_tiles():
    class Response:
        def __init__(self, status):
            self.status_code, self.content = status, b"zip"

        def raise_for_status(self):
            pass

    class Session:
        def get(self, url, timeout):
            return Response(404 if "_517_" in url else 200)

    real = shadow.requests.Session
    shadow.requests.Session = Session
    try:
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d)
            (dest / "LoD2_32_513_5442_2_bw.zip").write_bytes(b"old")
            shadow.download_tiles([(513, 5442), (515, 5442), (517, 5442)], dest)
            assert (dest / "LoD2_32_513_5442_2_bw.zip").read_bytes() == b"old"  # kept
            assert (dest / "LoD2_32_515_5442_2_bw.zip").read_bytes() == b"zip"  # downloaded
            assert not (dest / "LoD2_32_517_5442_2_bw.zip").exists()            # 404 -> skipped
    finally:
        shadow.requests.Session = real


def test_edge_shadow_and_slots():
    ways = {1: [0.2, 0.8], 2: [0.4, 0.0]}
    assert edge_shadow([1, 2], ways, 0) == pytest.approx(0.3)
    assert edge_shadow(3, ways, 0, default=None) is None
    slots = ["2026-07-21T09:00+02:00", "2026-07-21T12:00+02:00", "2026-07-21T15:00+02:00", "2026-07-21T18:00+02:00"]
    assert slot_index(slots, 13) == 1 and slot_index(slots, 20) == 3
