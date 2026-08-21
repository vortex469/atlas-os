from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from threading import Event, Thread

import pytest
from pydantic import ValidationError

from app.discovery.dynamic_cache import (
    CachedFactRecord,
    DiscoveryCacheStore,
)
from app.discovery.dynamic_evaluation import (
    CanonicalFactKey,
    CanonicalReleaseValue,
    ConflictState,
    CuratedClaimProvenance,
    EvaluatedDynamicClaim,
    ExplicitCuratedReleaseClaim,
    FreshnessState,
    NormalizedDynamicProvenance,
    evaluate_freshness,
)
from app.discovery.dynamic_projection import (
    MERGED_ITEM_SCHEMA,
    DiscoveryMergedItemProjection,
    DynamicCacheState,
    DynamicDiscoveryCacheReader,
    DynamicDiscoveryProjectionService,
    DynamicSourceReadSnapshot,
    DynamicSourceState,
    PublicDynamicProvenance,
)
from app.discovery.dynamic_sources import (
    DYNAMIC_RELEASE_FACT_SCHEMA,
    FRIGATE_ADAPTER_ID,
    DynamicReleaseFact,
    DynamicSourceHealth,
    DynamicSourceProvenance,
)
from app.discovery.models import (
    CATALOG_SCHEMA_VERSION,
    CatalogEntry,
    CatalogProvenance,
    CatalogSourceType,
    CatalogTrustLevel,
    DiscoveryItem,
    DiscoveryItemType,
)
from app.discovery.release_evaluation import (
    ReleaseEvaluationBaseline,
    ReleaseEvaluationBaselineSource,
    ReleaseEvaluationResult,
    ReleaseEvaluationStatus,
)
from app.services.discovery import DiscoveryCatalogService, DiscoveryItemNotFoundError

NOW = datetime(2026, 8, 17, 12, tzinfo=UTC)
PUBLISHED = NOW - timedelta(days=1)


def entry(item_id: str = "frigate", version: str | None = None) -> CatalogEntry:
    return CatalogEntry(
        schema_version=CATALOG_SCHEMA_VERSION,
        item=DiscoveryItem(
            id=item_id,
            type=DiscoveryItemType.APPLICATION,
            name=item_id.title(),
            version=version,
        ),
        provenance=CatalogProvenance(
            source_type=CatalogSourceType.CURATED,
            source="atlas-curated-discovery-catalog",
            entry_id=f"entry-{item_id}",
            trust_level=CatalogTrustLevel.CURATED,
        ),
    )


class StaticLoader:
    def __init__(self, entries: tuple[CatalogEntry, ...]):
        self.entries = entries

    def load(self):
        return self.entries


def catalog(*entries: CatalogEntry) -> DiscoveryCatalogService:
    return DiscoveryCatalogService(StaticLoader(tuple(entries)))


def p1_record(
    *,
    version: str = "0.16.1",
    retrieved_at: datetime = NOW,
) -> CachedFactRecord:
    return CachedFactRecord(
        fact=DynamicReleaseFact(
            schema_version=DYNAMIC_RELEASE_FACT_SCHEMA,
            catalog_item_id="frigate",
            fact_kind="latest_stable_release",
            version=version,
            published_at=PUBLISHED,
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
            response_etag='"private-etag"',
            api_version="2022-11-28",
        ),
    )


def evaluated(
    source_id: str,
    *,
    version: str = "0.16.1",
    retrieved_at: datetime = NOW,
    now: datetime = NOW,
    release_id: int = 123,
) -> EvaluatedDynamicClaim:
    provenance = NormalizedDynamicProvenance(
        source_id=source_id,
        source_type="github_latest_release",
        origin_class="public_https_allowlisted",
        trust_tier="supplemental",
        repository="synthetic/public-project",
        upstream_release_id=release_id,
        retrieved_at=retrieved_at,
        expires_at=retrieved_at + timedelta(hours=24),
        response_etag='"internal"',
        api_version="2022-11-28",
    )
    freshness = evaluate_freshness(provenance, now=now)
    assert freshness.state is not None
    return EvaluatedDynamicClaim(
        schema_version="discovery-evaluated-dynamic-claim-v1",
        fact=DynamicReleaseFact(
            schema_version=DYNAMIC_RELEASE_FACT_SCHEMA,
            catalog_item_id="frigate",
            fact_kind="latest_stable_release",
            version=version,
            published_at=PUBLISHED,
        ),
        provenance=provenance,
        freshness=freshness.state,
        evaluated_at=now,
    )


class FakeReader:
    def __init__(self, snapshots: dict[str, DynamicSourceReadSnapshot]):
        self.snapshots = snapshots
        self.calls: list[tuple[str, datetime]] = []

    def read_source(self, source_id: str, *, now: datetime):
        self.calls.append((source_id, now))
        return self.snapshots[source_id]


