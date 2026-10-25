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
        "execution_readiness": {"configured_enabled":execution_enabled,"isolation_observed_safe":True if execution_enabled is True else None,"full_readiness_proven":False,"activation_authorized":False},
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


@pytest.mark.parametrize('safe', [None,False])
def test_configured_execution_without_observation_is_not_healthy(safe):
    payload = health(execution_enabled=True)
    payload['execution_readiness']['isolation_observed_safe'] = safe
    with pytest.raises(ValueError, match='not observed'):
        healthcheck.validate_health(payload, expected_execution_enabled=True)


def test_complete_durable_state_health_and_legacy_compatibility():
    payload = {**health(), 'ledger_status': 'available', 'ledger_counts': {
        'claimed': 0, 'executing': 1, 'completed': 2, 'failed_terminal': 3, 'unknown_outcome': 4}}
    healthcheck.validate_health(payload, expected_execution_enabled=False)
    payload['ledger_counts'].pop('executing')
    with pytest.raises(ValueError):
        healthcheck.validate_health(payload, expected_execution_enabled=False)
    payload.update(ledger_status='unavailable', ledger_counts=None)
    with pytest.raises(ValueError):
        healthcheck.validate_health(payload, expected_execution_enabled=False)
