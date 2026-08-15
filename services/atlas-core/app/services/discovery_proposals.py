"""Read-only derivation and freshness evaluation for Discovery proposals."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.discovery.compatibility import CompatibilityAssessment, CompatibilityStatus
from app.discovery.models import CatalogEntry, DiscoveryCenterModel
from app.discovery.proposals import (
    DiscoveryOperatorProposal,
    DiscoveryProposalCompatibility,
    DiscoveryProposalDestination,
    DiscoveryProposalDestinationKind,
    DiscoveryProposalProvenance,
    DiscoveryProposalReason,
    DiscoveryProposalStatus,
    DiscoveryProposalTargetHint,
    build_discovery_operator_proposal,
    catalog_source_entry_fingerprint,
)
from app.intelligence.discovery import (
    collect_discovery_compatibility_findings,
    eligible_entries,
)
from app.intelligence.findings import Finding
from app.services.discovery import (
    DiscoveryCatalogUnavailableError,
    DiscoveryItemNotFoundError,
    get_discovery_service,
)
from app.services.discovery_compatibility import (
    DiscoveryCompatibilityServiceError,
    get_discovery_compatibility_service,
)

DEFAULT_PROPOSAL_LIFETIME = timedelta(minutes=30)
MAX_PROPOSAL_RESULTS = 100
_ADVISORY_RECOMMENDATIONS = frozenset(
    {
        "investigate_compatibility",
        "review_incompatibility",
        "review_compatibility_warning",
    }
)
_KNOWN_UNSUPPORTED_EXECUTION_RECOMMENDATIONS = frozenset({"restart_service"})


class ProposalCatalogReader(Protocol):
    def list_entries(self, **kwargs: object) -> tuple[CatalogEntry, ...]: ...

    def get_entry(self, item_id: str) -> CatalogEntry: ...


class ProposalCompatibilityReader(Protocol):
    def assess_item(self, item_id: str, *, target: str = "atlas") -> CompatibilityAssessment: ...


class DiscoveryProposalEvaluation(DiscoveryCenterModel):
    """Current read-only state for an immutable stored or transported proposal."""

    proposal: DiscoveryOperatorProposal
    status: DiscoveryProposalStatus
    reason: DiscoveryProposalReason
    effective_destination: DiscoveryProposalDestination | None
    actionable_navigation: bool


FindingCollector = Callable[[], Iterable[Finding]]
Clock = Callable[[], datetime]


class DiscoveryProposalService:
    """Derive advisory proposals without persistence, provider access, or writes."""

    def __init__(
        self,
        *,
        discovery: ProposalCatalogReader | None = None,
        compatibility: ProposalCompatibilityReader | None = None,
        finding_collector: FindingCollector = collect_discovery_compatibility_findings,
        clock: Clock | None = None,
        lifetime: timedelta = DEFAULT_PROPOSAL_LIFETIME,
    ) -> None:
        if lifetime <= timedelta(0) or lifetime > timedelta(hours=1):
            raise ValueError("proposal derivation lifetime must be within one hour")
        self._discovery = discovery or get_discovery_service()
        self._compatibility = compatibility or get_discovery_compatibility_service()
        self._finding_collector = finding_collector
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lifetime = lifetime

    def derive(self, *, target: str = "atlas", limit: int = 50) -> tuple[DiscoveryOperatorProposal, ...]:
        if limit < 1 or limit > MAX_PROPOSAL_RESULTS:
            raise ValueError("proposal result limit must be between 1 and 100")
        entries = eligible_entries(self._discovery.list_entries())
        findings = tuple(self._finding_collector())
        proposals = tuple(
            self._derive_entry(entry, target=target, findings=findings) for entry in entries
        )
        return tuple(sorted(proposals, key=lambda value: value.proposal_id))[:limit]

    def evaluate(
        self,
        proposal: DiscoveryOperatorProposal,
        *,
        now: datetime | None = None,
    ) -> DiscoveryProposalEvaluation:
        checked_at = now or self._clock()
        if checked_at.tzinfo is None or checked_at.utcoffset() is None:
            raise ValueError("proposal evaluation time must be timezone-aware")
        checked_at = checked_at.astimezone(UTC)
        if checked_at >= proposal.expires_at:
            return self._evaluation(
                proposal,
                status=DiscoveryProposalStatus.EXPIRED,
                reason=DiscoveryProposalReason.EXPIRED,
                destination=None,
            )

        try:
            entry = self._discovery.get_entry(proposal.provenance.catalog_item_id)
        except (DiscoveryCatalogUnavailableError, DiscoveryItemNotFoundError, ValueError):
            return self._evaluation(
                proposal,
                status=DiscoveryProposalStatus.STALE,
                reason=DiscoveryProposalReason.SOURCE_MISSING,
                destination=None,
            )

        current_provenance = _proposal_provenance(entry)
        if current_provenance != proposal.provenance:
            return self._evaluation(
                proposal,
                status=DiscoveryProposalStatus.STALE,
                reason=DiscoveryProposalReason.SOURCE_CHANGED,
                destination=None,
            )

        try:
            assessment = self._compatibility.assess_item(
                proposal.provenance.catalog_item_id,
                target=proposal.compatibility.target_id,
            )
            findings = tuple(self._finding_collector())
        except (
            DiscoveryCatalogUnavailableError,
            DiscoveryCompatibilityServiceError,
            DiscoveryItemNotFoundError,
            ValueError,
        ):
            return self._evaluation(
                proposal,
                status=DiscoveryProposalStatus.STALE,
                reason=DiscoveryProposalReason.SOURCE_MISSING,
                destination=None,
            )

        current = self._derive_entry(entry, target=assessment.target_id, findings=findings, assessment=assessment)
        if proposal.source_finding_id is not None and current.source_finding_id is None:
            return self._evaluation(
                proposal,
                status=DiscoveryProposalStatus.STALE,
                reason=DiscoveryProposalReason.SOURCE_MISSING,
                destination=None,
            )
        if (
            proposal.compatibility.finding_ids != current.compatibility.finding_ids
            or proposal.compatibility.evidence_ids != current.compatibility.evidence_ids
        ):
            reason = (
                DiscoveryProposalReason.EVIDENCE_MISSING
                if not set(proposal.compatibility.finding_ids).issubset(current.compatibility.finding_ids)
                or not set(proposal.compatibility.evidence_ids).issubset(current.compatibility.evidence_ids)
                else DiscoveryProposalReason.EVIDENCE_CHANGED
            )
            return self._evaluation(
                proposal,
                status=DiscoveryProposalStatus.STALE,
                reason=reason,
                destination=None,
            )
        if proposal.source_state_fingerprint != current.source_state_fingerprint:
            return self._evaluation(
                proposal,
                status=DiscoveryProposalStatus.STALE,
                reason=DiscoveryProposalReason.SOURCE_CHANGED,
                destination=None,
            )
        return self._evaluation(
            proposal,
            status=current.status,
            reason=current.reason,
            destination=current.destination,
        )

    def _derive_entry(
        self,
        entry: CatalogEntry,
        *,
        target: str,
        findings: tuple[Finding, ...],
        assessment: CompatibilityAssessment | None = None,
    ) -> DiscoveryOperatorProposal:
        assessment = assessment or self._compatibility.assess_item(entry.item.id, target=target)
        matches = tuple(
            finding
            for finding in findings
            if _is_matching_discovery_finding(finding, entry.item.id, assessment)
        )
        source_finding = matches[0] if len(matches) == 1 else None
        compatibility = _proposal_compatibility(assessment, source_finding)
        status, reason, destination = _derive_state(
            assessment=assessment,
            source_finding=source_finding,
            matching_finding_count=len(matches),
            compatibility=compatibility,
        )
        generated_at = _require_aware_utc(self._clock())
        return build_discovery_operator_proposal(
            status=status,
            reason=reason,
            provenance=_proposal_provenance(entry),
            source_finding_id=source_finding.id if source_finding else None,
            compatibility=compatibility,
            destination=DiscoveryProposalDestination(kind=destination),
            intent_hint=None,
            target_hints=(DiscoveryProposalTargetHint(catalog_target_id=assessment.target_id),),
            generated_at=generated_at,
            expires_at=generated_at + self._lifetime,
        )

    @staticmethod
    def _evaluation(
        proposal: DiscoveryOperatorProposal,
        *,
        status: DiscoveryProposalStatus,
        reason: DiscoveryProposalReason,
        destination: DiscoveryProposalDestination | None,
    ) -> DiscoveryProposalEvaluation:
        actionable = (
            status is DiscoveryProposalStatus.CURRENT
            and destination is not None
            and destination.kind
            is DiscoveryProposalDestinationKind.OPERATOR_MAINTENANCE_SELECTION
        )
        return DiscoveryProposalEvaluation(
            proposal=proposal,
            status=status,
            reason=reason,
            effective_destination=destination,
            actionable_navigation=actionable,
        )


def _proposal_provenance(entry: CatalogEntry) -> DiscoveryProposalProvenance:
    entry_id = entry.provenance.entry_id
    if entry_id is None:
        raise ValueError("proposal derivation requires catalog provenance entry id")
    return DiscoveryProposalProvenance(
        catalog_source_type=entry.provenance.source_type,
        catalog_entry_id=entry_id,
        catalog_item_id=entry.item.id,
        source_version=entry.provenance.version,
        source_entry_fingerprint=(
            None if entry.provenance.version else catalog_source_entry_fingerprint(entry)
        ),
    )


def _proposal_compatibility(
    assessment: CompatibilityAssessment,
    source_finding: Finding | None,
) -> DiscoveryProposalCompatibility:
    finding_ids = {value.id for value in assessment.findings}
    evidence_ids = {value.id for value in assessment.evidence}
    if source_finding is not None:
        finding_ids.update(_detail_references(source_finding, "compatibility_finding_ids"))
        evidence_ids.update(_detail_references(source_finding, "compatibility_evidence_ids"))
    return DiscoveryProposalCompatibility(
        target_id=assessment.target_id,
        target_type=assessment.target_type,
        status=assessment.status,
        finding_ids=tuple(finding_ids),
        evidence_ids=tuple(evidence_ids),
    )


def _derive_state(
    *,
    assessment: CompatibilityAssessment,
    source_finding: Finding | None,
    matching_finding_count: int,
    compatibility: DiscoveryProposalCompatibility,
) -> tuple[DiscoveryProposalStatus, DiscoveryProposalReason, DiscoveryProposalDestinationKind]:
    if assessment.status is CompatibilityStatus.COMPATIBLE and matching_finding_count == 0:
        return (
            DiscoveryProposalStatus.CURRENT,
            DiscoveryProposalReason.COMPATIBLE,
            DiscoveryProposalDestinationKind.DISCOVERY_DETAIL,
        )
    if matching_finding_count == 0:
        return (
            DiscoveryProposalStatus.NOT_ACTIONABLE,
            DiscoveryProposalReason.SOURCE_MISSING,
            DiscoveryProposalDestinationKind.DISCOVERY_DETAIL,
        )
    if matching_finding_count != 1 or source_finding is None:
        return (
            DiscoveryProposalStatus.NOT_ACTIONABLE,
            DiscoveryProposalReason.NO_SUPPORTED_DESTINATION,
            DiscoveryProposalDestinationKind.DISCOVERY_DETAIL,
        )

    recommendation = _recommendation_class(source_finding)
    if recommendation in _KNOWN_UNSUPPORTED_EXECUTION_RECOMMENDATIONS:
        return (
            DiscoveryProposalStatus.NOT_ACTIONABLE,
            DiscoveryProposalReason.UNSUPPORTED_RESOURCE,
            DiscoveryProposalDestinationKind.DISCOVERY_DETAIL,
        )
    if recommendation not in _ADVISORY_RECOMMENDATIONS:
        return (
            DiscoveryProposalStatus.NOT_ACTIONABLE,
            DiscoveryProposalReason.NO_SUPPORTED_DESTINATION,
            DiscoveryProposalDestinationKind.DISCOVERY_DETAIL,
        )

    actual_findings = {value.id for value in assessment.findings}
    actual_evidence = {value.id for value in assessment.evidence}
    if not set(compatibility.finding_ids).issubset(actual_findings) or not set(
        compatibility.evidence_ids
    ).issubset(actual_evidence):
        return (
            DiscoveryProposalStatus.NOT_ACTIONABLE,
            DiscoveryProposalReason.EVIDENCE_MISSING,
            DiscoveryProposalDestinationKind.DISCOVERY_DETAIL,
        )
    if assessment.status is CompatibilityStatus.INCOMPATIBLE:
        reason = DiscoveryProposalReason.INCOMPATIBLE
    elif assessment.status is CompatibilityStatus.INSUFFICIENT_INFORMATION:
        reason = DiscoveryProposalReason.INSUFFICIENT_INFORMATION
    elif assessment.status is CompatibilityStatus.COMPATIBLE_WITH_WARNINGS:
        reason = DiscoveryProposalReason.COMPATIBILITY_WARNING
    else:
        return (
            DiscoveryProposalStatus.NOT_ACTIONABLE,
            DiscoveryProposalReason.NO_SUPPORTED_DESTINATION,
            DiscoveryProposalDestinationKind.DISCOVERY_DETAIL,
        )
    return (
        DiscoveryProposalStatus.CURRENT,
        reason,
        DiscoveryProposalDestinationKind.COMPATIBILITY_REVIEW,
    )


def _is_matching_discovery_finding(
    finding: Finding,
    item_id: str,
    assessment: CompatibilityAssessment,
) -> bool:
    details = finding.details
    return (
        finding.source == "discovery"
        and finding.category == "discovery-compatibility"
        and details.get("source_subsystem") == "discovery"
        and details.get("catalog_item_id") == item_id
        and details.get("target_id") == assessment.target_id
        and details.get("target_type") == assessment.target_type
        and details.get("compatibility_status") == assessment.status.value
    )


def _recommendation_class(finding: Finding) -> str | None:
    value = finding.details.get("recommendation_class")
    return value if isinstance(value, str) else None


def _detail_references(finding: Finding, field: str) -> tuple[str, ...]:
    value = finding.details.get(field)
    if not isinstance(value, (tuple, list)) or not all(isinstance(item, str) for item in value):
        return ()
    return tuple(value)


def _require_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("proposal derivation clock must be timezone-aware")
    return value.astimezone(UTC)


_discovery_proposal_service = DiscoveryProposalService()


def get_discovery_proposal_service() -> DiscoveryProposalService:
    return _discovery_proposal_service
