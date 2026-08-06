from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.execution_candidates.models import (
    ApprovalLevel,
    ExecutionCandidateStatus,
    ExecutionCategory,
    ExecutionIntent,
)
from app.execution_candidates.projection import (
    ProjectionReasonCode,
    ProjectionStatus,
    execution_candidate_from_finding,
    project_execution_candidates,
)
from app.intelligence.findings import Finding, Severity

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def finding(**overrides: object) -> Finding:
    details: dict[str, object] = {
        "source_subsystem": "orion",
        "recommendation_class": "restart_service",
        "target_id": "service-frigate",
        "target_type": "service",
        "evidence_ids": ("evidence-1",),
    }
    details.update(overrides.pop("details", {}))  # type: ignore[arg-type]
    values: dict[str, object] = {
        "id": "finding-1",
        "severity": Severity.WARNING,
        "category": "test",
        "source": "orion",
        "title": "Restart Frigate",
        "message": "Restart Frigate after approval.",
        "recommendation": "Restart Frigate.",
        "component": "Frigate",
        "details": details,
        "affects_health": False,
        "score_penalty": 0,
    }
    values.update(overrides)
    return Finding(**values)


def test_advisory_discovery_finding_returns_not_executable() -> None:
    result = execution_candidate_from_finding(
        finding(
            id="discovery-frigate-atlas-investigate-compatibility",
            source="discovery",
            details={
                "source_subsystem": "discovery",
                "recommendation_class": "investigate_compatibility",
                "target_id": "atlas",
                "target_type": "atlas_environment",
                "compatibility_evidence_ids": ("runtime-docker-unknown",),
            },
        ),
        available_evidence_ids=("runtime-docker-unknown",),
        now=NOW,
    )

    assert result.status == ProjectionStatus.NOT_EXECUTABLE
    assert result.reason_code == ProjectionReasonCode.ADVISORY_RECOMMENDATION_CLASS
    assert result.candidate is not None
    assert result.candidate.status == ExecutionCandidateStatus.NOT_ELIGIBLE
    assert result.candidate.execution_category == ExecutionCategory.UNSUPPORTED
    assert result.candidate.execution_intent.value == "unsupported-recommendation"


def test_executable_class_maps_to_expected_category_and_intent() -> None:
    result = execution_candidate_from_finding(
        finding(),
        available_evidence_ids=("evidence-1",),
        now=NOW,
    )

    assert result.status == ProjectionStatus.PROJECTED
    assert result.candidate is not None
    assert result.candidate.execution_category == ExecutionCategory.RESTART
    assert result.candidate.execution_intent == ExecutionIntent.RESTART_SERVICE
    assert result.candidate.status == ExecutionCandidateStatus.ELIGIBLE


def test_unknown_class_returns_unsupported() -> None:
    result = execution_candidate_from_finding(
        finding(details={"recommendation_class": "do_magic"}),
        now=NOW,
    )

    assert result.status == ProjectionStatus.UNSUPPORTED
    assert result.reason_code == ProjectionReasonCode.INVALID_RECOMMENDATION_CLASS
    assert result.candidate is None


def test_untrusted_source_returns_rejected() -> None:
    result = execution_candidate_from_finding(
        finding(source="untrusted", details={"source_subsystem": "untrusted"}),
        now=NOW,
    )

    assert result.status == ProjectionStatus.REJECTED
    assert result.reason_code == ProjectionReasonCode.UNTRUSTED_SOURCE_SUBSYSTEM
    assert result.candidate is None


def test_missing_evidence_yields_not_eligible_candidate() -> None:
    result = execution_candidate_from_finding(
        finding(details={"evidence_ids": ()}),
        now=NOW,
    )

    assert result.status == ProjectionStatus.INSUFFICIENT_DATA
    assert result.reason_code == ProjectionReasonCode.MISSING_EVIDENCE
    assert result.candidate is not None
    assert result.candidate.status == ExecutionCandidateStatus.NOT_ELIGIBLE
    assert result.candidate.evidence_ids == ()


def test_complete_evidence_yields_projected_eligible_candidate() -> None:
    result = execution_candidate_from_finding(
        finding(),
        available_evidence_ids=("evidence-1",),
        now=NOW,
    )

    assert result.status == ProjectionStatus.PROJECTED
    assert result.candidate is not None
    assert result.candidate.status == ExecutionCandidateStatus.ELIGIBLE


def test_stable_finding_id_produces_stable_candidate_id() -> None:
    first = execution_candidate_from_finding(finding(), available_evidence_ids=("evidence-1",), now=NOW)
    second = execution_candidate_from_finding(finding(), available_evidence_ids=("evidence-1",), now=NOW)

    assert first.candidate is not None
    assert second.candidate is not None
    assert first.candidate.id == second.candidate.id


