from __future__ import annotations

import asyncio
import itertools
from datetime import UTC, datetime, timedelta
from functools import wraps
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.discovery.dynamic_cache import (
    CachedFactRecord,
    CacheFailureReason,
    CachePublishResult,
    CachePublishStatus,
    CacheReadResult,
    CacheReadStatus,
    DiscoveryCacheStore,
)
from app.discovery.dynamic_evaluation import FreshnessState
from app.discovery.dynamic_refresh import (
    MAX_CONCURRENT_REFRESHES,
    RefreshCoordinator,
    RefreshOutcome,
    RefreshRequestError,
    RefreshSourceResult,
)
from app.discovery.dynamic_sources import (
    DYNAMIC_RELEASE_FACT_SCHEMA,
    FRIGATE_ADAPTER_ID,
    DynamicReleaseFact,
    DynamicSourceFailure,
    DynamicSourceHealth,
    DynamicSourceProvenance,
    DynamicSourceResult,
)

NOW = datetime(2026, 8, 17, 12, tzinfo=UTC)


def async_test(function):
    @wraps(function)
    def run(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))

    return run


def result(
    *,
    version: str = "0.16.1",
    retrieved_at: datetime = NOW,
) -> DynamicSourceResult:
    return DynamicSourceResult(
        health=DynamicSourceHealth.HEALTHY,
        fact=DynamicReleaseFact(
            schema_version=DYNAMIC_RELEASE_FACT_SCHEMA,
            catalog_item_id="frigate",
            fact_kind="latest_stable_release",
            version=version,
            published_at=NOW - timedelta(days=1),
        ),
        provenance=DynamicSourceProvenance(
            source_id=FRIGATE_ADAPTER_ID,
            source_type="github_latest_release",
            origin_class="public_https_allowlisted",
            trust_tier="supplemental",
            repository="blakeblackshear/frigate",
            upstream_release_id=123,
            retrieved_at=retrieved_at,
            expires_at=retrieved_at + timedelta(hours=24),
            response_etag='"etag"',
            api_version="2022-11-28",
        ),
    )


def failed(
    reason: DynamicSourceFailure = DynamicSourceFailure.CONNECTION_FAILED,
) -> DynamicSourceResult:
    unavailable = {
        DynamicSourceFailure.DNS_DISALLOWED,
        DynamicSourceFailure.CONNECTION_FAILED,
        DynamicSourceFailure.TIMEOUT,
        DynamicSourceFailure.TLS_FAILED,
        DynamicSourceFailure.RATE_LIMITED,
    }
    return DynamicSourceResult(
        health=(
            DynamicSourceHealth.UNAVAILABLE
            if reason in unavailable
            else DynamicSourceHealth.DEGRADED
        ),
        failure_reason=reason,
    )


class FakeAdapter:
    def __init__(self, value: DynamicSourceResult, source_id: str = FRIGATE_ADAPTER_ID):
        self.source_id = source_id
        self.value = value
        self.calls = 0
        self.started = asyncio.Event()
        self.release: asyncio.Event | None = None

    async def fetch(self) -> DynamicSourceResult:
        self.calls += 1
        self.started.set()
        if self.release is not None:
            await self.release.wait()
        return self.value


def initialized(tmp_path: Path) -> DiscoveryCacheStore:
    tmp_path.mkdir(mode=0o700, parents=True, exist_ok=True)
    store = DiscoveryCacheStore(tmp_path / "cache")
    store.initialize()
    return store


def coordinator(store, adapter: FakeAdapter) -> RefreshCoordinator:
    return RefreshCoordinator._for_testing(store, {adapter.source_id: adapter})


@async_test
async def test_explicit_healthy_refresh_publishes_and_reads_snapshot(tmp_path: Path):
    store = initialized(tmp_path)
    adapter = FakeAdapter(result())
    batch = await coordinator(store, adapter).refresh(now=NOW)
    source = batch.sources[0]
    assert source.outcome is RefreshOutcome.REFRESHED
    assert source.health is DynamicSourceHealth.HEALTHY
    assert source.snapshot is not None
    assert source.snapshot.claims[0].freshness is FreshnessState.FRESH
    assert adapter.calls == 1


@async_test
async def test_same_generation_is_a_deterministic_noop(tmp_path: Path):
    store = initialized(tmp_path)
    adapter = FakeAdapter(result())
    service = coordinator(store, adapter)
    assert (await service.refresh(now=NOW)).sources[
        0
    ].outcome is RefreshOutcome.REFRESHED
    assert (await service.refresh(now=NOW)).sources[0].outcome is RefreshOutcome.NOOP


