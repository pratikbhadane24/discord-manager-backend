"""Tests for API endpoints."""


def test_root_endpoint(client):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "version" in data
    assert "status" in data


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "ok"


def test_readiness_check(client):
    """Test readiness check endpoint."""
    response = client.get("/api/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "ready"


def test_liveness_check(client):
    """Test liveness check endpoint."""
    response = client.get("/api/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "alive"


def test_list_examples_without_auth(client):
    """Test listing examples without authentication fails."""
    response = client.get("/api/examples")
    assert response.status_code == 401


def test_list_examples_with_auth(client, auth_headers):
    """Test listing examples with authentication."""
    response = client.get("/api/examples", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)


def test_create_example_with_auth(client, auth_headers):
    """Test creating an example item with authentication."""
    item_data = {
        "name": "Test Item",
        "description": "Test description",
        "is_active": True,
    }
    response = client.post("/api/examples", json=item_data, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "Test Item"
    assert data["data"]["id"] is not None


def test_get_example_with_auth(client, auth_headers):
    """Test getting a specific example item."""
    # Create an item first
    item_data = {"name": "Test Item", "description": "Test description"}
    create_response = client.post("/api/examples", json=item_data, headers=auth_headers)
    item_id = create_response.json()["data"]["id"]

    # Get the item
    response = client.get(f"/api/examples/{item_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] == item_id


def test_update_example_with_auth(client, auth_headers):
    """Test updating an example item."""
    # Create an item first
    item_data = {"name": "Test Item", "description": "Test description"}
    create_response = client.post("/api/examples", json=item_data, headers=auth_headers)
    item_id = create_response.json()["data"]["id"]

    # Update the item
    update_data = {"name": "Updated Item"}
    response = client.put(
        f"/api/examples/{item_id}", json=update_data, headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "Updated Item"


def test_delete_example_with_auth(client, auth_headers):
    """Test deleting an example item."""
    # Create an item first
    item_data = {"name": "Test Item", "description": "Test description"}
    create_response = client.post("/api/examples", json=item_data, headers=auth_headers)
    item_id = create_response.json()["data"]["id"]

    # Delete the item
    response = client.delete(f"/api/examples/{item_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # Verify item is deleted
    get_response = client.get(f"/api/examples/{item_id}", headers=auth_headers)
    assert get_response.status_code == 404


def test_get_nonexistent_example(client, auth_headers):
    """Test getting a non-existent item returns 404."""
    response = client.get("/api/examples/9999", headers=auth_headers)
    assert response.status_code == 404