def test_changed_prose_does_not_alter_candidate_identity() -> None:
    first = execution_candidate_from_finding(finding(message="Restart after approval."), now=NOW)
    second = execution_candidate_from_finding(finding(message="Different display wording."), now=NOW)

    assert first.candidate is not None
    assert second.candidate is not None
    assert first.candidate.id == second.candidate.id


def test_reordered_evidence_does_not_alter_candidate_identity() -> None:
    first = execution_candidate_from_finding(
        finding(details={"evidence_ids": ("evidence-b", "evidence-a")}),
        available_evidence_ids=("evidence-a", "evidence-b"),
        now=NOW,
    )
    second = execution_candidate_from_finding(
        finding(details={"evidence_ids": ("evidence-a", "evidence-b")}),
        available_evidence_ids=("evidence-b", "evidence-a"),
        now=NOW,
    )

    assert first.candidate is not None
    assert second.candidate is not None
    assert first.candidate.id == second.candidate.id
    assert first.candidate.evidence_ids == second.candidate.evidence_ids


def test_duplicate_findings_do_not_duplicate_projected_candidates() -> None:
    duplicate = finding()

    results = project_execution_candidates(
        (duplicate, duplicate),
        available_evidence_ids=("evidence-1",),
        now=NOW,
    )

    assert len(results) == 1
    assert results[0].status == ProjectionStatus.PROJECTED


def test_insufficient_compatibility_blocks_eligibility() -> None:
    result = execution_candidate_from_finding(
        finding(
            details={
                "compatibility_assessment_id": "assessment-1",
                "compatibility_status": "insufficient_information",
                "catalog_item_id": "frigate",
            },
        ),
        available_evidence_ids=("evidence-1",),
        now=NOW,
    )

    assert result.status == ProjectionStatus.INSUFFICIENT_DATA
    assert result.candidate is not None
    assert result.candidate.status == ExecutionCandidateStatus.NOT_ELIGIBLE


def test_incompatible_compatibility_blocks_eligibility() -> None:
    result = execution_candidate_from_finding(
        finding(
            details={
                "compatibility_assessment_id": "assessment-1",
                "compatibility_status": "incompatible",
                "catalog_item_id": "frigate",
            },
        ),
        available_evidence_ids=("evidence-1",),
        now=NOW,
    )

    assert result.status == ProjectionStatus.INSUFFICIENT_DATA
    assert result.candidate is not None
    assert result.candidate.status == ExecutionCandidateStatus.NOT_ELIGIBLE


def test_destructive_action_requires_destructive_approval() -> None:
    result = execution_candidate_from_finding(
        finding(details={"recommendation_class": "remove_resource"}),
        available_evidence_ids=("evidence-1",),
        now=NOW,
    )

    assert result.candidate is not None
    assert result.candidate.required_approval_level == ApprovalLevel.DESTRUCTIVE


def test_command_like_content_is_rejected() -> None:
    result = execution_candidate_from_finding(
        finding(message="Run rm -rf / immediately."),
        available_evidence_ids=("evidence-1",),
        now=NOW,
    )

    assert result.status == ProjectionStatus.REJECTED
    assert result.reason_code in {
        ProjectionReasonCode.UNSAFE_PAYLOAD,
        ProjectionReasonCode.VALIDATION_FAILED,
    }


def test_secret_like_content_is_rejected() -> None:
    result = execution_candidate_from_finding(
        finding(details={"target_id": "token=abc123"}),
        available_evidence_ids=("evidence-1",),
        now=NOW,
    )

    assert result.status == ProjectionStatus.REJECTED
    assert result.reason_code in {
        ProjectionReasonCode.UNSAFE_PAYLOAD,
        ProjectionReasonCode.VALIDATION_FAILED,
    }


def test_projection_imports_no_execution_or_io_boundaries() -> None:
    source = Path("app/execution_candidates/projection.py").read_text()

    assert "app.planning" not in source
    assert "app.actions" not in source
    assert "app.routes" not in source
    assert "requests" not in source
    assert "httpx" not in source


def test_repeated_projection_returns_identical_results() -> None:
    findings = (finding(details={"evidence_ids": ("evidence-b", "evidence-a")}),)

    first = project_execution_candidates(findings, available_evidence_ids=("evidence-a", "evidence-b"), now=NOW)
    second = project_execution_candidates(findings, available_evidence_ids=("evidence-b", "evidence-a"), now=NOW)

    assert first == second
