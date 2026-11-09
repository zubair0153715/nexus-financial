# NEXUS FINANCIAL — Stage 1 Architecture Spec (coordinator's contract)

Stage 1 = financial-core prototype ONLY. Software-only, simulated PKR test
units, testnet-only wallet, advisory-only AI agents. NO real money anywhere.

## Locked decisions
1. Scope: complete hybrid (crypto wallet + digital bank + wallet) as ONE modular
   monolith first; microservices later only where validated.
2. Custody: NON-custodial initially (user holds keys; testnet only).
3. Objective: prototype → licensing → launch. Licensing is Stage 4, his call.

## Hard guards (code must enforce, not just comment)
- Every HTML page and every JSON response carries the prototype disclaimer:
  "PROTOTYPE — NOT a bank, NOT licensed, NO real money. Simulated funds only."
  FastAPI: add it as an `X-Nexus-Prototype` response header + a `disclaimer`
  field in JSON envelopes.
- AI agents NEVER move money: agents are pure functions over plain data
  (dicts/lists). They take data in, return findings out. They never receive
  the store, never mutate anything, never touch private keys. Tests must prove
  the store is byte-identical after agent runs.
- No real-money code paths: no fiat rails, no mainnet endpoints/chain IDs,
  no payment-gateway calls. A test must assert no mainnet strings exist in
  the wallet module.
