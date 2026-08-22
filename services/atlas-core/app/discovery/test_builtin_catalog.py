from __future__ import annotations

import pytest

from app.discovery.loader import DEFAULT_DISCOVERY_CATALOG_DIR, YamlCatalogLoader
from app.discovery.models import CATALOG_SCHEMA_VERSION, DiscoveryRelationshipType
from app.discovery.repository import InMemoryDiscoveryRepository
from app.discovery.search import DiscoverySearchQuery, search_repository
from app.main import app
from app.routes import discovery as route_module
from app.services.discovery import DiscoveryCatalogService
from app.testing import ASGITestClient

EXPECTED_BUILTIN_IDS = {
    "atlas-agent",
    "atlas-core",
    "coral-usb",
    "docker-compose",
    "frigate",
    "home-assistant",
    "mission-control",
    "mqtt",
    "ollama",
    "open-webui",
    "postgresql",
    "redis",
}

ALLOWED_METADATA_KEYS = {"reviewed_for_d5", "catalog_notes"}
FORBIDDEN_PUBLIC_FRAGMENTS = (
    "password",
    "token",
    "secret",
    "10.",
    "192.168.",
    "172.16.",
    "/var/",
    "/opt/atlas/data",
)

client = ASGITestClient(app)


@pytest.fixture(scope="module")
def loaded_catalog():
    return YamlCatalogLoader().load()


@pytest.fixture(scope="module")
def repository(loaded_catalog):
    return InMemoryDiscoveryRepository.build(loaded_catalog)


def test_builtin_catalog_directory_exists_for_d5() -> None:
    assert DEFAULT_DISCOVERY_CATALOG_DIR.is_dir()


def test_builtin_catalog_loads_expected_curated_entries(loaded_catalog) -> None:
    assert len(loaded_catalog.entries) == len(EXPECTED_BUILTIN_IDS)
    assert {entry.item.id for entry in loaded_catalog.entries} == EXPECTED_BUILTIN_IDS
    assert loaded_catalog.source_paths == tuple(sorted(loaded_catalog.source_paths))


def test_builtin_catalog_entries_meet_d5_completeness_rules(loaded_catalog) -> None:
    for entry in loaded_catalog.entries:
        assert entry.schema_version == CATALOG_SCHEMA_VERSION
        assert entry.item.id
        assert entry.item.type
        assert entry.item.status
        assert entry.item.name
        assert entry.item.description
        assert entry.provenance
        assert entry.provenance.source == "atlas-curated-discovery-catalog"
        assert entry.provenance.entry_id == f"d5-{entry.item.id}"
        assert entry.item.capabilities or entry.item.relationships
        assert set(entry.metadata) <= ALLOWED_METADATA_KEYS
        assert set(entry.item.metadata) <= ALLOWED_METADATA_KEYS
        assert entry.metadata.get("reviewed_for_d5") is True


def test_builtin_catalog_has_only_public_safe_metadata() -> None:
    for path in sorted(DEFAULT_DISCOVERY_CATALOG_DIR.rglob("*.yml")) + sorted(
        DEFAULT_DISCOVERY_CATALOG_DIR.rglob("*.yaml")
    ):
        text = path.read_text(encoding="utf-8").lower()
        for fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
            assert fragment not in text, f"{path} contains forbidden fragment {fragment!r}"


def test_builtin_catalog_repository_build_validates_required_relationships(repository) -> None:
    for item_id in EXPECTED_BUILTIN_IDS:
        assert repository.get_item(item_id) is not None

    open_webui_relationships = repository.outgoing_relationships("open-webui")
    assert any(
        reference.relationship.type == DiscoveryRelationshipType.DEPENDS_ON
        and reference.target == "ollama"
        and reference.relationship.required
        and reference.resolved
        for reference in open_webui_relationships
    )


def test_builtin_catalog_relationship_graph_is_conservative(repository) -> None:
    atlas_core_incoming = repository.incoming_relationships("atlas-core")
    assert {reference.source_item_id for reference in atlas_core_incoming} == {
        "atlas-agent",
        "mission-control",
    }

    frigate_targets = {reference.target for reference in repository.outgoing_relationships("frigate")}
    assert {"mqtt", "coral-usb"}.issubset(frigate_targets)

    deployed_by_relationships = [
        reference
        for item_id in EXPECTED_BUILTIN_IDS
        for reference in repository.outgoing_relationships(item_id)
        if reference.relationship.type == DiscoveryRelationshipType.DEPLOYED_BY
    ]
    assert deployed_by_relationships == []


def test_builtin_catalog_search_finds_expected_items(repository) -> None:
    home_results = search_repository(repository, DiscoverySearchQuery(text="home assistant"))
    assert [result.item.id for result in home_results][:1] == ["home-assistant"]

    ollama_results = search_repository(repository, DiscoverySearchQuery(text="ollama"))
    assert ollama_results[0].item.id == "ollama"


def test_builtin_catalog_filters_by_capability_and_relationship(repository) -> None:
    database_entries = repository.filter(
        DiscoverySearchQuery(capabilities=("relational-database",))
    )
    assert [entry.item.id for entry in database_entries] == ["postgresql"]

    atlas_integrations = repository.filter(
        DiscoverySearchQuery(relationship_targets=("atlas-core",))
    )
    assert [entry.item.id for entry in atlas_integrations] == [
        "atlas-agent",
        "mission-control",
    ]


def test_builtin_catalog_api_returns_populated_results(monkeypatch: pytest.MonkeyPatch) -> None:
    service = DiscoveryCatalogService(YamlCatalogLoader(DEFAULT_DISCOVERY_CATALOG_DIR))
    monkeypatch.setattr(route_module, "get_discovery_service", lambda: service)

    metadata = client.get("/api/v1/discovery")
    assert metadata.status_code == 200
    assert metadata.json()["entry_count"] == len(EXPECTED_BUILTIN_IDS)

    items = client.get("/api/v1/discovery/items", params={"limit": "50"})
    assert items.status_code == 200
    body = items.json()
    assert body["total"] == len(EXPECTED_BUILTIN_IDS)
    assert {entry["item"]["id"] for entry in body["entries"]} == EXPECTED_BUILTIN_IDS

    search = client.get("/api/v1/discovery/search", params={"q": "frigate"})
    assert search.status_code == 200
    assert search.json()["results"][0]["item"]["id"] == "frigate"

    relationships = client.get("/api/v1/discovery/items/frigate/relationships")
    assert relationships.status_code == 200
    assert {reference["target"] for reference in relationships.json()["outgoing"]} >= {
        "mqtt",
        "coral-usb",
    }


def test_all_builtin_entries_have_no_deployment_binding(loaded_catalog) -> None:
    """P0 ships no real deployment binding.

    Every current builtin catalog entry must load with
    ``deployment_binding is None``. The first real binding is deferred
    to a separately reviewed catalog-curation change.
    """
    assert len(loaded_catalog.entries) == len(EXPECTED_BUILTIN_IDS)
    for entry in loaded_catalog.entries:
        assert entry.deployment_binding is None, entry.item.id


def test_deployment_binding_schema_is_validated_independently_of_catalog() -> None:
    """The DeploymentBinding schema remains available on its own.

    The schema must stay independently constructible and validated
    without any catalog entry carrying a binding, so the deferred
    first real binding can be reviewed against the same contract.
    """
    from pydantic import ValidationError

    from app.discovery import CatalogEntry, CatalogProvenance, DeploymentBinding

    binding = DeploymentBinding(
        compose_file="compose.synthetic.yaml",
        compose_service="synthetic-service",
    )
    assert binding.mutable_property == "image"
    assert binding.deployment_method == "docker-compose"
    assert binding.model_dump() == {
        "compose_file": "compose.synthetic.yaml",
        "compose_service": "synthetic-service",
        "mutable_property": "image",
        "deployment_method": "docker-compose",
    }

    for invalid in (
        {"compose_file": "", "compose_service": "synthetic-service"},
        {"compose_file": "../compose.yaml", "compose_service": "synthetic-service"},
        {"compose_file": "/abs/compose.yaml", "compose_service": "synthetic-service"},
        {"compose_file": "compose.txt", "compose_service": "synthetic-service"},
        {"compose_file": "compose.yaml", "compose_service": "Bad Service"},
        {"compose_file": "compose.yaml", "compose_service": ""},
    ):
        with pytest.raises(ValidationError):
            DeploymentBinding(**invalid)

    entry = CatalogEntry(
        item={
            "id": "synthetic-item",
            "type": "service",
            "status": "active",
            "name": "Synthetic Item",
        },
        provenance=CatalogProvenance(source="catalog/synthetic.yaml"),
        deployment_binding=binding,
    )
    assert entry.deployment_binding is not None
    assert entry.deployment_binding.compose_file == "compose.synthetic.yaml"
