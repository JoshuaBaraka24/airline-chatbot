"""Register, log in (with a password or Google), log out and current-user endpoints."""
import re
import secrets
from typing import Optional
from urllib.parse import urlencode

import psycopg2
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, validator

from backend import auth, google_auth
from backend.config import COOKIE_SECURE, SESSION_COOKIE, SESSION_HOURS
from backend.security import MIN_PASSWORD_LENGTH

router = APIRouter(prefix="/api/auth", tags=["auth"])

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
GOOGLE_COOKIE = "kq_google_login"
GOOGLE_COOKIE_PATH = "/api/auth/google"
GOOGLE_LOGIN_SECONDS = 600
MAX_NAME_LENGTH = 100
MAX_EMAIL_LENGTH = 150


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


# ---------- Sign in with Google ----------


@router.get("/providers")
def providers() -> dict:
    """Which optional ways of logging in are set up, so the login page can offer them."""
    return {"google": google_auth.is_configured()}


def _safe_next(page: Optional[str]) -> Optional[str]:
    """Only our own passenger pages (prevents open redirects via ?next=)."""
    return page if page and re.fullmatch(r"[a-z]+\.html", page) and page != "admin.html" else None


def _back_to_login(**query: str) -> RedirectResponse:
    response = RedirectResponse(f"/login.html?{urlencode(query)}", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(GOOGLE_COOKIE, path=GOOGLE_COOKIE_PATH)
    return response


@router.get("/google/start")
def google_start(next: Optional[str] = Query(None, max_length=50)) -> RedirectResponse:
    if not google_auth.is_configured():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Google sign-in is not set up.")
    login_values = google_auth.new_login()
    response = RedirectResponse(google_auth.authorization_url(login_values), status_code=status.HTTP_302_FOUND)
    # Lax, so that it is sent when Google redirects the browser back
    response.set_cookie(
        GOOGLE_COOKIE, ".".join([*login_values.values(), _safe_next(next) or ""]),
        max_age=GOOGLE_LOGIN_SECONDS, httponly=True, samesite="lax", secure=COOKIE_SECURE, path=GOOGLE_COOKIE_PATH,
    )
    return response


@router.get("/google/callback")
def google_callback(
    code: Optional[str] = Query(None, max_length=2048),
    state: Optional[str] = Query(None, max_length=128),
    error: Optional[str] = Query(None, max_length=128),
    login_cookie: Optional[str] = Cookie(None, alias=GOOGLE_COOKIE),
) -> RedirectResponse:
    if error:
        return _back_to_login(error="google_cancelled")
    parts = (login_cookie or "").split(".", 3)
    if not code or not state or len(parts) != 4 or not secrets.compare_digest(state, parts[0]):
        return _back_to_login(error="google")
    login_values = dict(zip(("state", "nonce", "verifier"), parts))
    try:
        claims = google_auth.exchange_code(code, login_values)
        email = claims["email"]
        if len(email) > MAX_EMAIL_LENGTH:
            raise google_auth.GoogleSignInError("email too long")
        name = " ".join(str(claims.get("name") or email.split("@")[0]).split())[:MAX_NAME_LENGTH]
        user = auth.google_user(str(claims["sub"]), email, name)
    except auth.EmailAlreadyRegistered:
        return _back_to_login(error="google_password")
    except (google_auth.GoogleSignInError, psycopg2.Error):
        return _back_to_login(error="google")
    # google=1 makes the login page clear any chat from before this login
    query = {"google": "1"}
    if parts[3]:
        query["next"] = parts[3]
    response = _back_to_login(**query)
    _start_session(response, user)
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, session: Optional[str] = Cookie(None, alias=SESSION_COOKIE)) -> None:
    if session:
        auth.delete_session(session)
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=Optional[User])
def me(user: Optional[dict] = Depends(auth.optional_user)) -> Optional[dict]:
    """The logged-in user, or null when nobody is logged in."""
    return user
