"""Standard response models for consistent API responses."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    """
    Standard API response format.

    Attributes:
        success: Indicates if the request was successful
        message: Human-readable message
        data: Response payload data
    """

    success: bool = Field(..., description="Request success status")
    message: str = Field(..., description="Response message")
    data: T | None = Field(None, description="Response data payload")


class ErrorResponse(BaseModel):
    """
    Error response format.

    Attributes:
        success: Always False for errors
        message: Error message
        error_code: Optional error code
        details: Optional additional error details
    """

    success: bool = Field(False, description="Request success status")
    message: str = Field(..., description="Error message")
    error_code: str | None = Field(None, description="Error code")
    details: dict[str, Any] | None = Field(None, description="Additional error details")
