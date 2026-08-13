from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.execution_candidates.models import (
    ApprovalLevel,
    ExecutionCandidate,
    ExecutionCandidateStatus,
    ExecutionCategory,
    ExecutionConstraint,
    ExecutionIntent,
    build_execution_candidate_id,
)

CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def make_candidate(**overrides: object) -> ExecutionCandidate:
    values: dict[str, object] = {
        "source_subsystem": "orion",
        "source_recommendation_id": "rec-1",
        "recommendation_class": "restart-service",
        "catalog_item_id": "frigate",
        "target_id": "host-1",
        "target_type": "host",
        "execution_category": ExecutionCategory.RESTART,
        "execution_intent": ExecutionIntent.RESTART_SERVICE,
        "status": ExecutionCandidateStatus.ELIGIBLE,
        "required_approval_level": ApprovalLevel.STANDARD,
        "rationale": "Restart the service after an approved operator decision.",
        "constraints": (ExecutionConstraint.SERVICE_DISRUPTION,),
        "evidence_ids": ("evidence-1",),
        "compatibility_assessment_id": "assessment-1",
        "compatibility_status": "compatible",
        "relationship_ids": ("rel-1",),
        "created_at": CREATED_AT,
    }
    values.update(overrides)
    values["id"] = build_execution_candidate_id(
        source_subsystem=str(values["source_subsystem"]),
        source_recommendation_id=str(values["source_recommendation_id"]),
        catalog_item_id=values["catalog_item_id"] if isinstance(values["catalog_item_id"], str) else None,
        target_id=str(values["target_id"]),
        execution_category=values["execution_category"],  # type: ignore[arg-type]
        execution_intent=values["execution_intent"],  # type: ignore[arg-type]
    )
    return ExecutionCandidate(**values)


def test_valid_minimal_candidate() -> None:
    candidate = make_candidate()

    assert candidate.status == ExecutionCandidateStatus.ELIGIBLE
    assert candidate.id == "candidate-orion-rec-1-frigate-host-1-restart-restart-service"
    assert candidate.execution_category == ExecutionCategory.RESTART


def test_candidate_is_immutable() -> None:
    candidate = make_candidate()

    with pytest.raises(ValidationError):
        candidate.rationale = "changed"  # type: ignore[misc]


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        make_candidate(unexpected="value")


def test_invalid_ids_are_rejected() -> None:
    with pytest.raises(ValidationError):
        make_candidate(source_recommendation_id="Bad ID")


def test_invalid_approval_level_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_candidate(required_approval_level="review")


def test_unsupported_intent_category_combination_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_candidate(execution_category=ExecutionCategory.INSTALL)


def test_duplicate_evidence_ids_are_deterministically_normalized() -> None:
    candidate = make_candidate(evidence_ids=("Evidence-B", "evidence-a", "evidence-b"))

    assert candidate.evidence_ids == ("evidence-a", "evidence-b")


def test_unsafe_command_like_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        make_candidate(rationale="Run rm -rf / without review.")

    with pytest.raises(ValidationError):
        make_candidate(target_id="token=secret")


def test_candidate_id_must_be_deterministic() -> None:
    values = make_candidate().model_dump()
    values["id"] = "candidate-wrong"

    with pytest.raises(ValidationError):
        ExecutionCandidate(**values)


def test_timestamps_do_not_affect_deterministic_id() -> None:
    first = make_candidate(created_at=CREATED_AT)
    second = make_candidate(created_at=CREATED_AT + timedelta(hours=1))

    assert first.id == second.id


def test_expires_at_must_follow_created_at() -> None:
    with pytest.raises(ValidationError):
        make_candidate(expires_at=CREATED_AT)
