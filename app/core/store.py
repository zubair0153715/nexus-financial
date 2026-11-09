"""JSON store: one file, atomic write (temp file + rename).

Data keys: users, accounts, ledger_entries, audit_events, wallets,
idempotency (key -> transaction id), sessions (token -> session record).
Money is integer paisa (PKR test units) — never floats.
"""

import json
import os
import tempfile
from pathlib import Path

from fastapi import Request

COLLECTIONS = (
    "users",
    "accounts",
    "ledger_entries",
    "audit_events",
    "wallets",
)

MAPS = ("idempotency", "sessions")


def empty_data() -> dict:
    data = {name: [] for name in COLLECTIONS}
    data.update({name: {} for name in MAPS})
    return data


class Store:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else None
        self.data = empty_data()

    def load(self):
        """Load from disk if the file exists; otherwise keep empty data."""
        if self.path is not None and self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            data = empty_data()
            for key, value in raw.items():
                data[key] = value
            self.data = data
        return self.data

    def save(self):
        """Atomic write: write a temp file in the same dir, then rename."""
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=".nexus-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, sort_keys=True)
                f.write("\n")
            os.replace(tmp_name, self.path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def get(self, key):
        return self.data[key]

    def append(self, collection, record):
        self.data[collection].append(record)
        return record


def get_store(request: Request) -> Store:
    """FastAPI dependency: the app's Store instance."""
    return request.app.state.store
