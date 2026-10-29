"""POST /auth/login and the token check on protected endpoints."""
from datetime import UTC, datetime, timedelta

import jwt

from backend.users.config import get_settings
from backend.users.models import User
from tests.users.conftest import PASSWORD


def login(client, username, password):
    return client.post("/auth/login", data={"username": username, "password": password})


def test_login_returns_a_bearer_token(client, user):
    response = login(client, "anna@example.com", PASSWORD)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_ignores_email_case(client, user):
    assert login(client, "ANNA@Example.com", PASSWORD).status_code == 200


def test_wrong_password_and_unknown_email_get_the_same_answer(client, user):
    wrong_password = login(client, "anna@example.com", "wrong-password")
    unknown_email = login(client, "nobody@example.com", PASSWORD)

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_login_needs_form_data_not_json(client, user):
    response = client.post("/auth/login", json={"username": "anna@example.com", "password": PASSWORD})

    assert response.status_code == 422


def test_inactive_user_cannot_log_in(client, db, user):
    db.get(User, user["id"]).is_active = False
    db.commit()

    assert login(client, "anna@example.com", PASSWORD).status_code == 401


def test_me_without_token_is_401(client):
    assert client.get("/users/me").status_code == 401


def test_me_with_invalid_token_is_401(client):
    response = client.get("/users/me", headers={"Authorization": "Bearer not.a.token"})

    assert response.status_code == 401


def test_me_with_token_signed_by_another_key_is_401(client, user):
    forged = jwt.encode({"sub": str(user["id"])}, "someone-elses-key", algorithm="HS256")

    response = client.get("/users/me", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401


def test_me_with_expired_token_is_401(client, user):
    settings = get_settings()
    expired = jwt.encode({"sub": str(user["id"]), "exp": datetime.now(UTC) - timedelta(minutes=1)},
                         settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    response = client.get("/users/me", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401


def test_token_stops_working_when_user_is_deactivated(client, db, user, auth_headers):
    db.get(User, user["id"]).is_active = False
    db.commit()

    assert client.get("/users/me", headers=auth_headers).status_code == 401


def test_token_of_deleted_user_is_401(client, db, user, auth_headers):
    db.delete(db.get(User, user["id"]))
    db.commit()

    assert client.get("/users/me", headers=auth_headers).status_code == 401