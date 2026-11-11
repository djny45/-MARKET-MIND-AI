"""Small, dependency-free cryptographic primitives for the auth implementation.

These helpers do not provide authentication by themselves. Callers must still
persist/revoke sessions, enforce expiry, protect routes, and validate CSRF and
Origin on every state-changing request.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets


_PASSWORD_SCHEME = "scrypt"
_SCRYPT_N = 1 << 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_PASSWORD_SALT_BYTES = 16
_PASSWORD_DK_BYTES = 64
_MAX_PASSWORD_BYTES = 1024
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
_BASE64URL_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_SESSION_TOKEN_DOMAIN = b"market-mind-session-token-v1:"


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    if not isinstance(value, str) or not _BASE64URL_PATTERN.fullmatch(value):
        raise ValueError("invalid unpadded base64url value")
    padded = value + "=" * (-len(value) % 4)
    decoded = base64.b64decode(padded, altchars=b"-_", validate=True)
    if _b64encode(decoded) != value:
        raise ValueError("non-canonical base64url value")
    return decoded


def hash_password(password: str) -> str:
    """Return a salted scrypt password hash suitable for server-side storage."""
    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")
    try:
        password_bytes = password.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError("password must contain valid Unicode text") from exc
    if len(password_bytes) > _MAX_PASSWORD_BYTES:
        raise ValueError("password exceeds the maximum supported length")

    salt = secrets.token_bytes(_PASSWORD_SALT_BYTES)
    digest = hashlib.scrypt(
        password_bytes,
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_PASSWORD_DK_BYTES,
    )
    return "$".join(
        (
            _PASSWORD_SCHEME,
            str(_SCRYPT_N),
            str(_SCRYPT_R),
            str(_SCRYPT_P),
            _b64encode(salt),
            _b64encode(digest),
        )
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    """Verify a stored hash without raising on malformed or unsupported input."""
    if not isinstance(password, str) or not isinstance(encoded_hash, str):
        return False
    try:
        if len(password.encode("utf-8")) > _MAX_PASSWORD_BYTES:
            return False
        parts = encoded_hash.split("$")
        if len(parts) != 6:
            return False
        scheme, n_text, r_text, p_text, salt_text, digest_text = parts
        if (
            scheme != _PASSWORD_SCHEME
            or n_text != str(_SCRYPT_N)
            or r_text != str(_SCRYPT_R)
            or p_text != str(_SCRYPT_P)
        ):
            return False
        salt = _b64decode(salt_text)
        expected = _b64decode(digest_text)
        if len(salt) != _PASSWORD_SALT_BYTES or len(expected) != _PASSWORD_DK_BYTES:
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=_SCRYPT_N,
            r=_SCRYPT_R,
            p=_SCRYPT_P,
            dklen=_PASSWORD_DK_BYTES,
        )
        return hmac.compare_digest(actual, expected)
    except (UnicodeError, ValueError, TypeError):
        return False


def generate_session_token() -> str:
    """Create a 256-bit URL-safe bearer token; never persist this raw value."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Return a domain-separated SHA-256 digest for session-token lookup."""
    if not isinstance(token, str) or not _TOKEN_PATTERN.fullmatch(token):
        raise ValueError("session token must be a generated 256-bit URL-safe token")
    return hashlib.sha256(_SESSION_TOKEN_DOMAIN + token.encode("ascii")).hexdigest()


def generate_csrf_token() -> str:
    """Create a high-entropy CSRF token for binding to a server-side session."""
    return secrets.token_urlsafe(32)


def verify_csrf_token(supplied: str, expected: str) -> bool:
    """Compare CSRF tokens in constant time; missing or malformed values fail."""
    if (
        not isinstance(supplied, str)
        or not isinstance(expected, str)
        or not _TOKEN_PATTERN.fullmatch(supplied)
        or not _TOKEN_PATTERN.fullmatch(expected)
    ):
        return False
    return hmac.compare_digest(supplied, expected)
