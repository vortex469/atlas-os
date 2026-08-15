from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.discovery.compatibility import (
    CompatibilityAssessment,
    CompatibilityCheckType,
    CompatibilityEvidence,
    CompatibilityFinding,
    CompatibilityFindingSeverity,
    CompatibilityStatus,
)
from app.discovery.models import (
    CatalogEntry,
    CatalogProvenance,
    CatalogSourceType,
    DiscoveryItem,
    DiscoveryItemType,
    DiscoveryRequirements,
    ResourceRequirements,
)
from app.discovery.proposals import (
    DiscoveryProposalDestination,
    DiscoveryProposalDestinationKind,
    DiscoveryProposalReason,
    DiscoveryProposalStatus,
    build_discovery_operator_proposal,
)
from app.intelligence.findings import Finding, Severity
from app.services.discovery import DiscoveryItemNotFoundError
from app.services.discovery_proposals import (
    MAX_PROPOSAL_RESULTS,
    DiscoveryProposalService,
)

NOW = datetime(2026, 8, 15, 12, tzinfo=UTC)


class CatalogReader:
    def __init__(self, entries: tuple[CatalogEntry, ...]) -> None:
        self.entries = entries
        self.list_calls = 0
        self.get_calls = 0

    def list_entries(self, **kwargs: object) -> tuple[CatalogEntry, ...]:
        self.list_calls += 1
        return self.entries

    def get_entry(self, item_id: str) -> CatalogEntry:
        self.get_calls += 1
        match = next((entry for entry in self.entries if entry.item.id == item_id), None)
        if match is None:
            raise DiscoveryItemNotFoundError("missing")
        return match


class CompatibilityReader:
    def __init__(self, assessments: dict[str, CompatibilityAssessment]) -> None:
        self.assessments = assessments
        self.calls = 0

    def assess_item(self, item_id: str, *, target: str = "atlas") -> CompatibilityAssessment:
        self.calls += 1
        return self.assessments[item_id]


def entry(item_id: str = "frigate", *, version: str | None = None) -> CatalogEntry:
    return CatalogEntry(
        item=DiscoveryItem(
            id=item_id,
            type=DiscoveryItemType.APPLICATION,
            name=item_id.title(),
            requirements=DiscoveryRequirements(
                resources=ResourceRequirements(memory_mb_min=512)
            ),
        ),
        provenance=CatalogProvenance(
            source_type=CatalogSourceType.CURATED,
            source=f"catalog/{item_id}.yaml",
            entry_id=item_id,
            version=version,
        ),
    )


def assessment(
    status: CompatibilityStatus,
    *,
    item_id: str = "frigate",
    finding_id: str = "finding-memory",
    evidence_id: str = "evidence-memory",
) -> CompatibilityAssessment:
    if status is CompatibilityStatus.COMPATIBLE:
        return CompatibilityAssessment(
            item_id=item_id,
            target_id="atlas",
            target_type="atlas_environment",
            status=status,
            checked_at=NOW,
        )
    severity = (
        CompatibilityFindingSeverity.BLOCKER
        if status is CompatibilityStatus.INCOMPATIBLE
        else CompatibilityFindingSeverity.WARNING
        if status is CompatibilityStatus.COMPATIBLE_WITH_WARNINGS
        else CompatibilityFindingSeverity.UNKNOWN
    )
    evidence = CompatibilityEvidence(
        id=evidence_id,
        check_type=CompatibilityCheckType.RESOURCE,
        subject="requirements.memory",
        status=status,
        message="Controlled compatibility evidence.",
        source="discovery",
    )
    finding_value = CompatibilityFinding(
        id=finding_id,
        check_type=CompatibilityCheckType.RESOURCE,
        severity=severity,
        status=status,
        subject="requirements.memory",
        message="Controlled compatibility finding.",
        evidence_ids=(evidence_id,),
    )
    return CompatibilityAssessment(
        item_id=item_id,
        target_id="atlas",
        target_type="atlas_environment",
        status=status,
        checked_at=NOW,
        findings=(finding_value,),
        evidence=(evidence,),
        unknown_facts=("memory_mb",)
        if status is CompatibilityStatus.INSUFFICIENT_INFORMATION
        else (),
    )


def source_finding(
    value: CompatibilityAssessment,
    *,
    recommendation_class: str | None = None,
    evidence_ids: tuple[str, ...] | None = None,
) -> Finding:
    default_class = {
        CompatibilityStatus.INCOMPATIBLE: "review_incompatibility",
        CompatibilityStatus.INSUFFICIENT_INFORMATION: "investigate_compatibility",
        CompatibilityStatus.COMPATIBLE_WITH_WARNINGS: "review_compatibility_warning",
    }.get(value.status, "review_compatibility_warning")
    return Finding(
        id=f"discovery-{value.item_id}-atlas-{default_class}",
        severity=Severity.WARNING,
        category="discovery-compatibility",
        source="discovery",
        title="Controlled finding",
        message="Controlled finding",
        details={
            "source_subsystem": "discovery",
            "recommendation_class": recommendation_class or default_class,
            "catalog_item_id": value.item_id,
            "target_id": value.target_id,
            "target_type": value.target_type,
            "compatibility_status": value.status.value,
            "compatibility_finding_ids": tuple(item.id for item in value.findings),
            "compatibility_evidence_ids": evidence_ids
            if evidence_ids is not None
            else tuple(item.id for item in value.evidence),
        },
        affects_health=False,
        score_penalty=0,
    )


