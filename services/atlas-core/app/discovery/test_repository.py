from __future__ import annotations

import pytest

from app.discovery import (
    CapabilityReference,
    CatalogEntry,
    CatalogProvenance,
    DiscoveryItem,
    DiscoveryItemStatus,
    DiscoveryItemType,
    DiscoveryRelationship,
    DiscoveryRelationshipType,
    DiscoverySearchQuery,
    InMemoryDiscoveryRepository,
    LoadedCatalog,
)
from app.discovery.exceptions import (
    DiscoveryRepositoryDuplicateError,
    DiscoveryRepositoryValidationError,
)


def make_entry(
    item_id: str,
    *,
    item_type: DiscoveryItemType = DiscoveryItemType.SERVICE,
    status: DiscoveryItemStatus = DiscoveryItemStatus.ACTIVE,
    name: str | None = None,
    aliases: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    capabilities: tuple[str, ...] = (),
    relationships: tuple[DiscoveryRelationship, ...] = (),
    entry_id: str | None = None,
) -> CatalogEntry:
    return CatalogEntry(
        item=DiscoveryItem(
            id=item_id,
            type=item_type,
            status=status,
            name=name or item_id.title(),
            aliases=aliases,
            tags=tags,
            capabilities=tuple(CapabilityReference(id=capability) for capability in capabilities),
            relationships=relationships,
        ),
        provenance=CatalogProvenance(
            source=f"app/discovery/catalog/{item_id}.yaml",
            entry_id=entry_id or item_id,
        ),
    )


def relationship(
    relationship_type: DiscoveryRelationshipType,
    target: str,
    *,
    required: bool = True,
) -> DiscoveryRelationship:
    return DiscoveryRelationship(type=relationship_type, target=target, required=required)


def test_repository_builds_from_loaded_catalog_and_sorts_by_item_id() -> None:
    catalog = LoadedCatalog(entries=(make_entry("redis"), make_entry("postgres")))

    repository = InMemoryDiscoveryRepository.build(catalog)

    assert [entry.item.id for entry in repository.list_entries()] == ["postgres", "redis"]
    assert repository.get_entry("postgres") is not None
    assert repository.get_item("missing") is None


def test_repository_builds_from_iterable_without_yaml_coupling() -> None:
    repository = InMemoryDiscoveryRepository.build([make_entry("postgres")])

    assert repository.get_item("postgres") is not None


def test_repository_exposes_immutable_collections_to_callers() -> None:
    repository = InMemoryDiscoveryRepository.build([make_entry("postgres")])

    entries = repository.list_entries()

    assert isinstance(entries, tuple)
    with pytest.raises(AttributeError):
        entries.append(make_entry("redis"))  # type: ignore[attr-defined]


def test_duplicate_item_ids_are_rejected() -> None:
    with pytest.raises(DiscoveryRepositoryDuplicateError, match="item.id 'postgres'"):
        InMemoryDiscoveryRepository.build(
            [
                make_entry("postgres", entry_id="postgres-a"),
                make_entry("postgres", entry_id="postgres-b"),
            ],
        )


def test_duplicate_non_null_entry_ids_are_rejected() -> None:
    with pytest.raises(DiscoveryRepositoryDuplicateError, match="provenance.entry_id 'shared'"):
        InMemoryDiscoveryRepository.build(
            [
                make_entry("postgres", entry_id="shared"),
                make_entry("redis", entry_id="shared"),
            ],
        )


def test_filter_semantics_are_deterministic() -> None:
    repository = InMemoryDiscoveryRepository.build(
        [
            make_entry(
                "postgres",
                item_type=DiscoveryItemType.SERVICE,
                tags=("database", "storage"),
                capabilities=("relational-database", "sql"),
            ),
            make_entry(
                "redis",
                item_type=DiscoveryItemType.SERVICE,
                tags=("cache", "storage"),
                capabilities=("cache",),
            ),
            make_entry(
                "ollama-model",
                item_type=DiscoveryItemType.AI_MODEL,
                tags=("ai",),
                capabilities=("inference",),
            ),
        ],
    )

    assert [
        entry.item.id
        for entry in repository.filter(
            DiscoverySearchQuery(item_types=(DiscoveryItemType.SERVICE,)),
        )
    ] == ["postgres", "redis"]
    assert [
        entry.item.id
        for entry in repository.filter(DiscoverySearchQuery(tags=("storage", "database")))
    ] == ["postgres"]
    assert [
        entry.item.id
        for entry in repository.filter(DiscoverySearchQuery(capabilities=("cache",)))
    ] == ["redis"]


