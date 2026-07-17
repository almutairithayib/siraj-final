"""
Transaction router tests.

Covers:
- Create a transaction (201)
- List transactions returns only the authenticated user's data
- Invalid payload rejection: zero/negative amount, missing required fields
- Ownership enforcement: user A cannot see or delete user B's transactions
"""
import pytest

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL    = "/api/v1/auth/login"
TXN_URL      = "/api/v1/transactions/"

USER_A = {"email": "alice@example.com", "full_name": "Alice", "password": "AlicePass1!", "currency": "SAR"}
USER_B = {"email": "bob@example.com",   "full_name": "Bob",   "password": "BobPass1!",   "currency": "SAR"}

VALID_TXN = {
    "amount": 150.00,
    "category": "Food",
    "type": "expense",
    "description": "Lunch",
    "transaction_date": "2026-07-17",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _register_and_login(client, user):
    await client.post(REGISTER_URL, json=user)
    resp = await client.post(LOGIN_URL, json={"email": user["email"], "password": user["password"]})
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_transaction_success(client):
    """A valid transaction is accepted and returns 201 with the saved data."""
    token = await _register_and_login(client, USER_A)
    resp = await client.post(TXN_URL, json=VALID_TXN, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["amount"] == VALID_TXN["amount"]
    assert body["category"] == VALID_TXN["category"]
    assert body["type"] == VALID_TXN["type"]
    assert "id" in body
    assert "user_id" in body


@pytest.mark.asyncio
async def test_create_transaction_zero_amount_rejected(client):
    """An amount of 0 violates the gt=0 constraint and must return 422."""
    token = await _register_and_login(client, USER_A)
    payload = {**VALID_TXN, "amount": 0}
    resp = await client.post(TXN_URL, json=payload, headers=_auth(token))
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_transaction_negative_amount_rejected(client):
    """A negative amount must be rejected with 422."""
    token = await _register_and_login(client, USER_A)
    payload = {**VALID_TXN, "amount": -50}
    resp = await client.post(TXN_URL, json=payload, headers=_auth(token))
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_transaction_missing_category_rejected(client):
    """Omitting the required 'category' field must return 422."""
    token = await _register_and_login(client, USER_A)
    payload = {k: v for k, v in VALID_TXN.items() if k != "category"}
    resp = await client.post(TXN_URL, json=payload, headers=_auth(token))
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_transaction_missing_type_rejected(client):
    """Omitting the required 'type' field must return 422."""
    token = await _register_and_login(client, USER_A)
    payload = {k: v for k, v in VALID_TXN.items() if k != "type"}
    resp = await client.post(TXN_URL, json=payload, headers=_auth(token))
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_transaction_requires_auth(client):
    """Creating a transaction without a token must return 401."""
    resp = await client.post(TXN_URL, json=VALID_TXN)
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# Read / List
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_transactions_returns_own_data(client):
    """Listing transactions returns only the authenticated user's records."""
    token = await _register_and_login(client, USER_A)
    await client.post(TXN_URL, json=VALID_TXN, headers=_auth(token))

    resp = await client.get(TXN_URL, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) >= 1
    for item in items:
        assert item["category"] == VALID_TXN["category"]


@pytest.mark.asyncio
async def test_list_transactions_requires_auth(client):
    """Listing transactions without a token must return 401."""
    resp = await client.get(TXN_URL)
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# Ownership enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_b_cannot_see_user_a_transactions(client):
    """User B's transaction list must not contain any of user A's records."""
    token_a = await _register_and_login(client, USER_A)
    await client.post(TXN_URL, json=VALID_TXN, headers=_auth(token_a))

    token_b = await _register_and_login(client, USER_B)
    resp = await client.get(TXN_URL, headers=_auth(token_b))
    assert resp.status_code == 200, resp.text
    # User B has no transactions of their own; the list must be empty.
    assert resp.json() == []


@pytest.mark.asyncio
async def test_user_b_cannot_delete_user_a_transaction(client):
    """Attempting to delete another user's transaction must return 404."""
    token_a = await _register_and_login(client, USER_A)
    create_resp = await client.post(TXN_URL, json=VALID_TXN, headers=_auth(token_a))
    txn_id = create_resp.json()["id"]

    token_b = await _register_and_login(client, USER_B)
    del_resp = await client.delete(f"{TXN_URL}{txn_id}", headers=_auth(token_b))
    assert del_resp.status_code == 404, del_resp.text
