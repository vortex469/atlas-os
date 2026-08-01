from __future__ import annotations

from datetime import UTC, datetime

from app.discovery.compatibility import (
    CompatibilityAssessment,
    CompatibilityCheckType,
    CompatibilityEvidence,
    CompatibilityFinding,
    CompatibilityFindingSeverity,
    CompatibilityStatus,
)
from app.discovery.models import (
    CapabilityReference,
    CatalogEntry,
    CatalogProvenance,
    DiscoveryItem,
    DiscoveryItemStatus,
    DiscoveryRelationship,
    DiscoveryRelationshipType,
    DiscoveryRequirements,
    NetworkRequirements,
    PlatformRequirements,
    PortRequirement,
    ResourceRequirements,
)
from app.intelligence.discovery import (
    collect_discovery_compatibility_findings,
    eligible_entries,
    findings_from_compatibility_assessment,
    is_eligible_for_discovery_intelligence,
)
from app.intelligence.findings import Severity

CHECKED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def item(
    item_id: str = "frigate",
    *,
    status: DiscoveryItemStatus = DiscoveryItemStatus.ACTIVE,
    requirements: DiscoveryRequirements | None = None,
    relationships: tuple[DiscoveryRelationship, ...] = (),
) -> DiscoveryItem:
    return DiscoveryItem(
        id=item_id,
        type="application",
        status=status,
        name="Frigate",
        description="Video NVR",
        requirements=requirements or DiscoveryRequirements(),
        relationships=relationships,
    )


def entry(discovery_item: DiscoveryItem) -> CatalogEntry:
    return CatalogEntry(
        item=discovery_item,
        provenance=CatalogProvenance(
            source="test-catalog",
            entry_id=f"test-{discovery_item.id}",
        ),
    )


def requirements_with_runtime() -> DiscoveryRequirements:
    return DiscoveryRequirements(
        platform=PlatformRequirements(runtimes=("docker",)),
    )


def assessment(
    status: CompatibilityStatus,
    *,
    findings: tuple[CompatibilityFinding, ...] = (),
    evidence: tuple[CompatibilityEvidence, ...] = (),
    unknown_facts: tuple[str, ...] = (),
) -> CompatibilityAssessment:
    return CompatibilityAssessment(
        item_id="frigate",
        target_id="atlas",
        target_type="atlas_environment",
        status=status,
        checked_at=CHECKED_AT,
        findings=findings,
        evidence=evidence,
        unknown_facts=unknown_facts,
    )


def evidence(
    evidence_id: str = "platform-runtime-docker-unknown",
    *,
    status: CompatibilityStatus = CompatibilityStatus.INSUFFICIENT_INFORMATION,
) -> CompatibilityEvidence:
    return CompatibilityEvidence(
        id=evidence_id,
        check_type=CompatibilityCheckType.PLATFORM,
        subject="runtime:docker",
        status=status,
        message="Docker runtime is unknown.",
        source="discovery.compatibility",
        requirement="runtime:docker",
        observed="unknown",
        observed_fact_id="runtime:docker",
    )


def compatibility_finding(
    finding_id: str = "platform-runtime-docker-unknown",
    *,
    severity: CompatibilityFindingSeverity = CompatibilityFindingSeverity.UNKNOWN,
    status: CompatibilityStatus = CompatibilityStatus.INSUFFICIENT_INFORMATION,
    evidence_ids: tuple[str, ...] = ("platform-runtime-docker-unknown",),
) -> CompatibilityFinding:
    return CompatibilityFinding(
        id=finding_id,
        check_type=CompatibilityCheckType.PLATFORM,
        severity=severity,
        status=status,
        subject="runtime:docker",
        message="Docker runtime is unknown.",
        evidence_ids=evidence_ids,
    )


class FakeDiscoveryService:
    def __init__(self, entries: tuple[CatalogEntry, ...]) -> None:
        self.entries = entries

    def list_entries(self, **_: object) -> tuple[CatalogEntry, ...]:
        return self.entries


class FailingDiscoveryService:
    def list_entries(self, **_: object) -> tuple[CatalogEntry, ...]:
        raise RuntimeError("catalog path /opt/atlas/private/catalog.yaml failed")


class FakeCompatibilityService:
    def __init__(self, assessments: dict[str, CompatibilityAssessment]) -> None:
        self.assessments = assessments
        self.assessed_item_ids: list[str] = []

    def assess_item(self, item_id: str, *, target: str = "atlas") -> CompatibilityAssessment:
        self.assessed_item_ids.append(item_id)
        return self.assessments[item_id]


