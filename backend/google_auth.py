"""Sign in with Google (OpenID Connect authorization code flow with PKCE).

The browser is sent to Google and back, and the gateway exchanges the returned code for an
ID token directly with Google over TLS, so no Google script runs in the portal and the
Content Security Policy stays strict.
"""
import base64
import binascii
import hashlib
import json
import secrets
import time
from typing import Dict
from urllib.parse import urlencode

import httpx

from backend import config

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ISSUERS = {"https://accounts.google.com", "accounts.google.com"}
TIMEOUT_SECONDS = 10


class GoogleSignInError(Exception):
    """The response from Google could not be trusted or used."""


def is_configured() -> bool:
    return bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET)


def new_login() -> Dict[str, str]:
    """Random values tying the return from Google to this browser (state, nonce, PKCE verifier)."""
    return {
        "state": secrets.token_urlsafe(32),
        "nonce": secrets.token_urlsafe(32),
        "verifier": secrets.token_urlsafe(48),
    }


def authorization_url(login: Dict[str, str]) -> str:
    challenge = hashlib.sha256(login["verifier"].encode()).digest()
    return AUTH_URL + "?" + urlencode({
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": config.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": login["state"],
        "nonce": login["nonce"],
        "code_challenge": base64.urlsafe_b64encode(challenge).rstrip(b"=").decode(),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    })


def decode_id_token(id_token: str) -> dict:
    """The token's claims. Its signature need not be checked because it came straight from
    Google's token endpoint over TLS (OpenID Connect Core 1.0, section 3.1.3.7)."""
    try:
        payload = id_token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError, binascii.Error) as error:
        raise GoogleSignInError("malformed ID token") from error
    if not isinstance(claims, dict):
        raise GoogleSignInError("malformed ID token")
    return claims


def verify_claims(claims: dict, nonce: str) -> dict:
    """Checks the token was issued by Google, for this app and this login, to a verified email."""
    if claims.get("iss") not in ISSUERS:
        raise GoogleSignInError("wrong issuer")
    if claims.get("aud") != config.GOOGLE_CLIENT_ID:
        raise GoogleSignInError("wrong audience")
    expires = claims.get("exp")
    if not isinstance(expires, (int, float)) or expires <= time.time():
        raise GoogleSignInError("expired token")
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise GoogleSignInError("wrong nonce")
    if not claims.get("sub") or not claims.get("email"):
        raise GoogleSignInError("missing identity")
    if claims.get("email_verified") is not True:
        raise GoogleSignInError("email not verified")
    return claims


def exchange_code(code: str, login: Dict[str, str]) -> dict:
    """Swaps the one-time code for verified identity claims."""
    try:
        response = httpx.post(TOKEN_URL, timeout=TIMEOUT_SECONDS, data={
            "code": code,
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "redirect_uri": config.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
            "code_verifier": login["verifier"],
        })
        response.raise_for_status()
        id_token = response.json()["id_token"]
    except (httpx.HTTPError, ValueError, KeyError) as error:
        raise GoogleSignInError("token exchange failed") from error
    return verify_claims(decode_id_token(id_token), login["nonce"])
