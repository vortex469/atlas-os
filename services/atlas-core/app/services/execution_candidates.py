from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from app.core.logging import get_logger
from app.execution_candidates.models import (
    ExecutionCandidate,
    ExecutionCandidateStatus,
    ExecutionCategory,
    ExecutionIntent,
    OperationalTargetReference,
    OperationalTargetResolutionReason,
)
from app.execution_candidates.operator_intents import (
    OperatorIntentStore,
    TargetResolver,
    project_operator_intent_with_reason,
)
from app.execution_candidates.projection import project_execution_candidates
from app.intelligence.coordinator import (
    _performance_findings,
    collect_discovery_compatibility_findings,
    collect_findings,
    collect_provider_findings_with_telemetry,
)
from app.intelligence.development_fixture import (
    collect_development_candidate_findings,
    fixture_evidence_ids,
    is_rc1_validation_smoke_enabled,
)
from app.intelligence.findings import Finding
from app.providers import ProviderNotFoundError
from app.services.provider_resources import (
    OperationalTargetAmbiguousError,
    OperationalTargetIdentityUnavailableError,
    OperationalTargetMarkedMissingError,
    OperationalTargetResourceNotFoundError,
    OperationalTargetSelectorError,
    OperationalTargetTypeMismatchError,
    ProviderResourceOperationError,
    ProviderResourcesNotSupportedError,
    resolve_operational_target,
)

logger = get_logger("atlas.execution_candidates")
FindingCollector = Callable[[], Iterable[Finding]]


class ExecutionCandidateServiceError(RuntimeError):
    """Base error for current execution candidate collection failures."""


class ExecutionCandidateCollectionError(ExecutionCandidateServiceError):
    """Raised when current intelligence findings cannot be collected."""


class ExecutionCandidateNotFoundError(ExecutionCandidateServiceError):
    """Raised when a current candidate ID is not present."""


_OPERATIONAL_RESOLUTION_REASONS = {
    OperationalTargetResourceNotFoundError: OperationalTargetResolutionReason.NOT_FOUND,
    OperationalTargetAmbiguousError: OperationalTargetResolutionReason.AMBIGUOUS,
    OperationalTargetTypeMismatchError: OperationalTargetResolutionReason.TYPE_MISMATCH,
    OperationalTargetMarkedMissingError: OperationalTargetResolutionReason.MARKED_MISSING,
    OperationalTargetIdentityUnavailableError: OperationalTargetResolutionReason.IDENTITY_UNAVAILABLE,
    OperationalTargetSelectorError: OperationalTargetResolutionReason.SELECTOR_INVALID,
}


async def _enrich_operational_candidate(
    candidate: ExecutionCandidate,
    finding: Finding,
    *,
    available_evidence_ids: Iterable[str],
    now: datetime,
) -> ExecutionCandidate:
    if candidate.execution_intent is not ExecutionIntent.RESTART_SERVICE:
        return candidate

    provider_id = finding.details.get("provider_id")
    if not isinstance(provider_id, str) or not provider_id.strip():
        return candidate.model_copy(
            update={
                "status": ExecutionCandidateStatus.NOT_ELIGIBLE,
                "operational_target_resolution_reason": OperationalTargetResolutionReason.SELECTOR_INVALID,
            }
        )
    try:
        resolved = await resolve_operational_target(
            provider_id.strip(), candidate.target_id, candidate.target_type
        )
    except tuple(_OPERATIONAL_RESOLUTION_REASONS) as error:
        reason = _OPERATIONAL_RESOLUTION_REASONS[type(error)]
        return candidate.model_copy(
            update={
                "status": ExecutionCandidateStatus.NOT_ELIGIBLE,
                "operational_target_resolution_reason": reason,
            }
        )
    except (
        ProviderNotFoundError,
        ProviderResourceOperationError,
        ProviderResourcesNotSupportedError,
    ) as error:
        raise ExecutionCandidateCollectionError(
            "Unable to determine current operational target state."
        ) from error

    enriched = candidate.model_copy(
        update={
            "status": ExecutionCandidateStatus.ELIGIBLE,
            "operational_target": OperationalTargetReference(
                provider_id=resolved.provider.id,
                resource_id=resolved.resource.resource_id,
                resource_type=resolved.resource.resource_type,
                resource_fingerprint=resolved.resource_fingerprint,
                resource_version=None,
                expected_state=resolved.resource.current_state,
            ),
            "operational_target_resolution_reason": None,
        }
    )
    from app.execution_candidates.eligibility import validate_candidate_for_planning

    eligibility = validate_candidate_for_planning(
        enriched,
        available_evidence_ids=available_evidence_ids,
        now=now,
    )
    return enriched.model_copy(update={"status": eligibility.status})


def _sort_candidates(
    candidates: Iterable[ExecutionCandidate],
) -> tuple[ExecutionCandidate, ...]:
    return tuple(sorted(candidates, key=lambda candidate: candidate.id))


