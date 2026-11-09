"""Daily-checks orchestrator (advisory only, READ-ONLY).

Runs fraud scoring over recent transactions + compliance scans + ledger
reconciliation and returns one combined advisory report. It reads
``store.data`` only — it never calls ``store.save()`` and never mutates
anything. Agents here receive plain dicts/lists, never the store.
"""

from datetime import datetime, timezone

from app.agents import compliance, finance, fraud

try:
    from app.core.constants import DISCLAIMER
except Exception:  # core not built yet; same literal as the contract
    DISCLAIMER = "PROTOTYPE — NOT a bank, NOT licensed, NO real money. Simulated funds only."


def run_daily_checks(store) -> dict:
    """Run all advisory checks read-only over the store's data."""
    data = store.data  # read-only access; no save, no mutation
    ledger_entries = list(data.get("ledger_entries", []))
    accounts = list(data.get("accounts", []))

    # Group ledger entries into per-transaction views (plain dicts).
    txs_by_id: dict = {}
    for entry in ledger_entries:
        tx = txs_by_id.setdefault(entry.get("tx_id"), {
            "tx_id": entry.get("tx_id"),
            "amount_paisa": 0,
            "counterparty_account_id": entry.get("counterparty_account_id"),
            "memo": entry.get("memo", ""),
            "recent_tx_count": 0,
            "counterparty_is_new": False,
        })
        if entry.get("type") == "debit":
            tx["amount_paisa"] += int(entry.get("amount_paisa", 0) or 0)
        tx["recent_tx_count"] += 1

    fraud_results = [
        {"tx_id": tx["tx_id"], **fraud.score_transaction(tx)}
        for tx in txs_by_id.values()
    ]

    compliance_results = []
    for account in accounts:
        account_txs = [
            {"tx_id": e.get("tx_id"),
             "amount_paisa": e.get("amount_paisa", 0),
             "counterparty_account_id": e.get("counterparty_account_id"),
             "memo": e.get("memo", "")}
            for e in ledger_entries
            if e.get("account_id") == account.get("id")
        ]
        compliance_results.append({
            "account_id": account.get("id"),
            "alerts": compliance.scan_account(account, account_txs),
        })

    reconciliation = finance.reconciliation_report(ledger_entries)

    total_alerts = sum(len(r["alerts"]) for r in compliance_results)
    flagged = [f for f in fraud_results if f["action"] != "allow"]
    return {
        "ok": True,
        "disclaimer": DISCLAIMER,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reconciliation": reconciliation,
        "fraud": fraud_results,
        "compliance": compliance_results,
        "summary": {
            "transactions_scored": len(fraud_results),
            "transactions_flagged": len(flagged),
            "accounts_scanned": len(compliance_results),
            "compliance_alerts": total_alerts,
            "ledger_balanced": reconciliation["balanced"],
        },
    }
