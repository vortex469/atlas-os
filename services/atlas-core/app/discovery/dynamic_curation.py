"""Read-only adaptation of explicit curated release assertions."""

from __future__ import annotations

from app.discovery.dynamic_evaluation import (
    CanonicalFactKey,
    CanonicalReleaseValue,
    CuratedClaimProvenance,
    ExplicitCuratedReleaseClaim,
)
from app.services.discovery import DiscoveryCatalogService, DiscoveryItemNotFoundError


class CatalogCuratedReleaseClaimProvider:
    def __init__(self, catalog: DiscoveryCatalogService) -> None:
        self._catalog = catalog

    def get_claim(self, item_id: str) -> ExplicitCuratedReleaseClaim | None:
        try:
            entry = self._catalog.get_entry(item_id)
        except DiscoveryItemNotFoundError:
            return None
        assertion = entry.release_claim
        if assertion is None:
            return None
        return ExplicitCuratedReleaseClaim(
            schema_version="discovery-curated-release-claim-v1",
            key=CanonicalFactKey(
                catalog_item_id=item_id,
                fact_kind="latest_stable_release",
            ),
            value=CanonicalReleaseValue(
                version=assertion.version,
                published_at=assertion.published_at,
            ),
            provenance=CuratedClaimProvenance(
                source_class="curated",
                source_id="atlas-curated-catalog",
                trust_tier="curated",
            ),
        )
