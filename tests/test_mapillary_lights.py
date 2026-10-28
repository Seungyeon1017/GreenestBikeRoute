import routing.mapillary_lights as ml


class Response:
    def __init__(self, data, status=200):
        self.status_code, self._data, self.text = status, data, ""

    def json(self):
        return {"data": self._data}

    def raise_for_status(self):
        pass


def light(i, lon, lat):
    return {"id": str(i), "object_value": ml.OBJECT_VALUE, "geometry": {"type": "Point", "coordinates": [lon, lat]}}


class Session:
    """Pretends the box (0, 0, 1, 1) holds LIMIT + 2 lights, spread over its four quarters."""

    def __init__(self):
        n = ml.LIMIT + 2
        self.lights = [light(i, (i % 2) * 0.5 + 0.25, (i // 2 % 2) * 0.5 + 0.25) for i in range(n)]
        self.calls = 0

    def get(self, url, params, timeout):
        self.calls += 1
        x0, y0, x1, y1 = map(float, params["bbox"].split(","))
        inside = [f for f in self.lights if x0 <= f["geometry"]["coordinates"][0] < x1
                  and y0 <= f["geometry"]["coordinates"][1] < y1]
        return Response(inside[:ml.LIMIT])


def test_full_box_is_split_until_everything_is_fetched():
    s = Session()
    found = ml.fetch_box(s, "token", (0, 0, 1, 1))
    assert len(found) == ml.LIMIT + 2
    assert s.calls == 5  # the full box, then its four quarters


def test_geojson_drops_duplicates():
    gj = ml.to_geojson([light(1, 9.2, 49.1), light(1, 9.2, 49.1), light(2, 9.3, 49.2)])
    assert [f["properties"]["id"] for f in gj["features"]] == ["1", "2"]


def test_boxes_cover_the_bbox():
    bxs = list(ml.boxes((0, 0, 0.025, 0.01), 0.01))
    assert len(bxs) == 3 and bxs[-1][2] == 0.025
