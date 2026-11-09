"""Wallet service (Stage 1 prototype).

Non-custodial: the store holds ONLY the public key + address. The private
key is returned ONCE to the caller of ``create_wallet`` and is NEVER
persisted. ``record_testnet_tx`` is a monitoring stub: it records an
observed testnet transaction; it never broadcasts anything.
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.wallet.keys import generate_keypair

if TYPE_CHECKING:  # typing only; core may not exist yet at runtime
    from app.core.store import Store


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append(store, collection: str, record: dict) -> None:
    append = getattr(store, "append", None)
    if callable(append):
        append(collection, record)
    else:
        store.data.setdefault(collection, []).append(record)


def create_wallet(store, user_id: str, label: str) -> dict:
    """Create a wallet: persist public key + address only.

    Returns the stored record PLUS ``private_key_hex`` (returned once, to
    the caller only). The private key is never written to the store.
    """
    keypair = generate_keypair()
    record = {
        "id": uuid.uuid4().hex[:16],
        "user_id": user_id,
        "label": label,
        "public_key_hex": keypair["public_key_hex"],
        "address": keypair["address"],
        "created_at": _now_iso(),
    }
    _append(store, "wallets", record)
    store.save()
    return {**record, "private_key_hex": keypair["private_key_hex"]}


def list_wallets(store, user_id: str) -> list:
    """Return stored wallets for a user (public data only)."""
    return [w for w in store.data.get("wallets", []) if w.get("user_id") == user_id]


def record_testnet_tx(store, wallet_id: str, tx: dict) -> dict:
    """Record an observed testnet transaction (monitoring stub).

    No broadcasting, no signing, no money movement. Raises ValueError for
    an unknown wallet.
    """
    wallets = store.data.get("wallets", [])
    if not any(w.get("id") == wallet_id for w in wallets):
        raise ValueError(f"unknown wallet: {wallet_id}")
    observation = {
        "id": uuid.uuid4().hex[:16],
        "wallet_id": wallet_id,
        "observed_at": _now_iso(),
        **tx,
    }
    _append(store, "testnet_txs", observation)
    store.save()
    return observation