- Money rules (ledger): every transaction is balanced (sum of debits == sum of
  credits, in integer minor units — paisa, never floats); no account may go
  negative; idempotency key → same key returns the original transaction,
  never a second one; audit log is hash-chained (each event hashes the
  previous event's hash) and `verify_chain()` must pass end-to-end.
- No new dependencies. Allowed: Python 3.12 stdlib + fastapi, uvicorn,
  pydantic, httpx, cryptography (all already in ~/workspace/.venv-fc).
  Passwords: `hashlib.pbkdf2_hmac`. TOTP: stdlib `hmac`/`hashlib` (RFC 6238),
  do NOT add pyotp. Keys: `cryptography` EC SECP256K1.
- Test runner: `~/workspace/.venv-fc/bin/python -m pytest tests/ -q`.
  App runner: `~/workspace/.venv-fc/bin/python -m uvicorn app.main:app`.

## Data model (JSON store, one file, atomic write)
`app/core/store.py` — class `Store(path)`:
- `data` dict with keys: `users`, `accounts`, `ledger_entries`,
  `audit_events`, `wallets`, `idempotency` (key -> transaction id).
- Methods: `load()`, `save()` (write temp + rename), `get(key)`,
  `append(collection, record)`.
- Money is integer paisa (PKR test units). Account record:
  `{"id","user_id","name","currency":"PKR-TEST","balance_paisa":int,
  "created_at":iso}`.
- Ledger entry: `{"id","tx_id","account_id","type":"debit"|"credit",
  "amount_paisa":int,"counterparty_account_id","memo","created_at":iso}`.
  A transfer = 2 entries sharing one `tx_id` (debit sender, credit
  receiver), equal amounts.
- Audit event: `{"seq":int,"event","actor","details":dict,
  "prev_hash":str,"hash":str,"created_at":iso}` where
  `hash = sha256(prev_hash + canonical_json(event-without-hash))`.

## File ownership (do NOT write files owned by the other child)
- CHILD A (core) owns: `app/__init__.py`, `app/main.py`,
  `app/core/`, `app/auth/`, `app/accounts/`, `app/ledger/`,
  `app/audit/`, `app/admin/`, `tests/test_core_*.py`, `scripts/demo.py`
  (skeleton only — coordinator runs the demo), `requirements.txt`.
- CHILD B (wallet + agents) owns: `app/wallet/`, `app/agents/`,
  `tests/test_wallet.py`, `tests/test_agents.py`.
- Coordinator owns integration: `app/main.py` router includes for wallet/agents,
  final README, GitHub push, demo run, memory log.

## Interfaces Child A must expose (Child B codes against these exact names)
- `from app.core.store import Store` — `Store(path)`; `.data` dict;
  `.save()`; `.append(collection, record)`.
- `from app.ledger.service import post_transfer(store, from_account_id,
  to_account_id, amount_paisa, memo, idempotency_key) -> dict`
  (the transaction record; raises `ValueError` on bad input/negative
  balance/unknown account; returns existing tx on duplicate key).
- `from app.ledger.service import get_balance(store, account_id) -> int`,
  `get_statement(store, account_id) -> list[dict]`.
- `from app.audit.service import log_event(store, event, actor, details)
  -> dict`, `verify_chain(store) -> bool`.
- `app/main.py`: `create_app(store_path=None) -> FastAPI`, module-level
  `app = create_app()`. Every route returns JSON envelope
  `{"ok":bool, "disclaimer": DISCLAIMER, ...}` or HTML with the disclaimer
  banner. `DISCLAIMER` constant lives in `app/core/constants.py`:
  `"PROTOTYPE — NOT a bank, NOT licensed, NO real money. Simulated funds only."`
- Auth: `app/auth/service.py` — `hash_password(pw) -> str`,
  `verify_password(pw, hashed) -> bool`, `create_user(store, email, pw)`,
  `authenticate(store, email, pw) -> dict|None`,
  `totp_secret() -> str`, `totp_code(secret, at=None) -> str`,
  `verify_totp(secret, code) -> bool`, `issue_token(store, user_id) -> str`
  (opaque `secrets.token_urlsafe` token stored server-side).

## Interfaces Child B must expose
- `app/wallet/keys.py`: `generate_keypair() -> {"private_key_hex",
  "public_key_hex", "address"}`, `address_from_public_key(pub_hex) -> str`
  (testnet address, prefix `tnx1`, derived via sha256 — document that this
  is a TESTNET-ONLY derivation, not mainnet-compatible),
  `sign_message(priv_hex, message) -> str`, `verify_signature(pub_hex,
  message, sig) -> bool`. NO mainnet chain id, endpoint, or address format
  anywhere (a test asserts this).
- `app/wallet/service.py`: `create_wallet(store, user_id, label) -> dict`
  (stores ONLY public key + address; private key is returned ONCE to the
  caller and NEVER persisted), `list_wallets(store, user_id) -> list`,
  `record_testnet_tx(store, wallet_id, tx) -> dict` (monitoring stub:
  records a testnet tx observation, no broadcasting).
- `app/agents/fraud.py`: `score_transaction(tx: dict) -> {"score":0-100,
  "reasons":[...], "action":"allow"|"flag"|"request_hold"}` — pure rules
  (amount thresholds, velocity, new counterparty, round amounts). Advisory
  only: it returns an action recommendation; it never holds/freeze anything.
- `app/agents/support.py`: `answer(question: str, context: dict) -> str` —
  answers account/balance/statement questions from supplied read-only
  context + a small built-in FAQ; never invents balances; says "I don't
  know" when context lacks the answer.
- `app/agents/compliance.py`: `scan_account(account, transactions) ->
  list[dict]` — KYC/AML alert rules (missing KYC flag, large/split
  transactions, high-risk memo keywords). Returns alerts, never blocks.
- `app/agents/finance.py`: `reconciliation_report(ledger_entries) ->
  {"balanced":bool, "total_debits":int, "total_credits":int,
  "differences":[...]}` — recomputes debits vs credits per tx_id.
- `app/agents/orchestrator.py`: `run_daily_checks(store) -> dict` —
  runs fraud scoring over recent txs + compliance scans + reconciliation and
  returns one combined advisory report. Takes the store as READ-ONLY input
  (it must not call store.save() — a test asserts the store file is
  unchanged after a run).
- `app/wallet/routes.py` + `app/agents/routes.py`: FastAPI routers with
  prefix `/wallet` and `/agents`, using the same JSON envelope + disclaimer.
  Routers must import core lazily/relatively and must NOT import
  `app.main` (no circular import).

## Tests required (exact invariants)
- Ledger: debits == credits per tx; no negative balance (attempt raises);
  idempotency (same key, one tx); statement lists entries in order.
- Audit: `verify_chain()` True after N events; tampering with any event
  makes it False.
- Auth: wrong password fails; TOTP code verifies within ±1 step, wrong code
  fails; token authenticates.
- Wallet: keypair round-trips (sign/verify); address starts `tnx1`;
  private key never in store after `create_wallet`; no "mainnet" string in
  `app/wallet/`.
- Agents: fraud flags a huge/velocity tx; support never invents a balance;
  compliance raises an alert on a split pattern; reconciliation reports
  balanced True on good data and lists the bad tx on tampered data;
  `run_daily_checks` leaves the store file byte-identical.

## Legal reality (README must state honestly)
- Full digital bank → SBP digital-bank licence.
- Digital wallet / e-money → SBP EMI licence.
- Payment processing → SBP PSO/PSP authorization. PSOs/PSPs are NOT
  custodians and cannot perform banking functions.
- Crypto exchange / custody → PVARA VASP licensing under the Pakistan
  Virtual Assets Act 2026.
- Prototype first; licensing/partnerships are Stage 4, his decision.

## Do NOT do
- Do NOT commit anything (coordinator pushes). Do NOT touch MEMORY.md
  (coordinator logs). Do NOT deploy. Do NOT add dependencies. Do NOT write
  files owned by the other child. Do NOT invent balances, users, or tx data
  in the demo — the demo script uses only what the run creates.