class FailingCompatibilityService:
    def assess_item(self, item_id: str, *, target: str = "atlas") -> CompatibilityAssessment:
        raise RuntimeError(f"compatibility failed for {item_id} in /tmp/private.yaml")


def test_compatible_assessment_produces_no_finding() -> None:
    findings = findings_from_compatibility_assessment(
        assessment(CompatibilityStatus.COMPATIBLE),
        item_name="Frigate",
        eligible=True,
    )

    assert findings == ()


def test_ineligible_item_produces_no_finding() -> None:
    findings = findings_from_compatibility_assessment(
        assessment(
            CompatibilityStatus.INCOMPATIBLE,
            findings=(
                compatibility_finding(
                    severity=CompatibilityFindingSeverity.BLOCKER,
                    status=CompatibilityStatus.INCOMPATIBLE,
                ),
            ),
            evidence=(evidence(status=CompatibilityStatus.INCOMPATIBLE),),
        ),
        item_name="Frigate",
        eligible=False,
    )

    assert findings == ()


def test_optional_only_unknowns_are_not_eligible() -> None:
    optional_item = item(
        relationships=(
            DiscoveryRelationship(
                type=DiscoveryRelationshipType.INTEGRATES_WITH,
                target="mqtt",
                required=False,
            ),
        ),
    )

    assert not is_eligible_for_discovery_intelligence(optional_item)


