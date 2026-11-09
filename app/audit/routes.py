"""Audit routes: list events, verify the hash chain."""

from fastapi import APIRouter, Depends

from app.audit.service import verify_chain
from app.auth.routes import get_current_user
from app.core.constants import envelope
from app.core.store import get_store

router = APIRouter(tags=["audit"])


@router.get("/events")
def list_events(store=Depends(get_store), user=Depends(get_current_user)):
    return envelope(True, events=store.data["audit_events"])


@router.get("/verify")
def verify(store=Depends(get_store), user=Depends(get_current_user)):
    return envelope(True, valid=verify_chain(store))
