"""Auth service: PBKDF2 passwords, stdlib HMAC TOTP (RFC 6238),
opaque server-side session tokens. No external auth dependencies."""

import base64
import hashlib
import hmac
import os
import secrets
import time
import uuid
from datetime import datetime, timezone

_PBKDF2_ITERATIONS = 200_000
_TOTP_STEP = 30
_TOTP_DIGITS = 6


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_password(password: str) -> str:
    """Return 'pbkdf2_sha256$iterations$salt_hex$hash_hex'."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        algo, iterations, salt_hex, hash_hex = hashed.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def totp_secret() -> str:
    """Random base32 secret (160-bit, RFC 4226/6238)."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii")


def totp_code(secret: str, at=None) -> str:
    """RFC 6238 TOTP, 6 digits, 30-second step, HMAC-SHA1."""
    timestamp = int(time.time()) if at is None else int(at)
    counter = timestamp // _TOTP_STEP
    key = base64.b32decode(secret)
    msg = counter.to_bytes(8, "big")
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (
        int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    ) % (10**_TOTP_DIGITS)
    return f"{code:0{_TOTP_DIGITS}d}"


def verify_totp(secret: str, code: str) -> bool:
    """Accept the code for the current step or ±1 step (clock skew)."""
    candidate = str(code).strip()
    if len(candidate) != _TOTP_DIGITS or not candidate.isdigit():
        return False
    now = int(time.time())
    for step_offset in (-1, 0, 1):
        if hmac.compare_digest(
            totp_code(secret, at=now + step_offset * _TOTP_STEP), candidate
        ):
            return True
    return False


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "created_at": user["created_at"],
    }


def _find_user_by_email(store, email: str):
    wanted = email.strip().lower()
    for user in store.data["users"]:
        if user["email"].lower() == wanted:
            return user
    return None


def create_user(store, email: str, password: str) -> dict:
    """Create a user. Raises ValueError on bad input or duplicate email."""
    email = (email or "").strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError("invalid email")
    if not password or len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    if _find_user_by_email(store, email) is not None:
        raise ValueError("email already registered")
    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": hash_password(password),
        "totp_secret": totp_secret(),
        "created_at": _now_iso(),
    }
    store.append("users", user)
    store.save()
    return public_user(user)


def authenticate(store, email: str, password: str):
    """Return the public user dict on success, None on failure."""
    user = _find_user_by_email(store, email or "")
    if user is None:
        return None
    if not verify_password(password or "", user["password_hash"]):
        return None
    return public_user(user)


def get_user_by_id(store, user_id: str):
    for user in store.data["users"]:
        if user["id"] == user_id:
            return user
    return None


def issue_token(store, user_id: str) -> str:
    """Opaque server-side session token (secrets.token_urlsafe)."""
    token = secrets.token_urlsafe(32)
    store.data["sessions"][token] = {
        "user_id": user_id,
        "created_at": _now_iso(),
    }
    store.save()
    return token


def user_from_token(store, token: str):
    """Return the public user dict for a valid token, else None."""
    if not token:
        return None
    session = store.data["sessions"].get(token)
    if session is None:
        return None
    user = get_user_by_id(store, session["user_id"])
    return public_user(user) if user is not None else None
