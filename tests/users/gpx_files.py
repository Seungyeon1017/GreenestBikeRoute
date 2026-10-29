"""Small GPX files for the leisure route tests."""
import math
from datetime import datetime, timedelta, timezone

NEAR_NECKAR = (9.2100, 49.1400)  # [lon, lat] in Heilbronn
STEP_M = 50
METRES_PER_DEG_LAT = 111_195


def line(start=NEAR_NECKAR, metres=3000, bearing_deg=0):
    """[lon, lat] points every STEP_M metres from `start`, `metres` long."""
    lon0, lat0 = start
    b = math.radians(bearing_deg)
    n = round(metres / STEP_M)
    return [[lon0 + i * STEP_M * math.sin(b) / (METRES_PER_DEG_LAT * math.cos(math.radians(lat0))),
             lat0 + i * STEP_M * math.cos(b) / METRES_PER_DEG_LAT] for i in range(n + 1)]


def gpx(points, step_s=10, times=True, creator="TestApp", kind="trk", version="1.1",
        start=datetime(2026, 9, 6, 8, 0, tzinfo=timezone.utc)):
    """A GPX file riding `points`, one every `step_s` seconds (10 s for 50 m = 18 km/h)."""
    ns = "http://www.topografix.com/GPX/1/1" if version == "1.1" else "http://www.topografix.com/GPX/1/0"
    tag = "trkpt" if kind == "trk" else "rtept"
    pts = "".join(
        f'<{tag} lat="{lat}" lon="{lon}">'
        + (f"<time>{(start + timedelta(seconds=i * step_s)).strftime('%Y-%m-%dT%H:%M:%SZ')}</time>" if times else "")
        + f"</{tag}>" for i, (lon, lat) in enumerate(points))
    body = f"<trk><name>Ride</name><trkseg>{pts}</trkseg></trk>" if kind == "trk" else f"<rte>{pts}</rte>"
    return (f'<?xml version="1.0" encoding="UTF-8"?><gpx version="{version}" creator="{creator}" xmlns="{ns}">'
            f"{body}</gpx>").encode()
