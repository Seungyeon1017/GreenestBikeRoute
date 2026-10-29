"""Fixtures for the users tests.

They run against a separate PostgreSQL database, <USERS_DATABASE_NAME>_test, on the same
server as your normal one (the Docker database from compose.users.yml). It's created if it
doesn't exist, and emptied after every test, so your real users are never touched.

If that server isn't reachable (e.g. Docker isn't running), these tests are skipped,
not failed, so the rest of the test suite still runs for everyone.
"""
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from backend.users.config import UserSettings
from backend.users.database import Base, get_db
from backend.users.router import router

PASSWORD = "a-long-password"


def _test_url(settings: UserSettings, database: str) -> str:
    return settings.database_url.rsplit("/", 1)[0] + "/" + database


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """One engine for the whole test run, on a fresh <name>_test database with the tables created."""
    try:
        settings = UserSettings()
    except Exception as error:  # e.g. no .env: the database settings are missing
        pytest.skip(f"users tests need the USERS_DATABASE_* settings: {error}")
    test_db = f"{settings.database_name}_test"

    # CREATE DATABASE can't run inside a transaction, hence AUTOCOMMIT; it connects to the
    # built-in "postgres" database because the test database may not exist yet.
    admin = create_engine(_test_url(settings, "postgres"), isolation_level="AUTOCOMMIT",
                          connect_args={"connect_timeout": 5})
    try:
        with admin.connect() as conn:
            exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": test_db})
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{test_db}"'))
    except OperationalError as error:
        pytest.skip(f"users tests need the PostgreSQL from compose.users.yml: {str(error).splitlines()[0]}")
    finally:
        admin.dispose()

    engine = create_engine(_test_url(settings, test_db))
    # Start from the current models every run. (The migrations themselves are checked
    # separately with `alembic check`, see backend/users/migrations/README.)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """A session on the test database. All tables are emptied after each test."""
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def client(db: Session) -> TestClient:
    """An app with only the users endpoints, so the tests don't load the Heilbronn street map."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)

def sign_up_and_log_in(client: TestClient, email: str) -> dict:
    """Creates a user and returns the headers for its requests: {"Authorization": "Bearer ..."}."""
    assert client.post("/users", json={"email": email, "password": PASSWORD}).status_code == 201
    response = client.post("/auth/login", data={"username": email, "password": PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

@pytest.fixture
def user(client: TestClient) -> dict:
    """A signed-up user, as POST /users returned it."""
    response = client.post("/users", json={"email": "anna@example.com", "password": PASSWORD, "display_name": "Anna"})
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def token(client: TestClient, user: dict) -> str:
    response = client.post("/auth/login", data={"username": user["email"], "password": PASSWORD})
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def other_auth_headers(client: TestClient) -> dict:
    """Headers of a second user, to check that users can't see or change each other's data."""
    return sign_up_and_log_in(client, "ben@example.com")