@async_test
@pytest.mark.parametrize(
    ("reason", "outcome"),
    [
        (DynamicSourceFailure.CONNECTION_FAILED, RefreshOutcome.UNAVAILABLE),
        (DynamicSourceFailure.SCHEMA_INVALID, RefreshOutcome.DEGRADED),
    ],
)
async def test_adapter_failure_does_not_publish(tmp_path: Path, reason, outcome):
    store = initialized(tmp_path)
    source = (
        await coordinator(store, FakeAdapter(failed(reason))).refresh(now=NOW)
    ).sources[0]
    assert source.outcome is outcome
    assert source.snapshot is None
    assert store.read_current(FRIGATE_ADAPTER_ID).status is CacheReadStatus.UNAVAILABLE


@async_test
async def test_malformed_adapter_result_fails_closed(tmp_path: Path):
    malformed = DynamicSourceResult.model_construct(health=DynamicSourceHealth.HEALTHY)
    source = (
        await coordinator(initialized(tmp_path), FakeAdapter(malformed)).refresh(
            now=NOW
        )
    ).sources[0]
    assert source.outcome is RefreshOutcome.DEGRADED
    assert source.source_failure is DynamicSourceFailure.SCHEMA_INVALID


@async_test
async def test_mismatched_source_identity_fails_closed(tmp_path: Path):
    healthy = result()
    mismatched = healthy.model_copy(
        update={
            "provenance": healthy.provenance.model_copy(
                update={"source_id": "other-source"}
            )
        }
    )
    source = (
        await coordinator(initialized(tmp_path), FakeAdapter(mismatched)).refresh(
            now=NOW
        )
    ).sources[0]
    assert source.outcome is RefreshOutcome.DEGRADED
    assert source.source_failure is DynamicSourceFailure.SCHEMA_INVALID


@async_test
async def test_future_retrieval_is_rejected_before_publication(tmp_path: Path):
    store = initialized(tmp_path)
    future = result(retrieved_at=NOW + timedelta(microseconds=1))
    source = (await coordinator(store, FakeAdapter(future)).refresh(now=NOW)).sources[0]
    assert source.outcome is RefreshOutcome.DEGRADED
    assert source.source_failure is DynamicSourceFailure.SCHEMA_INVALID
    assert store.read_current(FRIGATE_ADAPTER_ID).status is CacheReadStatus.UNAVAILABLE


@async_test
async def test_already_expired_healthy_result_is_not_published(tmp_path: Path):
    store = initialized(tmp_path)
    expired = result(retrieved_at=NOW - timedelta(days=31))
    source = (await coordinator(store, FakeAdapter(expired)).refresh(now=NOW)).sources[
        0
    ]
    assert source.outcome is RefreshOutcome.DEGRADED
    assert source.source_failure is DynamicSourceFailure.SCHEMA_INVALID
    assert store.read_current(FRIGATE_ADAPTER_ID).status is CacheReadStatus.UNAVAILABLE


@async_test
@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (timedelta(hours=12), FreshnessState.FRESH),
        (timedelta(days=2), FreshnessState.STALE),
    ],
)
async def test_failed_refresh_returns_fresh_or_stale_cache(
    tmp_path: Path, age, expected
):
    store = initialized(tmp_path)
    cached = result(retrieved_at=NOW - age)
    store.publish(
        FRIGATE_ADAPTER_ID,
        (CachedFactRecord(fact=cached.fact, provenance=cached.provenance),),
    )
    source = (await coordinator(store, FakeAdapter(failed())).refresh(now=NOW)).sources[
        0
    ]
    assert source.health is DynamicSourceHealth.UNAVAILABLE
    assert source.snapshot is not None
    assert source.snapshot.claims[0].freshness is expected


@async_test
async def test_failed_refresh_excludes_expired_cache(tmp_path: Path):
    store = initialized(tmp_path)
    cached = result(retrieved_at=NOW - timedelta(days=31))
    store.publish(
        FRIGATE_ADAPTER_ID,
        (CachedFactRecord(fact=cached.fact, provenance=cached.provenance),),
    )
    source = (await coordinator(store, FakeAdapter(failed())).refresh(now=NOW)).sources[
        0
    ]
    assert source.outcome is RefreshOutcome.UNAVAILABLE
    assert source.snapshot is None


