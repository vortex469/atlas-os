from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.execution_candidates.fingerprint import (
    FINGERPRINT_VERSION,
    build_candidate_fingerprint,
)
from app.execution_candidates.models import (
    ApprovalLevel,
    ExecutionCandidate,
    ExecutionCandidateStatus,
    ExecutionCategory,
    ExecutionConstraint,
    ExecutionIntent,
    build_execution_candidate_id,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def candidate(**overrides: object) -> ExecutionCandidate:
    values: dict[str, object] = {
        "source_recommendation_id": "finding-1",
        "source_subsystem": "orion",
        "recommendation_class": "restart-service",
        "catalog_item_id": "frigate",
        "target_id": "service-frigate",
        "target_type": "service",
        "execution_category": ExecutionCategory.RESTART,
        "execution_intent": ExecutionIntent.RESTART_SERVICE,
        "status": ExecutionCandidateStatus.ELIGIBLE,
        "required_approval_level": ApprovalLevel.STANDARD,
        "rationale": "Restart the service after approval.",
        "constraints": (ExecutionConstraint.REQUIRES_CURRENT_EVIDENCE, ExecutionConstraint.SERVICE_DISRUPTION),
        "evidence_ids": ("evidence-1", "evidence-2"),
        "compatibility_assessment_id": "assessment-1",
        "compatibility_status": "compatible",
        "relationship_ids": ("relationship-1", "relationship-2"),
        "created_at": NOW,
        "expires_at": NOW + timedelta(hours=1),
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


def test_fingerprint_is_deterministic() -> None:
    first = build_candidate_fingerprint(candidate())
    second = build_candidate_fingerprint(candidate())

    assert first == second
    assert first.startswith(f"{FINGERPRINT_VERSION}:")


def test_reordered_evidence_relationships_and_constraints_do_not_change_fingerprint() -> None:
    first = candidate(
        evidence_ids=("evidence-2", "evidence-1"),
        relationship_ids=("relationship-2", "relationship-1"),
        constraints=(ExecutionConstraint.SERVICE_DISRUPTION, ExecutionConstraint.REQUIRES_CURRENT_EVIDENCE),
    )
    second = candidate(
        evidence_ids=("evidence-1", "evidence-2"),
        relationship_ids=("relationship-1", "relationship-2"),
        constraints=(ExecutionConstraint.REQUIRES_CURRENT_EVIDENCE, ExecutionConstraint.SERVICE_DISRUPTION),
    )

    assert build_candidate_fingerprint(first) == build_candidate_fingerprint(second)


def test_created_at_does_not_change_fingerprint() -> None:
    assert build_candidate_fingerprint(candidate(created_at=NOW, expires_at=None)) == build_candidate_fingerprint(
        candidate(created_at=NOW + timedelta(days=1), expires_at=None)
    )


def test_expires_at_changes_fingerprint() -> None:
    assert build_candidate_fingerprint(candidate(expires_at=NOW + timedelta(hours=1))) != build_candidate_fingerprint(
        candidate(expires_at=NOW + timedelta(hours=2))
    )


def test_compatibility_status_changes_fingerprint() -> None:
    assert build_candidate_fingerprint(candidate(compatibility_status="compatible")) != build_candidate_fingerprint(
        candidate(compatibility_status="compatible_with_warnings")
    )


def test_approval_level_changes_fingerprint() -> None:
    assert build_candidate_fingerprint(
        candidate(required_approval_level=ApprovalLevel.STANDARD)
    ) != build_candidate_fingerprint(candidate(required_approval_level=ApprovalLevel.ELEVATED))


def test_normalized_rationale_whitespace_produces_same_fingerprint() -> None:
    assert build_candidate_fingerprint(candidate(rationale="Restart the service after approval.")) == build_candidate_fingerprint(
        candidate(rationale="  Restart   the service\n after approval.  ")
    )


def test_material_rationale_change_changes_fingerprint() -> None:
    assert build_candidate_fingerprint(candidate(rationale="Restart the service after approval.")) != build_candidate_fingerprint(
        candidate(rationale="Restart a different service after approval.")
    )
