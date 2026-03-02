"""Example service for business logic operations."""

from app.models.example import ExampleItem, ExampleItemCreate, ExampleItemUpdate

# Shared in-memory storage for demonstration (replace with database in production)
_shared_items: dict[int, ExampleItem] = {}
_shared_next_id = [1]  # Using list to make it mutable


class ExampleService:
    """Service layer for example item operations."""

    def __init__(self):
        """Initialize the service with shared in-memory storage."""
        # Use shared storage across all instances
        self._items = _shared_items
        self._next_id_ref = _shared_next_id

    async def list_items(self, skip: int = 0, limit: int = 10) -> list[ExampleItem]:
        """
        List all items with pagination.

        Args:
            skip: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of example items
        """
        items = list(self._items.values())
        return items[skip : skip + limit]

    async def get_item(self, item_id: int) -> ExampleItem | None:
        """
        Get a specific item by ID.

        Args:
            item_id: ID of the item to retrieve

        Returns:
            ExampleItem if found, None otherwise
        """
        return self._items.get(item_id)

    async def create_item(self, item_data: ExampleItemCreate) -> ExampleItem:
        """
        Create a new item.

        Args:
            item_data: Data for creating the item

        Returns:
            Created ExampleItem with assigned ID
        """
        current_id = self._next_id_ref[0]
        item = ExampleItem(
            id=current_id,
            name=item_data.name,
            description=item_data.description,
            is_active=item_data.is_active,
        )
        self._items[current_id] = item
        self._next_id_ref[0] += 1
        return item

    async def update_item(
        self, item_id: int, item_data: ExampleItemUpdate
    ) -> ExampleItem | None:
        """
        Update an existing item.

        Args:
            item_id: ID of the item to update
            item_data: Data for updating the item

        Returns:
            Updated ExampleItem if found, None otherwise
        """
        item = self._items.get(item_id)
        if not item:
            return None

        update_data = item_data.model_dump(exclude_unset=True)
        updated_item = item.model_copy(update=update_data)
        self._items[item_id] = updated_item
        return updated_item

    async def delete_item(self, item_id: int) -> bool:
        """
        Delete an item.

        Args:
            item_id: ID of the item to delete

        Returns:
            True if item was deleted, False if not found
        """
        if item_id in self._items:
            del self._items[item_id]
            return True
        return False
