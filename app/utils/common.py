"""Common utility functions."""

import re
from datetime import datetime, timezone


def get_current_timestamp() -> datetime:
    """
    Get current UTC timestamp.

    Returns:
        Current datetime in UTC timezone
    """
    return datetime.now(timezone.utc)


def sanitize_string(text: str) -> str:
    """
    Sanitize a string by removing special characters.

    Args:
        text: Input string to sanitize

    Returns:
        Sanitized string with only alphanumeric characters and spaces
    """
    return re.sub(r"[^a-zA-Z0-9\s]", "", text)


def truncate_string(text: str, max_length: int = 100) -> str:
    """
    Truncate a string to a maximum length.

    Args:
        text: Input string to truncate
        max_length: Maximum allowed length

    Returns:
        Truncated string with ellipsis if needed
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def format_error_message(error: Exception) -> str:
    """
    Format an exception into a user-friendly error message.

    Args:
        error: Exception to format

    Returns:
        Formatted error message string
    """
    return f"{error.__class__.__name__}: {str(error)}"
