# NEXUS FINANCIAL — AI-Native Digital Finance Infrastructure (Stage 1 Prototype)

> **PROTOTYPE — NOT a bank, NOT licensed, NO real money. Simulated funds only.**

Stage 1 is the **financial core prototype**: identity + accounts + a double-entry
ledger + simulated PKR test-unit wallets + internal transfers + a hash-chained
audit log + a testnet-only wallet module + advisory-only AI agents. It is a
software-only prototype for learning and demonstration. It holds no real money,
takes no real deposits, and performs no real financial services.

## Decisions locked (Stage 1)
1. **Scope:** complete hybrid architecture (crypto wallet + digital bank +
   wallet) built as ONE modular monolith first; microservices later, only
   where validated.
2. **Custody:** NON-custodial initially — the user holds their keys; testnet only.
3. **Objective:** prototype → licensing → launch. Licensing is Stage 4.

## Legal reality in Pakistan (honest, not legal advice)
| Business | Regulatory route |
|---|---|
| Full digital bank | SBP digital-bank licence |
| Digital wallet / e-money | SBP EMI licence |
| Payment processing | SBP PSO/PSP authorization — PSOs/PSPs are NOT custodians and cannot perform banking functions |
| Crypto exchange / custody | PVARA VASP licensing under the Pakistan Virtual Assets Act 2026 |

Real customer deposits, fiat transfers, exchange, custody, or public financial
services start ONLY after the relevant licensing and partnerships exist.
Prototype first; licensing/partnerships are Stage 4.

## AI agents never move money
Agents are advisory only: fraud flagging, support answers, compliance alerts,
reconciliation reports. All money movement goes through a deterministic policy
engine — double-entry ledger, authorization checks, transaction limits,
idempotency keys, hash-chained audit log. Agents cannot touch private keys,
cannot modify balances, cannot bypass KYC, cannot raise their own permissions.

## Quickstart (prototype)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
# or run the demo: python scripts/demo.py
```

## Modules
- `app/core/` — JSON store, constants (incl. the prototype disclaimer)
- `app/auth/` — password hashing (PBKDF2), TOTP MFA (stdlib), opaque tokens
- `app/accounts/` — user accounts, PKR-TEST balances
- `app/ledger/` — double-entry transfers, statements (balanced, idempotent)
- `app/audit/` — hash-chained immutable audit log
- `app/wallet/` — testnet-only keypairs, addresses, signing (no mainnet)
- `app/agents/` — fraud, support, compliance, finance agents + orchestrator
- `app/admin/` — read-only admin views

## Tests
```bash
python -m pytest tests/ -q
```

## Stages
- **Stage 1 (this repo):** financial core prototype.
- **Stage 2:** crypto testnet wallet deepening (monitoring, signing policies).
- **Stage 3:** AI intelligence (fraud, compliance, analytics, support).
- **Stage 4:** real-world operations — regulatory applications, licensed
  partnerships, independent security audits, controlled pilot.
