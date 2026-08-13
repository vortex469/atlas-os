from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.discovery import (
    CATALOG_SCHEMA_VERSION,
    CapabilityReference,
    CatalogEntry,
    CatalogProvenance,
    CatalogSourceType,
    CatalogTrustLevel,
    DiscoveryItem,
    DiscoveryItemStatus,
    DiscoveryItemType,
    DiscoveryRelationship,
    DiscoveryRelationshipType,
    DiscoveryRequirements,
    NetworkRequirements,
    PlatformRequirements,
    PortRequirement,
    ResourceRequirements,
)


def provenance() -> CatalogProvenance:
    return CatalogProvenance(
        source="app/discovery/catalog/postgres.yaml",
        entry_id="postgres",
    )


def item(**overrides: object) -> DiscoveryItem:
    data: dict[str, object] = {
        "id": "postgres",
        "type": DiscoveryItemType.SERVICE,
        "name": "PostgreSQL",
        "description": "Relational database service.",
    }
    data.update(overrides)
    return DiscoveryItem(**data)


def entry(**overrides: object) -> CatalogEntry:
    data: dict[str, object] = {
        "item": item(),
        "provenance": provenance(),
    }
    data.update(overrides)
    return CatalogEntry(**data)


def test_minimal_catalog_entry_validates() -> None:
    catalog_entry = entry()

    assert catalog_entry.schema_version == CATALOG_SCHEMA_VERSION
    assert catalog_entry.item.id == "postgres"
    assert catalog_entry.item.type is DiscoveryItemType.SERVICE
    assert catalog_entry.item.status is DiscoveryItemStatus.ACTIVE
    assert catalog_entry.provenance.source_type is CatalogSourceType.CURATED
    assert catalog_entry.provenance.trust_level is CatalogTrustLevel.CURATED


def test_all_initial_item_types_are_supported() -> None:
    assert {item_type.value for item_type in DiscoveryItemType} == {
        "application",
        "service",
        "container_image",
        "ai_model",
        "integration",
        "hardware_device",
        "deployment_method",
    }


def test_invalid_item_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        item(id="PostgreSQL")


def test_unknown_schema_version_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unsupported catalog schema version"):
        entry(schema_version=2)


def test_models_are_immutable() -> None:
    catalog_entry = entry()

    with pytest.raises(ValidationError, match="frozen"):
        catalog_entry.item.name = "Changed"  # type: ignore[misc]

    with pytest.raises(ValidationError, match="frozen"):
        catalog_entry.schema_version = 2  # type: ignore[misc]


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        DiscoveryItem(
            id="postgres",
            type="service",
            name="PostgreSQL",
            unsupported="value",
        )


def test_capability_reference_is_minimal() -> None:
    capability = CapabilityReference(id="relational-database")

    assert capability.model_dump() == {"id": "relational-database"}

    with pytest.raises(ValidationError):
        CapabilityReference(
            id="relational-database",
            name="Relational Database",
        )


def test_item_capability_ids_must_be_unique() -> None:
    with pytest.raises(ValidationError, match="capability ids must be unique"):
        item(
            capabilities=(
                CapabilityReference(id="database"),
                CapabilityReference(id="database"),
            ),
        )


def test_requirement_capability_ids_must_be_unique() -> None:
    with pytest.raises(ValidationError, match="requirement capability ids must be unique"):
        DiscoveryRequirements(
            capabilities=(
                CapabilityReference(id="database"),
                CapabilityReference(id="database"),
            ),
        )


def test_relationship_contains_version_bounds_and_metadata() -> None:
    relationship = DiscoveryRelationship(
        type=DiscoveryRelationshipType.DEPENDS_ON,
        target="postgres",
        required=True,
        minimum_version="14",
        maximum_version="17",
        description="Requires PostgreSQL.",
        metadata={"capability": "relational-database"},
    )

    assert relationship.minimum_version == "14"
    assert relationship.maximum_version == "17"
    assert relationship.metadata["capability"] == "relational-database"


