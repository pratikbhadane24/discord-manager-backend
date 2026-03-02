"""Example domain models for demonstration purposes."""

from pydantic import BaseModel, Field


class ExampleItem(BaseModel):
    """Example item model."""

    id: int | None = Field(None, description="Item ID")
    name: str = Field(..., description="Item name", min_length=1, max_length=100)
    description: str | None = Field(None, description="Item description")
    is_active: bool = Field(True, description="Item active status")


class ExampleItemCreate(BaseModel):
    """Model for creating a new example item."""

    name: str = Field(..., description="Item name", min_length=1, max_length=100)
    description: str | None = Field(None, description="Item description")
    is_active: bool = Field(True, description="Item active status")


class ExampleItemUpdate(BaseModel):
    """Model for updating an existing example item."""

    name: str | None = Field(
        None, description="Item name", min_length=1, max_length=100
    )
    description: str | None = Field(None, description="Item description")
    is_active: bool | None = Field(None, description="Item active status")
