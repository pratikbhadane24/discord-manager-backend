"""Integration tests for the complete application flow."""


def test_complete_crud_flow(client, auth_headers):
    """Test complete CRUD flow for example items."""
    # Create an item
    create_data = {
        "name": "Integration Test Item",
        "description": "Testing complete flow",
        "is_active": True,
    }
    create_response = client.post(
        "/api/examples", json=create_data, headers=auth_headers
    )
    assert create_response.status_code == 201
    created_item = create_response.json()["data"]
    item_id = created_item["id"]

    # Read the item
    get_response = client.get(f"/api/examples/{item_id}", headers=auth_headers)
    assert get_response.status_code == 200
    retrieved_item = get_response.json()["data"]
    assert retrieved_item["name"] == create_data["name"]

    # Update the item
    update_data = {"name": "Updated Integration Test Item"}
    update_response = client.put(
        f"/api/examples/{item_id}", json=update_data, headers=auth_headers
    )
    assert update_response.status_code == 200
    updated_item = update_response.json()["data"]
    assert updated_item["name"] == update_data["name"]

    # List items (should contain our item)
    list_response = client.get("/api/examples", headers=auth_headers)
    assert list_response.status_code == 200
    items = list_response.json()["data"]
    assert any(item["id"] == item_id for item in items)

    # Delete the item
    delete_response = client.delete(f"/api/examples/{item_id}", headers=auth_headers)
    assert delete_response.status_code == 200

    # Verify deletion
    get_deleted_response = client.get(f"/api/examples/{item_id}", headers=auth_headers)
    assert get_deleted_response.status_code == 404


def test_health_checks_integration(client):
    """Test all health check endpoints."""
    # Health check
    health_response = client.get("/api/health")
    assert health_response.status_code == 200
    assert health_response.json()["data"]["status"] == "ok"

    # Readiness check
    ready_response = client.get("/api/health/ready")
    assert ready_response.status_code == 200
    assert ready_response.json()["data"]["status"] == "ready"

    # Liveness check
    live_response = client.get("/api/health/live")
    assert live_response.status_code == 200
    assert live_response.json()["data"]["status"] == "alive"


def test_authentication_flow(client, test_token):
    """Test authentication flow with different token sources."""
    # Test with Authorization header
    headers = {"Authorization": f"Bearer {test_token}"}
    response = client.get("/api/examples", headers=headers)
    assert response.status_code == 200

    # Test without token
    response = client.get("/api/examples")
    assert response.status_code == 401

    # Test with invalid token
    headers = {"Authorization": "Bearer invalid_token"}
    response = client.get("/api/examples", headers=headers)
    assert response.status_code == 401


def test_pagination(client, auth_headers):
    """Test pagination on list endpoints."""
    # Create multiple items
    for i in range(15):
        item_data = {"name": f"Pagination Test Item {i}"}
        client.post("/api/examples", json=item_data, headers=auth_headers)

    # Test pagination
    response = client.get("/api/examples?skip=0&limit=5", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()["data"]
    assert len(items) <= 5

    # Test skip parameter
    response = client.get("/api/examples?skip=10&limit=10", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()["data"]
    assert len(items) <= 10
