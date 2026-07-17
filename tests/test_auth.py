"""
Auth-flow regression tests.

Covers:
- Successful user registration
- Duplicate-email rejection on registration
- Login with correct credentials (returns JWT)
- Login with wrong password (returns 401)
- GET /auth/me with a valid token (returns user profile)
- GET /auth/me without a token (returns 401)
"""
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"

BASE_USER = {
    "email": "testuser@example.com",
    "full_name": "Test User",
    "password": "StrongPass123!",
    "currency": "SAR",
}


async def _register(client, payload=None):
    """Register a user and return the response."""
    return await client.post(REGISTER_URL, json=payload or BASE_USER)


async def _login(client, email=None, password=None):
    """Log in and return the response."""
    return await client.post(LOGIN_URL, json={
        "email": email or BASE_USER["email"],
        "password": password or BASE_USER["password"],
    })


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_success(client):
    """A new user can register and the response contains user details."""
    resp = await _register(client)
    assert resp.status_code == 201, resp.text

    body = resp.json()
    assert body["email"] == BASE_USER["email"]
    assert body["full_name"] == BASE_USER["full_name"]
    assert body["currency"] == BASE_USER["currency"]
    # Password must never be returned
    assert "password" not in body
    assert "hashed_password" not in body
    assert "id" in body


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    """Registering the same email twice returns HTTP 400."""
    await _register(client)                        # first registration
    resp = await _register(client)                 # duplicate
    assert resp.status_code == 400, resp.text


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_correct_credentials(client):
    """A registered user can log in and receives an access token."""
    await _register(client)
    resp = await _login(client)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    # The response also contains the user object
    assert body["user"]["email"] == BASE_USER["email"]


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    """Logging in with the wrong password returns HTTP 401."""
    await _register(client)
    resp = await _login(client, password="WrongPassword!")
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_login_unknown_email(client):
    """Logging in with an email that was never registered returns HTTP 401."""
    resp = await _login(client, email="nobody@example.com")
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# /auth/me protected endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_me_with_valid_token(client):
    """A valid Bearer token lets the user fetch their own profile."""
    await _register(client)
    login_resp = await _login(client)
    token = login_resp.json()["access_token"]

    resp = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["email"] == BASE_USER["email"]
    assert body["full_name"] == BASE_USER["full_name"]


@pytest.mark.asyncio
async def test_get_me_without_token(client):
    """Calling /auth/me without a token returns HTTP 401."""
    resp = await client.get(ME_URL)
    assert resp.status_code == 401, resp.text
