"""Tests for candidate-planning domain models."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from app.candidate_planning.models import (
    CandidatePlanningSessionStatus,
    CandidatePlanRequest,
    build_candidate_planning_session_id,
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
    assert is_supported_execution_intent("update-compose-stack") is True
    assert is_supported_execution_intent("restart-service") is False


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


def test_p3_7_status_vocabulary_is_planning_only() -> None:
    assert {status.value for status in CandidatePlanningSessionStatus} == {
        "intake_rejected",
        "ready_for_planning",
        "unsupported_intent",
    }


# Keep datetime imported by this module so Ruff proves tests do not rely on wall clock.
_NOW = datetime(2026, 8, 1, tzinfo=UTC)
