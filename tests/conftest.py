"""Pytest configuration and fixtures."""

import os

# Must be set before any app modules are imported so pydantic-settings can
# validate the required JWT_SECRET_KEY field.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.core.security import create_access_token
from app.database import database as db_module


@pytest_asyncio.fixture
async def mock_db():
    """Initialise an in-memory MongoDB mock and tear it down after the test."""
    mock_client = AsyncMongoMockClient()
    await db_module.init_database(motor_client=mock_client)
    yield mock_client
    await db_module.close_database()


@pytest_asyncio.fixture
async def async_client(mock_db):
    """
    Create an async HTTPX test client with the database mock pre-initialised.

    The app lifespan is *not* invoked here – we control DB init via mock_db.
    """
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def test_token():
    """Create a test JWT token."""
    return create_access_token(
        data={"sub": "test_user", "user_id": "1", "is_admin": False}
    )


@pytest.fixture
def admin_token():
    """Create an admin JWT token."""
    return create_access_token(
        data={"sub": "admin_user", "user_id": "admin1", "is_admin": True}
    )


@pytest.fixture
def auth_headers(test_token):
    """Create authorization headers with test token."""
    return {"Authorization": f"Bearer {test_token}"}


@pytest.fixture
def admin_headers(admin_token):
    """Create authorization headers with admin token."""
    return {"Authorization": f"Bearer {admin_token}"}
