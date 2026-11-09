"""Core ledger tests: balanced double-entry, no negatives, idempotency,
statement order — service-level and API-level."""

import pytest

from app.accounts.service import create_account
from app.auth.service import create_user
from app.core.store import Store
from app.ledger.service import (
    get_balance,
    get_statement,
    post_transfer,
)


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "ledger.json"))
    user = create_user(s, "a@example.com", "correct-horse-1")
    sender = create_account(s, user["id"], "Main", 100_000)
    receiver = create_account(s, user["id"], "Savings", 0)
    return s, user, sender, receiver


def test_transfer_is_balanced_and_moves_funds(store):
    s, _u, sender, receiver = store
    tx = post_transfer(s, sender["id"], receiver["id"], 25_000, memo="test")
    assert tx["amount_paisa"] == 25_000
    assert get_balance(s, sender["id"]) == 75_000
    assert get_balance(s, receiver["id"]) == 25_000
    entries = [e for e in s.data["ledger_entries"] if e["tx_id"] == tx["id"]]
    assert len(entries) == 2
    debits = sum(e["amount_paisa"] for e in entries if e["type"] == "debit")
    credits = sum(e["amount_paisa"] for e in entries if e["type"] == "credit")
    assert debits == credits == 25_000
    assert all(isinstance(e["amount_paisa"], int) for e in entries)


def test_transfer_overdraft_raises_and_changes_nothing(store):
    s, _u, sender, receiver = store
    with pytest.raises(ValueError):
        post_transfer(s, sender["id"], receiver["id"], 100_001)
    assert get_balance(s, sender["id"]) == 100_000
    assert get_balance(s, receiver["id"]) == 0
    assert s.data["ledger_entries"] == []


def test_transfer_rejects_bad_input(store):
    s, _u, sender, receiver = store
    for bad_amount in (0, -5, 12.5, "1000", True, None):
        with pytest.raises(ValueError):
            post_transfer(s, sender["id"], receiver["id"], bad_amount)
    with pytest.raises(ValueError):
        post_transfer(s, sender["id"], sender["id"], 1_000)
    with pytest.raises(ValueError):
        post_transfer(s, "missing-id", receiver["id"], 1_000)
    with pytest.raises(ValueError):
        post_transfer(s, sender["id"], "missing-id", 1_000)
    assert s.data["ledger_entries"] == []


def test_idempotency_same_key_posts_once(store):
    s, _u, sender, receiver = store
    tx1 = post_transfer(
        s, sender["id"], receiver["id"], 10_000, idempotency_key="key-1"
    )
    tx2 = post_transfer(
        s, sender["id"], receiver["id"], 10_000, idempotency_key="key-1"
    )
    assert tx1["id"] == tx2["id"]
    assert len(s.data["ledger_entries"]) == 2
    assert get_balance(s, sender["id"]) == 90_000
    assert get_balance(s, receiver["id"]) == 10_000
    # A different key posts a second, distinct transfer.
    tx3 = post_transfer(
        s, sender["id"], receiver["id"], 10_000, idempotency_key="key-2"
    )
    assert tx3["id"] != tx1["id"]
    assert len(s.data["ledger_entries"]) == 4


def test_statement_lists_entries_in_order(store):
    s, _u, sender, receiver = store
    post_transfer(s, sender["id"], receiver["id"], 5_000, memo="one")
    post_transfer(s, sender["id"], receiver["id"], 7_000, memo="two")
    post_transfer(s, receiver["id"], sender["id"], 1_000, memo="three")
    stmt = get_statement(s, sender["id"])
    assert [e["memo"] for e in stmt] == ["one", "two", "three"]
    assert [e["type"] for e in stmt] == ["debit", "debit", "credit"]
    with pytest.raises(ValueError):
        get_statement(s, "missing-id")
    with pytest.raises(ValueError):
        get_balance(s, "missing-id")


def test_transfer_via_api_moves_funds_and_is_idempotent(client, funded):
    headers, sender, receiver = funded
    body = {
        "from_account_id": sender["id"],
        "to_account_id": receiver["id"],
        "amount_paisa": 40_000,
        "memo": "api test",
        "idempotency_key": "api-key-1",
    }
    r1 = client.post("/ledger/transfer", json=body, headers=headers)
    assert r1.status_code == 201, r1.text
    assert r1.json()["ok"] is True
    r2 = client.post("/ledger/transfer", json=body, headers=headers)
    assert r2.status_code == 201
    assert r2.json()["transaction"]["id"] == r1.json()["transaction"]["id"]
    bal = client.get(f"/ledger/balance/{sender['id']}", headers=headers).json()
    assert bal["balance_paisa"] == 60_000
    stmt = client.get(
        f"/ledger/statement/{sender['id']}", headers=headers
    ).json()
    assert len(stmt["entries"]) == 1
    assert stmt["entries"][0]["type"] == "debit"


def test_transfer_api_rejects_overdraft(client, funded):
    headers, sender, receiver = funded
    resp = client.post(
        "/ledger/transfer",
        json={
            "from_account_id": sender["id"],
            "to_account_id": receiver["id"],
            "amount_paisa": 100_001,
        },
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["ok"] is False


def test_balance_api_rejects_other_users_account(client, funded):
    from tests.conftest import register_login

    headers, sender, _receiver = funded
    other_headers, _uid = register_login(
        client, email="other@example.com", password="correct-horse-1"
    )
    resp = client.get(f"/ledger/balance/{sender['id']}", headers=other_headers)
    assert resp.status_code == 403
