class AtlasCoreClientError(Exception):
    """Base exception for Atlas Core client errors."""

class AtlasCoreConnectionError(AtlasCoreClientError):
    """Exception raised for connection errors."""

class AtlasCoreTimeoutError(AtlasCoreClientError):
    """Exception raised for timeout errors."""

class AtlasCoreResponseError(AtlasCoreClientError):
    """Exception raised for response errors."""

class AtlasCorePayloadError(AtlasCoreClientError):
    """Exception raised for payload errors."""
