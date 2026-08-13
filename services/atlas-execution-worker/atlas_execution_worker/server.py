"""Private TCP server configuration for the execution worker."""

from __future__ import annotations

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8081


def validate_port(port: int) -> int:
    if not 1 <= port <= 65535:
        raise ValueError("worker port must be between 1 and 65535")
    return port
