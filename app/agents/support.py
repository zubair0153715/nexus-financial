"""Support agent (advisory only).

Read-only: answers from the supplied context dict + a small built-in FAQ.
It NEVER invents a balance, account, or transaction — if the context does
not contain the answer, it says "I don't know".
"""

_FAQ = {
    "what is nexus": (
        "NEXUS FINANCIAL is a Stage 1 prototype — not a bank, not licensed, "
        "no real money. All funds shown are simulated PKR test units."
    ),
    "is this a bank": (
        "No. NEXUS FINANCIAL is a prototype — not a bank and not licensed. "
        "No real money is involved."
    ),
    "real money": (
        "No real money is involved. This prototype uses simulated PKR test "
        "units only."
    ),
    "how do i create a wallet": (
        "Use the wallet creation endpoint (/wallet/create). You receive a "
        "testnet address (tnx1...) and a private key — keep the private key "
        "safe; it is shown once and never stored."
    ),
    "forgot password": (
        "I don't know — password recovery is not part of this prototype. "
        "Please contact the administrator."
    ),
}


def answer(question: str, context: dict) -> str:
    """Answer a question from read-only context + FAQ; never invents data."""
    context = context or {}
    q = (question or "").strip().lower()

    # Balance / account questions: only from supplied context, never invented.
    if "balance" in q:
        if "balance_paisa" in context:
            name = context.get("account_name") or "your account"
            return (
                f"The balance of {name} is {int(context['balance_paisa'])} paisa "
                f"(simulated PKR test units)."
            )
        return (
            "I don't know — no balance was provided for your account. "
            "Please supply the account context and ask again."
        )
    if "statement" in q or "transactions" in q or "history" in q:
        entries = context.get("statement")
        if entries is None:
            return (
                "I don't know — no statement was provided. "
                "Please supply the statement context and ask again."
            )
        if not entries:
            return "Your statement is empty — no transactions were provided."
        lines = [f"- {e}" for e in entries]
        return "Your recent transactions:\n" + "\n".join(lines)
    if "account" in q:
        if "account_name" in context:
            return f"Your account is '{context['account_name']}'."
        return "I don't know — no account information was provided."

    for key, text in _FAQ.items():
        if key in q:
            return text
    return (
        "I don't know — I can only answer from the information provided "
        "and the prototype FAQ. Please rephrase or provide more context."
    )
