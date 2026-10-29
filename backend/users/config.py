"""Settings for the users package, read from environment variables or the .env file.

All variables start with USERS_, e.g. USERS_DATABASE_URL, so they can't clash
with settings of other parts of the backend.
"""
import logging
import secrets
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

log = logging.getLogger(__name__)


class UserSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="USERS_", env_file=".env", extra="ignore")
    # The database, in parts like the practice repo. Defaults match compose.users.yml,
    # which publishes PostgreSQL on port 5433 (5432 is often taken by a local install).
    database_hostname: str
    database_port: int
    database_username: str
    database_password: str
    database_name: str

    # Signs the login tokens. Set a long random value in production:
    #   python -c "import secrets; print(secrets.token_urlsafe(48))"
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    @property
    def database_url(self) -> str:
        """The parts as one SQLAlchemy URL. URL.create escapes special characters in the password."""
        return URL.create(
            "postgresql+psycopg",  # PostgreSQL with the psycopg 3 driver
            username=self.database_username,
            password=self.database_password,
            host=self.database_hostname,
            port=self.database_port,
            database=self.database_name,
        ).render_as_string(hide_password=False)

@lru_cache
def get_settings() -> UserSettings:
    """The settings, read once. Cached so every request uses the same values."""
    settings = UserSettings()
    if not settings.jwt_secret_key:
                # Lets you try things without a secret, but tokens stop working after every restart.
        log.warning("USERS_JWT_SECRET_KEY is not set: using a random key until the server restarts")
        settings.jwt_secret_key = secrets.token_urlsafe(48)
    return settings
