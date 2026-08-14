from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any, Final

from pydantic import Field
from pydantic import ValidationError as PydanticValidationError

from app.execution_candidates.classification import (
    ADVISORY_RECOMMENDATION_CLASSES,
    RecommendationClass,
    classify_recommendation_class,
    parse_recommendation_class,
)
from app.execution_candidates.eligibility import validate_candidate_for_planning
from app.execution_candidates.models import (
    ApprovalLevel,
    ComposeMutationSpecification,
    ExecutionCandidate,
    ExecutionCandidateEffectKind,
    ExecutionCandidateModel,
    ExecutionCandidateStatus,
    ExecutionCategory,
    ExecutionIntent,
    build_execution_candidate_id,
    contains_unsafe_payload,
)
from app.intelligence.findings import Finding

TRUSTED_SOURCE_SUBSYSTEMS: Final[frozenset[str]] = frozenset(
    {"discovery", "intelligence", "orion"}
)


class ProjectionStatus(StrEnum):
    """Stable outcome of projecting one Finding into an ExecutionCandidate."""

    PROJECTED = "projected"
    NOT_EXECUTABLE = "not_executable"
    INSUFFICIENT_DATA = "insufficient_data"
    UNSUPPORTED = "unsupported"
    REJECTED = "rejected"


class ProjectionReasonCode(StrEnum):
    """Controlled projection reason codes."""

    PROJECTED = "projected"
    ADVISORY_RECOMMENDATION_CLASS = "advisory_recommendation_class"
    CANDIDATE_NOT_ELIGIBLE = "candidate_not_eligible"
    INVALID_RECOMMENDATION_CLASS = "invalid_recommendation_class"
    MISSING_EVIDENCE = "missing_evidence"
    MISSING_RECOMMENDATION_CLASS = "missing_recommendation_class"
    MISSING_SOURCE_IDENTITY = "missing_source_identity"
    MISSING_TARGET = "missing_target"
    UNTRUSTED_SOURCE_SUBSYSTEM = "untrusted_source_subsystem"
    UNSAFE_PAYLOAD = "unsafe_payload"
    VALIDATION_FAILED = "validation_failed"


class ProjectionResult(ExecutionCandidateModel):
    """Immutable result of attempting to project one Finding."""

    status: ProjectionStatus
    source_finding_id: str
    candidate: ExecutionCandidate | None = None
    reason_code: ProjectionReasonCode
    message: str = Field(min_length=1)