@async_test
async def test_corrupt_cache_is_bounded_and_not_repaired(tmp_path: Path):
    store = initialized(tmp_path)
    cached = result()
    store.publish(
        FRIGATE_ADAPTER_ID,
        (CachedFactRecord(fact=cached.fact, provenance=cached.provenance),),
    )
    pointer = store.sources_path / FRIGATE_ADAPTER_ID / "current.json"
    pointer.write_text("{broken", encoding="utf-8")
    before = pointer.read_bytes()
    source = (await coordinator(store, FakeAdapter(failed())).refresh(now=NOW)).sources[
        0
    ]
    assert source.outcome is RefreshOutcome.CACHE_CORRUPT
    assert pointer.read_bytes() == before


class PublishFailureStore:
    def __init__(self, delegate: DiscoveryCacheStore):
        self.delegate = delegate

    def publish(self, source_id, records):
        return CachePublishResult(
            status=CachePublishStatus.FAILED,
            failure_reason=CacheFailureReason.PUBLICATION_FAILED,
        )

    def read_current(self, source_id):
        return self.delegate.read_current(source_id)


@async_test
async def test_publication_failure_preserves_previous_generation(tmp_path: Path):
    store = initialized(tmp_path)
    old = result(version="0.15.0", retrieved_at=NOW - timedelta(hours=1))
    store.publish(
        FRIGATE_ADAPTER_ID,
        (CachedFactRecord(fact=old.fact, provenance=old.provenance),),
    )
    service = coordinator(PublishFailureStore(store), FakeAdapter(result()))
    source = (await service.refresh(now=NOW)).sources[0]
    assert source.outcome is RefreshOutcome.PUBLICATION_FAILED
    assert source.snapshot is not None
    assert source.snapshot.claims[0].fact.version == "0.15.0"


class NoopReadStore(PublishFailureStore):
    def publish(self, source_id, records):
        current = self.delegate.read_current(source_id)
        assert current.generation is not None
        return CachePublishResult(
            status=CachePublishStatus.NOOP,
            generation_id=current.generation.metadata.generation_id,
        )


class MissingAfterPublishStore:
    def publish(self, source_id, records):
        return CachePublishResult(
            status=CachePublishStatus.PUBLISHED,
            generation_id="g-durable-but-unreadable",
        )

    def read_current(self, source_id):
        return CacheReadResult(
            status=CacheReadStatus.UNAVAILABLE,
            failure_reason=CacheFailureReason.CURRENT_MISSING,
        )


@async_test
async def test_successful_publication_requires_authoritative_readback():
    source = (
        await coordinator(MissingAfterPublishStore(), FakeAdapter(result())).refresh(
            now=NOW
        )
    ).sources[0]
    assert source.outcome is RefreshOutcome.PUBLICATION_FAILED
    assert source.cache_failure is CacheFailureReason.CURRENT_MISSING


@async_test
async def test_snapshot_is_authoritative_read_not_adapter_result(tmp_path: Path):
    store = initialized(tmp_path)
    old = result(version="0.15.0", retrieved_at=NOW - timedelta(hours=1))
    store.publish(
        FRIGATE_ADAPTER_ID,
        (CachedFactRecord(fact=old.fact, provenance=old.provenance),),
    )
    source = (
        await coordinator(
            NoopReadStore(store), FakeAdapter(result(version="0.16.1"))
        ).refresh(now=NOW)
    ).sources[0]
    assert source.outcome is RefreshOutcome.NOOP
    assert source.snapshot is not None
    assert source.snapshot.claims[0].fact.version == "0.15.0"


@async_test
async def test_same_source_overlap_joins_and_cancelled_waiter_is_shielded(
    tmp_path: Path,
):
    adapter = FakeAdapter(result())
    adapter.release = asyncio.Event()
    service = coordinator(initialized(tmp_path), adapter)
    one = asyncio.create_task(service.refresh(now=NOW))
    await adapter.started.wait()
    two = asyncio.create_task(service.refresh(now=NOW))
    await asyncio.sleep(0)
    one.cancel()
    with pytest.raises(asyncio.CancelledError):
        await one
    assert FRIGATE_ADAPTER_ID in service._inflight
    adapter.release.set()
    completed = await two
    await asyncio.sleep(0)
    assert adapter.calls == 1
    assert completed.sources[0].outcome is RefreshOutcome.REFRESHED
    assert service._inflight == {}


@async_test
async def test_cancelled_coordinator_before_fetch_completion_publishes_nothing(
    tmp_path: Path,
):
    store = initialized(tmp_path)
    adapter = FakeAdapter(result())
    adapter.release = asyncio.Event()
    service = coordinator(store, adapter)
    waiter = asyncio.create_task(service.refresh(now=NOW))
    await adapter.started.wait()
    await service.aclose()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    assert store.read_current(FRIGATE_ADAPTER_ID).status is CacheReadStatus.UNAVAILABLE
    assert service._inflight == {}
    assert service._semaphore._value == MAX_CONCURRENT_REFRESHES
    await service.aclose()
    with pytest.raises(RefreshRequestError, match="coordinator_closed"):
        await service.refresh(now=NOW)


