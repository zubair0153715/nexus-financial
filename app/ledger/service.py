"""Ledger service: balanced double-entry transfers in integer paisa.

A transfer = 2 entries sharing one tx_id (debit sender, credit receiver),
equal amounts. No account may go negative. An idempotency key returns the
original transaction instead of posting a second one.
"""

import uuid
from datetime import datetime, timezone

from app.audit.service import log_event


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _find_account(store, account_id: str):
    for account in store.data["accounts"]:
        if account["id"] == account_id:
            return account
    return None


def _tx_from_entries(store, tx_id: str):
    entries = [e for e in store.data["ledger_entries"] if e["tx_id"] == tx_id]
    if not entries:
        return None
    debit = next(e for e in entries if e["type"] == "debit")
    credit = next(e for e in entries if e["type"] == "credit")
    return {
        "id": tx_id,
        "from_account_id": debit["account_id"],
        "to_account_id": credit["account_id"],
        "amount_paisa": debit["amount_paisa"],
        "memo": debit["memo"],
        "created_at": debit["created_at"],
    }


def post_transfer(
    store,
    from_account_id: str,
    to_account_id: str,
    amount_paisa: int,
    memo: str = "",
    idempotency_key: str = None,
) -> dict:
    """Post a transfer. Raises ValueError on bad input, unknown account,
    or insufficient funds. Returns the existing tx on duplicate key."""
    if idempotency_key:
        existing_tx_id = store.data["idempotency"].get(idempotency_key)
        if existing_tx_id:
            existing = _tx_from_entries(store, existing_tx_id)
            if existing is not None:
                return existing
    if not _is_int(amount_paisa) or amount_paisa <= 0:
        raise ValueError("amount must be a positive integer (paisa)")
    if not from_account_id or not to_account_id:
        raise ValueError("both account ids are required")
    if from_account_id == to_account_id:
        raise ValueError("sender and receiver must differ")
    sender = _find_account(store, from_account_id)
    receiver = _find_account(store, to_account_id)
    if sender is None or receiver is None:
        raise ValueError("unknown account")
    if sender["balance_paisa"] < amount_paisa:
        raise ValueError("insufficient funds")

    tx_id = str(uuid.uuid4())
    now = _now_iso()
    debit = {
        "id": str(uuid.uuid4()),
        "tx_id": tx_id,
        "account_id": from_account_id,
        "type": "debit",
        "amount_paisa": amount_paisa,
        "counterparty_account_id": to_account_id,
        "memo": memo or "",
        "created_at": now,
    }
    credit = {
        "id": str(uuid.uuid4()),
        "tx_id": tx_id,
        "account_id": to_account_id,
        "type": "credit",
        "amount_paisa": amount_paisa,
        "counterparty_account_id": from_account_id,
        "memo": memo or "",
        "created_at": now,
    }
    sender["balance_paisa"] -= amount_paisa
    receiver["balance_paisa"] += amount_paisa
    store.append("ledger_entries", debit)
    store.append("ledger_entries", credit)
    if idempotency_key:
        store.data["idempotency"][idempotency_key] = tx_id
    store.save()
    log_event(
        store,
        "transfer",
        sender["user_id"],
        {
            "tx_id": tx_id,
            "from_account_id": from_account_id,
            "to_account_id": to_account_id,
            "amount_paisa": amount_paisa,
            "memo": memo or "",
        },
    )
    return _tx_from_entries(store, tx_id)


def get_balance(store, account_id: str) -> int:
    """Return the balance in paisa. Raises ValueError for unknown accounts."""
    account = _find_account(store, account_id)
    if account is None:
        raise ValueError("unknown account")
    return account["balance_paisa"]


def get_statement(store, account_id: str) -> list:
    """Ledger entries for one account, in posting order."""
    if _find_account(store, account_id) is None:
        raise ValueError("unknown account")
    return [
        e for e in store.data["ledger_entries"] if e["account_id"] == account_id
    ]
