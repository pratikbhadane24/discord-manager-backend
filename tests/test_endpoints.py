"""Tests for API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_root_endpoint(async_client):
    """Test the root endpoint."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "version" in data
    assert "status" in data


@pytest.mark.asyncio
async def test_health_check(async_client):
    """Test health check endpoint."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "ok"


@pytest.mark.asyncio
async def test_readiness_check(async_client):
    """Test readiness check endpoint."""
    response = await async_client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "ready"


@pytest.mark.asyncio
async def test_liveness_check(async_client):
    """Test liveness check endpoint."""
    response = await async_client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "alive"


@pytest.mark.asyncio
async def test_list_examples_without_auth(async_client):
    """Test listing examples without authentication fails."""
    response = await async_client.get("/api/v1/examples")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_examples_with_auth(async_client, auth_headers):
    """Test listing examples with authentication."""
    response = await async_client.get("/api/v1/examples", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_create_example_with_auth(async_client, auth_headers):
    """Test creating an example item with authentication."""
    item_data = {
        "name": "Test Item",
        "description": "Test description",
        "is_active": True,
    }
    response = await async_client.post("/api/v1/examples", json=item_data, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "Test Item"
    assert data["data"]["id"] is not None


@pytest.mark.asyncio
async def test_get_example_with_auth(async_client, auth_headers):
    """Test getting a specific example item."""
    # Create an item first
    item_data = {"name": "Test Item", "description": "Test description"}
    create_response = await async_client.post(
        "/api/v1/examples", json=item_data, headers=auth_headers
    )
    item_id = create_response.json()["data"]["id"]

    # Get the item
    response = await async_client.get(f"/api/v1/examples/{item_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] == item_id


@pytest.mark.asyncio
async def test_update_example_with_auth(async_client, auth_headers):
    """Test updating an example item."""
    # Create an item first
    item_data = {"name": "Test Item", "description": "Test description"}
    create_response = await async_client.post(
        "/api/v1/examples", json=item_data, headers=auth_headers
    )
    item_id = create_response.json()["data"]["id"]

    # Update the item
    update_data = {"name": "Updated Item"}
    response = await async_client.put(
        f"/api/v1/examples/{item_id}", json=update_data, headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "Updated Item"


@pytest.mark.asyncio
async def test_delete_example_with_auth(async_client, auth_headers):
    """Test deleting an example item."""
    # Create an item first
    item_data = {"name": "Test Item", "description": "Test description"}
    create_response = await async_client.post(
        "/api/v1/examples", json=item_data, headers=auth_headers
    )
    item_id = create_response.json()["data"]["id"]

    # Delete the item
    response = await async_client.delete(f"/api/v1/examples/{item_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # Verify item is deleted
    get_response = await async_client.get(f"/api/v1/examples/{item_id}", headers=auth_headers)
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_example(async_client, auth_headers):
    """Test getting a non-existent item returns 404."""
    response = await async_client.get("/api/v1/examples/9999", headers=auth_headers)
    assert response.status_code == 404
