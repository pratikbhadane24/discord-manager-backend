"""Tests for app/utils/common.py utility functions."""

from datetime import timezone

import pytest

from app.utils.common import (
    format_error_message,
    get_current_timestamp,
    sanitize_string,
    truncate_string,
)


def test_get_current_timestamp_is_utc():
    """Returned timestamp should be timezone-aware UTC."""
    ts = get_current_timestamp()
    assert ts.tzinfo is not None
    assert ts.tzinfo == timezone.utc


def test_sanitize_string_removes_special_chars():
    """Special characters should be stripped, leaving alphanumeric and spaces."""
    assert sanitize_string("hello, world!") == "hello world"
    assert sanitize_string("test@example.com") == "testexamplecom"
    assert sanitize_string("abc 123") == "abc 123"


def test_sanitize_string_already_clean():
    """A string with only alphanumeric characters and spaces is unchanged."""
    assert sanitize_string("hello world") == "hello world"


def test_truncate_string_short_string():
    """Strings shorter than max_length are returned unchanged."""
    assert truncate_string("hello", 100) == "hello"
    assert truncate_string("hello", 5) == "hello"


def test_truncate_string_long_string():
    """Strings longer than max_length are truncated with an ellipsis."""
    result = truncate_string("a" * 200, 10)
    assert len(result) == 10
    assert result.endswith("...")


def test_truncate_string_custom_max_length():
    """Default max_length is 100."""
    long_str = "x" * 150
    result = truncate_string(long_str)
    assert len(result) == 100
    assert result.endswith("...")


def test_format_error_message():
    """Error message should include the exception class name and message."""
    exc = ValueError("something went wrong")
    msg = format_error_message(exc)
    assert "ValueError" in msg
    assert "something went wrong" in msg


def test_format_error_message_runtime_error():
    """Works correctly for any exception type."""
    exc = RuntimeError("boom")
    msg = format_error_message(exc)
    assert "RuntimeError" in msg
    assert "boom" in msg
