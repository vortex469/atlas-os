from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.discovery.compatibility import (
    CompatibilityAssessment,
    CompatibilityCheckType,
    CompatibilityContext,
    CompatibilityFinding,
    CompatibilityFindingSeverity,
    CompatibilityStatus,
    ObservedFact,
    ObservedService,
    assess_compatibility,
    installed_version_key,
)
from app.discovery.models import (
    CapabilityReference,
    CatalogEntry,
    CatalogProvenance,
    DiscoveryItem,
    DiscoveryRelationship,
    DiscoveryRelationshipType,
    DiscoveryRequirements,
    PlatformRequirements,
    ResourceRequirements,
)
from app.discovery.repository import InMemoryDiscoveryRepository

CHECKED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def entry(
    item_id: str,
    *,
    capabilities: tuple[str, ...] = (),
    requirements: DiscoveryRequirements | None = None,
    relationships: tuple[DiscoveryRelationship, ...] = (),
) -> CatalogEntry:
    return CatalogEntry(
        item=DiscoveryItem(
            id=item_id,
            type="application",
            name=item_id.title(),
            capabilities=tuple(CapabilityReference(id=item) for item in capabilities),
            requirements=requirements or DiscoveryRequirements(),
            relationships=relationships,
        ),
        provenance=CatalogProvenance(source="test"),
    )


def assess(
    target: CatalogEntry,
    context: CompatibilityContext,
    *extras: CatalogEntry,
):
    repository = InMemoryDiscoveryRepository.build((target, *extras))
    return assess_compatibility(
        target.item,
        context,
        repository,
        checked_at=CHECKED_AT,
    )


def test_same_input_produces_same_assessment() -> None:
    target = entry(
        "app",
        requirements=DiscoveryRequirements(
            capabilities=(CapabilityReference(id="container-orchestration"),),
        ),
    )
    context = CompatibilityContext(
        capabilities=("container-orchestration",),
        facts=(
            ObservedFact(
                id="capability:container-orchestration",
                kind="capability",
                value="container-orchestration",
                source="test",
            ),
        ),
    )

    first = assess(target, context)
    second = assess(target, context)

    assert first == second
    assert first.status == CompatibilityStatus.COMPATIBLE
    assert first.evidence[1].observed_fact_id == "capability:container-orchestration"


def test_missing_fact_never_becomes_compatible() -> None:
    target = entry(
        "app",
        requirements=DiscoveryRequirements(
            capabilities=(CapabilityReference(id="container-orchestration"),),
        ),
    )

    assessment = assess(target, CompatibilityContext(capabilities=None))

    assert assessment.status == CompatibilityStatus.INSUFFICIENT_INFORMATION
    assert assessment.unknown_facts == ("capabilities",)
    assert assessment.findings[0].severity == CompatibilityFindingSeverity.UNKNOWN
    assert assessment.findings[0].status == CompatibilityStatus.INSUFFICIENT_INFORMATION


def test_known_absent_requirement_is_incompatible() -> None:
    target = entry(
        "app",
        requirements=DiscoveryRequirements(
            capabilities=(CapabilityReference(id="relational-database"),),
        ),
    )

    assessment = assess(target, CompatibilityContext(capabilities=("cache",)))

    assert assessment.status == CompatibilityStatus.INCOMPATIBLE
    assert assessment.findings[0].severity == CompatibilityFindingSeverity.BLOCKER
    assert assessment.evidence[1].status == CompatibilityStatus.INCOMPATIBLE


def test_unknown_resource_information_is_insufficient_only() -> None:
    target = entry(
        "app",
        requirements=DiscoveryRequirements(
            resources=ResourceRequirements(memory_mb_min=2048, gpu_required=True),
        ),
    )

    assessment = assess(target, CompatibilityContext())

    assert assessment.status == CompatibilityStatus.INSUFFICIENT_INFORMATION
    assert assessment.unknown_facts == ("gpu_available", "memory_mb")
    assert {finding.severity for finding in assessment.findings} == {
        CompatibilityFindingSeverity.UNKNOWN,
    }


def test_resource_and_platform_checks_can_pass_and_fail_deterministically() -> None:
    target = entry(
        "app",
        requirements=DiscoveryRequirements(
            resources=ResourceRequirements(memory_mb_min=2048),
            platform=PlatformRequirements(runtimes=("docker",)),
        ),
    )

    passing = assess(
        target,
        CompatibilityContext(memory_mb=4096, runtimes=("docker",)),
    )
    failing = assess(
        target,
        CompatibilityContext(memory_mb=1024, runtimes=("docker",)),
    )

    assert passing.status == CompatibilityStatus.COMPATIBLE
    assert failing.status == CompatibilityStatus.INCOMPATIBLE
    assert failing.findings[0].subject == "requirements.resources.memory_mb_min"


def test_required_relationship_unknown_and_observed() -> None:
    target = entry(
        "app",
        relationships=(
            DiscoveryRelationship(
                type=DiscoveryRelationshipType.DEPENDS_ON,
                target="postgresql",
                required=True,
            ),
        ),
    )
    postgresql = entry("postgresql", capabilities=("relational-database",))

    unknown = assess(target, CompatibilityContext(installed_services=None), postgresql)
    observed = assess(
        target,
        CompatibilityContext(
            installed_services=(
                ObservedService(
                    id="postgresql",
                    name="PostgreSQL",
                    capabilities=("relational-database",),
                    source="test",
                ),
            ),
        ),
        postgresql,
    )

    assert unknown.status == CompatibilityStatus.INSUFFICIENT_INFORMATION
    assert unknown.unknown_facts == ("installed_services",)
    assert observed.status == CompatibilityStatus.COMPATIBLE


