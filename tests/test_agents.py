"""Agents tests (Stage 1 invariants).

Covers: fraud flags huge/velocity txs; support never invents a balance;
compliance raises alerts on split patterns; reconciliation reports balanced
True on good data and lists the bad tx on tampered data; run_daily_checks
leaves the store file byte-identical; agents never mutate their inputs;
and the /agents routes + envelope.
"""

import copy
import json
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents import compliance, finance, fraud, orchestrator, support
from app.agents.routes import router as agents_router
from app.agents.routes import set_store

DISCLAIMER = "PROTOTYPE — NOT a bank, NOT licensed, NO real money. Simulated funds only."
# HTTP headers are latin-1: routes send the ASCII-safe form of the disclaimer.
HEADER_DISCLAIMER = DISCLAIMER.replace("—", "-")


class FakeStore:
    """Minimal stand-in for app.core.store.Store (core not built yet)."""

    def __init__(self, path):
        self.path = Path(path)
        self.data = {"users": [], "accounts": [], "ledger_entries": [],
                     "audit_events": [], "wallets": [], "testnet_txs": [],
                     "idempotency": {}}
        self.save_calls = 0
        self.save()

    def save(self):
        self.save_calls += 1
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, sort_keys=True))
        os.replace(tmp, self.path)

    def append(self, collection, record):
        self.data.setdefault(collection, []).append(record)


def _seed_store(store):
    """Two balanced transfers + one unverified-KYC account."""
    store.data["accounts"] = [
        {"id": "acc-1", "user_id": "u1", "name": "Main", "currency": "PKR-TEST",
         "balance_paisa": 900_000, "kyc_status": "verified"},
        {"id": "acc-2", "user_id": "u2", "name": "Other", "currency": "PKR-TEST",
         "balance_paisa": 100_000, "kyc_status": "pending"},
    ]
    store.data["ledger_entries"] = [
        {"id": "e1", "tx_id": "tx-1", "account_id": "acc-1", "type": "debit",
         "amount_paisa": 50_000, "counterparty_account_id": "acc-2", "memo": "pay"},
        {"id": "e2", "tx_id": "tx-1", "account_id": "acc-2", "type": "credit",
         "amount_paisa": 50_000, "counterparty_account_id": "acc-1", "memo": "pay"},
        {"id": "e3", "tx_id": "tx-2", "account_id": "acc-1", "type": "debit",
         "amount_paisa": 25_000, "counterparty_account_id": "acc-2", "memo": "pay"},
        {"id": "e4", "tx_id": "tx-2", "account_id": "acc-2", "type": "credit",
         "amount_paisa": 25_000, "counterparty_account_id": "acc-1", "memo": "pay"},
    ]
    store.save()


@pytest.fixture
def store(tmp_path):
    s = FakeStore(tmp_path / "store.json")
    _seed_store(s)
    return s


@pytest.fixture
def client(store):
    set_store(store)
    app = FastAPI()
    app.include_router(agents_router)
    return TestClient(app)


# --- fraud ---

def test_fraud_flags_huge_tx():
    result = fraud.score_transaction({"amount_paisa": 50_000_000,
                                      "counterparty_is_new": True,
                                      "recent_tx_count": 12})
    assert result["score"] >= 70
    assert result["action"] == "request_hold"
    assert result["reasons"]


def test_fraud_flags_velocity_and_round_amount():
    velocity = fraud.score_transaction({"amount_paisa": 100_000,
                                        "recent_tx_count": 10})
    assert velocity["action"] in ("flag", "request_hold")
    assert any("velocity" in r for r in velocity["reasons"])
    round_tx = fraud.score_transaction({"amount_paisa": 200_000})
    assert any("round amount" in r for r in round_tx["reasons"])


def test_fraud_allows_small_normal_tx():
    result = fraud.score_transaction({"amount_paisa": 5_000,
                                      "counterparty_is_new": False,
                                      "recent_tx_count": 1})
    assert result["action"] == "allow"
    assert 0 <= result["score"] <= 100


# --- support ---

def test_support_never_invents_balance():
    ans = support.answer("What is my balance?", {})
    assert "don't know" in ans.lower()
    # No invented figure may appear anywhere in the answer.
    assert not any(ch.isdigit() for ch in ans)


def test_support_answers_balance_only_from_context():
    ans = support.answer("What is my balance?",
                         {"balance_paisa": 123_456, "account_name": "Main"})
    assert "123456" in ans
    assert support.answer("What is my balance?",
                          {"balance_paisa": 0, "account_name": "Main"}) != \
        support.answer("What is my balance?", {"balance_paisa": 999})


