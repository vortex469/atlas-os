from __future__ import annotations

import pytest

from app.discovery.compatibility import (
    CompatibilityContext,
    CompatibilityContextBuilder,
    CompatibilityStatus,
)
from app.discovery.loader import LoadedCatalog
from app.discovery.models import (
    CapabilityReference,
    CatalogEntry,
    CatalogProvenance,
    DiscoveryItem,
    DiscoveryRequirements,
)
from app.services.discovery import DiscoveryCatalogService, DiscoveryItemNotFoundError
from app.services.discovery_compatibility import (
    DiscoveryCompatibilityContextUnavailableError,
    DiscoveryCompatibilityService,
)


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
