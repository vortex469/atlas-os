from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "atlas_execution_worker_healthcheck", Path(__file__).parents[1] / "healthcheck.py"
)
assert SPEC is not None and SPEC.loader is not None
healthcheck = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(healthcheck)


def health(*, execution_enabled: object = False) -> dict[str, object]:
    return {
        "service": "atlas-execution-worker",
        "status": "healthy",
        "contract_schema_version": 1,
        "execution_enabled": execution_enabled,
    }


def test_configured_false_and_reported_false_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_EXECUTION_WORKER_EXECUTION_ENABLED", "false")
    healthcheck.validate_health(health(), expected_execution_enabled=healthcheck.configured_execution_enabled())


def test_configured_true_and_reported_true_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_EXECUTION_WORKER_EXECUTION_ENABLED", "true")
    healthcheck.validate_health(health(execution_enabled=True), expected_execution_enabled=healthcheck.configured_execution_enabled())


def test_execution_mode_mismatch_fails() -> None:
    with pytest.raises(ValueError, match="execution mode"):
        healthcheck.validate_health(health(execution_enabled=True), expected_execution_enabled=False)


def test_malformed_environment_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_EXECUTION_WORKER_EXECUTION_ENABLED", "yes")
    with pytest.raises(ValueError, match="invalid"):
        healthcheck.configured_execution_enabled()


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"service": "wrong", "status": "healthy", "contract_schema_version": 1, "execution_enabled": False},
        {"service": "atlas-execution-worker", "status": "healthy", "contract_schema_version": 2, "execution_enabled": False},
        {**health(), "execution_enabled": "false"},
        {**health(), "ledger_counts": {"claimed": -1, "completed": 0, "unknown_outcome": 0}},
    ],
)
def test_malformed_response_fails(payload: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        healthcheck.validate_health(payload, expected_execution_enabled=False)
