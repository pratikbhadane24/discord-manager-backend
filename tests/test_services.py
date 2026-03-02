"""Tests for service layer."""

import pytest

from app.models.example import ExampleItemCreate, ExampleItemUpdate
from app.services.example_service import ExampleService


@pytest.mark.asyncio
async def test_create_item():
    """Test creating an item in the service."""
    service = ExampleService()
    item_data = ExampleItemCreate(name="Test Item", description="Test description")
    item = await service.create_item(item_data)
    assert item.id is not None
    assert item.name == "Test Item"
    assert item.description == "Test description"


@pytest.mark.asyncio
async def test_get_item():
    """Test getting an item from the service."""
    service = ExampleService()
    item_data = ExampleItemCreate(name="Test Item")
    created_item = await service.create_item(item_data)

    retrieved_item = await service.get_item(created_item.id)
    assert retrieved_item is not None
    assert retrieved_item.id == created_item.id
    assert retrieved_item.name == created_item.name


@pytest.mark.asyncio
async def test_list_items():
    """Test listing items from the service."""
    service = ExampleService()
    # Get initial count
    initial_items = await service.list_items(skip=0, limit=100)
    initial_count = len(initial_items)
    
    # Create multiple items
    for i in range(5):
        item_data = ExampleItemCreate(name=f"Test Item {i}")
        await service.create_item(item_data)

    items = await service.list_items(skip=0, limit=100)
    # Should have at least 5 more items than before
    assert len(items) >= initial_count + 5


@pytest.mark.asyncio
async def test_update_item():
    """Test updating an item in the service."""
    service = ExampleService()
    item_data = ExampleItemCreate(name="Test Item")
    created_item = await service.create_item(item_data)

    update_data = ExampleItemUpdate(name="Updated Item")
    updated_item = await service.update_item(created_item.id, update_data)
    assert updated_item is not None
    assert updated_item.name == "Updated Item"


@pytest.mark.asyncio
async def test_delete_item():
    """Test deleting an item from the service."""
    service = ExampleService()
    item_data = ExampleItemCreate(name="Test Item")
    created_item = await service.create_item(item_data)

    success = await service.delete_item(created_item.id)
    assert success is True

    deleted_item = await service.get_item(created_item.id)
    assert deleted_item is None


@pytest.mark.asyncio
async def test_get_nonexistent_item():
    """Test getting a non-existent item returns None."""
    service = ExampleService()
    item = await service.get_item(9999)
    assert item is None


@pytest.mark.asyncio
async def test_update_nonexistent_item():
    """Test updating a non-existent item returns None."""
    service = ExampleService()
    update_data = ExampleItemUpdate(name="Updated Item")
    item = await service.update_item(9999, update_data)
    assert item is None


@pytest.mark.asyncio
async def test_delete_nonexistent_item():
    """Test deleting a non-existent item returns False."""
    service = ExampleService()
    success = await service.delete_item(9999)
    assert success is False
