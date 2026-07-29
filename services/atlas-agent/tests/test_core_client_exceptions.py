
from app.core_client.exceptions import (
    AtlasCoreClientError,
    AtlasCoreConnectionError,
    AtlasCorePayloadError,
    AtlasCoreResponseError,
    AtlasCoreTimeoutError,
)


def test_exception_hierarchy():
    """Test that all specialized exceptions subclass AtlasCoreClientError."""
    assert issubclass(AtlasCoreConnectionError, AtlasCoreClientError)
    assert issubclass(AtlasCoreTimeoutError, AtlasCoreClientError)
    assert issubclass(AtlasCoreResponseError, AtlasCoreClientError)
    assert issubclass(AtlasCorePayloadError, AtlasCoreClientError)

def test_exception_can_be_caught_by_base():
    """Test that each exception can be caught through AtlasCoreClientError."""
    # Test connection error
    try:
        raise AtlasCoreConnectionError("Connection failed")
    except AtlasCoreClientError as e:
        assert str(e) == "Connection failed"

    # Test timeout error
    try:
        raise AtlasCoreTimeoutError("Request timed out")
    except AtlasCoreClientError as e:
        assert str(e) == "Request timed out"

    # Test response error
    try:
        raise AtlasCoreResponseError("Invalid response")
    except AtlasCoreClientError as e:
        assert str(e) == "Invalid response"

    # Test payload error
    try:
        raise AtlasCorePayloadError("Invalid payload")
    except AtlasCoreClientError as e:
        assert str(e) == "Invalid payload"

def test_exception_messages_preserved():
    """Test that exception messages are preserved."""
    assert str(AtlasCoreConnectionError("Test message")) == "Test message"
    assert str(AtlasCoreTimeoutError("Test message")) == "Test message"
    assert str(AtlasCoreResponseError("Test message")) == "Test message"
    assert str(AtlasCorePayloadError("Test message")) == "Test message"
