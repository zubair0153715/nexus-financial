"""Core audit tests: hash chain verifies, any tampering breaks it."""

from app.audit.service import log_event, verify_chain
from app.core.store import Store


def test_verify_chain_true_after_many_events(tmp_path):
    store = Store(str(tmp_path / "audit.json"))
    for i in range(10):
        log_event(store, f"event-{i}", "actor-1", {"n": i})
    assert verify_chain(store) is True
    assert len(store.data["audit_events"]) == 10
    assert [e["seq"] for e in store.data["audit_events"]] == list(range(1, 11))


def test_tampering_with_details_breaks_chain(tmp_path):
    store = Store(str(tmp_path / "audit.json"))
    for i in range(5):
        log_event(store, f"event-{i}", "actor-1", {"n": i})
    assert verify_chain(store) is True
    store.data["audit_events"][2]["details"] = {"n": 999}
    assert verify_chain(store) is False


def test_tampering_with_hash_or_prev_hash_breaks_chain(tmp_path):
    store = Store(str(tmp_path / "audit.json"))
    for i in range(3):
        log_event(store, f"event-{i}", "actor-1", {})
    store.data["audit_events"][1]["hash"] = "0" * 64
    assert verify_chain(store) is False
    store2 = Store(str(tmp_path / "audit2.json"))
    for i in range(3):
        log_event(store2, f"event-{i}", "actor-1", {})
    store2.data["audit_events"][1]["prev_hash"] = "f" * 64
    assert verify_chain(store2) is False


def test_empty_chain_verifies(tmp_path):
    store = Store(str(tmp_path / "audit.json"))
    assert verify_chain(store) is True


def test_audit_events_logged_by_transfer_and_verify_api(client, funded):
    headers, sender, receiver = funded
    client.post(
        "/ledger/transfer",
        json={
            "from_account_id": sender["id"],
            "to_account_id": receiver["id"],
            "amount_paisa": 1_000,
        },
        headers=headers,
    )
    events = client.get("/audit/events", headers=headers).json()
    assert events["ok"] is True
    assert any(e["event"] == "transfer" for e in events["events"])
    verify = client.get("/audit/verify", headers=headers).json()
    assert verify["ok"] is True
    assert verify["valid"] is True
