"""Inactive read-only P3a projection of curated and dynamic Discovery evidence."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Literal, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

from app.discovery.api_models import DiscoveryCatalogEntryResponse, entry_to_response
from app.discovery.dynamic_cache import (
    CacheFailureReason,
    CacheReadResult,
    CacheReadStatus,
    DiscoveryCacheStore,
)
from app.discovery.dynamic_evaluation import (
    ConflictState,
    EvaluatedDynamicClaim,
    ExplicitCuratedReleaseClaim,
    FreshnessState,
    evaluate_freshness,
    evaluate_release_conflict,
)
from app.discovery.dynamic_sources import (
    FRIGATE_ADAPTER_ID,
    DynamicReleaseFact,
    DynamicSourceHealth,
    DynamicSourceProvenance,
)
from app.discovery.models import DISCOVERY_ID_PATTERN
from app.services.discovery import DiscoveryCatalogService

MERGED_ITEM_SCHEMA = "discovery-merged-item-v1"
ITEM_SOURCE_MAPPING: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {"frigate": (FRIGATE_ADAPTER_ID,)}
)


class ProjectionModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class DynamicCacheState(StrEnum):
    AVAILABLE = "available"
    ABSENT = "absent"
    CORRUPT = "corrupt"


class PublicDynamicProvenance(ProjectionModel):
    source_id: str = Field(pattern=DISCOVERY_ID_PATTERN, max_length=128)
    source_type: Literal["github_latest_release"]
    trust_tier: Literal["supplemental"]
    repository: str = Field(min_length=1, max_length=256)
    upstream_release_id: int = Field(ge=1)
    retrieved_at: datetime
    expires_at: datetime

    @field_validator("repository")
    @classmethod
    def validate_repository(cls, value: str) -> str:
        if (
            value != value.strip()
            or not value.isprintable()
            or "://" in value
            or "?" in value
            or "#" in value
            or "@" in value
            or "\\" in value
            or value.startswith("/")
        ):
            raise ValueError("repository must be bounded printable text")
        return value

    @field_validator("retrieved_at", "expires_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("provenance timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_chronology(self) -> PublicDynamicProvenance:
        if self.expires_at != self.retrieved_at + timedelta(hours=24):
            raise ValueError("expiry must be exactly 24 hours after retrieval")
        return self


class PublicDynamicClaim(ProjectionModel):
    fact_kind: Literal["latest_stable_release"]
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$", max_length=64)
    published_at: datetime
    freshness: Literal[FreshnessState.FRESH, FreshnessState.STALE]
    provenance: PublicDynamicProvenance

    @field_validator("published_at")
    @classmethod
    def normalize_published_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("published_at must be timezone-aware")
        return value.astimezone(UTC)


class DynamicSourceState(ProjectionModel):
    source_id: str = Field(pattern=DISCOVERY_ID_PATTERN, max_length=128)
    health: DynamicSourceHealth | None = None
    cache_state: DynamicCacheState


class DiscoveryMergedItemProjection(ProjectionModel):
    schema_version: Literal["discovery-merged-item-v1"]
    catalog_item_id: str = Field(pattern=DISCOVERY_ID_PATTERN, max_length=128)
    curated: DiscoveryCatalogEntryResponse
    dynamic_claims: tuple[PublicDynamicClaim, ...] = ()
    source_states: tuple[DynamicSourceState, ...] = ()
    conflict_state: ConflictState

    @model_validator(mode="after")
    def validate_contract(self, info: ValidationInfo) -> DiscoveryMergedItemProjection:
        if self.curated.item.id != self.catalog_item_id:
            raise ValueError("curated item must match projection identity")
        if self.source_states != tuple(
            sorted(self.source_states, key=lambda state: state.source_id)
        ):
            raise ValueError("source states must use canonical order")
        source_ids = tuple(state.source_id for state in self.source_states)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source states must be unique")
        context = info.context or {}
        mapping = context.get("item_source_mapping", ITEM_SOURCE_MAPPING)
        expected_sources = tuple(mapping.get(self.catalog_item_id, ()))
        if source_ids != tuple(sorted(expected_sources)):
            raise ValueError("source states must match the code-owned item mapping")
        if self.dynamic_claims != tuple(
            sorted(self.dynamic_claims, key=_public_claim_sort_key)
        ):
            raise ValueError("dynamic claims must use canonical order")
        available = {
            state.source_id
            for state in self.source_states
            if state.cache_state is DynamicCacheState.AVAILABLE
        }
        if any(
            claim.provenance.source_id not in available for claim in self.dynamic_claims
        ):
            raise ValueError("dynamic claims require an available source state")
        if not self.dynamic_claims and self.conflict_state is not ConflictState.NONE:
            raise ValueError("empty dynamic evidence cannot conflict")
        curated_claim = context.get("curated_claim")
        if (
            "curated_claim" not in context
            and self.conflict_state
            in {ConflictState.AGREEMENT, ConflictState.CURATED_CONFLICT}
        ):
            # Response serialization revalidates the already-constructed model
            # without the private curated assertion used by projection evaluation.
            # The assertion is intentionally not part of the public response.
            return self
        expected_conflict = _public_conflict_state(
            self.dynamic_claims,
            curated_claim=(
                curated_claim
                if isinstance(curated_claim, ExplicitCuratedReleaseClaim)
                else None
            ),
        )
        if self.conflict_state is not expected_conflict:
            raise ValueError("conflict state must match included public claims")
        return self


class DynamicSourceReadSnapshot(ProjectionModel):
    source_id: str = Field(pattern=DISCOVERY_ID_PATTERN, max_length=128)
    cache_state: DynamicCacheState
    claims: tuple[EvaluatedDynamicClaim, ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> DynamicSourceReadSnapshot:
        if self.cache_state is not DynamicCacheState.AVAILABLE and self.claims:
            raise ValueError("absent or corrupt cache cannot contain claims")
        if any(claim.provenance.source_id != self.source_id for claim in self.claims):
            raise ValueError("claims must match snapshot source")
        if any(claim.freshness is FreshnessState.EXPIRED for claim in self.claims):
            raise ValueError("expired claims cannot appear in snapshots")
        if self.claims != tuple(sorted(self.claims, key=_evaluated_claim_sort_key)):
            raise ValueError("snapshot claims must use canonical order")
        identities = {
            (
                claim.provenance.source_id,
                claim.provenance.retrieved_at,
                claim.fact.catalog_item_id,
                claim.fact.fact_kind,
            )
            for claim in self.claims
        }
        if len(identities) != len(self.claims):
            raise ValueError("snapshot claim identities must be unique")
        return self


class DynamicSourceSnapshotReader(Protocol):
    def read_source(
        self, source_id: str, *, now: datetime
    ) -> DynamicSourceReadSnapshot: ...


class SourceHealthProvider(Protocol):
    def read_health(self, source_id: str) -> DynamicSourceHealth | None: ...


class ExplicitCuratedClaimProvider(Protocol):
    def get_claim(self, item_id: str) -> ExplicitCuratedReleaseClaim | None: ...


class DynamicDiscoveryCacheReader:
    """Read validated P2a generations without initialization or repair."""

    def __init__(self, store: DiscoveryCacheStore) -> None:
        self._store = store

    def read_source(
        self, source_id: str, *, now: datetime
    ) -> DynamicSourceReadSnapshot:
        evaluated_at = _normalize_now(now)
        try:
            current = self._store.read_current(source_id)
            current = CacheReadResult.model_validate(current.model_dump())
        except Exception:  # noqa: BLE001 - bounded cache service boundary
            return DynamicSourceReadSnapshot(
                source_id=source_id,
                cache_state=DynamicCacheState.CORRUPT,
            )
        if current.failure_reason in {
            CacheFailureReason.NOT_INITIALIZED,
            CacheFailureReason.CURRENT_MISSING,
        }:
            return DynamicSourceReadSnapshot(
                source_id=source_id,
                cache_state=DynamicCacheState.ABSENT,
            )
        if current.status is CacheReadStatus.UNAVAILABLE:
            return DynamicSourceReadSnapshot(
                source_id=source_id,
                cache_state=DynamicCacheState.CORRUPT,
            )
        if current.status is CacheReadStatus.CORRUPT or current.generation is None:
            return DynamicSourceReadSnapshot(
                source_id=source_id,
                cache_state=DynamicCacheState.CORRUPT,
            )

        generation = current.generation
        try:
            if generation.metadata.source_id != source_id:
                raise ValueError("generation source identity mismatch")
            if generation.metadata.fact_count != len(generation.records):
                raise ValueError("generation fact count mismatch")
            if any(
                record.provenance.source_id != source_id
                for record in generation.records
            ):
                raise ValueError("record source identity mismatch")
            validated_records = tuple(
                (
                    DynamicReleaseFact.model_validate(record.fact.model_dump()),
                    DynamicSourceProvenance.model_validate(
                        record.provenance.model_dump()
                    ),
                )
                for record in generation.records
            )
            if any(
                provenance.retrieved_at != generation.metadata.retrieved_at
                for _, provenance in validated_records
            ):
                raise ValueError("generation retrieval identity mismatch")
        except (AttributeError, TypeError, ValueError, ValidationError):
            return DynamicSourceReadSnapshot(
                source_id=source_id,
                cache_state=DynamicCacheState.CORRUPT,
            )

        claims: list[EvaluatedDynamicClaim] = []
        for fact, provenance in validated_records:
            try:
                claim = EvaluatedDynamicClaim.from_p1(
                    fact=fact,
                    provenance=provenance,
                    now=evaluated_at,
                )
            except (TypeError, ValueError, ValidationError):
                return DynamicSourceReadSnapshot(
                    source_id=source_id,
                    cache_state=DynamicCacheState.CORRUPT,
                )
            if claim.freshness is not FreshnessState.EXPIRED:
                claims.append(claim)
        return DynamicSourceReadSnapshot(
            source_id=source_id,
            cache_state=DynamicCacheState.AVAILABLE,
            claims=tuple(sorted(claims, key=_evaluated_claim_sort_key)),
        )


class DynamicDiscoveryProjectionService:
    """Merge curated catalog data with read-only validated dynamic evidence."""

    def __init__(
        self,
        catalog: DiscoveryCatalogService,
        cache_reader: DynamicSourceSnapshotReader,
        *,
        health_provider: SourceHealthProvider | None = None,
        curated_claim_provider: ExplicitCuratedClaimProvider | None = None,
    ) -> None:
        self._catalog = catalog
        self._cache_reader = cache_reader
        self._health_provider = health_provider
        self._curated_claim_provider = curated_claim_provider
        self._mapping = ITEM_SOURCE_MAPPING

    @classmethod
    def _for_testing(
        cls,
        catalog: DiscoveryCatalogService,
        cache_reader: DynamicSourceSnapshotReader,
        *,
        mapping: Mapping[str, tuple[str, ...]],
        health_provider: SourceHealthProvider | None = None,
        curated_claim_provider: ExplicitCuratedClaimProvider | None = None,
    ) -> DynamicDiscoveryProjectionService:
        instance = cls(
            catalog,
            cache_reader,
            health_provider=health_provider,
            curated_claim_provider=curated_claim_provider,
        )
        instance._mapping = {
            item_id: tuple(sorted(set(source_ids)))
            for item_id, source_ids in mapping.items()
        }
        return instance

    def get_item_projection(
        self, item_id: str, *, now: datetime
    ) -> DiscoveryMergedItemProjection:
        evaluated_at = _normalize_now(now)
        curated_entry = self._catalog.get_entry(item_id)
        source_ids = self._mapping.get(curated_entry.item.id, ())
        snapshots: list[DynamicSourceReadSnapshot] = []
        states: list[DynamicSourceState] = []
        for source_id in source_ids:
            try:
                snapshot = self._cache_reader.read_source(source_id, now=evaluated_at)
                snapshot = DynamicSourceReadSnapshot.model_validate(
                    snapshot.model_dump()
                )
                if snapshot.source_id != source_id:
                    raise ValueError("snapshot source identity mismatch")
                snapshot = _reevaluate_snapshot(snapshot, now=evaluated_at)
                if any(
                    claim.fact.catalog_item_id != curated_entry.item.id
                    for claim in snapshot.claims
                ):
                    raise ValueError("snapshot claim item identity mismatch")
            except Exception:  # noqa: BLE001 - source isolation boundary
                snapshot = DynamicSourceReadSnapshot(
                    source_id=source_id,
                    cache_state=DynamicCacheState.CORRUPT,
                )
            snapshots.append(snapshot)
            states.append(
                DynamicSourceState(
                    source_id=source_id,
                    health=self._read_health(source_id),
                    cache_state=snapshot.cache_state,
                )
            )

        claims = tuple(
            sorted(
                (
                    claim
                    for snapshot in snapshots
                    for claim in snapshot.claims
                    if claim.fact.catalog_item_id == curated_entry.item.id
                ),
                key=_evaluated_claim_sort_key,
            )
        )
        curated_claim = self._read_curated_claim(curated_entry.item.id)
        conflict = evaluate_release_conflict(
            curated_claim=curated_claim,
            dynamic_claims=claims,
        )
        return DiscoveryMergedItemProjection.model_validate(
            {
                "schema_version": MERGED_ITEM_SCHEMA,
                "catalog_item_id": curated_entry.item.id,
                "curated": entry_to_response(curated_entry),
                "dynamic_claims": tuple(_to_public_claim(claim) for claim in claims),
                "source_states": tuple(
                    sorted(states, key=lambda state: state.source_id)
                ),
                "conflict_state": (
                    conflict.state if conflict is not None else ConflictState.NONE
                ),
            },
            context={
                "item_source_mapping": self._mapping,
                "curated_claim": curated_claim,
            },
        )

    def _read_health(self, source_id: str) -> DynamicSourceHealth | None:
        if self._health_provider is None:
            return None
        try:
            health = self._health_provider.read_health(source_id)
        except Exception:  # noqa: BLE001 - optional observation boundary
            return None
        if health is not None and not isinstance(health, DynamicSourceHealth):
            return None
        return health

    def _read_curated_claim(self, item_id: str) -> ExplicitCuratedReleaseClaim | None:
        if self._curated_claim_provider is None:
            return None
        try:
            claim = self._curated_claim_provider.get_claim(item_id)
            if claim is None:
                return None
            validated = ExplicitCuratedReleaseClaim.model_validate(claim.model_dump())
            if validated.key.catalog_item_id != item_id:
                return None
            return validated
        except Exception:  # noqa: BLE001 - optional code-owned claim boundary
            return None


def _to_public_claim(claim: EvaluatedDynamicClaim) -> PublicDynamicClaim:
    provenance = claim.provenance
    return PublicDynamicClaim(
        fact_kind=claim.fact.fact_kind,
        version=claim.fact.version,
        published_at=claim.fact.published_at,
        freshness=claim.freshness,
        provenance=PublicDynamicProvenance(
            source_id=provenance.source_id,
            source_type=provenance.source_type,
            trust_tier=provenance.trust_tier,
            repository=provenance.repository,
            upstream_release_id=provenance.upstream_release_id,
            retrieved_at=provenance.retrieved_at,
            expires_at=provenance.expires_at,
        ),
    )


def _reevaluate_snapshot(
    snapshot: DynamicSourceReadSnapshot, *, now: datetime
) -> DynamicSourceReadSnapshot:
    if snapshot.cache_state is not DynamicCacheState.AVAILABLE:
        return snapshot
    claims: list[EvaluatedDynamicClaim] = []
    for claim in snapshot.claims:
        try:
            freshness = evaluate_freshness(claim.provenance, now=now)
            if freshness.state is None:
                return DynamicSourceReadSnapshot(
                    source_id=snapshot.source_id,
                    cache_state=DynamicCacheState.CORRUPT,
                )
            if freshness.state is FreshnessState.EXPIRED:
                continue
            claims.append(
                EvaluatedDynamicClaim(
                    schema_version="discovery-evaluated-dynamic-claim-v1",
                    fact=claim.fact,
                    provenance=claim.provenance,
                    freshness=freshness.state,
                    evaluated_at=now,
                )
            )
        except (TypeError, ValueError, ValidationError):
            return DynamicSourceReadSnapshot(
                source_id=snapshot.source_id,
                cache_state=DynamicCacheState.CORRUPT,
            )
    return DynamicSourceReadSnapshot(
        source_id=snapshot.source_id,
        cache_state=snapshot.cache_state,
        claims=tuple(sorted(claims, key=_evaluated_claim_sort_key)),
    )


def _evaluated_claim_sort_key(claim: EvaluatedDynamicClaim) -> tuple[object, ...]:
    return (
        claim.fact.catalog_item_id,
        claim.fact.fact_kind,
        claim.provenance.source_id,
        claim.provenance.retrieved_at,
        claim.fact.version,
        claim.fact.published_at,
        claim.provenance.upstream_release_id,
    )


def _public_claim_sort_key(claim: PublicDynamicClaim) -> tuple[object, ...]:
    return (
        claim.fact_kind,
        claim.provenance.source_id,
        claim.provenance.retrieved_at,
        claim.version,
        claim.published_at,
        claim.provenance.upstream_release_id,
    )


def _public_conflict_state(
    claims: tuple[PublicDynamicClaim, ...],
    *,
    curated_claim: ExplicitCuratedReleaseClaim | None,
) -> ConflictState:
    values = {(claim.version, claim.published_at) for claim in claims}
    if curated_claim is not None:
        if not claims:
            return ConflictState.NONE
        curated_value = (
            curated_claim.value.version,
            curated_claim.value.published_at,
        )
        return (
            ConflictState.AGREEMENT
            if values == {curated_value}
            else ConflictState.CURATED_CONFLICT
        )
    if len(claims) <= 1:
        return ConflictState.NONE
    return (
        ConflictState.AGREEMENT if len(values) == 1 else ConflictState.DYNAMIC_CONFLICT
    )


def _normalize_now(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("projection time must be timezone-aware")
    return now.astimezone(UTC)
