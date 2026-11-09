"""Compliance agent (advisory only).

Pure function over a plain account dict + transaction list. Returns KYC/AML
alerts; it never blocks, freezes, or approves anything.
"""

LARGE_TX_PAISA = 5_000_000  # Rs 50,000
SPLIT_COUNT = 3             # >=3 similar txs to one counterparty = split pattern
HIGH_RISK_KEYWORDS = ("casino", "gambling", "hawala", "ransom", "crypto")


def scan_account(account: dict, transactions: list) -> list:
    """Scan an account and its transactions; return a list of alerts."""
    account = account or {}
    transactions = transactions or []
    alerts = []

    if account.get("kyc_status") != "verified":
        alerts.append({
            "type": "missing_kyc",
            "severity": "high",
            "detail": f"KYC status is '{account.get('kyc_status', 'unknown')}', not 'verified'.",
        })

    for tx in transactions:
        amount = int(tx.get("amount_paisa", 0) or 0)
        if amount >= LARGE_TX_PAISA:
            alerts.append({
                "type": "large_transaction",
                "severity": "medium",
                "detail": f"Transaction {tx.get('tx_id', '?')} of {amount} paisa "
                          f">= {LARGE_TX_PAISA} paisa.",
            })
        memo = str(tx.get("memo", "")).lower()
        for keyword in HIGH_RISK_KEYWORDS:
            if keyword in memo:
                alerts.append({
                    "type": "high_risk_keyword",
                    "severity": "high",
                    "detail": f"Transaction {tx.get('tx_id', '?')} memo contains "
                              f"high-risk keyword '{keyword}'.",
                })

    # Split / structuring pattern: >=3 txs to the same counterparty with
    # amounts within 10% of each other.
    by_counterparty: dict = {}
    for tx in transactions:
        by_counterparty.setdefault(tx.get("counterparty_account_id"), []).append(tx)
    for counterparty, txs in by_counterparty.items():
        if len(txs) >= SPLIT_COUNT:
            amounts = [int(t.get("amount_paisa", 0) or 0) for t in txs]
            if amounts and max(amounts) <= min(amounts) * 1.1:
                alerts.append({
                    "type": "split_pattern",
                    "severity": "high",
                    "detail": f"{len(txs)} similar transactions ({min(amounts)}-"
                              f"{max(amounts)} paisa) to counterparty "
                              f"'{counterparty}' — possible split/structuring.",
                })

    return alerts
