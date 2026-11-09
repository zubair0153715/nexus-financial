"""Fraud agent (advisory only).

Pure function over a plain transaction dict. Returns a score, reasons, and
an action RECOMMENDATION. It never holds, freezes, or blocks anything —
that decision belongs to a human / a later stage.
"""

# Amounts in integer paisa (PKR test units).
LARGE_AMOUNT_PAISA = 10_000_000       # Rs 100,000
ELEVATED_AMOUNT_PAISA = 1_000_000     # Rs 10,000
ROUND_AMOUNT_STEP_PAISA = 100_000     # Rs 1,000


def score_transaction(tx: dict) -> dict:
    """Score a transaction 0-100 and recommend allow/flag/request_hold."""
    score = 0
    reasons = []

    amount = int(tx.get("amount_paisa", 0) or 0)
    if amount >= LARGE_AMOUNT_PAISA:
        score += 40
        reasons.append(f"large amount: {amount} paisa (>= {LARGE_AMOUNT_PAISA})")
    elif amount >= ELEVATED_AMOUNT_PAISA:
        score += 20
        reasons.append(f"elevated amount: {amount} paisa (>= {ELEVATED_AMOUNT_PAISA})")

    recent_count = int(tx.get("recent_tx_count", 0) or 0)
    if recent_count >= 10:
        score += 30
        reasons.append(f"high velocity: {recent_count} recent transactions")
    elif recent_count >= 5:
        score += 15
        reasons.append(f"elevated velocity: {recent_count} recent transactions")

    if tx.get("counterparty_is_new"):
        score += 15
        reasons.append("new counterparty (no prior transactions)")

    if amount >= ROUND_AMOUNT_STEP_PAISA and amount % ROUND_AMOUNT_STEP_PAISA == 0:
        score += 10
        reasons.append("round amount (exact multiple of Rs 1,000)")

    score = min(score, 100)
    if score >= 70:
        action = "request_hold"
    elif score >= 40:
        action = "flag"
    else:
        action = "allow"
    return {"score": score, "reasons": reasons, "action": action}
