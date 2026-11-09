"""Ledger routes: transfer, balance, statement (own accounts only)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.accounts.service import get_account
from app.auth.routes import get_current_user
from app.core.constants import envelope
from app.core.store import get_store
from app.ledger.service import get_balance, get_statement, post_transfer

router = APIRouter(tags=["ledger"])


class TransferBody(BaseModel):
    from_account_id: str
    to_account_id: str
    amount_paisa: int
    memo: str = ""
    idempotency_key: str | None = None


def _own_account(store, account_id: str, user_id: str):
    account = get_account(store, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    if account["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="not your account")
    return account


@router.post("/transfer", status_code=201)
def transfer(body: TransferBody, store=Depends(get_store), user=Depends(get_current_user)):
    _own_account(store, body.from_account_id, user["id"])
    receiver = get_account(store, body.to_account_id)
    if receiver is None:
        raise HTTPException(status_code=404, detail="account not found")
    try:
        tx = post_transfer(
            store,
            body.from_account_id,
            body.to_account_id,
            body.amount_paisa,
            memo=body.memo,
            idempotency_key=body.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return envelope(True, transaction=tx)


@router.get("/balance/{account_id}")
def balance(account_id: str, store=Depends(get_store), user=Depends(get_current_user)):
    account = _own_account(store, account_id, user["id"])
    return envelope(
        True,
        account_id=account["id"],
        currency=account["currency"],
        balance_paisa=get_balance(store, account_id),
    )


@router.get("/statement/{account_id}")
def statement(account_id: str, store=Depends(get_store), user=Depends(get_current_user)):
    _own_account(store, account_id, user["id"])
    return envelope(
        True, account_id=account_id, entries=get_statement(store, account_id)
    )
