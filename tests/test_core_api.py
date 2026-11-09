"""Core API tests: disclaimer on every response (header + envelope field),
full happy-path flow, admin read-only surface."""

from app.core.constants import DISCLAIMER, DISCLAIMER_HEADER


def test_root_carries_disclaimer_header_and_field(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["X-Nexus-Prototype"] == DISCLAIMER_HEADER
    body = resp.json()
    assert body["ok"] is True
    assert body["disclaimer"] == DISCLAIMER


def test_every_core_response_carries_disclaimer(client, funded):
    headers, sender, receiver = funded
    probes = [
        ("GET", "/accounts", headers),
        ("GET", f"/ledger/balance/{sender['id']}", headers),
        ("GET", f"/ledger/statement/{sender['id']}", headers),
        ("GET", "/audit/events", headers),
        ("GET", "/audit/verify", headers),
        ("GET", "/admin/users", headers),
        ("GET", "/admin/accounts", headers),
        ("GET", "/admin/transactions", headers),
        ("GET", "/admin/audit", headers),
    ]
    for method, path, hdrs in probes:
        resp = client.request(method, path, headers=hdrs)
        assert resp.status_code == 200, path
        assert resp.headers["X-Nexus-Prototype"] == DISCLAIMER_HEADER, path
        assert resp.json()["disclaimer"] == DISCLAIMER, path


def test_error_responses_also_carry_disclaimer(client):
    resp = client.get("/accounts")
    assert resp.status_code == 401
    assert resp.headers["X-Nexus-Prototype"] == DISCLAIMER_HEADER
    assert resp.json()["ok"] is False
    assert resp.json()["disclaimer"] == DISCLAIMER


def test_full_flow_register_to_statement(client):
    from tests.conftest import register_login

    headers, _uid = register_login(client)
    acct = client.post(
        "/accounts",
        json={"name": "Main", "initial_balance_paisa": 50_000},
        headers=headers,
    ).json()["account"]
    assert acct["currency"] == "PKR-TEST"
    assert acct["balance_paisa"] == 50_000
    assert isinstance(acct["balance_paisa"], int)
    other = client.post(
        "/accounts", json={"name": "Pocket"}, headers=headers
    ).json()["account"]
    tx = client.post(
        "/ledger/transfer",
        json={
            "from_account_id": acct["id"],
            "to_account_id": other["id"],
            "amount_paisa": 12_345,
            "memo": "full flow",
        },
        headers=headers,
    ).json()["transaction"]
    assert tx["amount_paisa"] == 12_345
    bal = client.get(f"/ledger/balance/{acct['id']}", headers=headers).json()
    assert bal["balance_paisa"] == 50_000 - 12_345
    stmt = client.get(f"/ledger/statement/{other['id']}", headers=headers).json()
    assert len(stmt["entries"]) == 1
    assert stmt["entries"][0]["type"] == "credit"
    assert client.get("/audit/verify", headers=headers).json()["valid"] is True


def test_accounts_create_get_list(client, funded):
    headers, sender, receiver = funded
    got = client.get(f"/accounts/{sender['id']}", headers=headers).json()
    assert got["account"]["id"] == sender["id"]
    listed = client.get("/accounts", headers=headers).json()
    assert {a["id"] for a in listed["accounts"]} == {sender["id"], receiver["id"]}
    assert client.get("/accounts/nope", headers=headers).status_code == 404
    bad = client.post(
        "/accounts",
        json={"name": "Bad", "initial_balance_paisa": -1},
        headers=headers,
    )
    assert bad.status_code == 400


def test_admin_lists_data_and_has_no_mutation_endpoints(client, funded):
    headers, sender, receiver = funded
    users = client.get("/admin/users", headers=headers).json()
    assert len(users["users"]) == 1
    assert "password_hash" not in str(users["users"])
    accounts = client.get("/admin/accounts", headers=headers).json()
    assert len(accounts["accounts"]) == 2
    txs = client.get("/admin/transactions", headers=headers).json()
    assert txs["transactions"] == []
    # Read-only: POST/PUT/DELETE on admin paths must not exist.
    for method in ("POST", "PUT", "DELETE"):
        resp = client.request(method, "/admin/users", headers=headers)
        assert resp.status_code == 405, method
