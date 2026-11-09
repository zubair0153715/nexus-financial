"""Account routes: create / get / list the caller's own accounts."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.accounts.service import create_account, get_account, list_accounts
from app.auth.routes import get_current_user
from app.core.constants import envelope
from app.core.store import get_store

router = APIRouter(tags=["accounts"])


class CreateAccountBody(BaseModel):
    name: str
    initial_balance_paisa: int = 0


def _own_account(store, account_id: str, user_id: str):
    account = get_account(store, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    if account["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="not your account")
    return account


@router.post("", status_code=201)
def create(body: CreateAccountBody, store=Depends(get_store), user=Depends(get_current_user)):
    try:
        account = create_account(
            store, user["id"], body.name, body.initial_balance_paisa
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return envelope(True, account=account)


@router.get("")
def list_mine(store=Depends(get_store), user=Depends(get_current_user)):
    return envelope(True, accounts=list_accounts(store, user["id"]))


@router.get("/{account_id}")
def get_one(account_id: str, store=Depends(get_store), user=Depends(get_current_user)):
    return envelope(True, account=_own_account(store, account_id, user["id"]))