def test_optional_relationship_does_not_block() -> None:
    target = entry(
        "app",
        relationships=(
            DiscoveryRelationship(
                type=DiscoveryRelationshipType.INTEGRATES_WITH,
                target="optional-target",
                required=False,
            ),
        ),
    )

    assessment = assess(target, CompatibilityContext(installed_services=None))

    assert assessment.status == CompatibilityStatus.COMPATIBLE
    assert not assessment.findings
    assert assessment.evidence[-1].message.endswith("not required.")


def test_findings_reference_shared_evidence_without_duplication() -> None:
    target = entry(
        "app",
        requirements=DiscoveryRequirements(
            resources=ResourceRequirements(cpu_cores_min=2),
        ),
    )

    assessment = assess(target, CompatibilityContext(cpu_cores=1))

    assert assessment.status == CompatibilityStatus.INCOMPATIBLE
    evidence_ids = {item.id for item in assessment.evidence}
    for finding in assessment.findings:
        assert set(finding.evidence_ids).issubset(evidence_ids)
        assert "evidence" not in finding.model_dump()


def test_observed_service_version_defaults_to_unknown() -> None:
    service = ObservedService(id="frigate", name="Frigate", source="test")

    assert service.installed_version is None
    assert installed_version_key(service) is None


def test_observed_service_strict_version_is_comparable() -> None:
    lower = ObservedService(
        id="frigate",
        name="Frigate",
        source="test",
        installed_version="1.9.9",
    )
    higher = ObservedService(
        id="frigate",
        name="Frigate",
        source="test",
        installed_version="1.10.0",
    )

    assert installed_version_key(lower) == (1, 9, 9)
    assert installed_version_key(higher) == (1, 10, 0)
    assert installed_version_key(higher) > installed_version_key(lower)


@pytest.mark.parametrize(
    "version",
    [
        "v1.2.3",
        "1.2",
        "1.2.3.4",
        "1.02.3",
        "1.2.x",
        "1.2.3-beta",
        " 1.2.3",
        "1.2.3 ",
    ],
)
def test_malformed_installed_versions_fail_closed(version: str) -> None:
    service = ObservedService(
        id="frigate",
        name="Frigate",
        source="test",
        installed_version=version,
    )

    assert installed_version_key(service) is None


def test_observed_service_rejects_out_of_bounds_version() -> None:
    with pytest.raises(ValidationError):
        ObservedService(
            id="frigate",
            name="Frigate",
            source="test",
            installed_version="1.2." + "3" * 64,
        )


def test_observed_service_rejects_empty_version() -> None:
    with pytest.raises(ValidationError):
        ObservedService(
            id="frigate",
            name="Frigate",
            source="test",
            installed_version="",
        )


def test_observed_service_with_version_round_trips() -> None:
    service = ObservedService(
        id="frigate",
        name="Frigate",
        source="test",
        installed_version="0.16.0",
    )

    assert ObservedService.model_validate(service.model_dump()) == service


def test_installed_version_is_advisory_for_relationship_checks() -> None:
    target = entry(
        "app",
        relationships=(
            DiscoveryRelationship(
                type=DiscoveryRelationshipType.DEPENDS_ON,
                target="frigate",
                required=True,
            ),
        ),
    )
    frigate = entry("frigate")
    context = CompatibilityContext(
        installed_services=(
            ObservedService(
                id="frigate",
                name="Frigate",
                source="test",
                installed_version="0.16.0",
            ),
        ),
    )

    assessment = assess(target, context, frigate)

    assert assessment.status == CompatibilityStatus.COMPATIBLE
    assert assessment.unknown_facts == ()


def test_installed_version_does_not_change_assessment() -> None:
    target = entry(
        "app",
        relationships=(
            DiscoveryRelationship(
                type=DiscoveryRelationshipType.DEPENDS_ON,
                target="frigate",
                required=True,
            ),
        ),
    )
    frigate = entry("frigate")
    context_without_version = CompatibilityContext(
        installed_services=(
            ObservedService(
                id="frigate",
                name="Frigate",
                source="test",
            ),
        ),
    )
    context_with_version = CompatibilityContext(
        installed_services=(
            ObservedService(
                id="frigate",
                name="Frigate",
                source="test",
                installed_version="0.16.0",
            ),
        ),
    )

    assessment_without_version = assess(target, context_without_version, frigate)
    assessment_with_version = assess(target, context_with_version, frigate)

    assert assessment_without_version == assessment_with_version


def test_assessment_rejects_findings_with_missing_evidence() -> None:
    with pytest.raises(ValidationError):
        CompatibilityAssessment(
            item_id="app",
            target_id="atlas",
            target_type="atlas_environment",
            status=CompatibilityStatus.INCOMPATIBLE,
            checked_at=CHECKED_AT,
            findings=(
                CompatibilityFinding(
                    id="f0001",
                    check_type=CompatibilityCheckType.CAPABILITY,
                    severity=CompatibilityFindingSeverity.BLOCKER,
                    status=CompatibilityStatus.INCOMPATIBLE,
                    subject="capability",
                    message="missing",
                    evidence_ids=("e-missing",),
                ),
            ),
            evidence=(),
        )
