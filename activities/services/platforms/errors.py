"""Custom exceptions for platform clients."""


class PlatformNetworkError(Exception):
    """Raised for infrastructural/network failures when calling upstream APIs."""


class PlatformTimeoutError(PlatformNetworkError):
    """Raised when an upstream API request times out."""
