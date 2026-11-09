"""Audit service: hash-chained event log.

Each event: hash = sha256(prev_hash + canonical_json(event-without-hash)).
Genesis prev_hash is 64 zeroes. verify_chain() recomputes every hash and
every prev_hash link; any tampering makes it False.
"""

import hashlib
import json
from datetime import datetime, timezone

GENESIS_HASH = "0" * 64


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _event_hash(body: dict) -> str:
    return hashlib.sha256(
        (body["prev_hash"] + _canonical(body)).encode("utf-8")
    ).hexdigest()


def log_event(store, event: str, actor: str, details=None) -> dict:
    """Append a hash-chained audit event and persist the store."""
    events = store.data["audit_events"]
    prev_hash = events[-1]["hash"] if events else GENESIS_HASH
    body = {
        "seq": len(events) + 1,
        "event": event,
        "actor": actor,
        "details": details or {},
        "prev_hash": prev_hash,
        "created_at": _now_iso(),
    }
    record = {**body, "hash": _event_hash(body)}
    store.append("audit_events", record)
    store.save()
    return record


def verify_chain(store) -> bool:
    """True only if every hash recomputes and every link/seq is intact."""
    prev_hash = GENESIS_HASH
    for index, event in enumerate(store.data["audit_events"], start=1):
        if event.get("seq") != index:
            return False
        if event.get("prev_hash") != prev_hash:
            return False
        body = {k: v for k, v in event.items() if k != "hash"}
        if _event_hash(body) != event.get("hash"):
            return False
        prev_hash = event["hash"]
    return True
