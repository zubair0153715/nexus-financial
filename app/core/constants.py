"""Core constants for NEXUS FINANCIAL Stage 1 prototype."""

DISCLAIMER = "PROTOTYPE — NOT a bank, NOT licensed, NO real money. Simulated funds only."

# HTTP headers are latin-1 only, so the header carries the same wording with
# an ASCII hyphen in place of the em dash. The JSON envelope carries the
# exact DISCLAIMER above.
DISCLAIMER_HEADER = "PROTOTYPE - NOT a bank, NOT licensed, NO real money. Simulated funds only."


def envelope(ok: bool, **fields) -> dict:
    """Standard JSON envelope: every response carries the disclaimer."""
    return {"ok": ok, "disclaimer": DISCLAIMER, **fields}