def test_support_faq_and_unknown():
    assert "not a bank" in support.answer("Is this a bank?", {}).lower()
    assert "don't know" in support.answer("What is the weather?", {}).lower()


# --- compliance ---

def test_compliance_missing_kyc_alert():
    alerts = compliance.scan_account({"kyc_status": "pending"}, [])
    assert any(a["type"] == "missing_kyc" for a in alerts)
    assert compliance.scan_account({"kyc_status": "verified"}, []) == []


def test_compliance_split_pattern_alert():
    txs = [{"tx_id": f"t{i}", "amount_paisa": 490_000,
            "counterparty_account_id": "acc-x", "memo": "pay"}
           for i in range(3)]
    alerts = compliance.scan_account({"kyc_status": "verified"}, txs)
    assert any(a["type"] == "split_pattern" for a in alerts)


def test_compliance_large_tx_and_keyword_alerts():
    txs = [{"tx_id": "t1", "amount_paisa": 6_000_000,
            "counterparty_account_id": "acc-y", "memo": "casino winnings"}]
    alerts = compliance.scan_account({"kyc_status": "verified"}, txs)
    types = {a["type"] for a in alerts}
    assert {"large_transaction", "high_risk_keyword"} <= types


# --- finance ---

def _good_entries():
    return [
        {"tx_id": "tx-1", "type": "debit", "amount_paisa": 50_000},
        {"tx_id": "tx-1", "type": "credit", "amount_paisa": 50_000},
        {"tx_id": "tx-2", "type": "debit", "amount_paisa": 25_000},
        {"tx_id": "tx-2", "type": "credit", "amount_paisa": 25_000},
    ]


def test_reconciliation_balanced_on_good_data():
    report = finance.reconciliation_report(_good_entries())
    assert report["balanced"] is True
    assert report["total_debits"] == report["total_credits"] == 75_000
    assert report["differences"] == []


def test_reconciliation_lists_bad_tx_on_tampered_data():
    entries = _good_entries()
    entries[1]["amount_paisa"] = 49_999  # tamper the credit of tx-1
    report = finance.reconciliation_report(entries)
    assert report["balanced"] is False
    assert [d["tx_id"] for d in report["differences"]] == ["tx-1"]
    assert report["differences"][0]["difference"] == 1


# --- agents never mutate inputs ---

def test_agents_do_not_mutate_inputs():
    tx = {"amount_paisa": 50_000_000, "counterparty_is_new": True, "recent_tx_count": 12}
    account = {"kyc_status": "pending"}
    txs = [{"tx_id": "t1", "amount_paisa": 6_000_000,
            "counterparty_account_id": "a", "memo": "x"}]
    entries = _good_entries()
    snapshot = copy.deepcopy((tx, account, txs, entries))
    fraud.score_transaction(tx)
    support.answer("What is my balance?", {"balance_paisa": 1})
    compliance.scan_account(account, txs)
    finance.reconciliation_report(entries)
    assert (tx, account, txs, entries) == snapshot


# --- orchestrator: read-only ---

def test_run_daily_checks_leaves_store_file_byte_identical(store):
    before = store.path.read_bytes()
    saves_before = store.save_calls
    report = orchestrator.run_daily_checks(store)
    assert store.path.read_bytes() == before
    assert store.save_calls == saves_before  # never called save()
    assert report["ok"] is True
    assert report["disclaimer"] == DISCLAIMER
    assert report["reconciliation"]["balanced"] is True
    assert report["summary"]["transactions_scored"] == 2
    assert report["summary"]["accounts_scanned"] == 2
    # acc-2 has pending KYC -> at least one alert
    assert report["summary"]["compliance_alerts"] >= 1


# --- routes ---

def test_agents_routes_envelope_and_header(client):
    r = client.post("/agents/fraud/score",
                    json={"tx": {"amount_paisa": 50_000_000, "recent_tx_count": 12}})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["disclaimer"] == DISCLAIMER
    assert r.headers["X-Nexus-Prototype"] == HEADER_DISCLAIMER
    assert r.json()["result"]["action"] == "request_hold"

    r = client.post("/agents/support/ask",
                    json={"question": "What is my balance?", "context": {}})
    assert "don't know" in r.json()["answer"].lower()

    r = client.post("/agents/compliance/scan",
                    json={"account": {"kyc_status": "pending"}, "transactions": []})
    assert any(a["type"] == "missing_kyc" for a in r.json()["alerts"])

    r = client.post("/agents/finance/reconcile",
                    json={"ledger_entries": _good_entries()})
    assert r.json()["report"]["balanced"] is True

    r = client.post("/agents/daily-checks")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["summary"]["ledger_balanced"] is True
    assert r.headers["X-Nexus-Prototype"] == HEADER_DISCLAIMER