def execution_candidate_from_finding(
    finding: Finding,
    *,
    available_evidence_ids: Iterable[str] | None = None,
    now: datetime,
) -> ProjectionResult:
    """Project one ACE Finding into an execution candidate without side effects."""

    source_finding_id = finding.id.strip() if finding.id else ""
    if not source_finding_id:
        return _result(
            ProjectionStatus.REJECTED,
            source_finding_id="missing",
            reason_code=ProjectionReasonCode.MISSING_SOURCE_IDENTITY,
            message="Finding identity is required for execution candidate projection.",
        )

    details = finding.details
    source_subsystem = _string_detail(details, "source_subsystem") or finding.source
    if source_subsystem not in TRUSTED_SOURCE_SUBSYSTEMS:
        return _result(
            ProjectionStatus.REJECTED,
            source_finding_id=source_finding_id,
            reason_code=ProjectionReasonCode.UNTRUSTED_SOURCE_SUBSYSTEM,
            message="Finding source subsystem is not trusted for execution candidate projection.",
        )

    raw_recommendation_class = _string_detail(details, "recommendation_class")
    if raw_recommendation_class is None:
        return _result(
            ProjectionStatus.UNSUPPORTED,
            source_finding_id=source_finding_id,
            reason_code=ProjectionReasonCode.MISSING_RECOMMENDATION_CLASS,
            message="Finding does not declare a structured recommendation class.",
        )

    try:
        recommendation_class = parse_recommendation_class(raw_recommendation_class)
    except ValueError:
        return _result(
            ProjectionStatus.UNSUPPORTED,
            source_finding_id=source_finding_id,
            reason_code=ProjectionReasonCode.INVALID_RECOMMENDATION_CLASS,
            message="Finding declares an unsupported recommendation class.",
        )

    target_id = _string_detail(details, "target_id")
    target_type = _string_detail(details, "target_type")
    if not target_id or not target_type:
        return _result(
            ProjectionStatus.INSUFFICIENT_DATA,
            source_finding_id=source_finding_id,
            reason_code=ProjectionReasonCode.MISSING_TARGET,
            message="Executable findings require target_id and target_type details.",
        )

    evidence_ids = _tuple_detail(details, "evidence_ids") or _tuple_detail(
        details,
        "compatibility_evidence_ids",
    )

    classification = classify_recommendation_class(recommendation_class)
    if recommendation_class in ADVISORY_RECOMMENDATION_CLASSES:
        return _result(
            ProjectionStatus.NOT_EXECUTABLE,
            source_finding_id=source_finding_id,
            reason_code=ProjectionReasonCode.ADVISORY_RECOMMENDATION_CLASS,
            message="Finding recommendation class is advisory and not executable.",
            candidate=_unsupported_candidate(
                finding=finding,
                source_finding_id=source_finding_id,
                source_subsystem=source_subsystem,
                recommendation_class=recommendation_class,
                target_id=target_id,
                target_type=target_type,
                evidence_ids=evidence_ids,
                now=now,
            ),
        )

    if classification is None:
        return _result(
            ProjectionStatus.NOT_EXECUTABLE,
            source_finding_id=source_finding_id,
            reason_code=ProjectionReasonCode.ADVISORY_RECOMMENDATION_CLASS,
            message="Finding recommendation class is advisory and not executable.",
        )
    if not evidence_ids:
        return _not_eligible_candidate_result(
            finding,
            source_finding_id=source_finding_id,
            source_subsystem=source_subsystem,
            recommendation_class=recommendation_class,
            target_id=target_id,
            target_type=target_type,
            evidence_ids=(),
            available_evidence_ids=available_evidence_ids,
            now=now,
            reason_code=ProjectionReasonCode.MISSING_EVIDENCE,
            message="Executable findings require at least one evidence reference.",
        )

    if _contains_unsafe_projection_payload(finding, details):
        return _result(
            ProjectionStatus.REJECTED,
            source_finding_id=source_finding_id,
            reason_code=ProjectionReasonCode.UNSAFE_PAYLOAD,
            message="Finding contains command-like or secret-like payloads.",
        )

    return _build_candidate_result(
        finding,
        source_finding_id=source_finding_id,
        source_subsystem=source_subsystem,
        recommendation_class=recommendation_class,
        target_id=target_id,
        target_type=target_type,
        evidence_ids=evidence_ids,
        available_evidence_ids=available_evidence_ids,
        now=now,
    )


def project_execution_candidates(
    findings: Iterable[Finding],
    *,
    available_evidence_ids: Iterable[str] | None = None,
    now: datetime,
) -> tuple[ProjectionResult, ...]:
    """Project findings in deterministic order, deduplicating candidate IDs."""

    results: list[ProjectionResult] = []
    projected_candidate_ids: set[str] = set()
    for finding in findings:
        result = execution_candidate_from_finding(
            finding,
            available_evidence_ids=available_evidence_ids,
            now=now,
        )
        if result.candidate is not None:
            if result.candidate.id in projected_candidate_ids:
                continue
            projected_candidate_ids.add(result.candidate.id)
        results.append(result)
    return tuple(results)