class HealthProvider:
    def __init__(self, values):
        self.values = values

    def read_health(self, source_id: str):
        value = self.values[source_id]
        if isinstance(value, Exception):
            raise value
        return value


class CuratedProvider:
    def __init__(self, claim: ExplicitCuratedReleaseClaim | None):
        self.claim = claim

    def get_claim(self, item_id: str):
        return self.claim


def curated_claim(version: str = "0.16.1") -> ExplicitCuratedReleaseClaim:
    return ExplicitCuratedReleaseClaim(
        schema_version="discovery-curated-release-claim-v1",
        key=CanonicalFactKey(
            catalog_item_id="frigate",
            fact_kind="latest_stable_release",
        ),
        value=CanonicalReleaseValue(version=version, published_at=PUBLISHED),
        provenance=CuratedClaimProvenance(
            source_class="curated",
            source_id="atlas-curated-catalog",
            trust_tier="curated",
        ),
    )


def initialized(tmp_path: Path) -> DiscoveryCacheStore:
    tmp_path.mkdir(mode=0o700, parents=True, exist_ok=True)
    store = DiscoveryCacheStore(tmp_path / "cache")
    store.initialize()
    return store


def service(
    reader,
    *,
    mapping=None,
    health_provider=None,
    curated_provider=None,
    entries=None,
) -> DynamicDiscoveryProjectionService:
    selected_entries = entries if entries is not None else (entry(),)
    return DynamicDiscoveryProjectionService._for_testing(
        catalog(*selected_entries),
        reader,
        mapping=mapping or {"frigate": (FRIGATE_ADAPTER_ID,)},
        health_provider=health_provider,
        curated_claim_provider=curated_provider,
    )


def test_models_are_strict_bounded_and_reject_contradictory_claim_sources():
    claim = evaluated(FRIGATE_ADAPTER_ID)
    snapshot = DynamicSourceReadSnapshot(
        source_id=FRIGATE_ADAPTER_ID,
        cache_state=DynamicCacheState.AVAILABLE,
        claims=(claim,),
    )
    projection = service(
        FakeReader({FRIGATE_ADAPTER_ID: snapshot})
    ).get_item_projection("frigate", now=NOW)
    assert projection.schema_version == MERGED_ITEM_SCHEMA
    with pytest.raises(ValidationError):
        DiscoveryMergedItemProjection.model_validate(
            projection.model_dump() | {"unknown": True}
        )
    with pytest.raises(ValidationError, match="available source"):
        DiscoveryMergedItemProjection.model_validate(
            projection.model_dump()
            | {
                "source_states": (
                    DynamicSourceState(
                        source_id=FRIGATE_ADAPTER_ID,
                        cache_state=DynamicCacheState.ABSENT,
                    ),
                )
            }
        )
    with pytest.raises(ValidationError):
        PublicDynamicProvenance.model_validate(
            projection.dynamic_claims[0].provenance.model_dump()
            | {"repository": "x" * 257}
        )
    with pytest.raises(ValidationError):
        PublicDynamicProvenance.model_validate(
            projection.dynamic_claims[0].provenance.model_dump()
            | {"repository": "https://api.github.com/project?token=secret"}
        )
    with pytest.raises(ValidationError, match="exactly 24 hours"):
        PublicDynamicProvenance.model_validate(
            projection.dynamic_claims[0].provenance.model_dump()
            | {"expires_at": NOW + timedelta(hours=25)}
        )

    with pytest.raises(ValidationError, match="code-owned item mapping"):
        DiscoveryMergedItemProjection.model_validate(
            projection.model_dump()
            | {
                "source_states": (
                    DynamicSourceState(
                        source_id="unrelated-source",
                        cache_state=DynamicCacheState.AVAILABLE,
                    ),
                ),
                "dynamic_claims": (),
                "conflict_state": ConflictState.NONE,
            }
        )
    with pytest.raises(ValidationError, match="conflict state"):
        DiscoveryMergedItemProjection.model_validate(
            projection.model_dump() | {"conflict_state": ConflictState.DYNAMIC_CONFLICT}
        )
    with pytest.raises(ValidationError, match="identities must be unique"):
        DynamicSourceReadSnapshot(
            source_id=FRIGATE_ADAPTER_ID,
            cache_state=DynamicCacheState.AVAILABLE,
            claims=(claim, claim),
        )


def test_unmapped_item_is_curated_only_and_unknown_item_uses_existing_error():
    reader = FakeReader({})
    projection = service(
        reader,
        mapping={"frigate": (FRIGATE_ADAPTER_ID,)},
        entries=(entry(), entry("mqtt")),
    ).get_item_projection("mqtt", now=NOW)
    assert projection.catalog_item_id == "mqtt"
    assert projection.dynamic_claims == projection.source_states == ()
    assert projection.conflict_state is ConflictState.NONE
    assert reader.calls == []
    with pytest.raises(DiscoveryItemNotFoundError):
        service(reader).get_item_projection("missing", now=NOW)