class FailsOnceAdapter(FakeAdapter):
    def __init__(self, value):
        super().__init__(value)
        self.release = asyncio.Event()

    async def fetch(self):
        self.calls += 1
        if self.calls == 1:
            self.started.set()
            await self.release.wait()
            raise RuntimeError("bounded")
        return self.value


@async_test
async def test_failed_shared_refresh_does_not_poison_retry(tmp_path: Path):
    adapter = FailsOnceAdapter(result())
    service = coordinator(initialized(tmp_path), adapter)
    first_waiter = asyncio.create_task(service.refresh(now=NOW))
    await adapter.started.wait()
    second_waiter = asyncio.create_task(service.refresh(now=NOW))
    await asyncio.sleep(0)
    adapter.release.set()
    first, joined = await asyncio.gather(first_waiter, second_waiter)
    second = await service.refresh(now=NOW)
    assert first.sources[0].outcome is RefreshOutcome.UNAVAILABLE
    assert joined == first
    assert second.sources[0].outcome is RefreshOutcome.REFRESHED
    assert adapter.calls == 2


class EmptyStore:
    def __init__(self):
        self.reads = 0
        self.publishes = 0

    def read_current(self, source_id):
        self.reads += 1
        return CacheReadResult(
            status=CacheReadStatus.UNAVAILABLE,
            failure_reason=CacheFailureReason.CURRENT_MISSING,
        )

    def publish(self, source_id, records):
        self.publishes += 1
        raise AssertionError("failure adapters cannot publish")


class ConcurrencyTracker:
    def __init__(self):
        self.active = 0
        self.maximum = 0
        self.release = asyncio.Event()


class ConcurrentAdapter(FakeAdapter):
    def __init__(self, source_id: str, tracker: ConcurrencyTracker):
        super().__init__(failed(), source_id)
        self.tracker = tracker

    async def fetch(self):
        self.calls += 1
        self.tracker.active += 1
        self.tracker.maximum = max(self.tracker.maximum, self.tracker.active)
        try:
            await self.tracker.release.wait()
            return self.value
        finally:
            self.tracker.active -= 1


@async_test
async def test_multi_source_concurrency_is_bounded_and_results_sorted():
    tracker = ConcurrencyTracker()
    adapters = {
        f"source-{index}": ConcurrentAdapter(f"source-{index}", tracker)
        for index in range(6)
    }
    service = RefreshCoordinator._for_testing(EmptyStore(), adapters)
    task = asyncio.create_task(
        service.refresh(tuple(reversed(tuple(adapters))), now=NOW)
    )
    while tracker.maximum < MAX_CONCURRENT_REFRESHES:
        await asyncio.sleep(0)
    assert tracker.maximum == MAX_CONCURRENT_REFRESHES
    tracker.release.set()
    batch = await task
    assert [item.source_id for item in batch.sources] == sorted(adapters)
    assert tracker.maximum == MAX_CONCURRENT_REFRESHES


class RaisingAdapter(FakeAdapter):
    async def fetch(self):
        self.calls += 1
        raise RuntimeError(
            "/secret/cache bearer-token https://api.github.com/?token=unsafe {raw-json}"
        )


class RaisingStore:
    def publish(self, source_id, records):
        raise RuntimeError(
            "/secret/cache bearer-token https://api.github.com/?token=unsafe {raw-json}"
        )

    def read_current(self, source_id):
        raise RuntimeError(
            "/secret/cache bearer-token https://api.github.com/?token=unsafe {raw-json}"
        )


@async_test
async def test_cache_exception_details_do_not_escape_result():
    source = (
        await coordinator(RaisingStore(), FakeAdapter(result())).refresh(now=NOW)
    ).sources[0]
    assert source.outcome is RefreshOutcome.CACHE_CORRUPT
    serialized = source.model_dump_json()
    assert "secret" not in serialized
    assert "bearer-token" not in serialized
    assert "api.github.com" not in serialized
    assert "raw-json" not in serialized


