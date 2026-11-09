"""Wallet tests (Stage 1 invariants).

Covers: keypair sign/verify round-trip, tnx1 address, private key never
persisted, testnet-tx monitoring stub, no live-network strings in
app/wallet/, and the /wallet routes + envelope.
"""

import json
import os
import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.wallet import keys, service
from app.wallet.routes import router as wallet_router
from app.wallet.routes import set_store

DISCLAIMER = "PROTOTYPE — NOT a bank, NOT licensed, NO real money. Simulated funds only."
# HTTP headers are latin-1: routes send the ASCII-safe form of the disclaimer.
HEADER_DISCLAIMER = DISCLAIMER.replace("—", "-")
WALLET_DIR = Path(__file__).resolve().parent.parent / "app" / "wallet"


class FakeStore:
    """Minimal stand-in for app.core.store.Store (core not built yet)."""

    def __init__(self, path):
        self.path = Path(path)
        self.data = {"users": [], "accounts": [], "ledger_entries": [],
                     "audit_events": [], "wallets": [], "testnet_txs": [],
                     "idempotency": {}}
        self.save_calls = 0
        self.save()

    def load(self):
        self.data = json.loads(self.path.read_text())

    def save(self):
        self.save_calls += 1
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, sort_keys=True))
        os.replace(tmp, self.path)

    def append(self, collection, record):
        self.data.setdefault(collection, []).append(record)


@pytest.fixture
def store(tmp_path):
    return FakeStore(tmp_path / "store.json")


@pytest.fixture
def client(store):
    set_store(store)
    app = FastAPI()
    app.include_router(wallet_router)
    return TestClient(app)


# --- keys ---

def test_keypair_sign_verify_round_trip():
    kp = keys.generate_keypair()
    sig = keys.sign_message(kp["private_key_hex"], "hello nexus")
    assert keys.verify_signature(kp["public_key_hex"], "hello nexus", sig) is True
    assert keys.verify_signature(kp["public_key_hex"], "tampered", sig) is False
    assert keys.verify_signature(kp["public_key_hex"], "hello nexus", "00" * 70) is False


def test_address_starts_tnx1_and_is_deterministic():
    kp = keys.generate_keypair()
    assert kp["address"].startswith("tnx1")
    assert keys.address_from_public_key(kp["public_key_hex"]) == kp["address"]
    assert re.fullmatch(r"tnx1[0-9a-f]{40}", kp["address"])


def test_two_keypairs_differ():
    assert keys.generate_keypair()["address"] != keys.generate_keypair()["address"]


# --- service ---

def test_create_wallet_returns_private_key_once_and_never_persists(store):
    wallet = service.create_wallet(store, "user-1", "main")
    assert wallet["private_key_hex"]
    assert wallet["address"].startswith("tnx1")
    assert wallet["public_key_hex"]

    # The persisted store must contain no trace of the private key.
    persisted = json.loads(store.path.read_text())
    assert wallet["private_key_hex"] not in json.dumps(persisted)
    assert "private_key" not in json.dumps(persisted)
    stored = persisted["wallets"][0]
    assert set(stored) == {"id", "user_id", "label", "public_key_hex",
                           "address", "created_at"}


def test_list_wallets_filters_by_user(store):
    service.create_wallet(store, "user-1", "a")
    service.create_wallet(store, "user-2", "b")
    service.create_wallet(store, "user-1", "c")
    mine = service.list_wallets(store, "user-1")
    assert len(mine) == 2
    assert all(w["user_id"] == "user-1" for w in mine)
    assert service.list_wallets(store, "nobody") == []


def test_record_testnet_tx_stores_observation_no_broadcast(store):
    wallet = service.create_wallet(store, "user-1", "a")
    obs = service.record_testnet_tx(store, wallet["id"],
                                    {"tx_hash": "abc123", "amount_paisa": 5000})
    assert obs["wallet_id"] == wallet["id"]
    assert obs["tx_hash"] == "abc123"
    assert obs in store.data["testnet_txs"]
    with pytest.raises(ValueError):
        service.record_testnet_tx(store, "no-such-wallet", {"tx_hash": "x"})


# --- no live-network strings in the wallet module ---

def test_no_mainnet_string_anywhere_in_wallet_module():
    for path in WALLET_DIR.rglob("*.py"):
        text = path.read_text().lower()
        assert "mainnet" not in text, f"'mainnet' found in {path}"


# --- routes ---

def test_wallet_routes_envelope_and_header(client):
    r = client.post("/wallet/create", json={"user_id": "u1", "label": "x"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["disclaimer"] == DISCLAIMER
    assert r.headers["X-Nexus-Prototype"] == HEADER_DISCLAIMER
    wallet = r.json()["wallet"]
    assert wallet["private_key_hex"]  # returned once over the wire

    r = client.get("/wallet/list", params={"user_id": "u1"})
    assert r.status_code == 200
    assert len(r.json()["wallets"]) == 1
    assert "private_key_hex" not in r.json()["wallets"][0]

    r = client.post("/wallet/testnet-tx",
                    json={"wallet_id": wallet["id"], "tx": {"tx_hash": "h1"}})
    assert r.status_code == 200
    assert r.json()["observation"]["tx_hash"] == "h1"

    r = client.post("/wallet/testnet-tx",
                    json={"wallet_id": "nope", "tx": {"tx_hash": "h2"}})
    assert r.json()["ok"] is False
