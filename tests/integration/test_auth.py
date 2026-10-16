from backend.config import SESSION_COOKIE
from backend.db import get_cursor

from .conftest import PASSENGER_PASSWORD, login


def test_register_logs_the_new_passenger_in(client):
    response = client.post("/api/auth/register",
                           json={"name": "  Wanjiru   Njeri ", "email": "Wanjiru@Example.com", "password": "safari2026"})

    assert response.status_code == 201
    assert response.json() == {"user_id": 8, "name": "Wanjiru Njeri", "email": "wanjiru@example.com", "role": "passenger"}
    assert response.cookies.get(SESSION_COOKIE)
    assert client.get("/api/auth/me").json()["email"] == "wanjiru@example.com"


def test_register_rejects_duplicate_email_and_weak_password(client):
    duplicate = client.post("/api/auth/register",
                            json={"name": "John Again", "email": "JOHN@email.com", "password": "another123"})
    assert duplicate.status_code == 409

    for password in ("short1", "lettersonly", "1234567890"):
        weak = client.post("/api/auth/register", json={"name": "New User", "email": "new@example.com", "password": password})
        assert weak.status_code == 422, password


def test_login_is_case_insensitive_and_sets_httponly_cookie(client):
    response = login(client, "John@Email.com", PASSENGER_PASSWORD)

    assert response.status_code == 200
    assert response.json()["name"] == "John Mwangi"
    cookie_header = response.headers["set-cookie"].lower()
    assert "httponly" in cookie_header and "samesite=lax" in cookie_header


def test_session_token_is_stored_only_as_a_hash(client):
    response = login(client, "john@email.com", PASSENGER_PASSWORD)
    token = response.cookies.get(SESSION_COOKIE)

    with get_cursor() as cur:
        cur.execute("SELECT token_hash FROM auth_sessions")
        stored = [row["token_hash"] for row in cur.fetchall()]
    assert len(stored) == 1 and token not in stored and len(stored[0]) == 64


def test_wrong_password_and_unknown_email_give_the_same_error(client):
    wrong = login(client, "john@email.com", "not-the-password1")
    unknown = login(client, "nobody@email.com", "whatever123")

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_repeated_failures_are_throttled(client):
    for _ in range(5):
        assert login(client, "john@email.com", "wrong-password1").status_code == 401

    blocked = login(client, "john@email.com", PASSENGER_PASSWORD)
    assert blocked.status_code == 429


def test_logout_ends_the_session(passenger):
    assert passenger.get("/api/auth/me").json()["name"] == "John Mwangi"

    assert passenger.post("/api/auth/logout").status_code == 204
    assert passenger.get("/api/auth/me").json() is None
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM auth_sessions")
        assert cur.fetchone()["n"] == 0


def test_expired_session_is_rejected(passenger):
    with get_cursor() as cur:
        cur.execute("UPDATE auth_sessions SET expires_at = NOW() - INTERVAL '1 minute'")

    assert passenger.get("/api/auth/me").json() is None
    assert passenger.get("/api/me/bookings").status_code == 401


def test_forged_cookie_is_rejected(client):
    client.cookies.set(SESSION_COOKIE, "made-up-token")
    assert client.get("/api/auth/me").json() is None
