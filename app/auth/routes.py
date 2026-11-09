"""Auth routes: POST /auth/register, /auth/login, /auth/mfa/verify.

Flow: register (returns the TOTP secret once, for enrollment) ->
login with password (returns mfa_required) -> MFA verify with the
6-digit TOTP code (returns the opaque session token).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.service import (
    authenticate,
    create_user,
    get_user_by_id,
    issue_token,
    user_from_token,
    verify_totp,
)
from app.core.constants import envelope
from app.core.store import get_store

router = APIRouter(tags=["auth"])


class RegisterBody(BaseModel):
    email: str
    password: str


class LoginBody(BaseModel):
    email: str
    password: str


class MfaVerifyBody(BaseModel):
    user_id: str
    code: str


def get_current_user(request: Request):
    """Dependency: Bearer token -> public user dict, else 401."""
    auth = request.headers.get("Authorization", "")
    token = auth[len("Bearer ") :] if auth.startswith("Bearer ") else ""
    user = user_from_token(request.app.state.store, token)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid or missing token")
    return user


@router.post("/register", status_code=201)
def register(body: RegisterBody, store=Depends(get_store)):
    try:
        user = create_user(store, body.email, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    record = get_user_by_id(store, user["id"])
    # TOTP secret is returned exactly once, at enrollment.
    return envelope(
        True, user=user, totp_secret=record["totp_secret"], mfa_required=True
    )


@router.post("/login")
def login(body: LoginBody, store=Depends(get_store)):
    user = authenticate(store, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid email or password")
    return envelope(True, mfa_required=True, user_id=user["id"])


@router.post("/mfa/verify")
def mfa_verify(body: MfaVerifyBody, store=Depends(get_store)):
    user = get_user_by_id(store, body.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="unknown user")
    if not verify_totp(user["totp_secret"], body.code):
        raise HTTPException(status_code=401, detail="invalid TOTP code")
    token = issue_token(store, user["id"])
    return envelope(True, token=token, user_id=user["id"])
