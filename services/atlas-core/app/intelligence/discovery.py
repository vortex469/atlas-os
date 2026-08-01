from __future__ import annotations

from collections.abc import Iterable

from app.core.logging import get_logger
from app.discovery.compatibility import (
    CompatibilityAssessment,
    CompatibilityFindingSeverity,
    CompatibilityStatus,
)
from app.discovery.models import (
    CatalogEntry,
    DiscoveryItem,
    DiscoveryItemStatus,
)
from app.intelligence.findings import Finding, Severity
from app.services.discovery import DiscoveryCatalogService, get_discovery_service
from app.services.discovery_compatibility import (
    DiscoveryCompatibilityService,
    get_discovery_compatibility_service,
)

logger = get_logger("atlas.intelligence.discovery")

DISCOVERY_CATEGORY = "discovery-compatibility"
DISCOVERY_SOURCE = "discovery"
ATLAS_INTERNAL_ITEM_IDS = frozenset(
    {
        "atlas-agent",
        "atlas-core",
        "mission-control",
    }
)


def collect_discovery_compatibility_findings(
    discovery_service: DiscoveryCatalogService | None = None,
    compatibility_service: DiscoveryCompatibilityService | None = None,
    *,
    target: str = "atlas",
) -> list[Finding]:
    """Collect advisory ACE findings from Discovery compatibility.

    Discovery failures are intentionally log-only. Compatibility recommendations
    must not interrupt existing provider intelligence collection.
    """

    discovery = discovery_service or get_discovery_service()
    compatibility = compatibility_service or get_discovery_compatibility_service()

    try:
        entries = discovery.list_entries(statuses=(DiscoveryItemStatus.ACTIVE,))
    except Exception:  # noqa: BLE001
        logger.error("Unable to collect Discovery catalog entries for Orion")
        return []

    findings: list[Finding] = []
    for entry in entries:
        if not is_eligible_for_discovery_intelligence(entry.item):
            continue

        try:
            assessment = compatibility.assess_item(entry.item.id, target=target)
        except Exception:  # noqa: BLE001
            logger.error(
                "Unable to assess Discovery compatibility for Orion",
                extra={"catalog_item_id": entry.item.id, "target": target},
            )
            continue

        findings.extend(
            findings_from_compatibility_assessment(
                assessment,
                item_name=entry.item.name,
                eligible=True,
            )
        )

    return findings


def findings_from_compatibility_assessment(
    assessment: CompatibilityAssessment,
    *,
    item_name: str,
    eligible: bool,
) -> tuple[Finding, ...]:
    """Convert one compatibility assessment to zero or one ACE finding."""

    if not eligible or assessment.status == CompatibilityStatus.COMPATIBLE:
        return ()

    if assessment.status == CompatibilityStatus.INSUFFICIENT_INFORMATION:
        if not assessment.unknown_facts:
            return ()
        return (
            _finding(
                assessment,
                item_name=item_name,
                recommendation_class="investigate-compatibility",
                severity=Severity.INFO,
                title=f"Discovery needs compatibility information for {item_name}",
                message=(
                    f"Discovery could not determine whether {item_name} is "
                    "compatible because required facts are unknown."
                ),
                recommendation=(
                    f"Review missing Discovery compatibility information for {item_name}."
                ),
                compatibility_finding_ids=tuple(
                    finding.id for finding in assessment.findings
                ),
                compatibility_evidence_ids=_referenced_evidence_ids(assessment),
                include_unknown_facts=True,
            ),
        )

    if assessment.status == CompatibilityStatus.INCOMPATIBLE:
        return (
            _finding(
                assessment,
                item_name=item_name,
                recommendation_class="review-incompatibility",
                severity=Severity.WARNING,
                title=f"Discovery found incompatible requirements for {item_name}",
                message=(
                    f"Discovery found that {item_name} has requirements that "
                    "are not currently satisfied by the assessed environment."
                ),
                recommendation=(
                    f"Review incompatible Discovery requirements for {item_name}."
                ),
                compatibility_finding_ids=tuple(
                    finding.id for finding in assessment.findings
                ),
                compatibility_evidence_ids=_referenced_evidence_ids(assessment),
                include_unknown_facts=False,
            ),
        )

    if assessment.status == CompatibilityStatus.COMPATIBLE_WITH_WARNINGS:
        warning_findings = tuple(
            finding
            for finding in assessment.findings
            if finding.severity == CompatibilityFindingSeverity.WARNING
        )
        if not warning_findings:
            return ()
        return (
            _finding(
                assessment,
                item_name=item_name,
                recommendation_class="review-compatibility-warning",
                severity=Severity.WARNING,
                title=f"Discovery found compatibility warnings for {item_name}",
                message=(
                    f"Discovery found compatibility warnings for {item_name} "
                    "that should be reviewed before relying on this catalog item."
                ),
                recommendation=(
                    f"Review Discovery compatibility warnings for {item_name}."
                ),
                compatibility_finding_ids=tuple(
                    finding.id for finding in warning_findings
                ),
                compatibility_evidence_ids=tuple(
                    evidence_id
                    for finding in warning_findings
                    for evidence_id in finding.evidence_ids
                ),
                include_unknown_facts=False,
            ),
        )

    return ()


