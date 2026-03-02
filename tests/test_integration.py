"""Integration tests for the complete application flow."""

import pytest


@pytest.mark.asyncio
async def test_complete_crud_flow(async_client, auth_headers):
    """Test complete CRUD flow for example items."""
    # Create an item
    create_data = {
        "name": "Integration Test Item",
        "description": "Testing complete flow",
        "is_active": True,
    }
    create_response = await async_client.post(
        "/api/v1/examples", json=create_data, headers=auth_headers
    )
    assert create_response.status_code == 201
    created_item = create_response.json()["data"]
    item_id = created_item["id"]

    # Read the item
    get_response = await async_client.get(f"/api/v1/examples/{item_id}", headers=auth_headers)
    assert get_response.status_code == 200
    retrieved_item = get_response.json()["data"]
    assert retrieved_item["name"] == create_data["name"]

    # Update the item
    update_data = {"name": "Updated Integration Test Item"}
    update_response = await async_client.put(
        f"/api/v1/examples/{item_id}", json=update_data, headers=auth_headers
    )
    assert update_response.status_code == 200
    updated_item = update_response.json()["data"]
    assert updated_item["name"] == update_data["name"]

    # List items (should contain our item)
    list_response = await async_client.get("/api/v1/examples", headers=auth_headers)
    assert list_response.status_code == 200
    items = list_response.json()["data"]
    assert any(item["id"] == item_id for item in items)

    # Delete the item
    delete_response = await async_client.delete(
        f"/api/v1/examples/{item_id}", headers=auth_headers
    )
    assert delete_response.status_code == 200

    # Verify deletion
    get_deleted_response = await async_client.get(
        f"/api/v1/examples/{item_id}", headers=auth_headers
    )
    assert get_deleted_response.status_code == 404


@pytest.mark.asyncio
async def test_health_checks_integration(async_client):
    """Test all health check endpoints."""
    # Health check
    health_response = await async_client.get("/api/v1/health")
    assert health_response.status_code == 200
    assert health_response.json()["data"]["status"] == "ok"

    # Readiness check
    ready_response = await async_client.get("/api/v1/health/ready")
    assert ready_response.status_code == 200
    assert ready_response.json()["data"]["status"] == "ready"

    # Liveness check
    live_response = await async_client.get("/api/v1/health/live")
    assert live_response.status_code == 200
    assert live_response.json()["data"]["status"] == "alive"


@pytest.mark.asyncio
async def test_authentication_flow(async_client, test_token):
    """Test authentication flow with different token sources."""
    # Test with Authorization header
    headers = {"Authorization": f"Bearer {test_token}"}
    response = await async_client.get("/api/v1/examples", headers=headers)
    assert response.status_code == 200

    # Test without token
    response = await async_client.get("/api/v1/examples")
    assert response.status_code == 401

    # Test with invalid token
    headers = {"Authorization": "Bearer invalid_token"}
    response = await async_client.get("/api/v1/examples", headers=headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_pagination(async_client, auth_headers):
    """Test pagination on list endpoints."""
    # Create multiple items
    for i in range(15):
        item_data = {"name": f"Pagination Test Item {i}"}
        await async_client.post("/api/v1/examples", json=item_data, headers=auth_headers)

    # Test pagination
    response = await async_client.get("/api/v1/examples?skip=0&limit=5", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()["data"]
    assert len(items) <= 5

    # Test skip parameter
    response = await async_client.get("/api/v1/examples?skip=10&limit=10", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()["data"]
    assert len(items) <= 10
