from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.discovery import (
    CapabilityReference,
    CatalogEntry,
    CatalogProvenance,
    DiscoveryItem,
    DiscoveryItemStatus,
    DiscoveryItemType,
    DiscoveryRelationship,
    DiscoveryRelationshipType,
    DiscoverySearchEvidence,
    DiscoverySearchQuery,
    InMemoryDiscoveryRepository,
    SearchWeights,
    search_repository,
)


def make_entry(
    item_id: str,
    *,
    name: str | None = None,
    description: str = "",
    item_type: DiscoveryItemType = DiscoveryItemType.SERVICE,
    status: DiscoveryItemStatus = DiscoveryItemStatus.ACTIVE,
    aliases: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    capabilities: tuple[str, ...] = (),
    relationships: tuple[DiscoveryRelationship, ...] = (),
) -> CatalogEntry:
    return CatalogEntry(
        item=DiscoveryItem(
            id=item_id,
            type=item_type,
            status=status,
            name=name or item_id.title(),
            description=description,
            aliases=aliases,
            tags=tags,
            capabilities=tuple(CapabilityReference(id=capability) for capability in capabilities),
            relationships=relationships,
        ),
        provenance=CatalogProvenance(
            source=f"app/discovery/catalog/{item_id}.yaml",
            entry_id=item_id,
        ),
    )


def relationship(
    relationship_type: DiscoveryRelationshipType,
    target: str,
) -> DiscoveryRelationship:
    return DiscoveryRelationship(type=relationship_type, target=target)


def repository() -> InMemoryDiscoveryRepository:
    return InMemoryDiscoveryRepository.build(
        [
            make_entry(
                "postgres",
                name="PostgreSQL",
                description="Enterprise relational database service.",
                aliases=("Postgres DB",),
                tags=("database", "storage"),
                capabilities=("relational-database", "sql"),
            ),
            make_entry(
                "postgres-name",
                name="postgres",
                description="Service whose exact name matches postgres.",
                aliases=("pg-name",),
                tags=("name-match",),
                capabilities=("name-capability",),
            ),
            make_entry(
                "pg-alias",
                name="Alias Service",
                description="Alias based matching service.",
                aliases=("postgres",),
                tags=("alias-match",),
                capabilities=("alias-capability",),
            ),
            make_entry(
                "post-prefix",
                name="Prefix Service",
                description="Prefix based matching service.",
                tags=("prefix-match",),
                capabilities=("prefix-capability",),
            ),
            make_entry(
                "named-prefix",
                name="Post Node",
                description="Name prefix matching service.",
                tags=("name-prefix",),
                capabilities=("named-prefix-capability",),
            ),
            make_entry(
                "capability-match",
                name="Capability Service",
                description="Capability matching service.",
                capabilities=("postgres",),
            ),
            make_entry(
                "tag-match",
                name="Tagged Service",
                description="Tagged matching service.",
                tags=("postgres",),
            ),
            make_entry(
                "description-match",
                name="Description Service",
                description="This service mentions postgres in descriptive text.",
            ),
        ],
    )


def result_ids(results: tuple) -> list[str]:
    return [result.item.id for result in results]


def test_search_result_shape_includes_item_entry_score_and_evidence() -> None:
    result = search_repository(repository(), DiscoverySearchQuery(text="relational"))[0]

    assert result.item is result.entry.item
    assert result.score > 0
    assert result.evidence
    assert isinstance(result.evidence[0], DiscoverySearchEvidence)
    assert result.evidence[0].matched_text == "relational"


def test_exact_item_id_outranks_exact_name_and_exact_alias() -> None:
    results = search_repository(repository(), DiscoverySearchQuery(text="postgres"))

    assert result_ids(results)[:3] == ["postgres", "postgres-name", "pg-alias"]
    assert results[0].score > results[1].score > results[2].score


def test_item_id_prefix_outranks_name_prefix() -> None:
    results = search_repository(repository(), DiscoverySearchQuery(text="post"))
    ids = result_ids(results)

    assert ids.index("post-prefix") < ids.index("named-prefix")


def test_exact_capability_outranks_exact_tag() -> None:
    results = search_repository(repository(), DiscoverySearchQuery(text="postgres"))
    ids = result_ids(results)

    assert ids.index("capability-match") < ids.index("tag-match")


def test_name_token_outranks_description_token() -> None:
    repo = InMemoryDiscoveryRepository.build(
        [
            make_entry("name-token", name="Postgres Worker"),
            make_entry("description-token", name="Worker", description="Mentions postgres here."),
        ],
    )

    assert result_ids(search_repository(repo, DiscoverySearchQuery(text="postgres"))) == [
        "name-token",
        "description-token",
    ]