def is_eligible_for_discovery_intelligence(item: DiscoveryItem) -> bool:
    """Return whether D8 should assess this catalog item for Orion."""

    if item.id in ATLAS_INTERNAL_ITEM_IDS:
        return False
    if item.status != DiscoveryItemStatus.ACTIVE:
        return False
    return _has_concrete_requirement(item) or _has_required_relationship(item)


def eligible_entries(entries: Iterable[CatalogEntry]) -> tuple[CatalogEntry, ...]:
    return tuple(
        entry
        for entry in entries
        if is_eligible_for_discovery_intelligence(entry.item)
    )


def _finding(
    assessment: CompatibilityAssessment,
    *,
    item_name: str,
    recommendation_class: str,
    severity: Severity,
    title: str,
    message: str,
    recommendation: str,
    compatibility_finding_ids: tuple[str, ...],
    compatibility_evidence_ids: tuple[str, ...],
    include_unknown_facts: bool,
) -> Finding:
    details: dict[str, object] = {
        "source_subsystem": "discovery",
        "recommendation_class": recommendation_class.replace("-", "_"),
        "catalog_item_id": assessment.item_id,
        "target_id": assessment.target_id,
        "target_type": assessment.target_type,
        "compatibility_status": assessment.status.value,
        "compatibility_finding_ids": compatibility_finding_ids,
        "compatibility_evidence_ids": tuple(dict.fromkeys(compatibility_evidence_ids)),
    }
    if include_unknown_facts:
        details["unknown_facts"] = assessment.unknown_facts

    return Finding(
        id=_finding_id(assessment, recommendation_class),
        severity=severity,
        category=DISCOVERY_CATEGORY,
        source=DISCOVERY_SOURCE,
        title=title,
        message=message,
        recommendation=recommendation,
        component=item_name,
        details=details,
        affects_health=False,
        score_penalty=0,
    )


def _finding_id(
    assessment: CompatibilityAssessment,
    recommendation_class: str,
) -> str:
    return f"discovery-{assessment.item_id}-{assessment.target_id}-{recommendation_class}"


def _referenced_evidence_ids(
    assessment: CompatibilityAssessment) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            evidence_id
            for finding in assessment.findings
            for evidence_id in finding.evidence_ids
        )
    )


def _has_concrete_requirement(item: DiscoveryItem) -> bool:
    requirements = item.requirements
    resources = requirements.resources
    platform = requirements.platform
    network = requirements.network

    return any(
        (
            bool(requirements.capabilities),
            resources.cpu_cores_min is not None,
            resources.memory_mb_min is not None,
            resources.storage_gb_min is not None,
            resources.gpu_required,
            resources.gpu_memory_gb_min is not None,
            bool(platform.architectures),
            bool(platform.operating_systems),
            bool(platform.runtimes),
            bool(platform.devices),
            any(port.required for port in network.ports),
            network.requires_internet,
            network.requires_lan,
        )
    )


def _has_required_relationship(item: DiscoveryItem) -> bool:
    return any(relationship.required for relationship in item.relationships)
