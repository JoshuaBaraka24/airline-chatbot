"""Sign in with Google: the redirect, the checks on Google's answer and account matching."""
import base64
import json
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from backend import config, google_auth
from backend.api_auth import GOOGLE_COOKIE
from backend.config import SESSION_COOKIE
from backend.db import get_cursor

from .conftest import PASSENGER_PASSWORD, login

CLIENT_ID = "kq-test-client"
GOOD = {"sub": "google-123", "email": "Wairimu@Gmail.test", "email_verified": True, "name": "Wairimu Kariuki"}


@pytest.fixture
def google(client, monkeypatch):
    """A configured client id and a stub of Google's token endpoint; set google.claims to change the answer."""
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "kq-test-secret")

    class Stub:
        claims = dict(GOOD)
        posted = None
        status = 200

    def post(url, data=None, timeout=None):
        Stub.posted = (url, data)
        nonce = parse_qs(urlparse(Stub.authorization).query)["nonce"][0]
        claims = {"iss": "https://accounts.google.com", "aud": CLIENT_ID, "exp": time.time() + 600, "nonce": nonce}
        claims.update(Stub.claims)
        body = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
        request = httpx.Request("POST", url)
        return httpx.Response(Stub.status, json={"id_token": f"header.{body}.signature"}, request=request)

    monkeypatch.setattr(google_auth.httpx, "post", post)
    return Stub


def sign_in(client, stub, state=None, next_page=None):
    """Runs the browser's trip: start, then the return from Google."""
    start = client.get("/api/auth/google/start", params={"next": next_page} if next_page else None,
                       follow_redirects=False)
    assert start.status_code == 302
    stub.authorization = start.headers["location"]
    query = parse_qs(urlparse(stub.authorization).query)
    return client.get("/api/auth/google/callback", follow_redirects=False,
                      params={"code": "one-time-code", "state": state or query["state"][0]})


def test_button_is_only_offered_when_configured(client, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "")
    assert client.get("/api/auth/providers").json() == {"google": False}
    assert client.get("/api/auth/google/start", follow_redirects=False).status_code == 404

    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "secret")
    assert client.get("/api/auth/providers").json() == {"google": True}


def test_start_sends_the_browser_to_google_with_pkce(google, client):
    start = client.get("/api/auth/google/start", follow_redirects=False)

    url = urlparse(start.headers["location"])
    query = parse_qs(url.query)
    assert url.netloc == "accounts.google.com"
    assert query["client_id"] == [CLIENT_ID]
    assert query["scope"] == ["openid email profile"]
    assert query["code_challenge_method"] == ["S256"]
    assert "kq-test-secret" not in start.headers["location"]
    cookie = start.headers["set-cookie"].lower()
    assert GOOGLE_COOKIE in cookie and "httponly" in cookie and "samesite=lax" in cookie


def test_new_google_user_gets_a_passenger_account_and_session(google, client):
    response = sign_in(client, google)

    assert response.status_code == 302
    assert response.headers["location"] == "/login.html?google=1"
    assert response.cookies.get(SESSION_COOKIE)
    me = client.get("/api/auth/me").json()
    assert (me["name"], me["email"], me["role"]) == ("Wairimu Kariuki", "wairimu@gmail.test", "passenger")
    assert google.posted[1]["code_verifier"] and google.posted[1]["code"] == "one-time-code"


def test_returning_user_is_matched_by_google_id_even_if_their_email_changed(google, client):
    sign_in(client, google)
    first = client.get("/api/auth/me").json()["user_id"]
    client.post("/api/auth/logout")

    google.claims = dict(GOOD, email="new.address@gmail.test")
    sign_in(client, google)

    assert client.get("/api/auth/me").json()["user_id"] == first


def test_account_from_a_chat_booking_is_taken_over_with_its_bookings(google, client):
    from actions import repository as repo
    flight_id = repo.next_flights_on_route("Nairobi", "Dubai")[0]["flight_id"]
    ref = repo.create_booking(flight_id, passenger_name="W Kariuki", email="wairimu@gmail.test")

    sign_in(client, google)

    assert [b["booking_ref"] for b in client.get("/api/me/bookings").json()] == [ref]