def test_discovery_item_version_is_not_reinterpreted_as_curated_release():
    claim = evaluated(FRIGATE_ADAPTER_ID, version="9.9.9")
    snapshot = DynamicSourceReadSnapshot(
        source_id=FRIGATE_ADAPTER_ID,
        cache_state=DynamicCacheState.AVAILABLE,
        claims=(claim,),
    )
    curated_entry = entry(version="1.0.0")
    before = curated_entry.model_dump()
    projection = service(
        FakeReader({FRIGATE_ADAPTER_ID: snapshot}),
        entries=(curated_entry,),
    ).get_item_projection("frigate", now=NOW)
    assert projection.curated.item.version == "1.0.0"
    assert projection.dynamic_claims[0].version == "9.9.9"
    assert projection.conflict_state is ConflictState.NONE
    assert curated_entry.model_dump() == before


def test_cache_reader_maps_uninitialized_and_missing_to_absent(tmp_path: Path):
    uninitialized = DiscoveryCacheStore(tmp_path / "uninitialized")
    assert (
        DynamicDiscoveryCacheReader(uninitialized)
        .read_source(FRIGATE_ADAPTER_ID, now=NOW)
        .cache_state
        is DynamicCacheState.ABSENT
    )
    store = initialized(tmp_path / "initialized")
    assert (
        DynamicDiscoveryCacheReader(store)
        .read_source(FRIGATE_ADAPTER_ID, now=NOW)
        .cache_state
        is DynamicCacheState.ABSENT
    )


@pytest.mark.parametrize(
    ("age", "expected", "visible"),
    [
        (timedelta(hours=12), FreshnessState.FRESH, True),
        (timedelta(days=2), FreshnessState.STALE, True),
        (timedelta(days=30), FreshnessState.STALE, True),
        (timedelta(days=30, microseconds=1), FreshnessState.EXPIRED, False),
    ],
)
def test_cache_reader_fresh_stale_and_expired_boundaries(
    tmp_path: Path, age, expected, visible
):
    store = initialized(tmp_path)
    store.publish(FRIGATE_ADAPTER_ID, (p1_record(retrieved_at=NOW - age),))
    snapshot = DynamicDiscoveryCacheReader(store).read_source(
        FRIGATE_ADAPTER_ID, now=NOW
    )
    assert snapshot.cache_state is DynamicCacheState.AVAILABLE
    assert bool(snapshot.claims) is visible
    if visible:
        assert snapshot.claims[0].freshness is expected


def test_available_cache_cross_object_identity_is_revalidated(tmp_path: Path):
    store = initialized(tmp_path)
    store.publish(FRIGATE_ADAPTER_ID, (p1_record(),))
    current = store.read_current(FRIGATE_ADAPTER_ID)
    assert current.generation is not None

    class BypassedStore:
        def __init__(self, value):
            self.value = value

        def read_current(self, source_id):
            return self.value

    wrong_source = current.model_copy(
        update={
            "generation": current.generation.model_copy(
                update={
                    "metadata": current.generation.metadata.model_copy(
                        update={"source_id": "other-source"}
                    )
                }
            )
        }
    )
    malformed_fact = current.model_copy(
        update={
            "generation": current.generation.model_copy(
                update={
                    "records": (
                        current.generation.records[0].model_copy(
                            update={
                                "fact": current.generation.records[0].fact.model_copy(
                                    update={"version": "not-canonical"}
                                )
                            }
                        ),
                    )
                }
            )
        }
    )
    for bypassed in (wrong_source, malformed_fact):
        snapshot = DynamicDiscoveryCacheReader(BypassedStore(bypassed)).read_source(
            FRIGATE_ADAPTER_ID, now=NOW
        )
        assert snapshot.cache_state is DynamicCacheState.CORRUPT
        assert snapshot.claims == ()


def test_future_evaluation_time_mismatch_marks_source_corrupt(
    tmp_path: Path,
):
    store = initialized(tmp_path)
    store.publish(
        FRIGATE_ADAPTER_ID,
        (p1_record(retrieved_at=NOW + timedelta(microseconds=1)),),
    )
    snapshot = DynamicDiscoveryCacheReader(store).read_source(
        FRIGATE_ADAPTER_ID, now=NOW
    )
    assert snapshot.cache_state is DynamicCacheState.CORRUPT
    assert snapshot.claims == ()


def test_corrupt_and_unreadable_cache_are_isolated_without_leakage(tmp_path: Path):
    store = initialized(tmp_path)
    store.publish(FRIGATE_ADAPTER_ID, (p1_record(),))
    pointer = store.sources_path / FRIGATE_ADAPTER_ID / "current.json"
    pointer.write_text("{broken /secret bearer-token", encoding="utf-8")
    snapshot = DynamicDiscoveryCacheReader(store).read_source(
        FRIGATE_ADAPTER_ID, now=NOW
    )
    assert snapshot.cache_state is DynamicCacheState.CORRUPT
    assert snapshot.claims == ()

    class RaisingStore:
        def read_current(self, source_id):
            raise RuntimeError("/secret bearer-token https://api.github.com?token=x")

    unreadable = DynamicDiscoveryCacheReader(RaisingStore()).read_source(
        FRIGATE_ADAPTER_ID, now=NOW
    )
    assert unreadable.cache_state is DynamicCacheState.CORRUPT
    assert "secret" not in unreadable.model_dump_json()


