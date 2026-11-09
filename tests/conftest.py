"""Shared fixtures for core tests: isolated app + store per test."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(store_path=str(tmp_path / "nexus.json"))
    with TestClient(app) as c:
        yield c


def register_login(client, email="user@example.com", password="correct-horse-1"):
    """Register + password login + TOTP verify. Returns (headers, user_id)."""
    reg = client.post(
        "/auth/register", json={"email": email, "password": password}
    )
    assert reg.status_code == 201, reg.text
    user_id = reg.json()["user"]["id"]
    secret = reg.json()["totp_secret"]
    login = client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200, login.text
    assert login.json()["mfa_required"] is True
    from app.auth.service import totp_code

    code = totp_code(secret)
    mfa = client.post(
        "/auth/mfa/verify", json={"user_id": user_id, "code": code}
    )
    assert mfa.status_code == 200, mfa.text
    token = mfa.json()["token"]
    return {"Authorization": f"Bearer {token}"}, user_id


@pytest.fixture
def auth(client):
    headers, user_id = register_login(client)
    return headers, user_id


@pytest.fixture
def funded(client, auth):
    """Two accounts for the authed user: sender funded 100_000 paisa."""
    headers, _user_id = auth
    sender = client.post(
        "/accounts",
        json={"name": "Main", "initial_balance_paisa": 100_000},
        headers=headers,
    ).json()["account"]
    receiver = client.post(
        "/accounts", json={"name": "Savings"}, headers=headers
    ).json()["account"]
    return headers, sender, receiver
