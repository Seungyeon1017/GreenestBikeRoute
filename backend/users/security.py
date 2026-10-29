"""Password hashing, login tokens (JWT) and the "who is logged in" dependency."""
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from backend.users.config import get_settings
from backend.users.database import get_db
from backend.users.models import User

# Argon2, the algorithm pwdlib recommends.
password_hash = PasswordHash.recommended()

# Compared against when an email doesn't exist, so a wrong email takes as long as a
# wrong password and response times don't reveal which emails have accounts.
_DUMMY_HASH = password_hash.hash("not-a-real-password")

# Tells /docs where to log in (the "Authorize" button) and reads the Bearer token from requests.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
# The same, for endpoints where logging in is optional: no token is None instead of a 401.
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    return password_hash.verify(password, hashed or _DUMMY_HASH) and hashed is not None


def create_access_token(user_id: int) -> str:
    """A signed token that says "this is user <id>" until it expires."""
    settings = get_settings()
    expires = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "exp": expires}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _user_from_token(token: str | None, db: Session) -> User | None:
    """The active user the token belongs to, or None if it is missing, invalid or expired."""
    if not token:
        return None
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None
    user = db.get(User, user_id)
    return user if user is not None and user.is_active else None


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """FastAPI dependency for endpoints that need a logged-in user. Answers 401 otherwise."""
    user = _user_from_token(token, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not logged in, or the login has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_optional_user(
    token: Annotated[str | None, Depends(optional_oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    """FastAPI dependency for endpoints anyone may call that answer a logged-in user with more (e.g. "you hearted
    this"). A missing or expired login is simply nobody, not an error."""
    return _user_from_token(token, db)


# Shorthand for endpoint parameters: `user: CurrentUser`.
CurrentUser = Annotated[User, Depends(get_current_user)]
# `user: OptionalUser`: the logged-in user, or None.
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