@pytest.mark.parametrize(
    "health",
    [
        None,
        DynamicSourceHealth.HEALTHY,
        DynamicSourceHealth.DEGRADED,
        DynamicSourceHealth.UNAVAILABLE,
    ],
)
@pytest.mark.parametrize("freshness", [FreshnessState.FRESH, FreshnessState.STALE])
def test_health_is_independent_from_freshness(health, freshness):
    now = NOW if freshness is FreshnessState.FRESH else NOW + timedelta(days=2)
    claim = evaluated(FRIGATE_ADAPTER_ID, now=now)
    snapshot = DynamicSourceReadSnapshot(
        source_id=FRIGATE_ADAPTER_ID,
        cache_state=DynamicCacheState.AVAILABLE,
        claims=(claim,),
    )
    projection = service(
        FakeReader({FRIGATE_ADAPTER_ID: snapshot}),
        health_provider=HealthProvider({FRIGATE_ADAPTER_ID: health}),
    ).get_item_projection("frigate", now=now)
    assert projection.source_states[0].health is health
    assert projection.dynamic_claims[0].freshness is freshness


def test_missing_or_failed_health_observation_is_null():
    snapshot = DynamicSourceReadSnapshot(
        source_id=FRIGATE_ADAPTER_ID,
        cache_state=DynamicCacheState.ABSENT,
    )
    missing = service(FakeReader({FRIGATE_ADAPTER_ID: snapshot})).get_item_projection(
        "frigate", now=NOW
    )
    failed_health = service(
        FakeReader({FRIGATE_ADAPTER_ID: snapshot}),
        health_provider=HealthProvider(
            {FRIGATE_ADAPTER_ID: RuntimeError("bearer-token /secret")}
        ),
    ).get_item_projection("frigate", now=NOW)
    assert missing.source_states[0].health is None
    assert failed_health.source_states[0].health is None
    invalid_health = service(
        FakeReader({FRIGATE_ADAPTER_ID: snapshot}),
        health_provider=HealthProvider({FRIGATE_ADAPTER_ID: "healthy"}),
    ).get_item_projection("frigate", now=NOW)
    assert invalid_health.source_states[0].health is None


def test_service_reevaluates_reader_claims_with_projection_now():
    snapshot = DynamicSourceReadSnapshot(
        source_id=FRIGATE_ADAPTER_ID,
        cache_state=DynamicCacheState.AVAILABLE,
        claims=(evaluated(FRIGATE_ADAPTER_ID, now=NOW),),
    )
    projection = service(
        FakeReader({FRIGATE_ADAPTER_ID: snapshot})
    ).get_item_projection("frigate", now=NOW + timedelta(days=2))
    assert projection.dynamic_claims[0].freshness is FreshnessState.STALE


def test_one_corrupt_source_does_not_hide_other_source_evidence():
    healthy = DynamicSourceReadSnapshot(
        source_id="source-healthy",
        cache_state=DynamicCacheState.AVAILABLE,
        claims=(evaluated("source-healthy"),),
    )

    class PartlyFailingReader:
        def read_source(self, source_id: str, *, now: datetime):
            if source_id == "source-corrupt":
                raise RuntimeError("/secret/cache bearer-token")
            return healthy

    projection = service(
        PartlyFailingReader(),
        mapping={"frigate": ("source-healthy", "source-corrupt")},
    ).get_item_projection("frigate", now=NOW)
    assert len(projection.dynamic_claims) == 1
    assert [state.cache_state for state in projection.source_states] == [
        DynamicCacheState.CORRUPT,
        DynamicCacheState.AVAILABLE,
    ]


@pytest.mark.parametrize(
    ("versions", "expected"),
    [
        (("0.16.1",), ConflictState.NONE),
        (("0.16.1", "0.16.1"), ConflictState.AGREEMENT),
        (("9.0.0", "10.0.0"), ConflictState.DYNAMIC_CONFLICT),
    ],
)
def test_supplemental_and_dynamic_conflict_states(versions, expected):
    snapshots = {
        f"source-{index}": DynamicSourceReadSnapshot(
            source_id=f"source-{index}",
            cache_state=DynamicCacheState.AVAILABLE,
            claims=(
                evaluated(
                    f"source-{index}",
                    version=version,
                    release_id=index + 1,
                ),
            ),
        )
        for index, version in enumerate(versions)
    }
    projection = service(
        FakeReader(snapshots),
        mapping={"frigate": tuple(reversed(tuple(snapshots)))},
    ).get_item_projection("frigate", now=NOW)
    assert projection.conflict_state is expected
    assert len(projection.dynamic_claims) == len(versions)
    assert "winner" not in projection.model_dump()


@pytest.mark.parametrize(
    ("dynamic_version", "curated_version", "expected"),
    [
        ("0.16.1", "0.16.1", ConflictState.AGREEMENT),
        ("0.16.1", "9.9.9", ConflictState.CURATED_CONFLICT),
    ],
)
def test_explicit_typed_curated_agreement_and_conflict(
    dynamic_version, curated_version, expected
):
    snapshot = DynamicSourceReadSnapshot(
        source_id=FRIGATE_ADAPTER_ID,
        cache_state=DynamicCacheState.AVAILABLE,
        claims=(evaluated(FRIGATE_ADAPTER_ID, version=dynamic_version),),
    )
    projection = service(
        FakeReader({FRIGATE_ADAPTER_ID: snapshot}),
        curated_provider=CuratedProvider(curated_claim(curated_version)),
    ).get_item_projection("frigate", now=NOW)
    assert projection.conflict_state is expected
    assert projection.curated.item.version is None


def test_source_and_claim_permutations_are_deterministic():
    source_ids = ("source-a", "source-b", "source-c")
    snapshots = {
        source_id: DynamicSourceReadSnapshot(
            source_id=source_id,
            cache_state=DynamicCacheState.AVAILABLE,
            claims=(evaluated(source_id, release_id=index + 1),),
        )
        for index, source_id in enumerate(source_ids)
    }
    expected = service(
        FakeReader(snapshots), mapping={"frigate": source_ids}
    ).get_item_projection("frigate", now=NOW)
    for permutation in itertools.permutations(source_ids):
        actual = service(
            FakeReader(snapshots), mapping={"frigate": permutation}
        ).get_item_projection("frigate", now=NOW)
        assert actual == expected


def test_equivalent_timezone_offsets_produce_identical_projection():
    snapshot = DynamicSourceReadSnapshot(
        source_id=FRIGATE_ADAPTER_ID,
        cache_state=DynamicCacheState.AVAILABLE,
        claims=(evaluated(FRIGATE_ADAPTER_ID),),
    )
    projection_service = service(FakeReader({FRIGATE_ADAPTER_ID: snapshot}))
    assert projection_service.get_item_projection(
        "frigate", now=NOW
    ) == projection_service.get_item_projection(
        "frigate", now=NOW.astimezone(timezone(timedelta(hours=5, minutes=30)))
    )


def test_public_projection_does_not_disclose_internal_cache_or_transport_fields():
    snapshot = DynamicSourceReadSnapshot(
        source_id=FRIGATE_ADAPTER_ID,
        cache_state=DynamicCacheState.AVAILABLE,
        claims=(evaluated(FRIGATE_ADAPTER_ID),),
    )
    payload = (
        service(FakeReader({FRIGATE_ADAPTER_ID: snapshot}))
        .get_item_projection("frigate", now=NOW)
        .model_dump_json()
    )
    for forbidden in (
        "etag",
        "api_version",
        "generation",
        "checksum",
        "cache/",
        "api.github.com",
        "private-etag",
        "internal",
    ):
        assert forbidden not in payload.lower()


def test_concurrent_publish_and_read_observes_only_complete_generation(tmp_path: Path):
    store = initialized(tmp_path)
    store.publish(FRIGATE_ADAPTER_ID, (p1_record(version="0.15.0"),))
    reached = Event()
    release = Event()

    def hook(phase: str):
        if phase == "before_current_pointer_replace":
            reached.set()
            release.wait(timeout=5)

    publisher = Thread(
        target=lambda: store.publish(
            FRIGATE_ADAPTER_ID,
            (p1_record(version="0.16.1", retrieved_at=NOW + timedelta(seconds=1)),),
            failure_hook=hook,
        )
    )
    publisher.start()
    assert reached.wait(timeout=5)
    holder: list[DynamicSourceReadSnapshot] = []
    reader = Thread(
        target=lambda: holder.append(
            DynamicDiscoveryCacheReader(store).read_source(
                FRIGATE_ADAPTER_ID, now=NOW + timedelta(seconds=1)
            )
        )
    )
    reader.start()
    release.set()
    publisher.join(timeout=5)
    reader.join(timeout=5)
    assert not publisher.is_alive() and not reader.is_alive()
    assert len(holder) == 1
    assert holder[0].claims[0].fact.version in {"0.15.0", "0.16.1"}


def test_construction_has_no_cache_or_catalog_read_side_effect(tmp_path: Path):
    root = tmp_path / "cache"
    store = DiscoveryCacheStore(root)
    reader = DynamicDiscoveryCacheReader(store)
    DynamicDiscoveryProjectionService(catalog(entry()), reader)
    assert not root.exists()


