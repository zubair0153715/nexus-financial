"""Finance agent (advisory only).

Pure function over plain ledger entries. Recomputes debits vs credits per
``tx_id`` and reports whether the ledger is balanced.
"""


def reconciliation_report(ledger_entries: list) -> dict:
    """Reconcile ledger entries per tx_id.

    Returns {"balanced", "total_debits", "total_credits", "differences"}.
    ``differences`` lists every tx_id whose debits != credits.
    """
    per_tx: dict = {}
    total_debits = 0
    total_credits = 0
    for entry in ledger_entries or []:
        tx_id = entry.get("tx_id")
        amount = int(entry.get("amount_paisa", 0) or 0)
        bucket = per_tx.setdefault(tx_id, {"debits": 0, "credits": 0})
        if entry.get("type") == "debit":
            bucket["debits"] += amount
            total_debits += amount
        elif entry.get("type") == "credit":
            bucket["credits"] += amount
            total_credits += amount

    differences = [
        {
            "tx_id": tx_id,
            "debits": sums["debits"],
            "credits": sums["credits"],
            "difference": sums["debits"] - sums["credits"],
        }
        for tx_id, sums in per_tx.items()
        if sums["debits"] != sums["credits"]
    ]
    return {
        "balanced": total_debits == total_credits and not differences,
        "total_debits": total_debits,
        "total_credits": total_credits,
        "differences": differences,
    }
