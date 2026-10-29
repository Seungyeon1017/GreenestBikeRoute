"""POST /users (sign-up) and GET /users/me."""
from sqlalchemy import select

from backend.users.models import User
from tests.users.conftest import PASSWORD


def test_sign_up_returns_the_user_without_password(client):
    response = client.post("/users", json={"email": "anna@example.com", "password": PASSWORD, "display_name": "Anna"})

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "anna@example.com"
    assert body["display_name"] == "Anna"
    assert isinstance(body["id"], int)
    assert "created_at" in body
    assert "password" not in body and "hashed_password" not in body


def test_display_name_is_optional(client):
    response = client.post("/users", json={"email": "bob@example.com", "password": PASSWORD})

    assert response.status_code == 201
    assert response.json()["display_name"] is None


def test_email_is_stored_in_lower_case(client):
    response = client.post("/users", json={"email": "Anna@Example.COM", "password": PASSWORD})

    assert response.json()["email"] == "anna@example.com"


def test_password_is_stored_as_argon2_hash(client, db):
    client.post("/users", json={"email": "anna@example.com", "password": PASSWORD})

    stored = db.scalar(select(User).where(User.email == "anna@example.com"))
    assert stored.hashed_password != PASSWORD
    assert stored.hashed_password.startswith("$argon2")


def test_same_email_twice_is_rejected(client, user):
    response = client.post("/users", json={"email": "ANNA@example.com", "password": "another-password"})

    assert response.status_code == 409


def test_invalid_email_is_rejected(client):
    response = client.post("/users", json={"email": "not-an-email", "password": PASSWORD})

    assert response.status_code == 422


def test_short_password_is_rejected(client):
    response = client.post("/users", json={"email": "anna@example.com", "password": "short"})

    assert response.status_code == 422


def test_me_returns_the_logged_in_user(client, user, auth_headers):
    response = client.get("/users/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == user