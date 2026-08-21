from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.discovery.compatibility import (
    CompatibilityContext,
    CompatibilityContextBuilder,
    CompatibilityStatus,
    ObservedService,
)
from app.discovery.loader import LoadedCatalog
from app.discovery.models import (
    CapabilityReference,
    CatalogEntry,
    CatalogProvenance,
    DiscoveryItem,
    DiscoveryRelationship,
    DiscoveryRelationshipType,
    DiscoveryRequirements,
)
from app.discovery.proposals import (
    DiscoveryProposalDestinationKind,
    DiscoveryProposalReason,
    DiscoveryProposalStatus,
)
from app.intelligence.discovery import collect_discovery_compatibility_findings
from app.services.discovery import DiscoveryCatalogService, DiscoveryItemNotFoundError
from app.services.discovery_compatibility import (
    DiscoveryCompatibilityContextUnavailableError,
    DiscoveryCompatibilityService,
)
from app.services.discovery_proposals import DiscoveryProposalService

NOW = datetime(2026, 8, 15, 12, tzinfo=UTC)


class StaticLoader:
    def __init__(self, entries: tuple[CatalogEntry, ...]) -> None:
        self._entries = entries

    def load(self) -> LoadedCatalog:
        return LoadedCatalog(entries=self._entries, source_paths=("memory://catalog",))


class StaticBuilder:
    def __init__(self, context: CompatibilityContext) -> None:
        self.context = context
        self.calls: list[str] = []

    def build_context(self, target: str = "atlas") -> CompatibilityContext:
        self.calls.append(target)
        return self.context.model_copy(update={"target_id": target})


class FailingBuilder:
    def build_context(self, target: str = "atlas") -> CompatibilityContext:
        raise RuntimeError("internal path /secret/catalog.yaml")


def entry() -> CatalogEntry:
    return CatalogEntry(
        item=DiscoveryItem(
            id="app",
            type="application",
            name="App",
            requirements=DiscoveryRequirements(
                capabilities=(CapabilityReference(id="container-orchestration"),),
            ),
        ),
        provenance=CatalogProvenance(source="test"),
    )


def service_with(
    builder: CompatibilityContextBuilder,
) -> DiscoveryCompatibilityService:
    discovery_service = DiscoveryCatalogService(StaticLoader((entry(),)))
    return DiscoveryCompatibilityService(
        discovery_service=discovery_service,
        context_builder=builder,
    )


def test_service_uses_context_builder_and_repository() -> None:
    builder = StaticBuilder(
        CompatibilityContext(capabilities=("container-orchestration",)),
    )
    service = service_with(builder)

    assessment = service.assess_item("app", target="lab")

    assert assessment.target_id == "lab"
    assert assessment.status == CompatibilityStatus.COMPATIBLE
    assert builder.calls == ["lab"]


def test_service_preserves_item_not_found_error() -> None:
    service = service_with(StaticBuilder(CompatibilityContext()))

    with pytest.raises(DiscoveryItemNotFoundError):
        service.assess_item("missing")


def test_service_sanitizes_context_builder_failures() -> None:
    service = service_with(FailingBuilder())

    with pytest.raises(DiscoveryCompatibilityContextUnavailableError) as error:
        service.assess_item("app")

    assert str(error.value) == "Discovery compatibility context is unavailable."
    assert "/secret" not in str(error.value)


def app_with_version_bound() -> CatalogEntry:
    return CatalogEntry(
        item=DiscoveryItem(
            id="app",
            type="application",
            name="App",
            relationships=(
                DiscoveryRelationship(
                    type=DiscoveryRelationshipType.DEPENDS_ON,
                    target="postgresql",
                    required=True,
                    minimum_version="15.0.0",
                ),
            ),
        ),
        provenance=CatalogProvenance(
            source="test",
            entry_id="app",
            version="1.0.0",
        ),
    )


def test_incompatible_version_flows_to_advisory_proposal() -> None:
    postgresql = CatalogEntry(
        item=DiscoveryItem(id="postgresql", type="service", name="PostgreSQL"),
        provenance=CatalogProvenance(source="test"),
    )
    discovery_service = DiscoveryCatalogService(
        StaticLoader((app_with_version_bound(), postgresql)),
    )
    compatibility_service = DiscoveryCompatibilityService(
        discovery_service=discovery_service,
        context_builder=StaticBuilder(
            CompatibilityContext(
                installed_services=(
                    ObservedService(
                        id="postgresql",
                        name="PostgreSQL",
                        source="test",
                        installed_version="14.9.0",
                    ),
                ),
            ),
        ),
    )

    findings = collect_discovery_compatibility_findings(
        discovery_service=discovery_service,
        compatibility_service=compatibility_service,
    )
    assert len(findings) == 1
    assert findings[0].details["compatibility_status"] == "incompatible"
    assert findings[0].details["recommendation_class"] == "review_incompatibility"

    proposal_service = DiscoveryProposalService(
        discovery=discovery_service,
        compatibility=compatibility_service,
        finding_collector=lambda: findings,
        clock=lambda: NOW,
    )
    (proposal,) = proposal_service.derive(target="atlas")

    assert proposal.status is DiscoveryProposalStatus.CURRENT
    assert proposal.reason is DiscoveryProposalReason.INCOMPATIBLE
    assert (
        proposal.destination.kind
        is DiscoveryProposalDestinationKind.COMPATIBILITY_REVIEW
    )
    assert proposal.intent_hint is None
    assert proposal.source_finding_id == findings[0].id
    assert set(proposal.compatibility.evidence_ids) == {
        "e0001",
        "e0002",
        "e0003",
    }