@async_test
async def test_mixed_source_failures_are_isolated_and_sorted(tmp_path: Path):
    store = initialized(tmp_path)
    malformed = DynamicSourceResult.model_construct(health=DynamicSourceHealth.HEALTHY)
    adapters = {
        FRIGATE_ADAPTER_ID: FakeAdapter(result()),
        "source-degraded": FakeAdapter(
            failed(DynamicSourceFailure.SCHEMA_INVALID), "source-degraded"
        ),
        "source-exception": RaisingAdapter(failed(), "source-exception"),
        "source-malformed": FakeAdapter(malformed, "source-malformed"),
    }
    batch = await RefreshCoordinator._for_testing(store, adapters).refresh(
        tuple(reversed(tuple(adapters))), now=NOW
    )
    assert [item.source_id for item in batch.sources] == sorted(adapters)
    assert [item.outcome for item in batch.sources] == [
        RefreshOutcome.REFRESHED,
        RefreshOutcome.DEGRADED,
        RefreshOutcome.UNAVAILABLE,
        RefreshOutcome.DEGRADED,
    ]
    serialized = batch.model_dump_json()
    assert "bearer-token" not in serialized
    assert "api.github.com" not in serialized
    assert "raw-json" not in serialized


@async_test
async def test_every_requested_source_permutation_is_equivalent():
    source_ids = ("source-a", "source-b", "source-c")
    adapters = {source_id: FakeAdapter(failed(), source_id) for source_id in source_ids}
    service = RefreshCoordinator._for_testing(EmptyStore(), adapters)
    expected = await service.refresh(source_ids, now=NOW)
    for permutation in itertools.permutations(source_ids):
        assert await service.refresh(permutation, now=NOW) == expected


@async_test
async def test_unknown_and_duplicate_requests_do_no_work():
    store = EmptyStore()
    adapter = FakeAdapter(failed())
    service = coordinator(store, adapter)
    unknown = await service.refresh(("unknown-source",), now=NOW)
    assert unknown.sources[0].outcome is RefreshOutcome.UNKNOWN_SOURCE
    with pytest.raises(RefreshRequestError, match="duplicate_source_id"):
        await service.refresh((FRIGATE_ADAPTER_ID, FRIGATE_ADAPTER_ID), now=NOW)
    assert adapter.calls == store.reads == store.publishes == 0


@async_test
async def test_explicit_selection_and_construction_have_no_side_effects(tmp_path: Path):
    root = tmp_path / "cache"
    store = DiscoveryCacheStore(root)
    adapter = FakeAdapter(failed())
    service = coordinator(store, adapter)
    assert not root.exists()
    empty = await service.refresh((), now=NOW)
    assert empty.sources == ()
    assert adapter.calls == 0
    assert not root.exists()


@async_test
async def test_production_constructor_has_exact_registry_and_no_side_effects(
    tmp_path: Path,
):
    root = tmp_path / "cache"
    tasks_before = asyncio.all_tasks()
    service = RefreshCoordinator(DiscoveryCacheStore(root))
    assert tuple(service._registry) == (FRIGATE_ADAPTER_ID,)
    assert service._registry[FRIGATE_ADAPTER_ID].source_id == FRIGATE_ADAPTER_ID
    assert asyncio.all_tasks() == tasks_before
    assert not root.exists()


@async_test
async def test_shutdown_after_publication_preserves_durable_cache(tmp_path: Path):
    store = initialized(tmp_path)
    service = coordinator(store, FakeAdapter(result()))
    completed = await service.refresh(now=NOW)
    await service.aclose()
    await service.aclose()
    assert completed.sources[0].outcome is RefreshOutcome.REFRESHED
    assert store.read_current(FRIGATE_ADAPTER_ID).status is CacheReadStatus.AVAILABLE
    assert service._inflight == {}
    with pytest.raises(RefreshRequestError, match="coordinator_closed"):
        await service.refresh(now=NOW)


@async_test
async def test_result_models_reject_contradictory_outcome_combinations(
    tmp_path: Path,
):
    valid = (
        await coordinator(initialized(tmp_path), FakeAdapter(result())).refresh(now=NOW)
    ).sources[0]
    invalid = (
        valid.model_dump() | {"snapshot": None},
        valid.model_dump()
        | {
            "health": DynamicSourceHealth.UNAVAILABLE,
            "source_failure": DynamicSourceFailure.CONNECTION_FAILED,
        },
        valid.model_dump()
        | {
            "outcome": RefreshOutcome.PUBLICATION_FAILED,
            "snapshot": None,
            "cache_failure": None,
        },
    )
    for payload in invalid:
        with pytest.raises(ValidationError):
            RefreshSourceResult.model_validate(payload)


@async_test
async def test_naive_now_is_rejected_before_work(tmp_path: Path):
    adapter = FakeAdapter(failed())
    with pytest.raises(RefreshRequestError, match="invalid_evaluation_time"):
        await coordinator(initialized(tmp_path), adapter).refresh(
            now=NOW.replace(tzinfo=None)
        )
    assert adapter.calls == 0
