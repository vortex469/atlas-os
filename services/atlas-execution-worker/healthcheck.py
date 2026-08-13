"""TCP health check for the execution worker container."""

from __future__ import annotations

import json
import os
import socket
from typing import Any

HOST = "127.0.0.1"
PORT = 8081
EXPECTED_SERVICE = "atlas-execution-worker"
EXPECTED_SCHEMA_VERSION = 1


def configured_execution_enabled() -> bool:
    value = os.environ.get("ATLAS_EXECUTION_WORKER_EXECUTION_ENABLED")
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError("invalid ATLAS_EXECUTION_WORKER_EXECUTION_ENABLED")


def validate_health(health: Any, *, expected_execution_enabled: bool) -> None:
    if not isinstance(health, dict):
        raise TypeError("worker health response is not an object")
    if health.get("service") != EXPECTED_SERVICE:
        raise ValueError("unexpected worker service")
    if health.get("status") != "healthy":
        raise ValueError("worker is not healthy")
    if health.get("contract_schema_version") != EXPECTED_SCHEMA_VERSION:
        raise ValueError("unexpected worker contract schema")
    if health.get("execution_enabled") is not expected_execution_enabled:
        raise ValueError("worker execution mode does not match configuration")
    counts = health.get("ledger_counts")
    if counts is not None:
        if not isinstance(counts, dict) or set(counts) != {"claimed", "completed", "unknown_outcome"}:
            raise ValueError("invalid worker ledger counts")
        if any(not isinstance(value, int) or value < 0 for value in counts.values()):
            raise ValueError("invalid worker ledger counts")


def main() -> None:
    expected_execution_enabled = configured_execution_enabled()
    with socket.create_connection((HOST, PORT), timeout=3) as connection:
        connection.sendall(
            b"GET /health HTTP/1.1\r\nHost: worker\r\nConnection: close\r\n\r\n"
        )
        response = b""
        while chunk := connection.recv(4096):
            response += chunk
    header, separator, body = response.partition(b"\r\n\r\n")
    if not separator or b" 200 " not in header.split(b"\r\n", 1)[0]:
        raise SystemExit("worker health contract failed")
    try:
        health = json.loads(body)
        validate_health(health, expected_execution_enabled=expected_execution_enabled)
    except (ValueError, TypeError, json.JSONDecodeError):
        raise SystemExit("worker health contract failed") from None


if __name__ == "__main__":
    main()
