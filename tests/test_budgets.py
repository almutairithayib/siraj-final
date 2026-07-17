"""
Budget router tests.

Covers:
- Create a budget (200)
- Updating an existing budget for the same category (upsert)
- List budgets returns only the authenticated user's data
- Invalid payload rejection: zero/negative limit_amount, missing required fields
- Ownership enforcement: user A cannot see user B's budgets
- Analysis endpoint: zero-spend, income exclusion, cross-user isolation, math accuracy
"""
import pytest

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL    = "/api/v1/auth/login"
BUDGET_URL   = "/api/v1/budgets/"
ANALYSIS_URL = "/api/v1/budgets/analysis"
TXN_URL      = "/api/v1/transactions/"

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


# ---------------------------------------------------------------------------
# Analysis endpoint
# ---------------------------------------------------------------------------

# Unique users to avoid collisions with other test users sharing the same DB session.
USER_ANA_A = {"email": "ana_alice@example.com", "full_name": "Ana Alice", "password": "AlicePass1!", "currency": "SAR"}
USER_ANA_B = {"email": "ana_bob@example.com",   "full_name": "Ana Bob",   "password": "BobPass1!",   "currency": "SAR"}

# A date safely within the current month (July 2026) so the analysis query captures it.
THIS_MONTH_DATE = "2026-07-10"


@pytest.mark.asyncio
async def test_analysis_zero_transactions(client):
    """A budget with no matching transactions reports spent_amount=0 and percentage_spent=0."""
    token = await _register_and_login(client, USER_ANA_A)

    # Create a budget but add no transactions.
    await client.post(BUDGET_URL, json={"category": "Utilities", "limit_amount": 200.0, "period": "monthly"}, headers=_auth(token))

    resp = await client.get(ANALYSIS_URL, headers=_auth(token))
    assert resp.status_code == 200, resp.text

    items = resp.json()
    utilities = next((i for i in items if i["category"] == "Utilities"), None)
    assert utilities is not None, "Utilities budget must appear in analysis"
    assert utilities["spent_amount"] == 0.0
    assert utilities["percentage_spent"] == 0.0
    assert utilities["remaining_amount"] == 200.0


@pytest.mark.asyncio
async def test_analysis_income_transactions_excluded(client):
    """Income-type transactions in the same category must not count toward spent_amount."""
    token = await _register_and_login(client, USER_ANA_A)

    category = "Freelance"
    await client.post(BUDGET_URL, json={"category": category, "limit_amount": 1000.0, "period": "monthly"}, headers=_auth(token))

    # Add an income transaction in the same category.
    await client.post(TXN_URL, json={
        "amount": 500.0,
        "category": category,
        "type": "income",
        "description": "Client payment",
        "transaction_date": THIS_MONTH_DATE,
    }, headers=_auth(token))

    resp = await client.get(ANALYSIS_URL, headers=_auth(token))
    assert resp.status_code == 200, resp.text

    items = resp.json()
    freelance = next((i for i in items if i["category"] == category), None)
    assert freelance is not None
    assert freelance["spent_amount"] == 0.0, "Income transactions must not inflate spent_amount"
    assert freelance["percentage_spent"] == 0.0


@pytest.mark.asyncio
async def test_analysis_cross_user_isolation(client):
    """User A's expense transactions must not appear in User B's budget analysis."""
    token_a = await _register_and_login(client, USER_ANA_A)
    token_b = await _register_and_login(client, USER_ANA_B)

    shared_category = "Transport"

    # Both users have a budget in the same category.
    await client.post(BUDGET_URL, json={"category": shared_category, "limit_amount": 300.0, "period": "monthly"}, headers=_auth(token_a))
    await client.post(BUDGET_URL, json={"category": shared_category, "limit_amount": 300.0, "period": "monthly"}, headers=_auth(token_b))

    # Only User A posts an expense transaction.
    await client.post(TXN_URL, json={
        "amount": 120.0,
        "category": shared_category,
        "type": "expense",
        "description": "Taxi",
        "transaction_date": THIS_MONTH_DATE,
    }, headers=_auth(token_a))

    # User A's analysis should show spending.
    resp_a = await client.get(ANALYSIS_URL, headers=_auth(token_a))
    item_a = next(i for i in resp_a.json() if i["category"] == shared_category)
    assert item_a["spent_amount"] == 120.0

    # User B's analysis must show zero — not bleed in User A's transaction.
    resp_b = await client.get(ANALYSIS_URL, headers=_auth(token_b))
    item_b = next(i for i in resp_b.json() if i["category"] == shared_category)
    assert item_b["spent_amount"] == 0.0, "User A's spending must not appear in User B's analysis"


@pytest.mark.asyncio
async def test_analysis_calculations_are_correct(client):
    """spent_amount, remaining_amount, and percentage_spent are numerically accurate."""
    token = await _register_and_login(client, USER_ANA_A)

    limit = 400.0
    category = "Entertainment"
    await client.post(BUDGET_URL, json={"category": category, "limit_amount": limit, "period": "monthly"}, headers=_auth(token))

    # Add two expense transactions that together total 100.
    for amount in [60.0, 40.0]:
        await client.post(TXN_URL, json={
            "amount": amount,
            "category": category,
            "type": "expense",
            "description": "expense",
            "transaction_date": THIS_MONTH_DATE,
        }, headers=_auth(token))

    resp = await client.get(ANALYSIS_URL, headers=_auth(token))
    assert resp.status_code == 200, resp.text

    item = next(i for i in resp.json() if i["category"] == category)
    assert item["spent_amount"] == 100.0
    assert item["remaining_amount"] == pytest.approx(300.0)
    assert item["percentage_spent"] == pytest.approx(25.0)