def filter_candidates(
    candidates: Iterable[ExecutionCandidate],
    *,
    statuses: Iterable[ExecutionCandidateStatus] = (),
    categories: Iterable[ExecutionCategory] = (),
    intents: Iterable[ExecutionIntent] = (),
    source_subsystems: Iterable[str] = (),
    target_ids: Iterable[str] = (),
) -> tuple[ExecutionCandidate, ...]:
    """Apply deterministic AND-combined candidate filters."""

    status_filter = set(statuses)
    category_filter = set(categories)
    intent_filter = set(intents)
    source_filter = {value.strip().lower() for value in source_subsystems if value.strip()}
    target_filter = {value.strip().lower() for value in target_ids if value.strip()}

    filtered: list[ExecutionCandidate] = []
    for candidate in candidates:
        if status_filter and candidate.status not in status_filter:
            continue
        if category_filter and candidate.execution_category not in category_filter:
            continue
        if intent_filter and candidate.execution_intent not in intent_filter:
            continue
        if source_filter and candidate.source_subsystem.lower() not in source_filter:
            continue
        if target_filter and candidate.target_id.lower() not in target_filter:
            continue
        filtered.append(candidate)
    return _sort_candidates(filtered)


def paginate_candidates(
    candidates: tuple[ExecutionCandidate, ...],
    *,
    limit: int,
    offset: int,
) -> tuple[tuple[ExecutionCandidate, ...], int, bool]:
    total = len(candidates)
    page = candidates[offset : offset + limit]
    has_more = offset + len(page) < total
    return page, total, has_more


async def collect_current_findings() -> tuple[Finding, ...]:
    """Collect current findings without mutating ACE reports or telemetry history."""

    if is_rc1_validation_smoke_enabled():
        return collect_development_candidate_findings()
    try:
        findings = list(collect_findings())
        provider_findings, telemetry = await collect_provider_findings_with_telemetry()
        findings.extend(provider_findings)
        try:
            findings.extend(collect_discovery_compatibility_findings())
        except Exception:
            logger.exception("Unable to collect Discovery compatibility findings for candidates")
        findings.extend(_performance_findings(telemetry))
        findings.extend(collect_development_candidate_findings())
    except Exception as error:
        raise ExecutionCandidateCollectionError(
            "Unable to collect current intelligence findings."
        ) from error
    return tuple(findings)


async def collect_current_execution_candidates(
    *,
    available_evidence_ids: Iterable[str] | None = (),
    now: datetime | None = None,
    finding_collector: Callable[[], tuple[Finding, ...]] | None = None,
    operator_intent_store: OperatorIntentStore | None = None,
    operational_target_resolver: TargetResolver = resolve_operational_target,
) -> tuple[ExecutionCandidate, ...]:
    """Project the current read-only candidate set from current findings."""

    projection_time = now or datetime.now(UTC)

    if available_evidence_ids is None:
        available_evidence_ids = ()
    augmented_evidence_ids = tuple(
        sorted(set(available_evidence_ids) | set(fixture_evidence_ids()))
    )

    try:
        findings = finding_collector() if finding_collector is not None else await collect_current_findings()
    except Exception as error:
        if isinstance(error, ExecutionCandidateCollectionError):
            raise
        raise ExecutionCandidateCollectionError(
            "Unable to collect current intelligence findings."
        ) from error

    results = project_execution_candidates(
        findings,
        available_evidence_ids=augmented_evidence_ids,
        now=projection_time,
    )
    findings_by_id = {finding.id: finding for finding in findings}
    candidates: list[ExecutionCandidate] = []
    for result in results:
        if result.candidate is None:
            logger.debug(
                "Execution candidate projection skipped finding %s: %s",
                result.source_finding_id,
                result.reason_code.value,
            )
            continue
        candidate = result.candidate
        finding = findings_by_id.get(result.source_finding_id)
        if finding is not None:
            candidate = await _enrich_operational_candidate(
                candidate,
                finding,
                available_evidence_ids=augmented_evidence_ids,
                now=projection_time,
            )
        candidates.append(candidate)
    if operator_intent_store is not None:
        for record in operator_intent_store.list():
            projection = await project_operator_intent_with_reason(
                record,
                resolver=operational_target_resolver,
                now=projection_time,
            )
            candidate = projection.candidate
            candidates.append(candidate)
            operator_intent_store.append_audit(
                event="candidate_projected",
                reason=projection.reason,
                occurred_at=projection_time,
                record_id=record.record_id,
                candidate_id=candidate.id,
                operator_id=record.operator_id,
            )
    return _sort_candidates(candidates)


async def get_current_execution_candidate(
    candidate_id: str,
    *,
    available_evidence_ids: Iterable[str] | None = (),
    now: datetime | None = None,
    finding_collector: Callable[[], tuple[Finding, ...]] | None = None,
    operator_intent_store: OperatorIntentStore | None = None,
    operational_target_resolver: TargetResolver = resolve_operational_target,
) -> ExecutionCandidate:
    """Return one current candidate by deterministic ID."""

    candidates = await collect_current_execution_candidates(
        available_evidence_ids=available_evidence_ids,
        now=now,
        finding_collector=finding_collector,
        operator_intent_store=operator_intent_store,
        operational_target_resolver=operational_target_resolver,
    )
    for candidate in candidates:
        if candidate.id == candidate_id:
            return candidate
    raise ExecutionCandidateNotFoundError("Execution candidate is not present in the current projection.")
