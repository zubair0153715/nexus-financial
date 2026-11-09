"""NEXUS FINANCIAL — Stage 1 prototype.

FastAPI modular monolith. Every response carries the prototype disclaimer
as an X-Nexus-Prototype header and a `disclaimer` field in the JSON envelope.
Simulated funds only — no real money anywhere.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.accounts import routes as accounts_routes
from app.admin import routes as admin_routes
from app.agents import routes as agents_routes
from app.audit import routes as audit_routes
from app.auth import routes as auth_routes
from app.core.constants import DISCLAIMER_HEADER, envelope
from app.core.store import Store
from app.ledger import routes as ledger_routes
from app.wallet import routes as wallet_routes

DEFAULT_STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "nexus.json"


def create_app(store_path=None) -> FastAPI:
    store = Store(store_path if store_path is not None else DEFAULT_STORE_PATH)
    store.load()

    app = FastAPI(title="NEXUS FINANCIAL — Stage 1 Prototype")
    app.state.store = store

    @app.middleware("http")
    async def add_prototype_header(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Nexus-Prototype"] = DISCLAIMER_HEADER
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope(False, error=exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=envelope(False, error="validation error", details=exc.errors()),
        )

    @app.get("/")
    def root():
        return envelope(
            True,
            service="NEXUS FINANCIAL",
            stage="Stage 1 prototype",
            currency="PKR-TEST (simulated units only)",
        )

    app.include_router(auth_routes.router, prefix="/auth")
    app.include_router(accounts_routes.router, prefix="/accounts")
    app.include_router(ledger_routes.router, prefix="/ledger")
    app.include_router(audit_routes.router, prefix="/audit")
    app.include_router(admin_routes.router, prefix="/admin")

    # Wallet + agents routers (wired by coordinator; both take the store
    # read-only/advisory — agents never move money, wallet is testnet-only).
    # NOTE: these routers already carry their own prefix=, so include them
    # WITHOUT an extra prefix (else paths double up: /wallet/wallet/...).
    wallet_routes.set_store(store)
    agents_routes.set_store(store)
    app.include_router(wallet_routes.router)
    app.include_router(agents_routes.router)

    return app


app = create_app()
