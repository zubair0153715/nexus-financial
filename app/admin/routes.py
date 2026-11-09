"""Admin routes: READ-ONLY listings. No mutation endpoints exist here."""

from fastapi import APIRouter, Depends

from app.auth.routes import get_current_user
from app.auth.service import public_user
from app.core.constants import envelope
from app.core.store import get_store

router = APIRouter(tags=["admin"])


@router.get("/users")
def list_users(store=Depends(get_store), user=Depends(get_current_user)):
    return envelope(True, users=[public_user(u) for u in store.data["users"]])


@router.get("/accounts")
def list_accounts(store=Depends(get_store), user=Depends(get_current_user)):
    return envelope(True, accounts=store.data["accounts"])


@router.get("/transactions")
def list_transactions(store=Depends(get_store), user=Depends(get_current_user)):
    return envelope(True, transactions=store.data["ledger_entries"])


@router.get("/audit")
def list_audit(store=Depends(get_store), user=Depends(get_current_user)):
    return envelope(True, events=store.data["audit_events"])
