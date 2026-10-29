"""The users endpoints. backend/app.py adds them with app.include_router(router)."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.users.database import get_db
from backend.users.models import User
from backend.users.schemas import Token, UserCreate, UserOut
from backend.users.security import CurrentUser, create_access_token, hash_password, verify_password
from backend.users import community_routes, saved_routes

router = APIRouter(tags=["Users"])
# /users/me/routes: saved routes (saved_routes.py). Included here so backend/app.py stays unchanged.
router.include_router(saved_routes.router)
# /community-routes: riders' leisure routes (community_routes.py).
router.include_router(community_routes.router)

DB = Annotated[Session, Depends(get_db)]


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserOut,
             summary="Create an account", responses={409: {"description": "Email already registered"}})
def create_user(body: UserCreate, db: DB) -> User:
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status_code=409, detail="This email is already registered")
    
    user = User(email=email, hashed_password=hash_password(body.password), display_name=body.display_name)
    db.add(user)

    try:
        db.commit()
    except IntegrityError:
        # Two sign-ups with the same email at the same moment: the unique index stops the second.
        db.rollback()
        raise HTTPException(status_code=409, detail="This email is already registered") from None
    db.refresh(user)
    return user


def wrong_login() -> HTTPException:
    """The same answer for an unknown email and a wrong password, so it doesn't reveal which emails exist."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Wrong email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/auth/login", response_model=Token, summary="Log in and get a token",
             responses={401: {"description": "Wrong email or password"}})
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DB) -> Token:
    """Takes a form (not JSON) with `username` = the email and `password`, as OAuth2 expects.
    That's also what the "Authorize" button in /docs sends."""
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if user is None:
        # Check a dummy hash anyway, so an unknown email takes as long as a wrong password.
        verify_password(form.password, None)
        raise wrong_login()
    if not verify_password(form.password, user.hashed_password) or not user.is_active:
        raise wrong_login()
    return Token(access_token=create_access_token(user.id))


@router.get("/users/me", response_model=UserOut, summary="The logged-in user",
            responses={401: {"description": "Not logged in"}})
def read_me(user: CurrentUser) -> User:
    return user