def test_an_account_with_a_password_is_not_linked(google, client):
    google.claims = dict(GOOD, sub="google-999", email="john@email.com")

    response = sign_in(client, google)

    assert response.headers["location"] == "/login.html?error=google_password"
    assert not response.cookies.get(SESSION_COOKIE)
    assert client.get("/api/auth/me").json() is None
    with get_cursor() as cur:
        cur.execute("SELECT google_sub FROM users WHERE email = 'john@email.com'")
        assert cur.fetchone()["google_sub"] is None


def test_staff_cannot_sign_in_with_google(google, client):
    google.claims = dict(GOOD, sub="google-999", email="admin@kq-demo.local")

    assert sign_in(client, google).headers["location"] == "/login.html?error=google_password"
    assert client.get("/api/auth/me").json() is None


def test_a_google_account_cannot_be_taken_over_by_registering(google, client):
    sign_in(client, google)
    client.post("/api/auth/logout")

    response = client.post("/api/auth/register",
                           json={"name": "Attacker", "email": "wairimu@gmail.test", "password": "takeover123"})

    assert response.status_code == 409
    assert login(client, "wairimu@gmail.test", "takeover123").status_code == 401


def test_a_second_google_id_cannot_claim_a_linked_email(google, client):
    sign_in(client, google)
    client.post("/api/auth/logout")

    google.claims = dict(GOOD, sub="google-other")

    assert sign_in(client, google).headers["location"] == "/login.html?error=google_password"
    assert client.get("/api/auth/me").json() is None


def test_wrong_state_is_refused_before_contacting_google(google, client):
    response = sign_in(client, google, state="forged")

    assert response.headers["location"] == "/login.html?error=google"
    assert google.posted is None
    assert not response.cookies.get(SESSION_COOKIE)


def test_callback_without_the_cookie_is_refused(google, client):
    response = client.get("/api/auth/google/callback", params={"code": "x", "state": "y"}, follow_redirects=False)

    assert response.headers["location"] == "/login.html?error=google"


def test_declining_at_google_returns_quietly(google, client):
    client.get("/api/auth/google/start", follow_redirects=False)

    response = client.get("/api/auth/google/callback", params={"error": "access_denied"}, follow_redirects=False)

    assert response.headers["location"] == "/login.html?error=google_cancelled"


@pytest.mark.parametrize("bad", [
    {"iss": "https://evil.test"},
    {"aud": "another-app"},
    {"exp": 1000},
    {"nonce": "replayed"},
    {"email_verified": False},
    {"email_verified": "true"},
    {"sub": ""},
    {"email": ""},
])
def test_untrustworthy_tokens_are_refused(google, client, bad):
    google.claims = dict(GOOD, **bad)

    response = sign_in(client, google)

    assert response.headers["location"] == "/login.html?error=google"
    assert client.get("/api/auth/me").json() is None


def test_google_being_down_is_handled(google, client, monkeypatch):
    def down(*args, **kwargs):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(google_auth.httpx, "post", down)

    assert sign_in(client, google).headers["location"] == "/login.html?error=google"


def test_a_rejected_code_is_handled(google, client):
    google.status = 400

    assert sign_in(client, google).headers["location"] == "/login.html?error=google"


@pytest.mark.parametrize("next_page, expected", [
    ("account.html", "/login.html?google=1&next=account.html"),
    ("assistant.html", "/login.html?google=1&next=assistant.html"),
    ("admin.html", "/login.html?google=1"),
    ("https://evil.test", "/login.html?google=1"),
    ("//evil.test/x.html", "/login.html?google=1"),
])
def test_only_our_own_pages_are_allowed_as_next(google, client, next_page, expected):
    assert sign_in(client, google, next_page=next_page).headers["location"] == expected


@pytest.mark.parametrize("token", ["no-dots", "a.!!!.c", "a.bm90LWpzb24.c", "a.WzFd.c"])
def test_malformed_tokens_are_refused(token):
    with pytest.raises(google_auth.GoogleSignInError):
        google_auth.decode_id_token(token)