def service(
    value: CompatibilityAssessment,
    *,
    entries: tuple[CatalogEntry, ...] | None = None,
    findings: tuple[Finding, ...] | None = None,
) -> tuple[DiscoveryProposalService, CatalogReader, CompatibilityReader]:
    catalog = CatalogReader(entries or (entry(value.item_id),))
    compatibility = CompatibilityReader({value.item_id: value})
    selected = findings if findings is not None else (
        () if value.status is CompatibilityStatus.COMPATIBLE else (source_finding(value),)
    )
    result = DiscoveryProposalService(
        discovery=catalog,
        compatibility=compatibility,
        finding_collector=lambda: selected,
        clock=lambda: NOW,
    )
    return result, catalog, compatibility


@pytest.mark.parametrize(
    ("status", "reason", "destination"),
    (
        (CompatibilityStatus.COMPATIBLE, DiscoveryProposalReason.COMPATIBLE, DiscoveryProposalDestinationKind.DISCOVERY_DETAIL),
        (CompatibilityStatus.INCOMPATIBLE, DiscoveryProposalReason.INCOMPATIBLE, DiscoveryProposalDestinationKind.COMPATIBILITY_REVIEW),
        (CompatibilityStatus.INSUFFICIENT_INFORMATION, DiscoveryProposalReason.INSUFFICIENT_INFORMATION, DiscoveryProposalDestinationKind.COMPATIBILITY_REVIEW),
        (CompatibilityStatus.COMPATIBLE_WITH_WARNINGS, DiscoveryProposalReason.COMPATIBILITY_WARNING, DiscoveryProposalDestinationKind.COMPATIBILITY_REVIEW),
    ),
)
def test_closed_compatibility_derivation(
    status: CompatibilityStatus,
    reason: DiscoveryProposalReason,
    destination: DiscoveryProposalDestinationKind,
) -> None:
    proposal = service(assessment(status))[0].derive()[0]
    assert proposal.status is DiscoveryProposalStatus.CURRENT
    assert proposal.reason is reason
    assert proposal.destination.kind is destination
    assert proposal.intent_hint is None


def test_missing_source_finding_fails_closed() -> None:
    proposal = service(assessment(CompatibilityStatus.INCOMPATIBLE), findings=())[0].derive()[0]
    assert proposal.status is DiscoveryProposalStatus.NOT_ACTIONABLE
    assert proposal.reason is DiscoveryProposalReason.SOURCE_MISSING
    assert proposal.destination.kind is DiscoveryProposalDestinationKind.DISCOVERY_DETAIL


def test_missing_evidence_fails_closed_without_dropping_reference() -> None:
    value = assessment(CompatibilityStatus.INCOMPATIBLE)
    finding = source_finding(value, evidence_ids=("missing-evidence",))
    proposal = service(value, findings=(finding,))[0].derive()[0]
    assert proposal.status is DiscoveryProposalStatus.NOT_ACTIONABLE
    assert proposal.reason is DiscoveryProposalReason.EVIDENCE_MISSING
    assert "missing-evidence" in proposal.compatibility.evidence_ids


@pytest.mark.parametrize(
    ("recommendation", "reason"),
    (
        ("unknown_recommendation", DiscoveryProposalReason.NO_SUPPORTED_DESTINATION),
        ("restart_service", DiscoveryProposalReason.UNSUPPORTED_RESOURCE),
    ),
)
def test_unknown_and_unsupported_recommendations_fail_closed(
    recommendation: str, reason: DiscoveryProposalReason
) -> None:
    value = assessment(CompatibilityStatus.INCOMPATIBLE)
    proposal = service(
        value, findings=(source_finding(value, recommendation_class=recommendation),)
    )[0].derive()[0]
    assert proposal.status is DiscoveryProposalStatus.NOT_ACTIONABLE
    assert proposal.reason is reason
    assert proposal.intent_hint is None
    assert proposal.destination.kind is DiscoveryProposalDestinationKind.DISCOVERY_DETAIL


def test_current_source_state_evaluates_current_without_changing_identity() -> None:
    derivation = service(assessment(CompatibilityStatus.INCOMPATIBLE))[0]
    proposal = derivation.derive()[0]
    result = derivation.evaluate(proposal, now=NOW + timedelta(minutes=1))
    assert result.status is DiscoveryProposalStatus.CURRENT
    assert result.proposal.proposal_id == proposal.proposal_id
    assert result.effective_destination == proposal.destination


