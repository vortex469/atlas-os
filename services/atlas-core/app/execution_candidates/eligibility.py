from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Final

from app.execution_candidates.classification import classify_recommendation_class
from app.execution_candidates.models import (
    DESTRUCTIVE_INTENTS,
    DISRUPTIVE_INTENTS,
    ApprovalLevel,
    ExecutionCandidate,
    ExecutionCandidateModel,
    ExecutionCandidateStatus,
    ExecutionConstraint,
    category_for_intent,
    contains_unsafe_payload,
)

SUPPORTED_SOURCE_SUBSYSTEMS: Final[tuple[str, ...]] = ("orion", "discovery", "intelligence")
_AMBIGUOUS_TARGET_IDS: Final[frozenset[str]] = frozenset({"*", "all", "unknown", "ambiguous"})
_BYPASS_MARKERS: Final[tuple[str, ...]] = (
    "bypass approval",
    "skip approval",
    "execute directly",
    "without approval",
    "skip atlas agent",
    "bypass agent",
)


class ExecutionEligibilityReason(StrEnum):
    """Stable reasons why a candidate cannot be planned."""

    CANDIDATE_NOT_ELIGIBLE = "candidate-not-eligible"
    NON_EXECUTABLE_RECOMMENDATION = "non-executable-recommendation"
    MISSING_TARGET = "missing-target"
    AMBIGUOUS_TARGET = "ambiguous-target"
    MISSING_EVIDENCE = "missing-evidence"
    UNREFERENCED_EVIDENCE = "unreferenced-evidence"
    MISSING_CATALOG_IDENTITY = "missing-catalog-identity"
    INSUFFICIENT_COMPATIBILITY = "insufficient-compatibility"
    INCOMPATIBLE_COMPATIBILITY = "incompatible-compatibility"
    UNRESOLVED_REQUIRED_RELATIONSHIP = "unresolved-required-relationship"
    UNSUPPORTED_SOURCE_SUBSYSTEM = "unsupported-source-subsystem"
    EXPIRED_CANDIDATE = "expired-candidate"
    UNSUPPORTED_INTENT_CATEGORY = "unsupported-intent-category"
    UNSAFE_PAYLOAD = "unsafe-payload"
    BYPASSES_AGENT_OR_APPROVAL = "bypasses-agent-or-approval"
    DESTRUCTIVE_APPROVAL_REQUIRED = "destructive-approval-required"
    SERVICE_DISRUPTION_CONSTRAINT_REQUIRED = "service-disruption-constraint-required"
    OPERATIONAL_TARGET_REQUIRED = "operational-target-required"


class ExecutionEligibilityFinding(ExecutionCandidateModel):
    """A deterministic eligibility blocker or reason."""

    reason: ExecutionEligibilityReason
    message: str
    evidence_ids: tuple[str, ...] = ()
    relationship_ids: tuple[str, ...] = ()


class ExecutionEligibilityResult(ExecutionCandidateModel):
    """Pure result of validating whether Atlas Agent may consider planning."""

    candidate_id: str
    status: ExecutionCandidateStatus
    findings: tuple[ExecutionEligibilityFinding, ...] = ()


def _sorted_tuple(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({value.strip().lower() for value in values if value.strip()}))


def _finding(
    reason: ExecutionEligibilityReason,
    message: str,
    *,
    evidence_ids: Iterable[str] = (),
    relationship_ids: Iterable[str] = (),
) -> ExecutionEligibilityFinding:
    return ExecutionEligibilityFinding(
        reason=reason,
        message=message,
        evidence_ids=_sorted_tuple(evidence_ids),
        relationship_ids=_sorted_tuple(relationship_ids),
    )


