"""Core auth tests: passwords, TOTP (±1 step), tokens, API flow."""

import time

import pytest

from app.auth.service import (
    authenticate,
    create_user,
    hash_password,
    issue_token,
    totp_code,
    user_from_token,
    verify_password,
    verify_totp,
)
from app.core.store import Store
from tests.conftest import register_login


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "auth.json"))


def test_password_hash_and_verify(store):
    hashed = hash_password("correct-horse-1")
    assert hashed != "correct-horse-1"
    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password("correct-horse-1", hashed) is True
    assert verify_password("wrong-password", hashed) is False
    assert verify_password("correct-horse-1", "not-a-hash") is False


def test_create_user_and_authenticate(store):
    user = create_user(store, "a@example.com", "correct-horse-1")
    assert user["email"] == "a@example.com"
    assert "password_hash" not in user
    assert authenticate(store, "a@example.com", "correct-horse-1")["id"] == user["id"]
    assert authenticate(store, "a@example.com", "wrong-password") is None
    assert authenticate(store, "nobody@example.com", "correct-horse-1") is None


def test_create_user_rejects_duplicate_and_short_password(store):
    create_user(store, "a@example.com", "correct-horse-1")
    with pytest.raises(ValueError):
        create_user(store, "a@example.com", "another-pass-1")
    with pytest.raises(ValueError):
        create_user(store, "b@example.com", "short")
    with pytest.raises(ValueError):
        create_user(store, "not-an-email", "correct-horse-1")


def test_totp_verifies_now_and_adjacent_steps(store):
    user = create_user(store, "a@example.com", "correct-horse-1")
    record = next(u for u in store.data["users"] if u["id"] == user["id"])
    secret = record["totp_secret"]
    now = int(time.time())
    assert verify_totp(secret, totp_code(secret, at=now)) is True
    assert verify_totp(secret, totp_code(secret, at=now + 30)) is True
    assert verify_totp(secret, totp_code(secret, at=now - 30)) is True
    assert verify_totp(secret, totp_code(secret, at=now + 90)) is False
    assert verify_totp(secret, "000000") is False
    assert verify_totp(secret, "not-a-code") is False


def test_token_authenticates_and_bad_token_fails(store):
    user = create_user(store, "a@example.com", "correct-horse-1")
    token = issue_token(store, user["id"])
    assert isinstance(token, str) and len(token) > 20
    assert user_from_token(store, token)["id"] == user["id"]
    assert user_from_token(store, "bogus-token") is None
    assert user_from_token(store, "") is None
    assert user_from_token(store, None) is None


def test_register_login_mfa_api_flow(client):
    headers, user_id = register_login(client)
    assert user_id
    # Token authenticates: a protected endpoint accepts it.
    resp = client.get("/accounts", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_login_wrong_password_fails(client):
    register_login(client)
    resp = client.post(
        "/auth/login", json={"email": "user@example.com", "password": "nope-nope-1"}
    )
    assert resp.status_code == 401
    assert resp.json()["ok"] is False


def test_mfa_wrong_code_fails(client):
    reg = client.post(
        "/auth/register",
        json={"email": "mfa@example.com", "password": "correct-horse-1"},
    )
    user_id = reg.json()["user"]["id"]
    resp = client.post(
        "/auth/mfa/verify", json={"user_id": user_id, "code": "000000"}
    )
    assert resp.status_code == 401
    assert resp.json()["ok"] is False


def test_register_duplicate_api_fails(client):
    register_login(client)
    resp = client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "correct-horse-1"},
    )
    assert resp.status_code == 400


def test_protected_endpoint_without_token_is_401(client):
    assert client.get("/accounts").status_code == 401
    assert client.get("/audit/verify").status_code == 401
