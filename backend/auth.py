"""Accounts, login sessions and role checks for the web portal (FR-06, NFR-06)."""
from datetime import datetime, timedelta
from typing import Optional

import psycopg2
from fastapi import Cookie, HTTPException, status

from backend.config import SESSION_COOKIE, SESSION_HOURS
from backend.db import get_cursor
from backend.security import hash_password, hash_token, new_session_token, verify_password
from backend.throttle import Throttle

_USER_FIELDS = "user_id, name, email, role"

# ---------- accounts ----------


class EmailAlreadyRegistered(Exception):
    pass


def create_passenger(name: str, email: str, password: str) -> dict:
    """Register a passenger. An account created by a chat booking (no password yet) is
    taken over, so the bookings made with that email appear under My bookings."""
    with get_cursor() as cur:
        cur.execute(
            f"""INSERT INTO users (name, email, password_hash, role)
                VALUES (%s, LOWER(%s), %s, 'passenger')
                ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name, password_hash = EXCLUDED.password_hash
                WHERE users.password_hash IS NULL AND users.google_sub IS NULL
                RETURNING {_USER_FIELDS}""",
            (name, email, hash_password(password)),
        )
        row = cur.fetchone()
    if not row:
        raise EmailAlreadyRegistered(email)
    return dict(row)


def authenticate(email: str, password: str) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute(
            f"SELECT {_USER_FIELDS}, password_hash FROM users WHERE email = LOWER(%s)",
            (email,),
        )
        row = cur.fetchone()
    if not row or not row["password_hash"] or not verify_password(password, row["password_hash"]):
        return None
    row = dict(row)
    del row["password_hash"]
    return row


def google_user(google_sub: str, email: str, name: str) -> dict:
    """The passenger for a verified Google identity, creating or linking the account if needed.

    Registration does not prove that someone owns an email, so an account with a password
    (which includes all staff) is never linked: EmailAlreadyRegistered asks them to use it.
    An account from a chat booking has no password, and is taken over as in create_passenger.
    """
    with get_cursor() as cur:
        cur.execute(f"SELECT {_USER_FIELDS} FROM users WHERE google_sub = %s", (google_sub,))
        row = cur.fetchone()
        if row:
            return dict(row)
        cur.execute(
            f"""INSERT INTO users (name, email, google_sub, role)
                VALUES (%s, LOWER(%s), %s, 'passenger')
                ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name, google_sub = EXCLUDED.google_sub
                WHERE users.password_hash IS NULL AND users.google_sub IS NULL AND users.role = 'passenger'
                RETURNING {_USER_FIELDS}""",
            (name, email, google_sub),
        )
        row = cur.fetchone()
    if not row:
        raise EmailAlreadyRegistered(email)
    return dict(row)


# ---------- sessions ----------


def create_session(user_id: int) -> str:
    token = new_session_token()
    with get_cursor() as cur:
        cur.execute("DELETE FROM auth_sessions WHERE expires_at < NOW()")
        cur.execute(
            "INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (%s, %s, %s)",
            (hash_token(token), user_id, datetime.now() + timedelta(hours=SESSION_HOURS)),
        )
    return token


def user_for_session(token: str) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute(
            f"""SELECT {', '.join('u.' + f for f in _USER_FIELDS.split(', '))}
                FROM auth_sessions s JOIN users u USING (user_id)
                WHERE s.token_hash = %s AND s.expires_at > NOW()""",
            (hash_token(token),),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def delete_session(token: str) -> None:
    with get_cursor() as cur:
        cur.execute("DELETE FROM auth_sessions WHERE token_hash = %s", (hash_token(token),))


# ---------- login throttling ----------


# Blocks an email after five failed attempts in 15 minutes
login_throttle = Throttle(max_events=5, window_seconds=900)

# ---------- FastAPI dependencies ----------


def optional_user(session: Optional[str] = Cookie(None, alias=SESSION_COOKIE)) -> Optional[dict]:
    """The logged-in user, or None. Database errors count as logged out."""
    if not session:
        return None
    try:
        return user_for_session(session)
    except psycopg2.Error:
        return None


def require_user(session: Optional[str] = Cookie(None, alias=SESSION_COOKIE)) -> dict:
    user = optional_user(session)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please log in.")
    return user


def require_admin(session: Optional[str] = Cookie(None, alias=SESSION_COOKIE)) -> dict:
    user = require_user(session)
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff access only.")
    return user