def test_required_unknown_produces_one_informational_finding() -> None:
    source_assessment = assessment(
        CompatibilityStatus.INSUFFICIENT_INFORMATION,
        findings=(compatibility_finding(),),
        evidence=(evidence(),),
        unknown_facts=("runtime:docker", "architecture"),
    )

    findings = findings_from_compatibility_assessment(
        source_assessment,
        item_name="Frigate",
        eligible=True,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.id == "discovery-frigate-atlas-investigate-compatibility"
    assert finding.severity == Severity.INFO
    assert finding.affects_health is False
    assert finding.score_penalty == 0
    assert finding.recommendation == (
        "Review missing Discovery compatibility information for Frigate."
    )
    assert finding.details == {
        "source_subsystem": "discovery",
        "recommendation_class": "investigate_compatibility",
        "catalog_item_id": "frigate",
        "target_id": "atlas",
        "target_type": "atlas_environment",
        "compatibility_status": "insufficient_information",
        "compatibility_finding_ids": ("platform-runtime-docker-unknown",),
        "compatibility_evidence_ids": ("platform-runtime-docker-unknown",),
        "unknown_facts": ("runtime:docker", "architecture"),
    }


def test_incompatible_produces_one_advisory_warning_finding() -> None:
    source_assessment = assessment(
        CompatibilityStatus.INCOMPATIBLE,
        findings=(
            compatibility_finding(
                "resource-memory-missing",
                severity=CompatibilityFindingSeverity.BLOCKER,
                status=CompatibilityStatus.INCOMPATIBLE,
                evidence_ids=("resource-memory-missing",),
            ),
        ),
        evidence=(
            evidence(
                "resource-memory-missing",
                status=CompatibilityStatus.INCOMPATIBLE,
            ),
        ),
    )

    findings = findings_from_compatibility_assessment(
        source_assessment,
        item_name="Frigate",
        eligible=True,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.id == "discovery-frigate-atlas-review-incompatibility"
    assert finding.severity == Severity.WARNING
    assert finding.affects_health is False
    assert finding.score_penalty == 0
    assert finding.recommendation == (
        "Review incompatible Discovery requirements for Frigate."
    )
    assert "unknown_facts" not in finding.details


def test_warning_assessment_requires_actual_warning_finding() -> None:
    no_warning = findings_from_compatibility_assessment(
        assessment(
            CompatibilityStatus.COMPATIBLE_WITH_WARNINGS,
            findings=(compatibility_finding(),),
            evidence=(evidence(),),
            unknown_facts=("runtime:docker",),
        ),
        item_name="Frigate",
        eligible=True,
    )
    assert no_warning == ()

    warning = findings_from_compatibility_assessment(
        assessment(
            CompatibilityStatus.COMPATIBLE_WITH_WARNINGS,
            findings=(
                compatibility_finding(
                    "network-port-warning",
                    severity=CompatibilityFindingSeverity.WARNING,
                    status=CompatibilityStatus.COMPATIBLE_WITH_WARNINGS,
                    evidence_ids=("network-port-warning",),
                ),
            ),
            evidence=(
                evidence(
                    "network-port-warning",
                    status=CompatibilityStatus.COMPATIBLE_WITH_WARNINGS,
                ),
            ),
        ),
        item_name="Frigate",
        eligible=True,
    )

    assert len(warning) == 1
    assert warning[0].id == "discovery-frigate-atlas-review-compatibility-warning"
    assert warning[0].details["compatibility_finding_ids"] == (
        "network-port-warning",
    )


def test_repeated_conversion_is_deterministic() -> None:
    source_assessment = assessment(
        CompatibilityStatus.INSUFFICIENT_INFORMATION,
        findings=(compatibility_finding(),),
        evidence=(evidence(),),
        unknown_facts=("runtime:docker",),
    )

    first = findings_from_compatibility_assessment(
        source_assessment,
        item_name="Frigate",
        eligible=True,
    )
    second = findings_from_compatibility_assessment(
        source_assessment,
        item_name="Frigate",
        eligible=True,
    )

    assert first == second


def test_evidence_ids_are_references_not_copied_payloads() -> None:
    source_assessment = assessment(
        CompatibilityStatus.INCOMPATIBLE,
        findings=(
            compatibility_finding(
                "resource-memory-missing",
                severity=CompatibilityFindingSeverity.BLOCKER,
                status=CompatibilityStatus.INCOMPATIBLE,
                evidence_ids=("resource-memory-missing",),
            ),
        ),
        evidence=(
            evidence(
                "resource-memory-missing",
                status=CompatibilityStatus.INCOMPATIBLE,
            ),
        ),
    )

    finding = findings_from_compatibility_assessment(
        source_assessment,
        item_name="Frigate",
        eligible=True,
    )[0]

    assert finding.details["compatibility_evidence_ids"] == (
        "resource-memory-missing",
    )
    serialized_details = str(finding.details)
    assert "Docker runtime is unknown." not in serialized_details
    assert "requirement" not in serialized_details
    assert "observed" not in serialized_details


def test_collector_processes_only_eligible_items() -> None:
    eligible_item = item(requirements=requirements_with_runtime())
    ineligible_item = item("open-webui")
    atlas_item = item(
        "atlas-core",
        requirements=requirements_with_runtime(),
    )
    source_assessment = assessment(
        CompatibilityStatus.INSUFFICIENT_INFORMATION,
        findings=(compatibility_finding(),),
        evidence=(evidence(),),
        unknown_facts=("runtime:docker",),
    )
    compatibility_service = FakeCompatibilityService(
        {"frigate": source_assessment},
    )

    findings = collect_discovery_compatibility_findings(
        FakeDiscoveryService(
            (entry(eligible_item), entry(ineligible_item), entry(atlas_item)),
        ),
        compatibility_service,
    )

    assert len(findings) == 1
    assert compatibility_service.assessed_item_ids == ["frigate"]


def test_collector_failure_is_log_only(caplog) -> None:
    findings = collect_discovery_compatibility_findings(
        FailingDiscoveryService(),
        FakeCompatibilityService({}),
    )

    assert findings == []
    assert "Unable to collect Discovery catalog entries" in caplog.text
    assert "/opt/atlas/private/catalog.yaml" not in caplog.text


def test_assessment_failure_is_log_only(caplog) -> None:
    findings = collect_discovery_compatibility_findings(
        FakeDiscoveryService((entry(item(requirements=requirements_with_runtime())),)),
        FailingCompatibilityService(),
    )

    assert findings == []
    assert "Unable to assess Discovery compatibility" in caplog.text
    assert "/tmp/private.yaml" not in caplog.text


def test_concrete_requirement_eligibility() -> None:
    assert is_eligible_for_discovery_intelligence(
        item(requirements=requirements_with_runtime())
    )
    assert is_eligible_for_discovery_intelligence(
        item(
            requirements=DiscoveryRequirements(
                capabilities=(CapabilityReference(id="mqtt-broker"),),
            )
        )
    )
    assert is_eligible_for_discovery_intelligence(
        item(
            requirements=DiscoveryRequirements(
                resources=ResourceRequirements(memory_mb_min=512),
            )
        )
    )
    assert is_eligible_for_discovery_intelligence(
        item(
            requirements=DiscoveryRequirements(
                network=NetworkRequirements(
                    ports=(PortRequirement(port=1883, required=True),),
                ),
            )
        )
    )
    assert not is_eligible_for_discovery_intelligence(
        item(status=DiscoveryItemStatus.EXPERIMENTAL, requirements=requirements_with_runtime())
    )


def test_eligible_entries_filters_internal_and_ineligible_items() -> None:
    entries = eligible_entries(
        (
            entry(item("atlas-core", requirements=requirements_with_runtime())),
            entry(item("mqtt", requirements=requirements_with_runtime())),
            entry(item("redis")),
        )
    )

    assert [catalog_entry.item.id for catalog_entry in entries] == ["mqtt"]
