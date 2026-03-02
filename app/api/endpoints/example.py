"""Example domain endpoints demonstrating CRUD operations."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_user
from app.models.example import ExampleItem, ExampleItemCreate, ExampleItemUpdate
from app.models.responses import StandardResponse
from app.services.example_service import ExampleService

router = APIRouter(prefix="/examples", tags=["examples"])


@router.get("", response_model=StandardResponse[list[ExampleItem]])
async def list_items(
    skip: int = 0,
    limit: int = 10,
    current_user: dict = Depends(get_current_user),
):
    """
    List all example items (authenticated).

    Args:
        skip: Number of items to skip
        limit: Maximum number of items to return
        current_user: Current authenticated user

    Returns:
        Standard response with list of items
    """
    service = ExampleService()
    items = await service.list_items(skip=skip, limit=limit)
    return StandardResponse(
        success=True,
        message="Items retrieved successfully",
        data=items,
    )


@router.get("/{item_id}", response_model=StandardResponse[ExampleItem])
async def get_item(
    item_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Get a specific example item by ID (authenticated).

    Args:
        item_id: ID of the item to retrieve
        current_user: Current authenticated user

    Returns:
        Standard response with item data

    Raises:
        HTTPException: If item not found
    """
    service = ExampleService()
    item = await service.get_item(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with id {item_id} not found",
        )
    return StandardResponse(
        success=True,
        message="Item retrieved successfully",
        data=item,
    )


@router.post(
    "",
    response_model=StandardResponse[ExampleItem],
    status_code=status.HTTP_201_CREATED,
)
async def create_item(
    item_data: ExampleItemCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new example item (authenticated).

    Args:
        item_data: Item creation data
        current_user: Current authenticated user

    Returns:
        Standard response with created item
    """
    service = ExampleService()
    item = await service.create_item(item_data)
    return StandardResponse(
        success=True,
        message="Item created successfully",
        data=item,
    )


@router.put("/{item_id}", response_model=StandardResponse[ExampleItem])
async def update_item(
    item_id: int,
    item_data: ExampleItemUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Update an existing example item (authenticated).

    Args:
        item_id: ID of the item to update
        item_data: Item update data
        current_user: Current authenticated user

    Returns:
        Standard response with updated item

    Raises:
        HTTPException: If item not found
    """
    service = ExampleService()
    item = await service.update_item(item_id, item_data)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with id {item_id} not found",
        )
    return StandardResponse(
        success=True,
        message="Item updated successfully",
        data=item,
    )


@router.delete("/{item_id}", response_model=StandardResponse[None])
async def delete_item(
    item_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete an example item (authenticated).

    Args:
        item_id: ID of the item to delete
        current_user: Current authenticated user

    Returns:
        Standard response confirming deletion

    Raises:
        HTTPException: If item not found
    """
    service = ExampleService()
    success = await service.delete_item(item_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with id {item_id} not found",
        )
    return StandardResponse(
        success=True,
        message="Item deleted successfully",
        data=None,
    )
