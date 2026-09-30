"""Custom exceptions and error-type vocabulary for platform clients."""

from enum import StrEnum


class ErrorType(StrEnum):
    """Canonical error_type values used across all platform payloads.

    Values compare equal to their string equivalents, so existing code
    doing ``payload["error_type"] == "RATE_LIMIT"`` continues to work
    after adopting this enum.
    """

    INVALID_USERNAME = "INVALID_USERNAME"
    RATE_LIMIT = "RATE_LIMIT"
    UNKNOWN = "UNKNOWN"
    DATA_MISSING = "DATA_MISSING"
    CAPTURE_FAILED = "CAPTURE_FAILED"
    PARSE_FAILED = "PARSE_FAILED"
    FETCH_FAILED = "FETCH_FAILED"


class PlatformNetworkError(Exception):
    """Raised for infrastructural/network failures when calling upstream APIs."""


class PlatformTimeoutError(PlatformNetworkError):
    """Raised when an upstream API request times out."""
