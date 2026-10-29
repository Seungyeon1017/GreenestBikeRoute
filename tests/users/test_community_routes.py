"""Riders' leisure routes: /community-routes and /users/me/community-routes."""
from backend.users import community_routes
from backend.users.models import User
from tests.users.conftest import sign_up_and_log_in
from tests.users.gpx_files import gpx, line

RIDE = gpx(line(metres=3000), creator="StravaGPX")


def publish(client, headers, name="Neckarrunde", data=RIDE, **fields):
    form = {"name": name, "description": "Am Wasser entlang", "tags": ["river", "quiet"], **fields}
    return client.post("/community-routes", data=form, files={"file": ("ride.gpx", data, "application/gpx+xml")},
                       headers=headers)


def listed(client, headers=None, **params):
    response = client.get("/community-routes", params=params, headers=headers or {})
    assert response.status_code == 200
    return response.json()


def test_preview_shows_the_trimmed_ride_without_storing_it(client, auth_headers):
    response = client.post("/community-routes/preview", files={"file": ("ride.gpx", RIDE)}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert 2550 < body["length_m"] < 2650
    assert body["creator"] == "StravaGPX" and body["recorded_on"] == "2026-09-06" and body["is_loop"] is False
    assert listed(client)["total"] == 0


def test_publishing_needs_a_login(client):
    assert publish(client, {}).status_code == 401
    assert client.post("/community-routes/preview", files={"file": ("ride.gpx", RIDE)}).status_code == 401


def test_a_published_route_is_listed_for_everyone(client, auth_headers):
    response = publish(client, auth_headers)

    assert response.status_code == 201
    route = response.json()
    assert route["name"] == "Neckarrunde" and route["author"] == "Anna" and route["tags"] == ["river", "quiet"]
    assert route["mine"] is True and route["status"] == "published" and len(route["coordinates"]) >= 2

    body = listed(client)
    assert body["total"] == 1
    summary = body["routes"][0]
    assert summary["id"] == route["id"] and summary["hearts"] == 0 and summary["mine"] is False
    assert "coordinates" not in summary and summary["preview"] and summary["start"] == route["coordinates"][0]

    detail = client.get(f"/community-routes/{route['id']}").json()
    assert detail["coordinates"] == route["coordinates"]


def test_a_file_that_isnt_a_recorded_ride_is_refused_with_a_code(client, auth_headers):
    response = publish(client, auth_headers, data=gpx(line(), times=False))

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "no_times"
    assert listed(client)["total"] == 0


def test_name_and_tags_are_checked(client, auth_headers):
    assert publish(client, auth_headers, name="  x ").status_code == 422
    assert publish(client, auth_headers, tags=["volcano"]).status_code == 422
    too_many = ["family", "view", "quiet", "river", "nature"]
    assert publish(client, auth_headers, tags=too_many).status_code == 422
    assert publish(client, auth_headers, tags=["river", "river"]).json()["tags"] == ["river"]


def test_list_filters_by_tag(client, auth_headers):
    publish(client, auth_headers, name="Am Neckar", tags=["river"])
    publish(client, auth_headers, name="Mit Kindern", tags=["family"])

    assert [r["name"] for r in listed(client, tag="family")["routes"]] == ["Mit Kindern"]
    assert listed(client, tag="view")["total"] == 0


def test_most_hearted_come_first_and_newest_on_request(client, auth_headers, other_auth_headers):
    first = publish(client, auth_headers, name="Erste").json()
    publish(client, auth_headers, name="Zweite")

    response = client.put(f"/community-routes/{first['id']}/heart", headers=other_auth_headers)

    assert response.json() == {"hearts": 1, "hearted": True}
    assert [r["name"] for r in listed(client)["routes"]] == ["Erste", "Zweite"]
    assert [r["name"] for r in listed(client, sort="newest")["routes"]] == ["Zweite", "Erste"]
    mine = listed(client, other_auth_headers)["routes"][0]
    assert mine["hearted"] is True and mine["hearts"] == 1
    assert listed(client)["routes"][0]["hearted"] is False


def test_hearting_twice_counts_once_and_can_be_taken_back(client, auth_headers, other_auth_headers):
    route = publish(client, auth_headers).json()
    url = f"/community-routes/{route['id']}/heart"

    client.put(url, headers=other_auth_headers)
    assert client.put(url, headers=other_auth_headers).json() == {"hearts": 1, "hearted": True}
    assert client.delete(url, headers=other_auth_headers).json() == {"hearts": 0, "hearted": False}


def test_you_cant_heart_or_flag_your_own_route(client, auth_headers):
    route = publish(client, auth_headers).json()

    assert client.put(f"/community-routes/{route['id']}/heart", headers=auth_headers).status_code == 400
    assert client.post(f"/community-routes/{route['id']}/flag", json={}, headers=auth_headers).status_code == 400


def test_saved_routes_show_on_the_profile(client, auth_headers, other_auth_headers):
    route = publish(client, auth_headers).json()
    url = f"/community-routes/{route['id']}/save"

    assert client.put(url, headers=other_auth_headers).status_code == 204
    assert client.put(url, headers=other_auth_headers).status_code == 204
    saved = client.get("/users/me/community-routes/saved", headers=other_auth_headers).json()
    assert [r["id"] for r in saved] == [route["id"]] and saved[0]["saved"] is True

    assert client.delete(url, headers=other_auth_headers).status_code == 204
    assert client.get("/users/me/community-routes/saved", headers=other_auth_headers).json() == []


def test_enough_flags_hide_a_route_until_a_maintainer_shows_it(client, db, auth_headers, other_auth_headers):
    route = publish(client, auth_headers).json()
    url = f"/community-routes/{route['id']}"
    client.put(f"{url}/save", headers=other_auth_headers)
    flaggers = [other_auth_headers] + [sign_up_and_log_in(client, f"rider{i}@example.com")
                                       for i in range(community_routes.FLAGS_TO_HIDE - 1)]

    for headers in flaggers[:-1]:
        assert client.post(f"{url}/flag", json={"reason": "Spam"}, headers=headers).status_code == 204
    # Flagging again doesn't count twice.
    client.post(f"{url}/flag", json={"reason": "Spam!"}, headers=flaggers[0])
    assert listed(client)["total"] == 1

    client.post(f"{url}/flag", json={}, headers=flaggers[-1])

    assert listed(client)["total"] == 0
    assert client.get(url).status_code == 404
    assert client.get("/users/me/community-routes/saved", headers=other_auth_headers).json() == []
    # The author still sees it, as hidden.
    assert client.get(url, headers=auth_headers).json()["status"] == "hidden"
    assert client.get("/users/me/community-routes", headers=auth_headers).json()[0]["status"] == "hidden"

    stored = db.get(community_routes.CommunityRoute, route["id"])
    stored.status = "published"  # what `python -m backend.users.community_routes show` does, with the flags
    db.commit()
    assert listed(client)["total"] == 1


def test_only_the_author_can_delete_a_route(client, auth_headers, other_auth_headers):
    route = publish(client, auth_headers).json()
    url = f"/community-routes/{route['id']}"

    assert client.delete(url, headers=other_auth_headers).status_code == 404
    assert client.delete(url, headers=auth_headers).status_code == 204
    assert client.get(url).status_code == 404


def test_routes_of_a_blocked_account_are_hidden(client, db, auth_headers, user):
    publish(client, auth_headers)

    db.get(User, user["id"]).is_active = False
    db.commit()

    assert listed(client)["total"] == 0


def test_an_account_can_publish_only_a_few_routes_a_day(client, auth_headers, monkeypatch):
    monkeypatch.setattr(community_routes, "MAX_PER_DAY", 2)

    assert publish(client, auth_headers).status_code == 201
    assert publish(client, auth_headers).status_code == 201
    assert publish(client, auth_headers).status_code == 429


def test_an_expired_login_still_sees_the_list(client, auth_headers):
    publish(client, auth_headers)

    assert listed(client, {"Authorization": "Bearer not-a-token"})["total"] == 1


def test_my_routes_lists_only_mine(client, auth_headers, other_auth_headers):
    publish(client, auth_headers, name="Annas Runde")
    publish(client, other_auth_headers, name="Bens Runde")

    assert [r["name"] for r in client.get("/users/me/community-routes", headers=auth_headers).json()] == ["Annas Runde"]
    assert client.get("/users/me/community-routes").status_code == 401