def test_naive_projection_time_is_rejected_before_reads():
    reader = FakeReader({})
    with pytest.raises(ValueError, match="timezone-aware"):
        service(reader).get_item_projection("frigate", now=NOW.replace(tzinfo=None))
    assert reader.calls == []


def _stale_snapshot() -> DynamicSourceReadSnapshot:
    claim = evaluated(
        FRIGATE_ADAPTER_ID,
        version="0.14.0",
        retrieved_at=NOW - timedelta(days=5),
    )
    return DynamicSourceReadSnapshot(
        source_id=FRIGATE_ADAPTER_ID,
        cache_state=DynamicCacheState.AVAILABLE,
        claims=(claim,),
    )


def test_release_evaluation_populated_from_fresh_dynamic_evidence():
    projection = service(
        FakeReader({FRIGATE_ADAPTER_ID: DynamicSourceReadSnapshot(
            source_id=FRIGATE_ADAPTER_ID,
            cache_state=DynamicCacheState.AVAILABLE,
            claims=(evaluated(FRIGATE_ADAPTER_ID, version="0.16.1"),),
        )}),
        entries=(entry(version="0.15.0"),),
    ).get_item_projection("frigate", now=NOW)
    evaluation = projection.release_evaluation
    assert isinstance(evaluation, ReleaseEvaluationResult)
    assert evaluation.status is ReleaseEvaluationStatus.UPDATE_AVAILABLE
    assert evaluation.baseline == ReleaseEvaluationBaseline(
        version="0.15.0", source=ReleaseEvaluationBaselineSource.ITEM_VERSION
    )
    assert evaluation.latest_candidate == "0.16.1"
    assert evaluation.reason is None


def test_release_evaluation_no_baseline_when_item_version_missing():
    projection = service(
        FakeReader({FRIGATE_ADAPTER_ID: DynamicSourceReadSnapshot(
            source_id=FRIGATE_ADAPTER_ID,
            cache_state=DynamicCacheState.AVAILABLE,
            claims=(evaluated(FRIGATE_ADAPTER_ID, version="0.16.1"),),
        )}),
        entries=(entry(version=None),),
    ).get_item_projection("frigate", now=NOW)
    evaluation = projection.release_evaluation
    assert evaluation is not None
    assert evaluation.status is ReleaseEvaluationStatus.NO_BASELINE
    assert evaluation.baseline is None
    assert evaluation.latest_candidate is None
    assert evaluation.reason is not None


def test_release_evaluation_curated_claim_is_authoritative_baseline():
    projection = service(
        FakeReader({FRIGATE_ADAPTER_ID: DynamicSourceReadSnapshot(
            source_id=FRIGATE_ADAPTER_ID,
            cache_state=DynamicCacheState.AVAILABLE,
            claims=(evaluated(FRIGATE_ADAPTER_ID, version="0.16.1"),),
        )}),
        curated_provider=CuratedProvider(curated_claim(version="0.16.1")),
    ).get_item_projection("frigate", now=NOW)
    assert projection.conflict_state is ConflictState.AGREEMENT
    evaluation = projection.release_evaluation
    assert evaluation is not None
    assert evaluation.status is ReleaseEvaluationStatus.UP_TO_DATE
    assert evaluation.baseline == ReleaseEvaluationBaseline(
        version="0.16.1", source=ReleaseEvaluationBaselineSource.CURATED
    )
    assert evaluation.latest_candidate == "0.16.1"


def test_release_evaluation_baseline_ahead_when_dynamic_is_older():
    projection = service(
        FakeReader({FRIGATE_ADAPTER_ID: DynamicSourceReadSnapshot(
            source_id=FRIGATE_ADAPTER_ID,
            cache_state=DynamicCacheState.AVAILABLE,
            claims=(evaluated(FRIGATE_ADAPTER_ID, version="0.14.0"),),
        )}),
        entries=(entry(version="0.15.0"),),
    ).get_item_projection("frigate", now=NOW)
    evaluation = projection.release_evaluation
    assert evaluation is not None
    assert evaluation.status is ReleaseEvaluationStatus.BASELINE_AHEAD
    assert evaluation.latest_candidate == "0.14.0"
    assert evaluation.baseline is not None
    assert evaluation.baseline.version == "0.15.0"


def test_release_evaluation_stale_evidence_is_never_positive():
    projection = service(
        FakeReader({FRIGATE_ADAPTER_ID: _stale_snapshot()}),
        entries=(entry(version="0.15.0"),),
    ).get_item_projection("frigate", now=NOW)
    evaluation = projection.release_evaluation
    assert evaluation is not None
    assert evaluation.status is ReleaseEvaluationStatus.STALE_EVIDENCE
    assert evaluation.baseline is not None
    assert evaluation.latest_candidate is None
    assert evaluation.reason is not None