def _build_candidate_result(
    finding: Finding,
    *,
    source_finding_id: str,
    source_subsystem: str,
    recommendation_class: RecommendationClass,
    target_id: str,
    target_type: str,
    evidence_ids: tuple[str, ...],
    available_evidence_ids: Iterable[str] | None,
    now: datetime,
) -> ProjectionResult:
    classification = classify_recommendation_class(recommendation_class)
    if classification is None:  # defensive, callers handle this before construction.
        return _result(
            ProjectionStatus.NOT_EXECUTABLE,
            source_finding_id=source_finding_id,
            reason_code=ProjectionReasonCode.ADVISORY_RECOMMENDATION_CLASS,
            message="Finding recommendation class is advisory and not executable.",
        )

    details = finding.details
    try:
        candidate = ExecutionCandidate(
            id=build_execution_candidate_id(
                source_subsystem=source_subsystem,
                source_recommendation_id=source_finding_id,
                catalog_item_id=_string_detail(details, "catalog_item_id"),
                target_id=target_id,
                execution_category=classification.execution_category,
                execution_intent=classification.execution_intent,
            ),
            source_recommendation_id=source_finding_id,
            source_subsystem=source_subsystem,
            recommendation_class=recommendation_class.value.replace("_", "-"),
            catalog_item_id=_string_detail(details, "catalog_item_id"),
            target_id=target_id,
            target_type=target_type,
            execution_category=classification.execution_category,
            execution_intent=classification.execution_intent,
            effect_kind=(
                ExecutionCandidateEffectKind.OPERATIONAL_ACTION
                if classification.execution_intent is ExecutionIntent.RESTART_SERVICE
                else ExecutionCandidateEffectKind.REPOSITORY_CHANGE
            ),
            status=ExecutionCandidateStatus.ELIGIBLE,
            required_approval_level=classification.required_approval_level,
            rationale=finding.message,
            constraints=classification.constraints,
            evidence_ids=evidence_ids,
            compatibility_assessment_id=_string_detail(details, "compatibility_assessment_id"),
            compatibility_status=_string_detail(details, "compatibility_status"),
            relationship_ids=_tuple_detail(details, "relationship_ids")
            or _tuple_detail(details, "compatibility_finding_ids"),
            created_at=now,
            mutation=_compose_mutation(details),
        )
    except (PydanticValidationError, ValueError):
        return _result(
            ProjectionStatus.REJECTED,
            source_finding_id=source_finding_id,
            reason_code=ProjectionReasonCode.VALIDATION_FAILED,
            message="Finding could not be safely converted into an execution candidate.",
        )

    eligibility = validate_candidate_for_planning(
        candidate,
        available_evidence_ids=available_evidence_ids,
        now=now,
    )
    candidate = candidate.model_copy(update={"status": eligibility.status})
    if eligibility.status == ExecutionCandidateStatus.ELIGIBLE:
        return _result(
            ProjectionStatus.PROJECTED,
            source_finding_id=source_finding_id,
            reason_code=ProjectionReasonCode.PROJECTED,
            message="Finding projected to an eligible execution candidate.",
            candidate=candidate,
        )
    return _result(
        ProjectionStatus.INSUFFICIENT_DATA,
        source_finding_id=source_finding_id,
        reason_code=ProjectionReasonCode.CANDIDATE_NOT_ELIGIBLE,
        message="Finding projected to a candidate that is not eligible for planning.",
        candidate=candidate,
    )


def _not_eligible_candidate_result(
    finding: Finding,
    *,
    source_finding_id: str,
    source_subsystem: str,
    recommendation_class: RecommendationClass,
    target_id: str,
    target_type: str,
    evidence_ids: tuple[str, ...],
    available_evidence_ids: Iterable[str] | None,
    now: datetime,
    reason_code: ProjectionReasonCode,
    message: str,
) -> ProjectionResult:
    result = _build_candidate_result(
        finding,
        source_finding_id=source_finding_id,
        source_subsystem=source_subsystem,
        recommendation_class=recommendation_class,
        target_id=target_id,
        target_type=target_type,
        evidence_ids=evidence_ids,
        available_evidence_ids=available_evidence_ids,
        now=now,
    )
    if result.candidate is None:
        return result
    return _result(
        ProjectionStatus.INSUFFICIENT_DATA,
        source_finding_id=source_finding_id,
        reason_code=reason_code,
        message=message,
        candidate=result.candidate,
    )


