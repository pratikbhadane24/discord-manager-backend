"""Pytest configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def test_token():
    """Create a test JWT token."""
    return create_access_token(data={"sub": "test_user", "user_id": 1})


@pytest.fixture
def auth_headers(test_token):
    """Create authorization headers with test token."""
    return {"Authorization": f"Bearer {test_token}"}
