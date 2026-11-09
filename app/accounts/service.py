"""Accounts service: PKR-TEST accounts, integer paisa balances only."""

import uuid
from datetime import datetime, timezone

CURRENCY = "PKR-TEST"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def create_account(store, user_id: str, name: str, initial_balance_paisa: int = 0) -> dict:
    """Create an account. Raises ValueError on bad input/unknown user."""
    if not any(u["id"] == user_id for u in store.data["users"]):
        raise ValueError("unknown user")
    if not name or not str(name).strip():
        raise ValueError("account name is required")
    if not _is_int(initial_balance_paisa) or initial_balance_paisa < 0:
        raise ValueError("initial balance must be a non-negative integer (paisa)")
    account = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "name": str(name).strip(),
        "currency": CURRENCY,
        "balance_paisa": initial_balance_paisa,
        "created_at": _now_iso(),
    }
    store.append("accounts", account)
    store.save()
    return account


def get_account(store, account_id: str):
    for account in store.data["accounts"]:
        if account["id"] == account_id:
            return account
    return None


def list_accounts(store, user_id: str) -> list:
    return [a for a in store.data["accounts"] if a["user_id"] == user_id]
