from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.execution_candidates.eligibility import (
    ExecutionEligibilityReason,
    validate_candidate_for_planning,
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
        "rationale": "Restart the service after approval.",
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


def reason_values(result: object) -> set[ExecutionEligibilityReason]:
    return {finding.reason for finding in result.findings}  # type: ignore[attr-defined]


def test_valid_candidate_becomes_eligible_for_planning_only() -> None:
    result = validate_candidate_for_planning(
        make_candidate(),
        available_evidence_ids=("evidence-1",),
        now=CREATED_AT + timedelta(minutes=1),
    )

    assert result.status == ExecutionCandidateStatus.ELIGIBLE
    assert result.findings == ()


def test_non_executable_recommendation_blocks_planning() -> None:
    result = validate_candidate_for_planning(
        make_candidate(recommendation_class="review-logs"),
        available_evidence_ids=("evidence-1",),
    )

    assert result.status == ExecutionCandidateStatus.NOT_ELIGIBLE
    assert ExecutionEligibilityReason.NON_EXECUTABLE_RECOMMENDATION in reason_values(result)


def test_missing_evidence_blocks_planning() -> None:
    result = validate_candidate_for_planning(make_candidate(evidence_ids=()))

    assert ExecutionEligibilityReason.MISSING_EVIDENCE in reason_values(result)


def test_unreferenced_evidence_blocks_planning() -> None:
    result = validate_candidate_for_planning(
        make_candidate(evidence_ids=("evidence-1", "missing-evidence")),
        available_evidence_ids=("evidence-1",),
    )

    assert ExecutionEligibilityReason.UNREFERENCED_EVIDENCE in reason_values(result)
    assert result.findings[0].evidence_ids == ("missing-evidence",)


def test_ambiguous_target_blocks_planning() -> None:
    result = validate_candidate_for_planning(
        make_candidate(target_id="all"),
        available_evidence_ids=("evidence-1",),
    )

    assert ExecutionEligibilityReason.AMBIGUOUS_TARGET in reason_values(result)


def test_insufficient_compatibility_blocks_planning() -> None:
    result = validate_candidate_for_planning(
        make_candidate(compatibility_status="insufficient_information"),
        available_evidence_ids=("evidence-1",),
    )

    assert ExecutionEligibilityReason.INSUFFICIENT_COMPATIBILITY in reason_values(result)


def test_incompatible_compatibility_blocks_planning() -> None:
    result = validate_candidate_for_planning(
        make_candidate(compatibility_status="incompatible"),
        available_evidence_ids=("evidence-1",),
    )

    assert ExecutionEligibilityReason.INCOMPATIBLE_COMPATIBILITY in reason_values(result)


def test_unresolved_required_relationship_blocks_planning() -> None:
    result = validate_candidate_for_planning(
        make_candidate(),
        available_evidence_ids=("evidence-1",),
        unresolved_required_relationship_ids=("rel-missing",),
    )

    assert ExecutionEligibilityReason.UNRESOLVED_REQUIRED_RELATIONSHIP in reason_values(result)


def test_optional_unresolved_relationship_does_not_block_alone() -> None:
    result = validate_candidate_for_planning(
        make_candidate(),
        available_evidence_ids=("evidence-1",),
        optional_unresolved_relationship_ids=("rel-optional",),
    )

    assert result.status == ExecutionCandidateStatus.ELIGIBLE


def test_expired_candidate_is_not_eligible() -> None:
    result = validate_candidate_for_planning(
        make_candidate(expires_at=CREATED_AT + timedelta(minutes=5)),
        available_evidence_ids=("evidence-1",),
        now=CREATED_AT + timedelta(minutes=10),
    )

    assert ExecutionEligibilityReason.EXPIRED_CANDIDATE in reason_values(result)


def test_destructive_intent_requires_destructive_approval() -> None:
    result = validate_candidate_for_planning(
        make_candidate(
            recommendation_class="remove-resource",
            execution_category=ExecutionCategory.REMOVE,
            execution_intent=ExecutionIntent.REMOVE_RESOURCE,
            required_approval_level=ApprovalLevel.ELEVATED,
            constraints=(ExecutionConstraint.DESTRUCTIVE_CHANGE, ExecutionConstraint.SERVICE_DISRUPTION),
        ),
        available_evidence_ids=("evidence-1",),
    )

    assert ExecutionEligibilityReason.DESTRUCTIVE_APPROVAL_REQUIRED in reason_values(result)


def test_restart_intent_requires_service_disruption_constraint() -> None:
    result = validate_candidate_for_planning(
        make_candidate(constraints=()),
        available_evidence_ids=("evidence-1",),
    )

    assert ExecutionEligibilityReason.SERVICE_DISRUPTION_CONSTRAINT_REQUIRED in reason_values(result)


def test_unsupported_source_subsystem_blocks_planning() -> None:
    result = validate_candidate_for_planning(
        make_candidate(source_subsystem="unknown"),
        available_evidence_ids=("evidence-1",),
    )

    assert ExecutionEligibilityReason.UNSUPPORTED_SOURCE_SUBSYSTEM in reason_values(result)


def test_discovery_backed_candidate_requires_catalog_identity() -> None:
    result = validate_candidate_for_planning(
        make_candidate(catalog_item_id=None, source_subsystem="discovery"),
        available_evidence_ids=("evidence-1",),
    )

    assert ExecutionEligibilityReason.MISSING_CATALOG_IDENTITY in reason_values(result)


def test_repeated_validation_is_deterministic() -> None:
    candidate = make_candidate(evidence_ids=("evidence-b", "evidence-a"))

    first = validate_candidate_for_planning(candidate, available_evidence_ids=("evidence-a", "evidence-b"))
    second = validate_candidate_for_planning(candidate, available_evidence_ids=("evidence-b", "evidence-a"))

    assert first == second


def test_reordered_evidence_produces_identical_candidate_and_validation() -> None:
    first = make_candidate(evidence_ids=("evidence-b", "evidence-a"))
    second = make_candidate(evidence_ids=("evidence-a", "evidence-b"))

    assert first.id == second.id
    assert first.evidence_ids == second.evidence_ids
    assert validate_candidate_for_planning(first, available_evidence_ids=first.evidence_ids) == validate_candidate_for_planning(
        second,
        available_evidence_ids=second.evidence_ids,
    )