def test_release_evaluation_no_dynamic_evidence_when_no_claims():
    projection = service(
        FakeReader({FRIGATE_ADAPTER_ID: DynamicSourceReadSnapshot(
            source_id=FRIGATE_ADAPTER_ID,
            cache_state=DynamicCacheState.ABSENT,
        )}),
        entries=(entry(version="0.15.0"),),
    ).get_item_projection("frigate", now=NOW)
    evaluation = projection.release_evaluation
    assert evaluation is not None
    assert evaluation.status is ReleaseEvaluationStatus.NO_DYNAMIC_EVIDENCE
    assert evaluation.baseline is not None
    assert evaluation.latest_candidate is None
    assert evaluation.reason is not None


def test_release_evaluation_curated_conflict_selects_no_latest_version():
    projection = service(
        FakeReader({FRIGATE_ADAPTER_ID: DynamicSourceReadSnapshot(
            source_id=FRIGATE_ADAPTER_ID,
            cache_state=DynamicCacheState.AVAILABLE,
            claims=(evaluated(FRIGATE_ADAPTER_ID, version="0.16.1"),),
        )}),
        curated_provider=CuratedProvider(curated_claim(version="0.15.0")),
    ).get_item_projection("frigate", now=NOW)
    assert projection.conflict_state is ConflictState.CURATED_CONFLICT
    evaluation = projection.release_evaluation
    assert evaluation is not None
    assert evaluation.status is ReleaseEvaluationStatus.CONFLICTED
    assert evaluation.latest_candidate is None
    assert evaluation.reason is not None


def test_release_evaluation_curated_claim_wins_when_item_version_also_present():
    # The explicit curated release claim is the authoritative baseline even when
    # the catalog entry also carries an item.version; item.version must not
    # shadow the curated claim.
    projection = service(
        FakeReader({FRIGATE_ADAPTER_ID: DynamicSourceReadSnapshot(
            source_id=FRIGATE_ADAPTER_ID,
            cache_state=DynamicCacheState.AVAILABLE,
            claims=(evaluated(FRIGATE_ADAPTER_ID, version="0.15.0"),),
        )}),
        curated_provider=CuratedProvider(curated_claim(version="0.15.0")),
        entries=(entry(version="0.14.0"),),
    ).get_item_projection("frigate", now=NOW)
    assert projection.curated.item.version == "0.14.0"
    assert projection.conflict_state is ConflictState.AGREEMENT
    evaluation = projection.release_evaluation
    assert evaluation is not None
    assert evaluation.status is ReleaseEvaluationStatus.UP_TO_DATE
    assert evaluation.baseline == ReleaseEvaluationBaseline(
        version="0.15.0", source=ReleaseEvaluationBaselineSource.CURATED
    )
    assert evaluation.latest_candidate == "0.15.0"


def test_release_evaluation_conflict_beats_stale_dynamic_evidence():
    # Two stale claims that disagree still form a dynamic conflict at the
    # projection level; the conflict must surface as CONFLICTED and must never
    # be masked by the stale-evidence bounded state.
    stale_a = DynamicSourceReadSnapshot(
        source_id="source-a",
        cache_state=DynamicCacheState.AVAILABLE,
        claims=(
            evaluated(
                "source-a",
                version="9.9.9",
                retrieved_at=NOW - timedelta(days=5),
                release_id=1,
            ),
        ),
    )
    stale_b = DynamicSourceReadSnapshot(
        source_id="source-b",
        cache_state=DynamicCacheState.AVAILABLE,
        claims=(
            evaluated(
                "source-b",
                version="8.8.8",
                retrieved_at=NOW - timedelta(days=5),
                release_id=2,
            ),
        ),
    )
    projection = service(
        FakeReader({"source-a": stale_a, "source-b": stale_b}),
        mapping={"frigate": ("source-a", "source-b")},
        entries=(entry(version="0.15.0"),),
    ).get_item_projection("frigate", now=NOW)
    assert projection.conflict_state is ConflictState.DYNAMIC_CONFLICT
    assert all(
        claim.freshness is FreshnessState.STALE for claim in projection.dynamic_claims
    )
    evaluation = projection.release_evaluation
    assert evaluation is not None
    assert evaluation.status is ReleaseEvaluationStatus.CONFLICTED
    assert evaluation.latest_candidate is None
    assert evaluation.reason is not None


