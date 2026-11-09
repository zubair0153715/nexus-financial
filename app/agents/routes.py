"""Agents routes (Stage 1 prototype). Prefix /agents.

Same JSON envelope + disclaimer header as core. Agents are pure functions
over the request payloads — they never receive or mutate the store, except
``/agents/daily-checks``, which passes the store read-only to the
orchestrator. The store is injected via ``set_store`` (coordinator calls it
in ``create_app``); this module never imports ``app.main``.
"""

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from app.agents import compliance, finance, fraud, orchestrator, support

try:
    from app.core.constants import DISCLAIMER
except Exception:  # core not built yet; same literal as the contract
    DISCLAIMER = "PROTOTYPE — NOT a bank, NOT licensed, NO real money. Simulated funds only."
# HTTP headers are latin-1 only: the em dash in DISCLAIMER is not encodable,
# so the header carries the ASCII-safe form; JSON keeps the exact string.
HEADER_DISCLAIMER = DISCLAIMER.replace("—", "-")

router = APIRouter(prefix="/agents", tags=["agents"])

_STORE = None


def set_store(store) -> None:
    global _STORE
    _STORE = store


def _envelope(response: Response, **data):
    response.headers["X-Nexus-Prototype"] = HEADER_DISCLAIMER
    return {"ok": True, "disclaimer": DISCLAIMER, **data}


class FraudRequest(BaseModel):
    tx: dict = Field(default_factory=dict)


class SupportRequest(BaseModel):
    question: str
    context: dict = Field(default_factory=dict)


class ComplianceRequest(BaseModel):
    account: dict = Field(default_factory=dict)
    transactions: list = Field(default_factory=list)


class ReconcileRequest(BaseModel):
    ledger_entries: list = Field(default_factory=list)


@router.post("/fraud/score")
def fraud_score(req: FraudRequest, response: Response):
    return _envelope(response, result=fraud.score_transaction(req.tx))


@router.post("/support/ask")
def support_ask(req: SupportRequest, response: Response):
    return _envelope(response, answer=support.answer(req.question, req.context))


@router.post("/compliance/scan")
def compliance_scan(req: ComplianceRequest, response: Response):
    return _envelope(response, alerts=compliance.scan_account(req.account, req.transactions))


@router.post("/finance/reconcile")
def finance_reconcile(req: ReconcileRequest, response: Response):
    return _envelope(response, report=finance.reconciliation_report(req.ledger_entries))


@router.post("/daily-checks")
def daily_checks(response: Response):
    if _STORE is None:
        response.headers["X-Nexus-Prototype"] = HEADER_DISCLAIMER
        return {"ok": False, "disclaimer": DISCLAIMER,
                "error": "agent store not configured; coordinator must call set_store()"}
    response.headers["X-Nexus-Prototype"] = HEADER_DISCLAIMER
    return orchestrator.run_daily_checks(_STORE)
