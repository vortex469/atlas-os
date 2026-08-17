"""Inactive explicit refresh coordination for D10 dynamic Discovery sources."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.discovery.dynamic_cache import (
    CachedFactRecord,
    CacheFailureReason,
    CachePublishStatus,
    CacheReadStatus,
    DiscoveryCacheStore,
)
from app.discovery.dynamic_evaluation import EvaluatedDynamicClaim, FreshnessState
from app.discovery.dynamic_sources import (
    FRIGATE_ADAPTER_ID,
    DynamicSourceAdapter,
    DynamicSourceFailure,
    DynamicSourceHealth,
    DynamicSourceResult,
    FrigateGitHubLatestReleaseAdapter,
)
from app.discovery.models import DISCOVERY_ID_PATTERN

MAX_CONCURRENT_REFRESHES = 4


class RefreshModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class RefreshOutcome(StrEnum):
    REFRESHED = "refreshed"
    NOOP = "noop"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    CACHE_CORRUPT = "cache_corrupt"
    PUBLICATION_FAILED = "publication_failed"
    UNKNOWN_SOURCE = "unknown_source"


class CachedSourceSnapshot(RefreshModel):
    source_id: str = Field(pattern=DISCOVERY_ID_PATTERN, max_length=128)
    generation_id: str = Field(min_length=1, max_length=160)
    claims: tuple[EvaluatedDynamicClaim, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_claims(self) -> CachedSourceSnapshot:
        if any(claim.provenance.source_id != self.source_id for claim in self.claims):
            raise ValueError("snapshot claims must match the source")
        if any(claim.freshness is FreshnessState.EXPIRED for claim in self.claims):
            raise ValueError("expired claims cannot appear in a source snapshot")
        if self.claims != tuple(
            sorted(
                self.claims,
                key=lambda claim: (claim.fact.catalog_item_id, claim.fact.fact_kind),
            )
        ):
            raise ValueError("snapshot claims must use canonical fact-key order")
        return self


class RefreshSourceResult(RefreshModel):
    source_id: str = Field(pattern=DISCOVERY_ID_PATTERN, max_length=128)
    outcome: RefreshOutcome
    health: DynamicSourceHealth | None = None
    source_failure: DynamicSourceFailure | None = None
    cache_failure: CacheFailureReason | None = None
    snapshot: CachedSourceSnapshot | None = None
    maintenance_degraded: bool = False

    @model_validator(mode="after")
    def validate_shape(self) -> RefreshSourceResult:
        if self.outcome is RefreshOutcome.UNKNOWN_SOURCE:
            if (
                any(
                    value is not None
                    for value in (
                        self.health,
                        self.source_failure,
                        self.cache_failure,
                        self.snapshot,
                    )
                )
                or self.maintenance_degraded
            ):
                raise ValueError("unknown source results contain no source state")
            return self
        if self.health is None:
            raise ValueError("registered source results require health")
        if (self.source_failure is None) == (
            self.health is not DynamicSourceHealth.HEALTHY
        ):
            raise ValueError("source failure must match unhealthy source health")
        if self.maintenance_degraded and self.outcome is not RefreshOutcome.REFRESHED:
            raise ValueError("maintenance degradation requires durable publication")
        if self.outcome in {RefreshOutcome.REFRESHED, RefreshOutcome.NOOP}:
            if (
                self.health is not DynamicSourceHealth.HEALTHY
                or self.source_failure is not None
                or self.cache_failure is not None
                or self.snapshot is None
            ):
                raise ValueError(
                    "successful refresh requires healthy persisted evidence"
                )
        elif self.outcome is RefreshOutcome.DEGRADED:
            if (
                self.health is not DynamicSourceHealth.DEGRADED
                or self.source_failure is None
                or self.cache_failure is not None
            ):
                raise ValueError("degraded outcome requires one source failure")
        elif self.outcome is RefreshOutcome.UNAVAILABLE:
            if (
                self.health is not DynamicSourceHealth.UNAVAILABLE
                or self.source_failure is None
                or self.cache_failure is not None
            ):
                raise ValueError("unavailable outcome requires one source failure")
        elif self.outcome is RefreshOutcome.PUBLICATION_FAILED:
            if (
                self.health is not DynamicSourceHealth.HEALTHY
                or self.source_failure is not None
                or self.cache_failure is None
            ):
                raise ValueError("publication failure requires one cache failure")
        elif self.outcome is RefreshOutcome.CACHE_CORRUPT and (
            self.cache_failure is None or self.snapshot is not None
        ):
            raise ValueError("cache corruption requires one failure and no evidence")
        return self


class RefreshBatchResult(RefreshModel):
    schema_version: Literal["discovery-refresh-batch-v1"]
    evaluated_at: datetime
    sources: tuple[RefreshSourceResult, ...]

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_order(self) -> RefreshBatchResult:
        source_ids = tuple(item.source_id for item in self.sources)
        if source_ids != tuple(sorted(set(source_ids))):
            raise ValueError("refresh source results must be unique and sorted")
        return self


class RefreshRequestError(ValueError):
    """Bounded caller-contract error."""


class RefreshCoordinator:
    """Explicit-only coordinator over a caller-initialized P2a cache store."""

    def __init__(self, store: DiscoveryCacheStore) -> None:
        self._store = store
        adapter = FrigateGitHubLatestReleaseAdapter()
        self._registry: Mapping[str, DynamicSourceAdapter] = {
            FRIGATE_ADAPTER_ID: adapter
        }
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REFRESHES)
        self._inflight: dict[str, asyncio.Task[RefreshSourceResult]] = {}
        self._inflight_lock = asyncio.Lock()
        self._closed = False

    @classmethod
    def _for_testing(
        cls,
        store: DiscoveryCacheStore,
        registry: Mapping[str, DynamicSourceAdapter],
    ) -> RefreshCoordinator:
        instance = cls.__new__(cls)
        instance._store = store
        instance._registry = dict(registry)
        instance._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REFRESHES)
        instance._inflight = {}
        instance._inflight_lock = asyncio.Lock()
        instance._closed = False
        return instance

    async def refresh(
        self,
        source_ids: tuple[str, ...] | None = None,
        *,
        now: datetime,
    ) -> RefreshBatchResult:
        evaluated_at = _normalize_now(now)
        selected = tuple(sorted(self._registry)) if source_ids is None else source_ids
        if len(selected) != len(set(selected)):
            raise RefreshRequestError("duplicate_source_id")
        if any(
            not isinstance(source_id, str)
            or re.fullmatch(DISCOVERY_ID_PATTERN, source_id) is None
            or len(source_id) > 128
            for source_id in selected
        ):
            raise RefreshRequestError("invalid_source_id")
        unknown = tuple(
            sorted(
                source_id for source_id in selected if source_id not in self._registry
            )
        )
        if unknown:
            return RefreshBatchResult(
                schema_version="discovery-refresh-batch-v1",
                evaluated_at=evaluated_at,
                sources=tuple(
                    RefreshSourceResult(
                        source_id=source_id,
                        outcome=RefreshOutcome.UNKNOWN_SOURCE,
                    )
                    for source_id in unknown
                ),
            )
        results = await asyncio.gather(
            *(self._join_source(source_id, evaluated_at) for source_id in selected)
        )
        return RefreshBatchResult(
            schema_version="discovery-refresh-batch-v1",
            evaluated_at=evaluated_at,
            sources=tuple(sorted(results, key=lambda item: item.source_id)),
        )

    async def _join_source(self, source_id: str, now: datetime) -> RefreshSourceResult:
        async with self._inflight_lock:
            if self._closed:
                raise RefreshRequestError("coordinator_closed")
            task = self._inflight.get(source_id)
            if task is not None and task.done():
                self._inflight.pop(source_id, None)
                task = None
            if task is None:
                task = asyncio.create_task(self._refresh_source(source_id, now))
                self._inflight[source_id] = task
                task.add_done_callback(
                    lambda completed, selected=source_id: self._completed(
                        selected, completed
                    )
                )
        return await asyncio.shield(task)

    async def aclose(self) -> None:
        """Cancel refreshes that have not entered synchronous publication."""
        async with self._inflight_lock:
            self._closed = True
            tasks = tuple(self._inflight.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        async with self._inflight_lock:
            self._inflight.clear()

    def _completed(
        self, source_id: str, task: asyncio.Task[RefreshSourceResult]
    ) -> None:
        if self._inflight.get(source_id) is task:
            self._inflight.pop(source_id, None)

    async def _refresh_source(
        self, source_id: str, now: datetime
    ) -> RefreshSourceResult:
        adapter = self._registry[source_id]
        async with self._semaphore:
            try:
                raw = await adapter.fetch()
                fetched = DynamicSourceResult.model_validate(raw.model_dump())
            except asyncio.CancelledError:
                raise
            except (AttributeError, TypeError, ValueError, ValidationError):
                fetched = DynamicSourceResult(
                    health=DynamicSourceHealth.DEGRADED,
                    failure_reason=DynamicSourceFailure.SCHEMA_INVALID,
                )
            except Exception:  # noqa: BLE001 - adapter boundary is controlled
                fetched = DynamicSourceResult(
                    health=DynamicSourceHealth.UNAVAILABLE,
                    failure_reason=DynamicSourceFailure.CONNECTION_FAILED,
                )

            if fetched.health is DynamicSourceHealth.HEALTHY:
                assert fetched.fact is not None and fetched.provenance is not None
                if fetched.provenance.source_id != source_id:
                    return self._fallback(
                        source_id,
                        now,
                        health=DynamicSourceHealth.DEGRADED,
                        source_failure=DynamicSourceFailure.SCHEMA_INVALID,
                        forced_outcome=RefreshOutcome.DEGRADED,
                    )
                try:
                    evaluated = EvaluatedDynamicClaim.from_p1(
                        fact=fetched.fact,
                        provenance=fetched.provenance,
                        now=now,
                    )
                    if evaluated.freshness is FreshnessState.EXPIRED:
                        raise ValueError("new source evidence is already expired")
                    record = CachedFactRecord(
                        fact=fetched.fact,
                        provenance=fetched.provenance,
                    )
                except (ValueError, ValidationError):
                    return self._fallback(
                        source_id,
                        now,
                        health=DynamicSourceHealth.DEGRADED,
                        source_failure=DynamicSourceFailure.SCHEMA_INVALID,
                        forced_outcome=RefreshOutcome.DEGRADED,
                    )
                try:
                    publication = self._store.publish(source_id, (record,))
                except Exception:  # noqa: BLE001 - cache service boundary is controlled
                    return self._fallback(
                        source_id,
                        now,
                        health=DynamicSourceHealth.HEALTHY,
                        cache_failure=CacheFailureReason.PUBLICATION_FAILED,
                        forced_outcome=RefreshOutcome.PUBLICATION_FAILED,
                    )
                if publication.status is CachePublishStatus.FAILED:
                    corrupt = publication.failure_reason in {
                        CacheFailureReason.MALFORMED,
                        CacheFailureReason.CHECKSUM_MISMATCH,
                        CacheFailureReason.SIZE_EXCEEDED,
                        CacheFailureReason.UNSAFE_FILESYSTEM,
                    }
                    return self._fallback(
                        source_id,
                        now,
                        health=DynamicSourceHealth.HEALTHY,
                        cache_failure=publication.failure_reason,
                        forced_outcome=(
                            RefreshOutcome.CACHE_CORRUPT
                            if corrupt
                            else RefreshOutcome.PUBLICATION_FAILED
                        ),
                    )
                return self._fallback(
                    source_id,
                    now,
                    health=DynamicSourceHealth.HEALTHY,
                    forced_outcome=(
                        RefreshOutcome.REFRESHED
                        if publication.status is CachePublishStatus.PUBLISHED
                        else RefreshOutcome.NOOP
                    ),
                    maintenance_degraded=publication.maintenance_failed,
                )

            assert fetched.failure_reason is not None
            return self._fallback(
                source_id,
                now,
                health=fetched.health,
                source_failure=fetched.failure_reason,
                forced_outcome=(
                    RefreshOutcome.UNAVAILABLE
                    if fetched.health is DynamicSourceHealth.UNAVAILABLE
                    else RefreshOutcome.DEGRADED
                ),
            )

    def _fallback(
        self,
        source_id: str,
        now: datetime,
        *,
        health: DynamicSourceHealth,
        forced_outcome: RefreshOutcome,
        source_failure: DynamicSourceFailure | None = None,
        cache_failure: CacheFailureReason | None = None,
        maintenance_degraded: bool = False,
    ) -> RefreshSourceResult:
        try:
            current = self._store.read_current(source_id)
        except Exception:  # noqa: BLE001 - cache service boundary is controlled
            return RefreshSourceResult(
                source_id=source_id,
                outcome=RefreshOutcome.CACHE_CORRUPT,
                health=health,
                source_failure=source_failure,
                cache_failure=cache_failure or CacheFailureReason.IO_FAILED,
            )
        if current.status is CacheReadStatus.CORRUPT:
            return RefreshSourceResult(
                source_id=source_id,
                outcome=RefreshOutcome.CACHE_CORRUPT,
                health=health,
                source_failure=source_failure,
                cache_failure=current.failure_reason or cache_failure,
            )
        if current.status is CacheReadStatus.UNAVAILABLE and forced_outcome in {
            RefreshOutcome.REFRESHED,
            RefreshOutcome.NOOP,
        }:
            return RefreshSourceResult(
                source_id=source_id,
                outcome=RefreshOutcome.PUBLICATION_FAILED,
                health=health,
                source_failure=source_failure,
                cache_failure=current.failure_reason or CacheFailureReason.IO_FAILED,
            )
        snapshot = None
        if (
            current.status is CacheReadStatus.AVAILABLE
            and current.generation is not None
        ):
            try:
                evaluated = tuple(
                    EvaluatedDynamicClaim.from_p1(
                        fact=record.fact,
                        provenance=record.provenance,
                        now=now,
                    )
                    for record in current.generation.records
                )
            except (TypeError, ValueError, ValidationError):
                return RefreshSourceResult(
                    source_id=source_id,
                    outcome=RefreshOutcome.CACHE_CORRUPT,
                    health=health,
                    source_failure=source_failure,
                    cache_failure=CacheFailureReason.MALFORMED,
                )
            claims = tuple(
                claim
                for claim in evaluated
                if claim.freshness is not FreshnessState.EXPIRED
            )
            if claims:
                snapshot = CachedSourceSnapshot(
                    source_id=source_id,
                    generation_id=current.generation.metadata.generation_id,
                    claims=claims,
                )
        return RefreshSourceResult(
            source_id=source_id,
            outcome=forced_outcome,
            health=health,
            source_failure=source_failure,
            cache_failure=cache_failure,
            snapshot=snapshot,
            maintenance_degraded=maintenance_degraded,
        )


def _normalize_now(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise RefreshRequestError("invalid_evaluation_time")
    return now.astimezone(UTC)
