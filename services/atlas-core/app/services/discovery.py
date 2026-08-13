from __future__ import annotations

from threading import Lock

from app.core.logging import get_logger
from app.discovery.exceptions import (
    DiscoveryCatalogError,
    DiscoveryRepositoryError,
)
from app.discovery.loader import LoadedCatalog, YamlCatalogLoader
from app.discovery.models import (
    DiscoveryItemStatus,
    DiscoveryItemType,
    DiscoveryRelationshipType,
)
from app.discovery.repository import (
    DiscoveryRelationshipReference,
    DiscoveryRepository,
    InMemoryDiscoveryRepository,
)
from app.discovery.search import (
    DiscoverySearchQuery,
    DiscoverySearchResult,
    search_repository,
)

logger = get_logger("atlas.discovery")


class DiscoveryServiceError(RuntimeError):
    """Base Discovery service error."""


class DiscoveryCatalogUnavailableError(DiscoveryServiceError):
    """Discovery catalog could not be loaded or indexed safely."""


class DiscoveryItemNotFoundError(DiscoveryServiceError):
    """Requested Discovery item does not exist."""


class DiscoveryCatalogService:
    """Thread-safe lazy Discovery repository service."""

    def __init__(self, loader: YamlCatalogLoader | None = None) -> None:
        self._loader = loader or YamlCatalogLoader()
        self._lock = Lock()
        self._repository: DiscoveryRepository | None = None
        self._loaded_catalog: LoadedCatalog | None = None

    def metadata(self) -> tuple[bool, int]:
        repository = self.repository()
        return True, len(repository.list_entries())

    def repository(self) -> DiscoveryRepository:
        repository = self._repository
        if repository is not None:
            return repository

        with self._lock:
            repository = self._repository
            if repository is not None:
                return repository
            try:
                catalog = self._loader.load()
                repository = InMemoryDiscoveryRepository.build(catalog)
            except (DiscoveryCatalogError, DiscoveryRepositoryError) as error:
                logger.exception("Discovery catalog initialization failed")
                raise DiscoveryCatalogUnavailableError(
                    "Discovery catalog is unavailable.",
                ) from error
            self._loaded_catalog = catalog
            self._repository = repository
            return repository

    def list_entries(
        self,
        *,
        item_types: tuple[DiscoveryItemType, ...] = (),
        statuses: tuple[DiscoveryItemStatus, ...] = (),
        tags: tuple[str, ...] = (),
        capabilities: tuple[str, ...] = (),
        relationship_types: tuple[DiscoveryRelationshipType, ...] = (),
        relationship_targets: tuple[str, ...] = (),
    ):
        query = DiscoverySearchQuery(
            item_types=item_types,
            statuses=statuses,
            tags=tags,
            capabilities=capabilities,
            relationship_types=relationship_types,
            relationship_targets=relationship_targets,
        )
        return self.repository().filter(query)

    def get_entry(self, item_id: str):
        entry = self.repository().get_entry(item_id)
        if entry is None:
            raise DiscoveryItemNotFoundError(
                f"Discovery item '{item_id}' was not found.",
            )
        return entry

    def relationships(
        self,
        item_id: str,
        relationship_type: DiscoveryRelationshipType | None = None,
    ) -> tuple[
        tuple[DiscoveryRelationshipReference, ...],
        tuple[DiscoveryRelationshipReference, ...],
    ]:
        repository = self.repository()
        if repository.get_entry(item_id) is None:
            raise DiscoveryItemNotFoundError(
                f"Discovery item '{item_id}' was not found.",
            )
        return (
            repository.incoming_relationships(item_id, relationship_type),
            repository.outgoing_relationships(item_id, relationship_type),
        )

    def search(
        self,
        *,
        text: str,
        item_types: tuple[DiscoveryItemType, ...] = (),
        statuses: tuple[DiscoveryItemStatus, ...] = (),
        tags: tuple[str, ...] = (),
        capabilities: tuple[str, ...] = (),
        relationship_types: tuple[DiscoveryRelationshipType, ...] = (),
        relationship_targets: tuple[str, ...] = (),
    ) -> tuple[DiscoverySearchResult, ...]:
        query = DiscoverySearchQuery(
            text=text,
            item_types=item_types,
            statuses=statuses,
            tags=tags,
            capabilities=capabilities,
            relationship_types=relationship_types,
            relationship_targets=relationship_targets,
        )
        return search_repository(self.repository(), query)


_discovery_service = DiscoveryCatalogService()


def get_discovery_service() -> DiscoveryCatalogService:
    return _discovery_service


def paginate(items: tuple, *, limit: int, offset: int) -> tuple[tuple, int, bool]:
    total = len(items)
    page = items[offset : offset + limit]
    has_more = offset + len(page) < total
    return page, total, has_more
