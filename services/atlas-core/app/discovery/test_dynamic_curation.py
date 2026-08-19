from datetime import UTC, datetime

from app.discovery.dynamic_curation import CatalogCuratedReleaseClaimProvider
from app.discovery.models import (
    CatalogEntry,
    CatalogProvenance,
    CuratedReleaseClaim,
    DiscoveryItem,
    DiscoveryItemType,
)
from app.services.discovery import DiscoveryCatalogService


class StaticLoader:
    def __init__(self, entries: tuple[CatalogEntry, ...]) -> None:
        self._entries = entries

    def load(self) -> tuple[CatalogEntry, ...]:
        return self._entries


def catalog(*entries: CatalogEntry) -> DiscoveryCatalogService:
    return DiscoveryCatalogService(StaticLoader(tuple(entries)))


def entry(*, release_claim: CuratedReleaseClaim | None) -> CatalogEntry:
    return CatalogEntry(
        item=DiscoveryItem(
            id="frigate",
            type=DiscoveryItemType.APPLICATION,
            name="Frigate",
        ),
        provenance=CatalogProvenance(source="atlas-curated-discovery-catalog"),
        release_claim=release_claim,
    )


def test_provider_adapts_only_the_explicit_curated_release_claim() -> None:
    published_at = datetime(2026, 8, 16, 18, 30, tzinfo=UTC)
    provider = CatalogCuratedReleaseClaimProvider(
        catalog(
            entry(
                release_claim=CuratedReleaseClaim(
                    version="0.16.1",
                    published_at=published_at,
                )
            )
        )
    )

    claim = provider.get_claim("frigate")

    assert claim is not None
    assert claim.key.catalog_item_id == "frigate"
    assert claim.key.fact_kind == "latest_stable_release"
    assert claim.value.version == "0.16.1"
    assert claim.value.published_at == published_at
    assert claim.provenance.source_id == "atlas-curated-catalog"


def test_provider_returns_none_for_absent_claim_or_item() -> None:
    provider = CatalogCuratedReleaseClaimProvider(catalog(entry(release_claim=None)))

    assert provider.get_claim("frigate") is None
    assert provider.get_claim("missing") is None
