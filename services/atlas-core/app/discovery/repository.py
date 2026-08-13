from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from app.discovery.exceptions import (
    DiscoveryRepositoryDuplicateError,
    DiscoveryRepositoryValidationError,
)
from app.discovery.loader import LoadedCatalog
from app.discovery.models import (
    CatalogEntry,
    DiscoveryCenterModel,
    DiscoveryItem,
    DiscoveryRelationship,
    DiscoveryRelationshipType,
)
from app.discovery.search import (
    DiscoverySearchQuery,
    SearchDocument,
    build_search_document,
    normalize_text,
)

_ITEM_TARGET_RELATIONSHIP_TYPES = {
    DiscoveryRelationshipType.DEPENDS_ON,
    DiscoveryRelationshipType.INTEGRATES_WITH,
    DiscoveryRelationshipType.CONFLICTS_WITH,
    DiscoveryRelationshipType.RUNS_ON,
    DiscoveryRelationshipType.DEPLOYED_BY,
    DiscoveryRelationshipType.COMPATIBLE_WITH,
    DiscoveryRelationshipType.INCOMPATIBLE_WITH,
}


class DiscoveryRelationshipReference(DiscoveryCenterModel):
    """Resolved direct relationship context for repository callers."""

    source_item_id: str
    target: str
    relationship: DiscoveryRelationship
    resolved_target_item_id: str | None = None
    resolved: bool = False


class DiscoveryRepository(Protocol):
    """Read-only Discovery Center repository contract."""

    def list_entries(self) -> tuple[CatalogEntry, ...]: ...

    def get_entry(self, item_id: str) -> CatalogEntry | None: ...

    def get_item(self, item_id: str) -> DiscoveryItem | None: ...

    def filter(self, query: DiscoverySearchQuery) -> tuple[CatalogEntry, ...]: ...

    def outgoing_relationships(
        self,
        item_id: str,
        relationship_type: DiscoveryRelationshipType | None = None,
    ) -> tuple[DiscoveryRelationshipReference, ...]: ...

    def incoming_relationships(
        self,
        item_id: str,
        relationship_type: DiscoveryRelationshipType | None = None,
    ) -> tuple[DiscoveryRelationshipReference, ...]: ...

    def search_document(self, item_id: str) -> SearchDocument: ...