def test_status_filter_uses_any_semantics() -> None:
    repository = InMemoryDiscoveryRepository.build(
        [
            make_entry("postgres", status=DiscoveryItemStatus.ACTIVE),
            make_entry("legacy", status=DiscoveryItemStatus.DEPRECATED),
        ],
    )

    assert [
        entry.item.id
        for entry in repository.filter(
            DiscoverySearchQuery(statuses=(DiscoveryItemStatus.DEPRECATED,)),
        )
    ] == ["legacy"]


def test_required_item_target_relationship_must_resolve() -> None:
    with pytest.raises(DiscoveryRepositoryValidationError, match="target 'redis'"):
        InMemoryDiscoveryRepository.build(
            [
                make_entry(
                    "app",
                    relationships=(relationship(DiscoveryRelationshipType.DEPENDS_ON, "redis"),),
                ),
            ],
        )


def test_optional_unresolved_item_target_relationship_is_retained() -> None:
    repository = InMemoryDiscoveryRepository.build(
        [
            make_entry(
                "app",
                relationships=(relationship(DiscoveryRelationshipType.DEPENDS_ON, "redis", required=False),),
            ),
        ],
    )

    outgoing = repository.outgoing_relationships("app")

    assert outgoing[0].target == "redis"
    assert outgoing[0].resolved is False


def test_capability_target_relationship_types_are_not_validated_yet() -> None:
    repository = InMemoryDiscoveryRepository.build(
        [
            make_entry(
                "postgres",
                relationships=(relationship(DiscoveryRelationshipType.PROVIDES, "relational-database"),),
            ),
        ],
    )

    assert repository.outgoing_relationships("postgres")[0].resolved is False


def test_self_references_are_rejected_for_validated_item_relationships() -> None:
    with pytest.raises(DiscoveryRepositoryValidationError, match="self-reference"):
        InMemoryDiscoveryRepository.build(
            [
                make_entry(
                    "postgres",
                    relationships=(relationship(DiscoveryRelationshipType.DEPENDS_ON, "postgres"),),
                ),
            ],
        )


def test_direct_relationship_lookups_use_consistent_reference_shape() -> None:
    repository = InMemoryDiscoveryRepository.build(
        [
            make_entry(
                "app",
                relationships=(
                    relationship(DiscoveryRelationshipType.DEPENDS_ON, "postgres"),
                    relationship(DiscoveryRelationshipType.INTEGRATES_WITH, "redis"),
                ),
            ),
            make_entry("postgres"),
            make_entry("redis"),
        ],
    )

    outgoing = repository.outgoing_relationships("app", DiscoveryRelationshipType.DEPENDS_ON)
    incoming = repository.incoming_relationships("postgres")

    assert outgoing[0].source_item_id == "app"
    assert outgoing[0].resolved_target_item_id == "postgres"
    assert outgoing[0].resolved is True
    assert incoming == outgoing


def test_relationship_filtering_uses_any_semantics() -> None:
    repository = InMemoryDiscoveryRepository.build(
        [
            make_entry(
                "app",
                relationships=(relationship(DiscoveryRelationshipType.DEPENDS_ON, "postgres"),),
            ),
            make_entry(
                "worker",
                relationships=(relationship(DiscoveryRelationshipType.INTEGRATES_WITH, "redis"),),
            ),
            make_entry("postgres"),
            make_entry("redis"),
        ],
    )

    assert [
        entry.item.id
        for entry in repository.filter(
            DiscoverySearchQuery(relationship_types=(DiscoveryRelationshipType.DEPENDS_ON,)),
        )
    ] == ["app"]
    assert [
        entry.item.id
        for entry in repository.filter(DiscoverySearchQuery(relationship_targets=("redis",)))
    ] == ["worker"]


def test_repository_does_not_perform_recursive_relationship_traversal() -> None:
    repository = InMemoryDiscoveryRepository.build(
        [
            make_entry("app", relationships=(relationship(DiscoveryRelationshipType.DEPENDS_ON, "postgres"),)),
            make_entry("postgres", relationships=(relationship(DiscoveryRelationshipType.DEPENDS_ON, "storage"),)),
            make_entry("storage"),
        ],
    )

    assert [reference.target for reference in repository.outgoing_relationships("app")] == ["postgres"]