def validate_candidate_for_planning(
    candidate: ExecutionCandidate,
    *,
    available_evidence_ids: Iterable[str] | None = None,
    unresolved_required_relationship_ids: Iterable[str] = (),
    optional_unresolved_relationship_ids: Iterable[str] = (),
    now: datetime | None = None,
    supported_source_subsystems: Iterable[str] = SUPPORTED_SOURCE_SUBSYSTEMS,
) -> ExecutionEligibilityResult:
    """Validate planning eligibility without creating plans, approvals, or workflows."""

    del optional_unresolved_relationship_ids
    findings: list[ExecutionEligibilityFinding] = []
    validation_time = now or datetime.now(UTC)
    supported_sources = _sorted_tuple(supported_source_subsystems)

    if candidate.status == ExecutionCandidateStatus.NOT_ELIGIBLE:
        findings.append(
            _finding(
                ExecutionEligibilityReason.CANDIDATE_NOT_ELIGIBLE,
                "The candidate status is not eligible for planning.",
            )
        )

    try:
        classification = classify_recommendation_class(candidate.recommendation_class)
    except ValueError:
        classification = None
    if classification is None:
        findings.append(
            _finding(
                ExecutionEligibilityReason.NON_EXECUTABLE_RECOMMENDATION,
                "The source recommendation class is not executable.",
            )
        )

    if candidate.source_subsystem not in supported_sources:
        findings.append(
            _finding(
                ExecutionEligibilityReason.UNSUPPORTED_SOURCE_SUBSYSTEM,
                "The source subsystem is not supported for planning eligibility.",
            )
        )

    normalized_target = candidate.target_id.strip().lower()
    if not normalized_target:
        findings.append(_finding(ExecutionEligibilityReason.MISSING_TARGET, "A target is required."))
    elif normalized_target in _AMBIGUOUS_TARGET_IDS:
        findings.append(
            _finding(
                ExecutionEligibilityReason.AMBIGUOUS_TARGET,
                "The target must identify one deterministic planning target.",
            )
        )

    if candidate.execution_category != category_for_intent(candidate.execution_intent):
        findings.append(
            _finding(
                ExecutionEligibilityReason.UNSUPPORTED_INTENT_CATEGORY,
                "The execution intent is not supported by the execution category.",
            )
        )

    if candidate.execution_intent.value == "restart-service" and candidate.operational_target is None:
        findings.append(
            _finding(
                ExecutionEligibilityReason.OPERATIONAL_TARGET_REQUIRED,
                "Operational planning requires an authoritative provider resource identity.",
            )
        )

    if not candidate.evidence_ids:
        findings.append(
            _finding(
                ExecutionEligibilityReason.MISSING_EVIDENCE,
                "At least one evidence reference is required before planning.",
            )
        )
    elif available_evidence_ids is not None:
        available = set(_sorted_tuple(available_evidence_ids))
        missing = tuple(evidence_id for evidence_id in candidate.evidence_ids if evidence_id not in available)
        if missing:
            findings.append(
                _finding(
                    ExecutionEligibilityReason.UNREFERENCED_EVIDENCE,
                    "Every candidate evidence reference must be present in the source assessment.",
                    evidence_ids=missing,
                )
            )

    discovery_backed = (
        candidate.source_subsystem == "discovery"
        or candidate.compatibility_assessment_id is not None
        or ExecutionConstraint.REQUIRES_COMPATIBILITY in candidate.constraints
    )
    if discovery_backed and candidate.catalog_item_id is None:
        findings.append(
            _finding(
                ExecutionEligibilityReason.MISSING_CATALOG_IDENTITY,
                "Discovery-backed planning candidates require a catalog item identity.",
            )
        )

    if candidate.compatibility_status == "insufficient_information":
        findings.append(
            _finding(
                ExecutionEligibilityReason.INSUFFICIENT_COMPATIBILITY,
                "Insufficient compatibility information cannot be treated as planning eligibility.",
            )
        )
    elif candidate.compatibility_status == "incompatible":
        findings.append(
            _finding(
                ExecutionEligibilityReason.INCOMPATIBLE_COMPATIBILITY,
                "An incompatible compatibility assessment blocks planning eligibility.",
            )
        )

    unresolved_required = _sorted_tuple(unresolved_required_relationship_ids)
    if unresolved_required:
        findings.append(
            _finding(
                ExecutionEligibilityReason.UNRESOLVED_REQUIRED_RELATIONSHIP,
                "Required relationships must be resolved before planning.",
                relationship_ids=unresolved_required,
            )
        )

    if candidate.expires_at is not None and candidate.expires_at <= validation_time:
        findings.append(
            _finding(
                ExecutionEligibilityReason.EXPIRED_CANDIDATE,
                "The candidate has expired and requires fresh evidence.",
            )
        )

    if any(contains_unsafe_payload(value) for value in (candidate.target_id, candidate.rationale)):
        findings.append(
            _finding(
                ExecutionEligibilityReason.UNSAFE_PAYLOAD,
                "Candidates must not contain commands or secret-like payloads.",
            )
        )

    lower_rationale = candidate.rationale.lower()
    if any(marker in lower_rationale for marker in _BYPASS_MARKERS):
        findings.append(
            _finding(
                ExecutionEligibilityReason.BYPASSES_AGENT_OR_APPROVAL,
                "Candidates must not bypass Atlas Agent planning or approval boundaries.",
            )
        )

    if (
        candidate.execution_intent in DESTRUCTIVE_INTENTS
        and candidate.required_approval_level != ApprovalLevel.DESTRUCTIVE
    ):
        findings.append(
            _finding(
                ExecutionEligibilityReason.DESTRUCTIVE_APPROVAL_REQUIRED,
                "Destructive intents require destructive approval.",
            )
        )

    if (
        candidate.execution_intent in DISRUPTIVE_INTENTS
        and ExecutionConstraint.SERVICE_DISRUPTION not in candidate.constraints
        and candidate.execution_category.value in {"restart", "update", "restore", "remove"}
    ):
        findings.append(
            _finding(
                ExecutionEligibilityReason.SERVICE_DISRUPTION_CONSTRAINT_REQUIRED,
                "Disruptive intents must declare the service-disruption constraint.",
            )
        )

    status = ExecutionCandidateStatus.ELIGIBLE if not findings else ExecutionCandidateStatus.NOT_ELIGIBLE
    return ExecutionEligibilityResult(
        candidate_id=candidate.id,
        status=status,
        findings=tuple(sorted(findings, key=lambda finding: finding.reason.value)),
    )
