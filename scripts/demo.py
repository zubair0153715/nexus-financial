"""NEXUS FINANCIAL — Stage 1 live demo (simulated funds only).

Creates 2 test users + accounts, runs simulated internal transfers, and
prints balances, ledger entries, statement, audit-chain verification,
a fraud-agent score, a reconciliation report, and a testnet wallet.
No real money, no network calls, no mainnet. Run:
    ~/workspace/.venv-fc/bin/python scripts/demo.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.accounts import service as accounts
from app.agents import finance, fraud, orchestrator
from app.audit import service as audit
from app.auth import service as auth
from app.core.constants import DISCLAIMER
from app.core.store import Store
from app.ledger import service as ledger
from app.wallet import service as wallet


def pkr(paisa: int) -> str:
    return f"PKR-TEST {paisa // 100:,}.{paisa % 100:02d}"


def main() -> None:
    print(DISCLAIMER)
    print("=" * 72)
    tmp = Path(tempfile.mkdtemp(prefix="nexus-demo-")) / "nexus.json"
    store = Store(tmp)
    store.load()

    # 1. Two test users + accounts (simulated funding only).
    u1 = auth.create_user(store, "ayesha@test.local", "demo-pass-123")
    u2 = auth.create_user(store, "bilal@test.local", "demo-pass-123")
    a1 = accounts.create_account(store, u1["id"], "Ayesha — main wallet",
                                 initial_balance_paisa=10_000_000)  # 100,000
    a2 = accounts.create_account(store, u2["id"], "Bilal — main wallet",
                                 initial_balance_paisa=5_000_000)   # 50,000
    print(f"accounts: Ayesha {pkr(ledger.get_balance(store, a1['id']))} | "
          f"Bilal {pkr(ledger.get_balance(store, a2['id']))}")

    # 2. Two simulated internal transfers (idempotency keys included).
    t1 = ledger.post_transfer(store, a1["id"], a2["id"], 2_500_000,
                              "Demo: Ayesha pays Bilal 25,000",
                              idempotency_key="demo-tx-001")
    t2 = ledger.post_transfer(store, a2["id"], a1["id"], 1_000_000,
                              "Demo: Bilal pays Ayesha 10,000",
                              idempotency_key="demo-tx-002")
    # Idempotency proof: replaying tx-001 returns the SAME transaction.
    t1_again = ledger.post_transfer(store, a1["id"], a2["id"], 2_500_000,
                                    "Demo: replay (must not double-post)",
                                    idempotency_key="demo-tx-001")
    print(f"transfers: {t1['id'][:8]}… 25,000 | {t2['id'][:8]}… 10,000")
    print(f"idempotency: replay of tx-001 returned same tx_id: "
          f"{t1_again['id'] == t1['id']}")

    # 3. Balances after transfers.
    b1, b2 = ledger.get_balance(store, a1["id"]), ledger.get_balance(store, a2["id"])
    print(f"balances after: Ayesha {pkr(b1)} | Bilal {pkr(b2)} "
          f"(expected 85,000 / 65,000)")
    assert (b1, b2) == (8_500_000, 6_500_000), "balance mismatch!"

    # 4. Ledger proof: every transaction balanced.
    entries = store.data["ledger_entries"]
    print(f"ledger entries: {len(entries)} (2 per transfer)")
    for tx_id in {e["tx_id"] for e in entries}:
        tx = [e for e in entries if e["tx_id"] == tx_id]
        debits = sum(e["amount_paisa"] for e in tx if e["type"] == "debit")
        credits = sum(e["amount_paisa"] for e in tx if e["type"] == "credit")
        assert debits == credits, f"unbalanced tx {tx_id}"
        print(f"  tx {tx_id[:8]}… debits {pkr(debits)} == credits {pkr(credits)}")

    # 5. Statement for Ayesha.
    print("Ayesha statement:")
    for e in ledger.get_statement(store, a1["id"]):
        print(f"  {e['type']:6s} {pkr(e['amount_paisa']):>18s}  {e['memo']}")

    # 6. Audit chain verifies end-to-end.
    events = store.data["audit_events"]
    print(f"audit events: {len(events)} | chain verifies: {audit.verify_chain(store)}")
    assert audit.verify_chain(store)

    # 7. Advisory-only agents over the demo data (they move no money).
    scored = fraud.score_transaction({"amount_paisa": 2_500_000,
                                     "counterparty_is_new": True,
                                     "recent_tx_count": 1})
    print(f"fraud agent on the 25,000 transfer: score {scored['score']} "
          f"-> {scored['action']}")
    recon = finance.reconciliation_report(entries)
    print(f"finance agent reconciliation: balanced={recon['balanced']} "
          f"debits={pkr(recon['total_debits'])} credits={pkr(recon['total_credits'])}")
    checks = orchestrator.run_daily_checks(store)
    print(f"daily checks: {checks['summary']}")

    # 8. Testnet wallet (non-custodial: private key shown once, never stored).
    w = wallet.create_wallet(store, u1["id"], "Ayesha testnet wallet")
    stored = [x for x in store.data["wallets"] if x["id"] == w["id"]][0]
    print(f"testnet wallet: address {w['address']} (label: {w['label']})")
    print(f"  private key persisted in store: {'private_key_hex' in stored} "
          f"(must be False)")
    assert "private_key_hex" not in stored

    print("=" * 72)
    print("DEMO OK — Stage 1 financial core works. " + DISCLAIMER)


if __name__ == "__main__":
    main()