def test_relationship_pairs_must_be_unique_per_item() -> None:
    with pytest.raises(ValidationError, match="relationship type and target pairs"):
        item(
            relationships=(
                DiscoveryRelationship(
                    type=DiscoveryRelationshipType.DEPENDS_ON,
                    target="postgres",
                ),
                DiscoveryRelationship(
                    type=DiscoveryRelationshipType.DEPENDS_ON,
                    target="postgres",
                ),
            ),
        )


def test_dependencies_are_modeled_as_relationships() -> None:
    catalog_item = item(
        relationships=(
            DiscoveryRelationship(
                type=DiscoveryRelationshipType.DEPENDS_ON,
                target="redis",
                required=False,
            ),
        ),
    )

    assert catalog_item.relationships[0].type is DiscoveryRelationshipType.DEPENDS_ON
    assert catalog_item.relationships[0].target == "redis"
    assert "dependencies" not in catalog_item.model_dump()


def test_independently_discoverable_dependency_can_be_service_item() -> None:
    redis = item(
        id="redis",
        type=DiscoveryItemType.SERVICE,
        name="Redis",
        capabilities=(CapabilityReference(id="cache"),),
    )

    assert redis.type is DiscoveryItemType.SERVICE
    assert redis.capabilities[0].id == "cache"


def test_port_requirements_validate_and_normalize() -> None:
    port = PortRequirement(port=5432, protocol="TCP", direction="Inbound")

    assert port.protocol == "tcp"
    assert port.direction == "inbound"

    with pytest.raises(ValidationError):
        PortRequirement(port=70000)


def test_platform_requirement_lists_normalize_and_reject_duplicates() -> None:
    platform = PlatformRequirements(
        architectures=("X86_64", "ARM64"),
        runtimes=("Docker",),
    )

    assert platform.architectures == ("x86_64", "arm64")
    assert platform.runtimes == ("docker",)

    with pytest.raises(ValidationError, match="values must be unique"):
        PlatformRequirements(runtimes=("docker", "Docker"))

    with pytest.raises(ValidationError, match="values must not be empty"):
        PlatformRequirements(devices=("",))


def test_gpu_memory_requires_gpu_required() -> None:
    with pytest.raises(ValidationError, match="gpu_required=true"):
        ResourceRequirements(gpu_memory_gb_min=8)

    requirements = ResourceRequirements(
        gpu_required=True,
        gpu_memory_gb_min=8,
    )

    assert requirements.gpu_required is True


def test_network_notes_normalize_without_lowercasing() -> None:
    network = NetworkRequirements(notes=("Requires LAN",))

    assert network.notes == ("Requires LAN",)


def test_provenance_requires_source_and_uses_typed_trust() -> None:
    source = CatalogProvenance(
        source_type=CatalogSourceType.PRIVATE,
        source="data/knowledge/private/postgres.yaml",
        entry_id="postgres",
        trust_level=CatalogTrustLevel.PRIVATE,
    )

    assert source.trust_level is CatalogTrustLevel.PRIVATE

    with pytest.raises(ValidationError):
        CatalogProvenance(source="")

    with pytest.raises(ValidationError):
        CatalogProvenance(source="catalog.yaml", trust_level="trusted")


def test_catalog_entry_separates_item_from_record_metadata() -> None:
    catalog_entry = entry(metadata={"catalog": "curated-core"})

    assert catalog_entry.item.metadata == {}
    assert catalog_entry.metadata == {"catalog": "curated-core"}
    assert catalog_entry.provenance.entry_id == "postgres"


def test_url_fields_use_explicit_names() -> None:
    catalog_item = item(
        homepage_url="https://www.postgresql.org/",
        documentation_url="https://www.postgresql.org/docs/",
    )

    assert catalog_item.homepage_url == "https://www.postgresql.org/"
    assert catalog_item.documentation_url == "https://www.postgresql.org/docs/"

    with pytest.raises(ValidationError):
        DiscoveryItem(
            id="postgres",
            type="service",
            name="PostgreSQL",
            homepage="https://www.postgresql.org/",
        )