def _unsupported_candidate(
    *,
    finding: Finding,
    source_finding_id: str,
    source_subsystem: str,
    recommendation_class: RecommendationClass,
    target_id: str,
    target_type: str,
    evidence_ids: tuple[str, ...],
    now: datetime,
) -> ExecutionCandidate:
    details = finding.details
    raw_target_type = target_type.replace("_", "-")
    normalized_recommendation_class = recommendation_class.value.replace("_", "-")
    return ExecutionCandidate(
        id=build_execution_candidate_id(
            source_subsystem=source_subsystem,
            source_recommendation_id=source_finding_id,
            catalog_item_id=_string_detail(details, "catalog_item_id"),
            target_id=target_id,
            execution_category=ExecutionCategory.UNSUPPORTED,
            execution_intent=ExecutionIntent.UNSUPPORTED_RECOMMENDATION,
        ),
        source_recommendation_id=source_finding_id,
        source_subsystem=source_subsystem,
        recommendation_class=normalized_recommendation_class,
        catalog_item_id=_string_detail(details, "catalog_item_id"),
        target_id=target_id,
        target_type=raw_target_type,
        execution_category=ExecutionCategory.UNSUPPORTED,
        execution_intent=ExecutionIntent.UNSUPPORTED_RECOMMENDATION,
        status=ExecutionCandidateStatus.NOT_ELIGIBLE,
        required_approval_level=ApprovalLevel.STANDARD,
        rationale=finding.message,
        constraints=(),
        evidence_ids=evidence_ids,
        compatibility_assessment_id=_string_detail(details, "compatibility_assessment_id"),
        compatibility_status=_string_detail(details, "compatibility_status"),
        relationship_ids=_tuple_detail(details, "relationship_ids")
        or _tuple_detail(details, "compatibility_finding_ids"),
        created_at=now,
    )


def _result(
    status: ProjectionStatus,
    *,
    source_finding_id: str,
    reason_code: ProjectionReasonCode,
    message: str,
    candidate: ExecutionCandidate | None = None,
) -> ProjectionResult:
    return ProjectionResult(
        status=status,
        source_finding_id=source_finding_id,
        candidate=candidate,
        reason_code=reason_code,
        message=message,
    )


def _string_detail(details: Mapping[str, Any], key: str) -> str | None:
    value = details.get(key)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _compose_mutation(details: Mapping[str, Any]) -> ComposeMutationSpecification | None:
    values = {
        key: _string_detail(details, key)
        for key in (
            "compose_file",
            "compose_service",
            "compose_property",
            "compose_operation",
            "compose_expected_value",
            "compose_desired_value",
        )
    }
    required = ("compose_file", "compose_service", "compose_property", "compose_operation", "compose_desired_value")
    if any(values[key] is None for key in required):
        return None
    return ComposeMutationSpecification(
        file=values["compose_file"],
        service=values["compose_service"],
        property=values["compose_property"],
        operation=values["compose_operation"],
        expected_value=values["compose_expected_value"],
        desired_value=values["compose_desired_value"],
        preservation_constraints=_tuple_detail(details, "compose_preservation_constraints"),
    )


def _tuple_detail(details: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = details.get(key)
    if value is None:
        return ()
    if isinstance(value, str):
        candidates: Iterable[object] = (value,)
    elif isinstance(value, Iterable):
        candidates = value
    else:
        return ()
    normalized = {
        item.strip().lower()
        for item in candidates
        if isinstance(item, str) and item.strip()
    }
    return tuple(sorted(normalized))


def _contains_unsafe_projection_payload(
    finding: Finding,
    details: Mapping[str, Any],
) -> bool:
    text_values = [finding.id, finding.message, finding.source]
    text_values.extend(value for value in details.values() if isinstance(value, str))
    return any(contains_unsafe_payload(value) for value in text_values)