def test_release_evaluation_rejects_contradictory_hand_built_payloads():
    # A dynamic-conflict projection is a valid base; the cross-field invariant
    # must reject release_evaluation payloads that contradict the conflict state.
    conflict_a = DynamicSourceReadSnapshot(
        source_id="source-a",
        cache_state=DynamicCacheState.AVAILABLE,
        claims=(evaluated("source-a", version="9.0.0", release_id=1),),
    )
    conflict_b = DynamicSourceReadSnapshot(
        source_id="source-b",
        cache_state=DynamicCacheState.AVAILABLE,
        claims=(evaluated("source-b", version="10.0.0", release_id=2),),
    )
    base = service(
        FakeReader({"source-a": conflict_a, "source-b": conflict_b}),
        mapping={"frigate": ("source-a", "source-b")},
    ).get_item_projection("frigate", now=NOW)
    assert base.conflict_state is ConflictState.DYNAMIC_CONFLICT
    conflict_dump = base.model_dump()
    # The hand-built payload must carry the same code-owned mapping the
    # projection was produced under, so only the cross-field invariant is the
    # thing being rejected (the mapping/conflict-shape checks already pass).
    conflict_context = {"item_source_mapping": {"frigate": ("source-a", "source-b")}}

    item_baseline = ReleaseEvaluationBaseline(
        version="0.15.0", source=ReleaseEvaluationBaselineSource.ITEM_VERSION
    )
    positive = {
        "status": ReleaseEvaluationStatus.UPDATE_AVAILABLE,
        "baseline": item_baseline,
        "latest_candidate": "0.16.0",
        "reason": None,
    }
    conflicted = {
        "status": ReleaseEvaluationStatus.CONFLICTED,
        "baseline": item_baseline,
        "latest_candidate": None,
        "reason": "conflicting release claims",
    }
    # conflict_state is DYNAMIC_CONFLICT here, so only CONFLICTED+null is valid.
    # (Values are typed, not strings, so the only check that can fire is the
    # cross-field invariant itself.)
    for payload in (
        conflict_dump | {"release_evaluation": positive},
        conflict_dump
        | {
            "release_evaluation": {
                **conflicted,
                "latest_candidate": "9.0.0",
            }
        },
    ):
        with pytest.raises(
            ValidationError, match="release_evaluation"
        ):
            DiscoveryMergedItemProjection.model_validate(
                payload, context=conflict_context
            )
    # The matching CONFLICTED+null evaluation is a valid projection.
    DiscoveryMergedItemProjection.model_validate(
        conflict_dump | {"release_evaluation": conflicted},
        context=conflict_context,
    )

    # A NO_DYNAMIC_EVIDENCE projection is a valid base; positive or conflicted
    # payloads that contradict conflict_state NONE are rejected, while the
    # matching bounded state is accepted.
    no_evidence = service(
        FakeReader(
            {FRIGATE_ADAPTER_ID: DynamicSourceReadSnapshot(
                source_id=FRIGATE_ADAPTER_ID,
                cache_state=DynamicCacheState.ABSENT,
            )}
        ),
        entries=(entry(version="0.15.0"),),
    ).get_item_projection("frigate", now=NOW)
    assert no_evidence.conflict_state is ConflictState.NONE
    none_dump = no_evidence.model_dump()
    stale = {
        "status": ReleaseEvaluationStatus.STALE_EVIDENCE,
        "baseline": item_baseline,
        "latest_candidate": None,
        "reason": "latest dynamic release evidence is stale",
    }
    # CONFLICTED requires a CURATED_CONFLICT or DYNAMIC_CONFLICT conflict_state,
    # and a positive status requires a non-null latest_candidate. Both are
    # rejected against the non-conflict NONE state.
    for payload in (
        none_dump | {"release_evaluation": conflicted},
        none_dump
        | {
            "release_evaluation": {
                **positive,
                "status": ReleaseEvaluationStatus.UP_TO_DATE,
                "latest_candidate": None,
            }
        },
    ):
        with pytest.raises(
            ValidationError, match="release_evaluation"
        ):
            DiscoveryMergedItemProjection.model_validate(payload)
    # A well-formed bounded state and a well-formed positive state are both
    # accepted against a non-conflict conflict_state, so the invariant is precise
    # and not over-rejecting.
    DiscoveryMergedItemProjection.model_validate(none_dump | {"release_evaluation": stale})
    DiscoveryMergedItemProjection.model_validate(none_dump | {"release_evaluation": positive})


def test_release_evaluation_baseline_ahead_is_projected_when_fresh_candidate_is_older():
    # A single fresh candidate older than the item baseline projects as
    # BASELINE_AHEAD, selecting the fresh candidate. (The related "a stale high
    # candidate is ignored in selection" behavior is asserted at the pure
    # evaluate_release level, because at the projection level a stale claim that
    # disagrees with the fresh claim is itself a dynamic conflict.)
    fresh = DynamicSourceReadSnapshot(
        source_id="source-fresh",
        cache_state=DynamicCacheState.AVAILABLE,
        claims=(evaluated("source-fresh", version="0.14.0", release_id=1),),
    )
    projection = service(
        FakeReader({"source-fresh": fresh}),
        mapping={"frigate": ("source-fresh",)},
        entries=(entry(version="0.15.0"),),
    ).get_item_projection("frigate", now=NOW)
    assert projection.conflict_state is ConflictState.NONE
    evaluation = projection.release_evaluation
    assert evaluation is not None
    assert evaluation.status is ReleaseEvaluationStatus.BASELINE_AHEAD
    assert evaluation.latest_candidate == "0.14.0"
    assert evaluation.baseline is not None
    assert evaluation.baseline.version == "0.15.0"
    assert evaluation.reason is None
