"""TCP health check for the execution worker container."""

from __future__ import annotations

import os
from typing import Any

from app.execution.worker_client import TcpWorkerClient, WorkerTransportError

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
    if type(health.get("contract_schema_version")) is not int or health.get("contract_schema_version") != EXPECTED_SCHEMA_VERSION:
        raise ValueError("unexpected worker contract schema")
    if health.get("execution_enabled") is not expected_execution_enabled:
        raise ValueError("worker execution mode does not match configuration")
    readiness = health.get("execution_readiness")
    if expected_execution_enabled and (not isinstance(readiness, dict) or readiness.get("isolation_observed_safe") is not True):
        raise ValueError("worker execution isolation is not observed")
    if readiness is not None and (
        not isinstance(readiness, dict)
        or readiness.get("configured_enabled") is not expected_execution_enabled
        or readiness.get("full_readiness_proven") is not False
        or readiness.get("activation_authorized") is not False
    ):
        raise ValueError("worker readiness must not imply authority")
    if "ledger_status" in health and health["ledger_status"] != "available":
        raise ValueError("worker ledger is unavailable")
    counts = health.get("ledger_counts")
    if "ledger_status" in health and (not isinstance(counts, dict) or set(counts) != {"claimed", "executing", "completed", "failed_terminal", "unknown_outcome"}):
        raise ValueError("incomplete worker ledger states")
    if counts is not None:
        if not isinstance(counts, dict) or set(counts) not in ({"claimed", "completed", "unknown_outcome"}, {"claimed", "executing", "completed", "failed_terminal", "unknown_outcome"}):
            raise ValueError("invalid worker ledger counts")
        if any(type(value) is not int or value < 0 for value in counts.values()):
            raise ValueError("invalid worker ledger counts")


def main() -> None:
    try:
        expected_execution_enabled = configured_execution_enabled()
        health = TcpWorkerClient(HOST, PORT, timeout_seconds=3).health()
        validate_health(health, expected_execution_enabled=expected_execution_enabled)
    except (WorkerTransportError, ValueError, TypeError):
        raise SystemExit("worker health contract failed") from None


if __name__ == "__main__":
    main()
