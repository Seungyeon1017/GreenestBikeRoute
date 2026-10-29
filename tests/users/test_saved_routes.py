"""POST, GET and DELETE /users/me/routes."""
from sqlalchemy import func, select

from backend.users.models import SavedRoute, User
from backend.users.saved_routes import MAX_SAVED_ROUTES
from routing.costs import DEFAULT_BUMP_PENALTY, DEFAULT_DANGER_PENALTY

ROUTE = {
    "start_lon": 9.21839, "start_lat": 49.14279, "start_label": "Rathaus Heilbronn",
    "end_lon": 9.2353, "end_lat": 49.1462, "end_label": "Pfühlpark",
    "options": {"bump_penalty": 8, "prefer_time": True, "depart_time": "2026-07-21T15:00"},
    "length_m": 1850.4, "duration_s": 520,
}


def save(client, headers, **changes):
    return client.post("/users/me/routes", json={**ROUTE, **changes}, headers=headers)


def test_save_returns_the_route_with_all_options_filled_in(client, auth_headers):
    response = save(client, auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["start_label"] == "Rathaus Heilbronn"
    assert body["end_lat"] == 49.1462
    assert body["duration_s"] == 520
    assert isinstance(body["id"], int) and body["created_at"]
    # Sent options are kept, the rest get the routing defaults.
    assert body["options"]["bump_penalty"] == 8
    assert body["options"]["prefer_time"] is True
    assert body["options"]["depart_time"] == "2026-07-21T15:00"
    assert body["options"]["danger_penalty"] == DEFAULT_DANGER_PENALTY


def test_labels_options_and_totals_are_optional(client, auth_headers):
    minimal = {"start_lon": 9.21, "start_lat": 49.14, "end_lon": 9.23, "end_lat": 49.15}

    response = client.post("/users/me/routes", json=minimal, headers=auth_headers)

    assert response.status_code == 201
    assert response.json()["start_label"] is None
    assert response.json()["options"]["bump_penalty"] == DEFAULT_BUMP_PENALTY


def test_list_is_newest_first(client, auth_headers):
    first = save(client, auth_headers, end_label="first").json()
    second = save(client, auth_headers, end_label="second").json()

    response = client.get("/users/me/routes", headers=auth_headers)

    assert response.status_code == 200
    assert [r["id"] for r in response.json()] == [second["id"], first["id"]]


def test_only_the_newest_routes_are_kept(client, db, auth_headers):
    labels = [f"trip {i}" for i in range(MAX_SAVED_ROUTES + 2)]
    for label in labels:
        assert save(client, auth_headers, end_label=label).status_code == 201

    listed = client.get("/users/me/routes", headers=auth_headers).json()

    assert [r["end_label"] for r in listed] == labels[::-1][:MAX_SAVED_ROUTES]
    # Deleted from the database, not just hidden from the list.
    assert db.scalar(select(func.count()).select_from(SavedRoute)) == MAX_SAVED_ROUTES


def test_the_limit_is_per_user(client, auth_headers, other_auth_headers):
    for _ in range(MAX_SAVED_ROUTES):
        save(client, auth_headers)
    save(client, other_auth_headers)

    assert len(client.get("/users/me/routes", headers=auth_headers).json()) == MAX_SAVED_ROUTES
    assert len(client.get("/users/me/routes", headers=other_auth_headers).json()) == 1


def test_users_only_see_their_own_routes(client, auth_headers, other_auth_headers):
    save(client, auth_headers)

    assert client.get("/users/me/routes", headers=other_auth_headers).json() == []


def test_delete_removes_the_route(client, auth_headers):
    route = save(client, auth_headers).json()

    response = client.delete(f"/users/me/routes/{route['id']}", headers=auth_headers)

    assert response.status_code == 204
    assert client.get("/users/me/routes", headers=auth_headers).json() == []


def test_cannot_delete_someone_elses_route(client, auth_headers, other_auth_headers):
    route = save(client, auth_headers).json()

    response = client.delete(f"/users/me/routes/{route['id']}", headers=other_auth_headers)

    assert response.status_code == 404
    assert len(client.get("/users/me/routes", headers=auth_headers).json()) == 1


def test_delete_unknown_route_is_404(client, auth_headers):
    assert client.delete("/users/me/routes/999999", headers=auth_headers).status_code == 404


def test_out_of_range_option_is_rejected(client, auth_headers):
    assert save(client, auth_headers, options={"bump_penalty": 99}).status_code == 422


def test_misspelled_option_is_rejected(client, auth_headers):
    assert save(client, auth_headers, options={"bump_penaltyy": 10}).status_code == 422


def test_invalid_coordinates_are_rejected(client, auth_headers):
    assert save(client, auth_headers, start_lat=123).status_code == 422


def test_all_endpoints_need_login(client, auth_headers):
    route = save(client, auth_headers).json()

    assert client.post("/users/me/routes", json=ROUTE).status_code == 401
    assert client.get("/users/me/routes").status_code == 401
    assert client.delete(f"/users/me/routes/{route['id']}").status_code == 401


def test_deleting_a_user_deletes_their_routes(client, db, user, auth_headers):
    save(client, auth_headers)
    save(client, auth_headers)

    db.delete(db.get(User, user["id"]))
    db.commit()

    assert db.scalar(select(func.count()).select_from(SavedRoute)) == 0