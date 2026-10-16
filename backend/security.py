"""Password hashing and session tokens (NFR-06).

Passwords are hashed with scrypt from the standard library, so no extra
dependency is needed. Stored format: scrypt$<n>$<r>$<p>$<salt hex>$<hash hex>
"""
import hashlib
import hmac
import secrets

_N, _R, _P = 2 ** 14, 8, 1
_KEY_LENGTH = 32
MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_KEY_LENGTH)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, hash_hex = stored.split("$")
        if algorithm != "scrypt":
            return False
        expected = bytes.fromhex(hash_hex)
        digest = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=len(expected),
        )
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(digest, expected)


def new_session_token() -> str:
    """Random token sent to the browser in an HttpOnly cookie."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Only this hash is stored in the database."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
