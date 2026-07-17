"""
Budget router tests.

Covers:
- Create a budget (200)
- Updating an existing budget for the same category (upsert)
- List budgets returns only the authenticated user's data
- Invalid payload rejection: zero/negative limit_amount, missing required fields
- Ownership enforcement: user A cannot see user B's budgets
"""
import pytest

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL    = "/api/v1/auth/login"
BUDGET_URL   = "/api/v1/budgets/"

USER_A = {"email": "alice_b@example.com", "full_name": "Alice B", "password": "AlicePass1!", "currency": "SAR"}
USER_B = {"email": "bob_b@example.com",   "full_name": "Bob B",   "password": "BobPass1!",   "currency": "SAR"}

VALID_BUDGET = {
    "category": "Groceries",
    "limit_amount": 500.00,
    "period": "monthly",
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
# Create / upsert
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_budget_success(client):
    """A valid budget payload is accepted and the budget is returned."""
    token = await _register_and_login(client, USER_A)
    resp = await client.post(BUDGET_URL, json=VALID_BUDGET, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["category"] == VALID_BUDGET["category"]
    assert body["limit_amount"] == VALID_BUDGET["limit_amount"]
    assert body["period"] == VALID_BUDGET["period"]
    assert "id" in body
    assert "user_id" in body


@pytest.mark.asyncio
async def test_create_budget_upserts_existing_category(client):
    """POSTing a second budget for the same category updates the existing record."""
    token = await _register_and_login(client, USER_A)
    await client.post(BUDGET_URL, json=VALID_BUDGET, headers=_auth(token))

    updated = {**VALID_BUDGET, "limit_amount": 750.00}
    resp = await client.post(BUDGET_URL, json=updated, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["limit_amount"] == 750.00

    # Confirm there is still only one budget for this category.
    list_resp = await client.get(BUDGET_URL, headers=_auth(token))
    groceries = [b for b in list_resp.json() if b["category"] == "Groceries"]
    assert len(groceries) == 1


@pytest.mark.asyncio
async def test_create_budget_zero_amount_rejected(client):
    """A limit_amount of 0 violates gt=0 and must return 422."""
    token = await _register_and_login(client, USER_A)
    payload = {**VALID_BUDGET, "limit_amount": 0}
    resp = await client.post(BUDGET_URL, json=payload, headers=_auth(token))
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_budget_negative_amount_rejected(client):
    """A negative limit_amount must be rejected with 422."""
    token = await _register_and_login(client, USER_A)
    payload = {**VALID_BUDGET, "limit_amount": -100}
    resp = await client.post(BUDGET_URL, json=payload, headers=_auth(token))
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_budget_missing_category_rejected(client):
    """Omitting 'category' must return 422."""
    token = await _register_and_login(client, USER_A)
    payload = {k: v for k, v in VALID_BUDGET.items() if k != "category"}
    resp = await client.post(BUDGET_URL, json=payload, headers=_auth(token))
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_budget_missing_limit_amount_rejected(client):
    """Omitting 'limit_amount' must return 422."""
    token = await _register_and_login(client, USER_A)
    payload = {k: v for k, v in VALID_BUDGET.items() if k != "limit_amount"}
    resp = await client.post(BUDGET_URL, json=payload, headers=_auth(token))
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_budget_requires_auth(client):
    """Creating a budget without a token must return 401."""
    resp = await client.post(BUDGET_URL, json=VALID_BUDGET)
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# Read / List
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_budgets_returns_own_data(client):
    """Listing budgets returns only the authenticated user's records."""
    token = await _register_and_login(client, USER_A)
    await client.post(BUDGET_URL, json=VALID_BUDGET, headers=_auth(token))

    resp = await client.get(BUDGET_URL, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) >= 1
    assert all(b["category"] for b in items)


@pytest.mark.asyncio
async def test_list_budgets_requires_auth(client):
    """Listing budgets without a token must return 401."""
    resp = await client.get(BUDGET_URL)
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# Ownership enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_b_cannot_see_user_a_budgets(client):
    """User B's budget list must not contain any of user A's records."""
    token_a = await _register_and_login(client, USER_A)
    await client.post(BUDGET_URL, json=VALID_BUDGET, headers=_auth(token_a))

    token_b = await _register_and_login(client, USER_B)
    resp = await client.get(BUDGET_URL, headers=_auth(token_b))
    assert resp.status_code == 200, resp.text
    # User B has created no budgets; their list must be empty.
    assert resp.json() == []
