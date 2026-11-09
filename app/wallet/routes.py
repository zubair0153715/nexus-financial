"""Wallet routes (Stage 1 prototype). Prefix /wallet.

Same JSON envelope + disclaimer header as core. The store is injected via
``set_store`` (called by the coordinator in ``create_app``); this module
never imports ``app.main`` (no circular import).
"""

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from app.wallet import service as wallet_service

try:
    from app.core.constants import DISCLAIMER
except Exception:  # core not built yet; same literal as the contract
    DISCLAIMER = "PROTOTYPE — NOT a bank, NOT licensed, NO real money. Simulated funds only."
# HTTP headers are latin-1 only: the em dash in DISCLAIMER is not encodable,
# so the header carries the ASCII-safe form; JSON keeps the exact string.
HEADER_DISCLAIMER = DISCLAIMER.replace("—", "-")

router = APIRouter(prefix="/wallet", tags=["wallet"])

_STORE = None


def set_store(store) -> None:
    global _STORE
    _STORE = store


def _get_store():
    if _STORE is None:
        raise RuntimeError("wallet store not configured; coordinator must call set_store()")
    return _STORE


def _envelope(response: Response, **data):
    response.headers["X-Nexus-Prototype"] = HEADER_DISCLAIMER
    return {"ok": True, "disclaimer": DISCLAIMER, **data}


class CreateWalletRequest(BaseModel):
    user_id: str
    label: str = "default"


class TestnetTxRequest(BaseModel):
    wallet_id: str
    tx: dict = Field(default_factory=dict)


@router.post("/create")
def create_wallet(req: CreateWalletRequest, response: Response):
    wallet = wallet_service.create_wallet(_get_store(), req.user_id, req.label)
    return _envelope(response, wallet=wallet)


@router.get("/list")
def list_wallets(user_id: str, response: Response):
    wallets = wallet_service.list_wallets(_get_store(), user_id)
    return _envelope(response, wallets=wallets)


@router.post("/testnet-tx")
def record_testnet_tx(req: TestnetTxRequest, response: Response):
    try:
        observation = wallet_service.record_testnet_tx(_get_store(), req.wallet_id, req.tx)
    except ValueError as exc:
        response.headers["X-Nexus-Prototype"] = HEADER_DISCLAIMER
        return {"ok": False, "disclaimer": DISCLAIMER, "error": str(exc)}
    return _envelope(response, observation=observation)