def test_alias_tag_capability_token_is_lowest_text_token_signal() -> None:
    repo = InMemoryDiscoveryRepository.build(
        [
            make_entry("description-token", name="Worker", description="Mentions redis here."),
            make_entry("alias-token", name="Worker", aliases=("redis service",)),
        ],
    )

    assert result_ids(search_repository(repo, DiscoverySearchQuery(text="redis"))) == [
        "description-token",
        "alias-token",
    ]


def test_stable_item_id_tie_break_for_equal_scores() -> None:
    repo = InMemoryDiscoveryRepository.build(
        [
            make_entry("b-service", name="Worker", description="Mentions queue."),
            make_entry("a-service", name="Worker", description="Mentions queue."),
        ],
    )

    assert result_ids(search_repository(repo, DiscoverySearchQuery(text="queue"))) == [
        "a-service",
        "b-service",
    ]


def test_all_query_tokens_must_match_some_searchable_field() -> None:
    assert search_repository(repository(), DiscoverySearchQuery(text="postgres nonexistent")) == ()


def test_search_is_case_insensitive_and_normalizes_separators() -> None:
    results = search_repository(repository(), DiscoverySearchQuery(text="RELATIONAL database"))

    assert result_ids(results)[0] == "postgres"


def test_empty_text_returns_filtered_entries_with_zero_scores() -> None:
    results = search_repository(
        repository(),
        DiscoverySearchQuery(tags=("storage",), capabilities=("sql",)),
    )

    assert result_ids(results) == ["postgres"]
    assert results[0].score == 0
    assert results[0].evidence == ()


def test_limit_truncates_deterministically() -> None:
    results = search_repository(repository(), DiscoverySearchQuery(text="service", limit=2))

    assert len(results) == 2
    assert result_ids(results) == sorted(result_ids(results))


def test_filter_categories_are_combined_with_and_semantics() -> None:
    repo = InMemoryDiscoveryRepository.build(
        [
            make_entry(
                "app",
                item_type=DiscoveryItemType.APPLICATION,
                tags=("media", "photo"),
                capabilities=("gallery", "upload"),
                relationships=(relationship(DiscoveryRelationshipType.DEPENDS_ON, "postgres"),),
            ),
            make_entry("postgres", item_type=DiscoveryItemType.SERVICE, tags=("database",), capabilities=("sql",)),
        ],
    )

    results = search_repository(
        repo,
        DiscoverySearchQuery(
            item_types=(DiscoveryItemType.APPLICATION,),
            statuses=(DiscoveryItemStatus.ACTIVE,),
            tags=("media", "photo"),
            capabilities=("gallery", "upload"),
            relationship_types=(DiscoveryRelationshipType.DEPENDS_ON,),
            relationship_targets=("postgres",),
        ),
    )

    assert result_ids(results) == ["app"]


def test_item_type_status_relationship_filters_use_any_semantics() -> None:
    repo = InMemoryDiscoveryRepository.build(
        [
            make_entry("app", item_type=DiscoveryItemType.APPLICATION, relationships=(relationship(DiscoveryRelationshipType.DEPENDS_ON, "postgres"),)),
            make_entry("model", item_type=DiscoveryItemType.AI_MODEL, status=DiscoveryItemStatus.EXPERIMENTAL),
            make_entry("postgres"),
        ],
    )

    results = search_repository(
        repo,
        DiscoverySearchQuery(
            item_types=(DiscoveryItemType.APPLICATION, DiscoveryItemType.AI_MODEL),
            statuses=(DiscoveryItemStatus.ACTIVE, DiscoveryItemStatus.EXPERIMENTAL),
            relationship_types=(DiscoveryRelationshipType.DEPENDS_ON, DiscoveryRelationshipType.INTEGRATES_WITH),
        ),
    )

    assert result_ids(results) == ["app"]


def test_query_filter_values_reject_duplicates_and_blanks() -> None:
    with pytest.raises(ValidationError, match="filter values must be unique"):
        DiscoverySearchQuery(tags=("database", "Database"))

    with pytest.raises(ValidationError, match="filter values must not be empty"):
        DiscoverySearchQuery(capabilities=("",))


def test_weights_are_named_and_immutable() -> None:
    weights = SearchWeights()

    assert weights.exact_item_id > weights.exact_name > weights.exact_alias
    assert weights.item_id_prefix > weights.name_prefix > weights.exact_capability
    assert weights.exact_capability > weights.exact_tag > weights.name_token
    assert weights.name_token > weights.description_token > weights.alias_tag_capability_token
    with pytest.raises(ValidationError, match="frozen"):
        weights.exact_item_id = 1  # type: ignore[misc]