def test_changed_provenance_is_stale() -> None:
    derivation, catalog, _ = service(assessment(CompatibilityStatus.INCOMPATIBLE))
    proposal = derivation.derive()[0]
    catalog.entries = (entry(version="changed"),)
    result = derivation.evaluate(proposal, now=NOW + timedelta(minutes=1))
    assert result.status is DiscoveryProposalStatus.STALE
    assert result.reason is DiscoveryProposalReason.SOURCE_CHANGED
    assert result.effective_destination is None


def test_missing_catalog_item_is_stale() -> None:
    derivation, catalog, _ = service(assessment(CompatibilityStatus.INCOMPATIBLE))
    proposal = derivation.derive()[0]
    catalog.entries = ()
    result = derivation.evaluate(proposal, now=NOW + timedelta(minutes=1))
    assert result.status is DiscoveryProposalStatus.STALE
    assert result.reason is DiscoveryProposalReason.SOURCE_MISSING


def test_changed_and_missing_evidence_are_stale() -> None:
    original = assessment(CompatibilityStatus.INCOMPATIBLE)
    derivation, _, compatibility = service(original)
    proposal = derivation.derive()[0]
    changed = assessment(
        CompatibilityStatus.INCOMPATIBLE,
        finding_id="finding-new",
        evidence_id="evidence-new",
    )
    compatibility.assessments["frigate"] = changed
    result = derivation.evaluate(proposal, now=NOW + timedelta(minutes=1))
    assert result.status is DiscoveryProposalStatus.STALE
    assert result.reason is DiscoveryProposalReason.EVIDENCE_CHANGED


def test_expired_proposal_is_non_actionable_without_rebuilding_identity() -> None:
    derivation = service(assessment(CompatibilityStatus.COMPATIBLE))[0]
    proposal = derivation.derive()[0]
    result = derivation.evaluate(proposal, now=proposal.expires_at)
    assert result.status is DiscoveryProposalStatus.EXPIRED
    assert result.reason is DiscoveryProposalReason.EXPIRED
    assert result.effective_destination is None
    assert result.proposal.proposal_fingerprint == proposal.proposal_fingerprint


def test_stale_proposal_loses_maintenance_navigation() -> None:
    derivation, catalog, _ = service(assessment(CompatibilityStatus.COMPATIBLE))
    original = derivation.derive()[0]
    maintenance = build_discovery_operator_proposal(
        status=original.status,
        reason=original.reason,
        provenance=original.provenance,
        compatibility=original.compatibility,
        destination=DiscoveryProposalDestination(
            kind=DiscoveryProposalDestinationKind.OPERATOR_MAINTENANCE_SELECTION
        ),
        generated_at=original.generated_at,
        expires_at=original.expires_at,
        source_finding_id=original.source_finding_id,
        target_hints=original.target_hints,
    )
    catalog.entries = ()
    result = derivation.evaluate(maintenance, now=NOW + timedelta(minutes=1))
    assert result.effective_destination is None
    assert result.actionable_navigation is False


def test_incompatible_and_insufficient_never_get_maintenance_destination() -> None:
    for status in (
        CompatibilityStatus.INCOMPATIBLE,
        CompatibilityStatus.INSUFFICIENT_INFORMATION,
    ):
        proposal = service(assessment(status))[0].derive()[0]
        assert proposal.destination.kind is not DiscoveryProposalDestinationKind.OPERATOR_MAINTENANCE_SELECTION


def test_results_are_bounded_and_deterministically_ordered() -> None:
    entries = (entry("zeta"), entry("alpha"))
    values = {
        item.item.id: assessment(CompatibilityStatus.COMPATIBLE, item_id=item.item.id)
        for item in entries
    }
    derivation = DiscoveryProposalService(
        discovery=CatalogReader(entries),
        compatibility=CompatibilityReader(values),
        finding_collector=lambda: (),
        clock=lambda: NOW,
    )
    proposals = derivation.derive(limit=2)
    assert tuple(item.proposal_id for item in proposals) == tuple(
        sorted(item.proposal_id for item in proposals)
    )
    assert len(derivation.derive(limit=1)) == 1
    with pytest.raises(ValueError):
        derivation.derive(limit=MAX_PROPOSAL_RESULTS + 1)


def test_derivation_is_read_only_and_schema_is_redacted() -> None:
    derivation, catalog, compatibility = service(assessment(CompatibilityStatus.INCOMPATIBLE))
    proposal = derivation.derive()[0]
    assert catalog.list_calls == 1
    assert catalog.get_calls == 0
    assert compatibility.calls == 1
    payload = json.loads(proposal.model_dump_json())
    field_names: set[str] = set()

    def collect_fields(value: object) -> None:
        if isinstance(value, dict):
            field_names.update(str(key).lower() for key in value)
            for child in value.values():
                collect_fields(child)
        elif isinstance(value, list):
            for child in value:
                collect_fields(child)

    collect_fields(payload)
    for forbidden in (
        "vmgenid",
        "target_fingerprint",
        "provider_action_id",
        "command",
            "environment_variables",
        "authorization",
        "cookie",
        "token",
        "native_payload",
    ):
        assert forbidden not in field_names
