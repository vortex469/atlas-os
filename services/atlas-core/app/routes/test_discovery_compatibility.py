from __future__ import annotations

from app.discovery.compatibility import CompatibilityContext
from app.discovery.loader import LoadedCatalog
from app.discovery.models import (
    CapabilityReference,
    CatalogEntry,
    CatalogProvenance,
    DiscoveryItem,
    DiscoveryRequirements,
)
from app.main import app
from app.routes import discovery as route_module
from app.services.discovery import DiscoveryCatalogService
from app.services.discovery_compatibility import DiscoveryCompatibilityService
from app.testing import ASGITestClient

client = ASGITestClient(app)


class StaticLoader:
    def __init__(self, entries: tuple[CatalogEntry, ...]) -> None:
        self._entries = entries

    def load(self) -> LoadedCatalog:
        return LoadedCatalog(entries=self._entries, source_paths=("memory://catalog",))


class StaticBuilder:
    def __init__(self, context: CompatibilityContext) -> None:
        self.context = context

    def build_context(self, target: str = "atlas") -> CompatibilityContext:
        return self.context.model_copy(update={"target_id": target})


class FailingBuilder:
    def build_context(self, target: str = "atlas") -> CompatibilityContext:
        raise RuntimeError("internal path /opt/atlas/config/private.yaml")


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


def install_service(monkeypatch, context: CompatibilityContext | None = None) -> None:
    discovery_service = DiscoveryCatalogService(StaticLoader((entry(),)))
    compatibility_service = DiscoveryCompatibilityService(
        discovery_service=discovery_service,
        context_builder=StaticBuilder(context or CompatibilityContext()),
    )
    monkeypatch.setattr(
        route_module,
        "get_discovery_compatibility_service",
        lambda: compatibility_service,
    )


def test_compatibility_route_returns_public_assessment(monkeypatch) -> None:
    install_service(
        monkeypatch,
        CompatibilityContext(capabilities=("container-orchestration",)),
    )

    response = client.get(
        "/api/v1/discovery/items/app/compatibility",
        params={"target": "lab"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["item_id"] == "app"
    assert body["target_id"] == "lab"
    assert body["status"] == "compatible"
    assert body["unknown_facts"] == []
    assert body["findings"] == []
    assert body["evidence"]
    assert "score" not in response.text


def test_compatibility_route_preserves_unknowns(monkeypatch) -> None:
    install_service(monkeypatch, CompatibilityContext(capabilities=None))

    response = client.get("/api/v1/discovery/items/app/compatibility")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficient_information"
    assert body["unknown_facts"] == ["capabilities"]
    assert body["findings"][0]["evidence_ids"] == ["e0002"]
    assert body["evidence"][1]["status"] == "insufficient_information"


def test_compatibility_route_missing_item_returns_404(monkeypatch) -> None:
    install_service(monkeypatch, CompatibilityContext())

    response = client.get("/api/v1/discovery/items/missing/compatibility")

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Discovery item 'missing' was not found."


def test_compatibility_route_sanitizes_context_failure(monkeypatch) -> None:
    discovery_service = DiscoveryCatalogService(StaticLoader((entry(),)))
    compatibility_service = DiscoveryCompatibilityService(
        discovery_service=discovery_service,
        context_builder=FailingBuilder(),
    )
    monkeypatch.setattr(
        route_module,
        "get_discovery_compatibility_service",
        lambda: compatibility_service,
    )

    response = client.get("/api/v1/discovery/items/app/compatibility")

    assert response.status_code == 503
    assert response.json()["error"]["message"] == (
        "Discovery compatibility context is unavailable."
    )
    assert "/opt/atlas" not in response.text


def test_compatibility_route_is_registered_as_read_only() -> None:
    schema = app.openapi()
    path = "/api/v1/discovery/items/{item_id}/compatibility"

    assert path in schema["paths"]
    assert set(schema["paths"][path]) == {"get"}
