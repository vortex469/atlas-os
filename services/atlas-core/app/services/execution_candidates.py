from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from app.core.logging import get_logger
from app.execution_candidates.models import (
    ExecutionCandidate,
    ExecutionCandidateStatus,
    ExecutionCategory,
    ExecutionIntent,
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

logger = get_logger("atlas.execution_candidates")
FindingCollector = Callable[[], Iterable[Finding]]


class ExecutionCandidateServiceError(RuntimeError):
    """Base error for current execution candidate collection failures."""


class ExecutionCandidateCollectionError(ExecutionCandidateServiceError):
    """Raised when current intelligence findings cannot be collected."""


class ExecutionCandidateNotFoundError(ExecutionCandidateServiceError):
    """Raised when a current candidate ID is not present."""


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
    candidates: list[ExecutionCandidate] = []
    for result in results:
        if result.candidate is None:
            logger.debug(
                "Execution candidate projection skipped finding %s: %s",
                result.source_finding_id,
                result.reason_code.value,
            )
            continue
        candidates.append(result.candidate)
    return _sort_candidates(candidates)


async def get_current_execution_candidate(
    candidate_id: str,
    *,
    available_evidence_ids: Iterable[str] | None = (),
    now: datetime | None = None,
    finding_collector: Callable[[], tuple[Finding, ...]] | None = None,
) -> ExecutionCandidate:
    """Return one current candidate by deterministic ID."""

    candidates = await collect_current_execution_candidates(
        available_evidence_ids=available_evidence_ids,
        now=now,
        finding_collector=finding_collector,
    )
    for candidate in candidates:
        if candidate.id == candidate_id:
            return candidate
    raise ExecutionCandidateNotFoundError("Execution candidate is not present in the current projection.")
