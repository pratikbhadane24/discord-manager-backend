"""Tests for authentication and authorization."""

from datetime import timedelta

import pytest

from app.core.security import create_access_token, decode_access_token


def test_create_access_token():
    """Test creating a JWT access token."""
    data = {"sub": "test_user", "user_id": "1"}
    token = create_access_token(data)
    assert isinstance(token, str)
    assert len(token) > 0


def test_decode_valid_token():
    """Test decoding a valid JWT token."""
    data = {"sub": "test_user", "user_id": "1"}
    token = create_access_token(data)
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "test_user"
    assert decoded["user_id"] == "1"


def test_decode_invalid_token():
    """Test decoding an invalid JWT token."""
    invalid_token = "invalid.token.here"
    decoded = decode_access_token(invalid_token)
    assert decoded is None


def test_create_access_token_with_expires_delta():
    """create_access_token respects an explicit expires_delta."""
    data = {"sub": "test_user"}
    token = create_access_token(data, expires_delta=timedelta(hours=1))
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "test_user"


@pytest.mark.asyncio
async def test_auth_with_bearer_token(async_client, auth_headers):
    """Test authentication with Bearer token in header."""
    response = await async_client.get("/api/v1/examples", headers=auth_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_auth_without_token(async_client):
    """Test authentication without token fails."""
    response = await async_client.get("/api/v1/examples")
    assert response.status_code == 401
    data = response.json()
    assert "Not authenticated" in data["detail"]


@pytest.mark.asyncio
async def test_auth_with_invalid_token(async_client):
    """Test authentication with invalid token fails."""
    headers = {"Authorization": "Bearer invalid_token"}
    response = await async_client.get("/api/v1/examples", headers=headers)
    assert response.status_code == 401