class InMemoryDiscoveryRepository:
    """Immutable in-memory Discovery Center repository."""

    def __init__(self, entries: Iterable[CatalogEntry]) -> None:
        sorted_entries = tuple(sorted(entries, key=lambda entry: entry.item.id))
        self._entries = sorted_entries
        self._entries_by_item_id = self._index_entries_by_item_id(sorted_entries)
        self._item_ids_by_entry_id = self._index_provenance_entry_ids(sorted_entries)
        self._item_ids_by_type = self._index_by_value(
            (entry.item.type, entry.item.id) for entry in sorted_entries
        )
        self._item_ids_by_status = self._index_by_value(
            (entry.item.status, entry.item.id) for entry in sorted_entries
        )
        self._item_ids_by_tag = self._index_by_many(
            (entry.item.tags, entry.item.id) for entry in sorted_entries
        )
        self._item_ids_by_alias = self._index_by_many(
            (entry.item.aliases, entry.item.id) for entry in sorted_entries
        )
        self._item_ids_by_capability = self._index_by_many(
            ((capability.id for capability in entry.item.capabilities), entry.item.id)
            for entry in sorted_entries
        )
        self._search_documents_by_item_id = {
            entry.item.id: build_search_document(entry) for entry in sorted_entries
        }
        outgoing, incoming = self._build_relationship_indexes(sorted_entries)
        self._outgoing_by_item_id = outgoing
        self._incoming_by_target = incoming

    @classmethod
    def build(
        cls,
        source: LoadedCatalog | Iterable[CatalogEntry],
    ) -> InMemoryDiscoveryRepository:
        """Build an immutable repository from loader output or entries."""

        if isinstance(source, LoadedCatalog):
            return cls(source.entries)
        return cls(source)

    def list_entries(self) -> tuple[CatalogEntry, ...]:
        return self._entries

    def get_entry(self, item_id: str) -> CatalogEntry | None:
        return self._entries_by_item_id.get(item_id)

    def get_item(self, item_id: str) -> DiscoveryItem | None:
        entry = self.get_entry(item_id)
        if entry is None:
            return None
        return entry.item

    def filter(self, query: DiscoverySearchQuery) -> tuple[CatalogEntry, ...]:
        matching_ids = set(self._entries_by_item_id)

        if query.item_types:
            matching_ids &= self._ids_for_any(self._item_ids_by_type, query.item_types)
        if query.statuses:
            matching_ids &= self._ids_for_any(self._item_ids_by_status, query.statuses)
        if query.tags:
            matching_ids &= self._ids_for_all(self._item_ids_by_tag, query.tags)
        if query.capabilities:
            matching_ids &= self._ids_for_all(self._item_ids_by_capability, query.capabilities)
        if query.relationship_types:
            matching_ids &= {
                item_id
                for item_id, relationships in self._outgoing_by_item_id.items()
                if any(reference.relationship.type in query.relationship_types for reference in relationships)
            }
        if query.relationship_targets:
            target_set = set(query.relationship_targets)
            matching_ids &= {
                item_id
                for item_id, relationships in self._outgoing_by_item_id.items()
                if any(normalize_text(reference.target) in target_set for reference in relationships)
            }

        entries = tuple(
            self._entries_by_item_id[item_id]
            for item_id in sorted(matching_ids)
            if item_id in self._entries_by_item_id
        )
        if query.limit is not None and not query.text:
            return entries[: query.limit]
        return entries

    def outgoing_relationships(
        self,
        item_id: str,
        relationship_type: DiscoveryRelationshipType | None = None,
    ) -> tuple[DiscoveryRelationshipReference, ...]:
        relationships = self._outgoing_by_item_id.get(item_id, ())
        if relationship_type is None:
            return relationships
        return tuple(
            relationship
            for relationship in relationships
            if relationship.relationship.type is relationship_type
        )

    def incoming_relationships(
        self,
        item_id: str,
        relationship_type: DiscoveryRelationshipType | None = None,
    ) -> tuple[DiscoveryRelationshipReference, ...]:
        relationships = self._incoming_by_target.get(item_id, ())
        if relationship_type is None:
            return relationships
        return tuple(
            relationship
            for relationship in relationships
            if relationship.relationship.type is relationship_type
        )

    def search_document(self, item_id: str) -> SearchDocument:
        return self._search_documents_by_item_id[item_id]

    @staticmethod
    def _index_entries_by_item_id(
        entries: tuple[CatalogEntry, ...],
    ) -> dict[str, CatalogEntry]:
        indexed: dict[str, CatalogEntry] = {}
        for entry in entries:
            previous = indexed.get(entry.item.id)
            if previous is not None:
                raise DiscoveryRepositoryDuplicateError(
                    f"Duplicate Discovery repository item.id '{entry.item.id}'.",
                )
            indexed[entry.item.id] = entry
        return indexed

    @staticmethod
    def _index_provenance_entry_ids(
        entries: tuple[CatalogEntry, ...],
    ) -> dict[str, str]:
        indexed: dict[str, str] = {}
        for entry in entries:
            entry_id = entry.provenance.entry_id
            if entry_id is None:
                continue
            previous_item_id = indexed.get(entry_id)
            if previous_item_id is not None:
                raise DiscoveryRepositoryDuplicateError(
                    "Duplicate Discovery repository provenance.entry_id "
                    f"'{entry_id}' for items '{previous_item_id}' and '{entry.item.id}'.",
                )
            indexed[entry_id] = entry.item.id
        return indexed

    @staticmethod
    def _index_by_value(
        pairs: Iterable[tuple[object, str]],
    ) -> dict[object, tuple[str, ...]]:
        indexed: dict[object, set[str]] = {}
        for value, item_id in pairs:
            indexed.setdefault(value, set()).add(item_id)
        return {value: tuple(sorted(item_ids)) for value, item_ids in indexed.items()}

    @staticmethod
    def _index_by_many(
        pairs: Iterable[tuple[Iterable[str], str]],
    ) -> dict[str, tuple[str, ...]]:
        indexed: dict[str, set[str]] = {}
        for values, item_id in pairs:
            for value in values:
                indexed.setdefault(normalize_text(value), set()).add(item_id)
        return {value: tuple(sorted(item_ids)) for value, item_ids in indexed.items()}

    def _build_relationship_indexes(
        self,
        entries: tuple[CatalogEntry, ...],
    ) -> tuple[
        dict[str, tuple[DiscoveryRelationshipReference, ...]],
        dict[str, tuple[DiscoveryRelationshipReference, ...]],
    ]:
        outgoing: dict[str, list[DiscoveryRelationshipReference]] = {}
        incoming: dict[str, list[DiscoveryRelationshipReference]] = {}
        item_ids = set(self._entries_by_item_id)

        for entry in entries:
            source_item_id = entry.item.id
            for relationship in entry.item.relationships:
                reference = self._build_relationship_reference(
                    source_item_id=source_item_id,
                    relationship=relationship,
                    item_ids=item_ids,
                )
                outgoing.setdefault(source_item_id, []).append(reference)
                incoming.setdefault(relationship.target, []).append(reference)

        return (
            {
                item_id: tuple(
                    sorted(
                        references,
                        key=lambda reference: (reference.relationship.type.value, reference.target),
                    ),
                )
                for item_id, references in outgoing.items()
            },
            {
                target: tuple(
                    sorted(
                        references,
                        key=lambda reference: (reference.source_item_id, reference.relationship.type.value),
                    ),
                )
                for target, references in incoming.items()
            },
        )

    def _build_relationship_reference(
        self,
        *,
        source_item_id: str,
        relationship: DiscoveryRelationship,
        item_ids: set[str],
    ) -> DiscoveryRelationshipReference:
        validates_item_target = relationship.type in _ITEM_TARGET_RELATIONSHIP_TYPES
        target_exists = relationship.target in item_ids

        if validates_item_target and relationship.target == source_item_id:
            raise DiscoveryRepositoryValidationError(
                "Discovery relationship self-reference is not allowed for "
                f"item '{source_item_id}' relationship '{relationship.type.value}'.",
            )
        if validates_item_target and relationship.required and not target_exists:
            raise DiscoveryRepositoryValidationError(
                "Required Discovery relationship target is unresolved for "
                f"item '{source_item_id}' relationship '{relationship.type.value}' "
                f"target '{relationship.target}'.",
            )

        return DiscoveryRelationshipReference(
            source_item_id=source_item_id,
            target=relationship.target,
            relationship=relationship,
            resolved_target_item_id=relationship.target if target_exists else None,
            resolved=target_exists,
        )

    @staticmethod
    def _ids_for_any(
        index: dict[object, tuple[str, ...]],
        values: Iterable[object],
    ) -> set[str]:
        item_ids: set[str] = set()
        for value in values:
            item_ids.update(index.get(value, ()))
        return item_ids

    @staticmethod
    def _ids_for_all(
        index: dict[str, tuple[str, ...]],
        values: Iterable[str],
    ) -> set[str]:
        iterator = iter(values)
        try:
            first = next(iterator)
        except StopIteration:
            return set()

        item_ids = set(index.get(first, ()))
        for value in iterator:
            item_ids &= set(index.get(value, ()))
        return item_ids
