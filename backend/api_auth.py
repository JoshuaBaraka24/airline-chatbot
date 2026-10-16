"""Register, log in, log out and current-user endpoints."""
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, validator

from backend import auth
from backend.config import COOKIE_SECURE, SESSION_COOKIE, SESSION_HOURS
from backend.security import MIN_PASSWORD_LENGTH

router = APIRouter(prefix="/api/auth", tags=["auth"])

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class Credentials(BaseModel):
    email: str = Field(..., max_length=150, regex=EMAIL_PATTERN)
    password: str = Field(..., min_length=1, max_length=128)


class Registration(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., max_length=150, regex=EMAIL_PATTERN)
    password: str = Field(..., min_length=MIN_PASSWORD_LENGTH, max_length=128)

    @validator("name")
    def name_not_blank(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("name is too short")
        return value

    @validator("password")
    def password_has_letters_and_digits(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("password must contain letters and numbers")
        return value


class User(BaseModel):
    user_id: int
    name: str
    email: str
    role: str


def _start_session(response: Response, user: dict) -> None:
    token = auth.create_session(user["user_id"])
    response.set_cookie(
        SESSION_COOKIE, token,
        max_age=SESSION_HOURS * 3600, httponly=True, samesite="lax", secure=COOKIE_SECURE, path="/",
    )


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def register(details: Registration, response: Response) -> dict:
    try:
        user = auth.create_passenger(details.name, details.email, details.password)
    except auth.EmailAlreadyRegistered:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
    _start_session(response, user)
    return user


@router.post("/login", response_model=User)
def login(credentials: Credentials, response: Response) -> dict:
    key = credentials.email.lower()
    if auth.login_throttle.is_blocked(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Please wait 15 minutes and try again.",
        )
    user = auth.authenticate(credentials.email, credentials.password)
    if not user:
        auth.login_throttle.record_failure(key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password.")
    auth.login_throttle.reset(key)
    _start_session(response, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, session: Optional[str] = Cookie(None, alias=SESSION_COOKIE)) -> None:
    if session:
        auth.delete_session(session)
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=Optional[User])
def me(user: Optional[dict] = Depends(auth.optional_user)) -> Optional[dict]:
    """The logged-in user, or null when nobody is logged in."""
    return user
