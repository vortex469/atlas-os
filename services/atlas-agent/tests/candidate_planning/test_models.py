"""Tests for candidate-planning domain models."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest
from app.candidate_planning.models import (
    OPERATIONAL_EXECUTION_INTENTS,
    OPERATIONAL_PLANNING_INTENTS,
    SUPPORTED_EXECUTION_INTENTS,
    CandidatePlanningSessionStatus,
    CandidatePlanRequest,
    build_candidate_planning_session_id,
    is_operational_execution_enabled,
    is_operational_planning_intent,
    is_supported_execution_intent,
)


def test_candidate_request_is_immutable() -> None:
    request = CandidatePlanRequest(
        candidate_id="candidate-1",
        expected_candidate_fingerprint="candidate-fingerprint-v1:abc",
    )

    with pytest.raises(FrozenInstanceError):
        request.candidate_id = "candidate-2"  # type: ignore[misc]


def test_supported_intent_policy_is_narrow() -> None:
    assert SUPPORTED_EXECUTION_INTENTS == frozenset({"update-compose-stack"})
    assert OPERATIONAL_PLANNING_INTENTS == frozenset({"restart-service"})
    assert OPERATIONAL_EXECUTION_INTENTS == frozenset()
    assert is_supported_execution_intent("update-compose-stack") is True
    assert is_supported_execution_intent("restart-service") is False
    assert is_operational_planning_intent("restart-service") is True
    assert is_operational_execution_enabled("restart-service") is False


def test_rc1_smoke_intent_requires_explicit_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATLAS_ENABLE_RC1_VALIDATION_SMOKE", raising=False)
    assert is_supported_execution_intent("rc1-validation-smoke") is False
    monkeypatch.setenv("ATLAS_ENABLE_RC1_VALIDATION_SMOKE", "true")
    assert is_supported_execution_intent("rc1-validation-smoke") is True


def test_session_id_is_stable_and_uses_full_fingerprint() -> None:
    first = build_candidate_planning_session_id(
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fingerprint-v1:" + "a" * 64,
    )
    repeated = build_candidate_planning_session_id(
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fingerprint-v1:" + "a" * 64,
    )
    different = build_candidate_planning_session_id(
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fingerprint-v1:" + "b" * 64,
    )

    assert first == repeated
    assert first != different
    assert first.startswith("candidate-plan-")


def test_candidate_planning_status_vocabulary_includes_workflow_and_implementation_gates() -> None:
    assert {status.value for status in CandidatePlanningSessionStatus} == {
        "implementation_not_supported",
        "implementation_ready",
        "implementation_translation_failed",
        "intake_rejected",
        "plan_ready",
        "planning",
        "planning_failed",
        "planning_not_supported",
        "ready_for_planning",
        "stale_before_implementation",
        "stale_before_planning",
        "stale_before_workflow",
        "unsupported_intent",
        "workflow_conversion_failed",
        "workflow_created",
    }


# Keep datetime imported by this module so Ruff proves tests do not rely on wall clock.
_NOW = datetime(2026, 8, 1, tzinfo=UTC)
