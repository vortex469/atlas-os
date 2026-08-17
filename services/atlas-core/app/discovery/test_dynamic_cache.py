from __future__ import annotations

import hashlib
import json
import os
import stat
from datetime import UTC, datetime, timedelta
from multiprocessing import Process, Queue
from pathlib import Path
from threading import Thread

import pytest
from pydantic import ValidationError

from app.discovery.dynamic_cache import (
    CACHE_FORMAT,
    GENERATION_FORMAT,
    MAX_FACTS_BYTES,
    MAX_FACTS_PER_GENERATION,
    CachedFactRecord,
    CachedFactsDocument,
    CacheFailureReason,
    CacheFormatMetadata,
    CachePublishStatus,
    CacheReadStatus,
    DiscoveryCacheStore,
    _CacheFault,
    _parse_json,
    canonical_json,
)
from app.discovery.dynamic_sources import (
    DYNAMIC_RELEASE_FACT_SCHEMA,
    FRIGATE_ADAPTER_ID,
    DynamicReleaseFact,
    DynamicSourceProvenance,
)

NOW = datetime(2026, 8, 17, 12, tzinfo=UTC)


def record(
    *, retrieved_at: datetime = NOW, version: str = "0.16.1"
) -> CachedFactRecord:
    return CachedFactRecord(
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


def initialized(tmp_path: Path) -> DiscoveryCacheStore:
    tmp_path.mkdir(mode=0o700, parents=True, exist_ok=True)
    store = DiscoveryCacheStore(tmp_path / "cache")
    store.initialize()
    return store


def publish(store: DiscoveryCacheStore, item: CachedFactRecord | None = None):
    return store.publish(FRIGATE_ADAPTER_ID, (item or record(),))


def current_path(store: DiscoveryCacheStore) -> Path:
    return store.sources_path / FRIGATE_ADAPTER_ID / "current.json"


def generation_path(store: DiscoveryCacheStore) -> Path:
    pointer = json.loads(current_path(store).read_text())
    return (
        store.sources_path
        / FRIGATE_ADAPTER_ID
        / "generations"
        / pointer["generation_id"]
    )


def _process_publish(root: str, offset: int, results: Queue) -> None:
    store = DiscoveryCacheStore(Path(root))
    outcome = publish(store, record(retrieved_at=NOW + timedelta(seconds=offset)))
    results.put((outcome.status.value, outcome.generation_id))


def _process_crash_with_lock(root: str) -> None:
    store = DiscoveryCacheStore(Path(root))

    def crash(phase: str) -> None:
        if phase == "after_incomplete_creation":
            os._exit(17)

    store.publish(
        FRIGATE_ADAPTER_ID,
        (record(retrieved_at=NOW + timedelta(seconds=3)),),
        failure_hook=crash,
    )


def test_constructor_and_import_are_side_effect_free(tmp_path: Path):
    root = tmp_path / "cache"
    DiscoveryCacheStore(root)
    assert not root.exists()


def test_explicit_initialization_has_private_layout_and_is_idempotent(tmp_path: Path):
    store = initialized(tmp_path)
    store.initialize()
    paths = [
        store.root,
        store.sources_path,
        store.sources_path / FRIGATE_ADAPTER_ID,
        store.sources_path / FRIGATE_ADAPTER_ID / "generations",
    ]
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o700 for path in paths)
    files = [
        store.root / "format.json",
        store.sources_path / FRIGATE_ADAPTER_ID / ".lock",
    ]
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in files)


@pytest.mark.parametrize("kind", ["file", "fifo", "world_readable", "world_writable"])
def test_unsafe_existing_root_fails_without_normalization(tmp_path: Path, kind: str):
    root = tmp_path / "cache"
    if kind == "file":
        root.write_text("not a directory")
    elif kind == "fifo":
        os.mkfifo(root)
    else:
        root.mkdir(mode=0o700)
        root.chmod(0o755 if kind == "world_readable" else 0o707)
    original = stat.S_IMODE(os.lstat(root).st_mode)
    with pytest.raises(_CacheFault):
        DiscoveryCacheStore(root).initialize()
    assert stat.S_IMODE(os.lstat(root).st_mode) == original


def test_non_owned_existing_root_fails_closed(tmp_path: Path):
    if os.geteuid() != 0:
        pytest.skip("ownership transition requires root test environment")
    root = tmp_path / "cache"
    root.mkdir(mode=0o700)
    os.chown(root, 12345, 12345)
    with pytest.raises(_CacheFault):
        DiscoveryCacheStore(root).initialize()
    assert os.stat(root).st_uid == 12345


def test_parent_traversal_root_is_rejected(tmp_path: Path):
    (tmp_path / "nested").mkdir(mode=0o700)
    root = tmp_path / "nested" / ".." / "cache"
    with pytest.raises(_CacheFault):
        DiscoveryCacheStore(root).initialize()
    assert not (tmp_path / "cache").exists()


def test_created_modes_remain_private_under_permissive_umask(tmp_path: Path):
    previous = os.umask(0)
    try:
        store = initialized(tmp_path)
        publish(store)
    finally:
        os.umask(previous)
    for path in (store.root, store.sources_path, generation_path(store)):
        assert stat.S_IMODE(path.stat().st_mode) == 0o700
    for path in (
        store.root / "format.json",
        current_path(store),
        generation_path(store) / "facts.json",
    ):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_models_and_canonical_serialization_are_closed_and_deterministic():
    model = CacheFormatMetadata(
        schema_version=CACHE_FORMAT,
        registered_source_ids=(FRIGATE_ADAPTER_ID,),
    )
    assert canonical_json(model) == canonical_json(model)
    assert canonical_json(model).endswith(b"\n")
    with pytest.raises(ValidationError):
        CacheFormatMetadata.model_validate({**model.model_dump(), "unknown": True})
    with pytest.raises(ValidationError):
        CacheFormatMetadata(
            schema_version="wrong",
            registered_source_ids=(FRIGATE_ADAPTER_ID,),
        )
    with pytest.raises(ValueError, match="duplicate JSON key"):
        _parse_json(b'{"schema_version":"x","schema_version":"y"}')


def test_existing_format_must_be_private_single_link_canonical_and_compatible(
    tmp_path: Path,
):
    for case in ("expanded", "duplicate", "wrong_schema", "hard_link"):
        case_root = tmp_path / case
        store = initialized(case_root)
        format_path = store.root / "format.json"
        if case == "expanded":
            format_path.write_text(
                json.dumps(json.loads(format_path.read_text()), indent=2) + "\n"
            )
        elif case == "duplicate":
            format_path.write_text(
                '{"registered_source_ids":[],"schema_version":"atlas-discovery-cache-v1",'
                '"schema_version":"atlas-discovery-cache-v1"}\n'
            )
        elif case == "wrong_schema":
            payload = json.loads(format_path.read_text()) | {"schema_version": "wrong"}
            format_path.write_text(json.dumps(payload) + "\n")
        else:
            os.link(format_path, case_root / "external")
        format_path.chmod(0o600)
        before = format_path.read_bytes()
        with pytest.raises(_CacheFault):
            store.initialize()
        assert format_path.read_bytes() == before


def test_fact_count_and_source_registry_are_bounded():
    with pytest.raises(ValidationError):
        CachedFactsDocument(
            schema_version=GENERATION_FORMAT,
            source_id=FRIGATE_ADAPTER_ID,
            records=tuple(record() for _ in range(MAX_FACTS_PER_GENERATION + 1)),
        )
    with pytest.raises(ValidationError):
        CachedFactsDocument(
            schema_version=GENERATION_FORMAT,
            source_id="external-source",
            records=(record(),),
        )


def test_publish_read_round_trip_and_pointer_is_regular(tmp_path: Path):
    store = initialized(tmp_path)
    result = publish(store)
    assert result.status is CachePublishStatus.PUBLISHED
    read = store.read_current(FRIGATE_ADAPTER_ID)
    assert read.status is CacheReadStatus.AVAILABLE
    assert read.generation is not None
    assert read.generation.records == (record(),)
    assert stat.S_ISREG(os.lstat(current_path(store)).st_mode)
    assert not current_path(store).is_symlink()


def test_generation_identity_is_deterministic_and_retrieval_time_bound(tmp_path: Path):
    first = initialized(tmp_path / "one")
    second = initialized(tmp_path / "two")
    first_id = publish(first).generation_id
    second_id = publish(second).generation_id
    assert first_id == second_id
    changed = publish(first, record(retrieved_at=NOW + timedelta(seconds=1)))
    assert changed.generation_id != first_id


def test_identical_publication_is_noop(tmp_path: Path):
    store = initialized(tmp_path)
    first = publish(store)
    second = publish(store)
    assert first.status is CachePublishStatus.PUBLISHED
    assert second.status is CachePublishStatus.NOOP
    generations = list(
        (store.sources_path / FRIGATE_ADAPTER_ID / "generations").iterdir()
    )
    assert len(generations) == 1


def test_retains_current_and_one_previous(tmp_path: Path):
    store = initialized(tmp_path)
    identifiers = []
    for offset in range(3):
        result = publish(store, record(retrieved_at=NOW + timedelta(seconds=offset)))
        identifiers.append(result.generation_id)
    directories = {
        path.name
        for path in (store.sources_path / FRIGATE_ADAPTER_ID / "generations").iterdir()
        if path.is_dir()
    }
    assert directories == set(identifiers[-2:])
    assert (
        store.read_current(FRIGATE_ADAPTER_ID).generation.metadata.generation_id
        == identifiers[-1]
    )


@pytest.mark.parametrize(
    "phase",
    [
        "after_incomplete_creation",
        "before_facts_write",
        "after_facts_write",
        "after_metadata_write",
        "after_checksums_write",
        "after_incomplete_directory_fsync",
        "after_generation_rename",
        "after_generations_directory_fsync",
        "after_pointer_temp_fsync",
        "before_current_pointer_replace",
    ],
)
def test_pre_pointer_failure_preserves_previous(tmp_path: Path, phase: str):
    store = initialized(tmp_path)
    previous = publish(store).generation_id

    def fail(candidate: str) -> None:
        if candidate == phase:
            raise RuntimeError("injected sensitive failure")

    result = store.publish(
        FRIGATE_ADAPTER_ID,
        (record(retrieved_at=NOW + timedelta(seconds=1)),),
        failure_hook=fail,
    )
    assert result.status is CachePublishStatus.FAILED
    read = store.read_current(FRIGATE_ADAPTER_ID)
    assert read.generation is not None
    assert read.generation.metadata.generation_id == previous


@pytest.mark.parametrize(
    "phase",
    [
        "after_current_pointer_replace",
        "after_source_directory_fsync",
        "during_pruning",
    ],
)
def test_post_pointer_failure_keeps_new_generation(tmp_path: Path, phase: str):
    store = initialized(tmp_path)
    publish(store)

    def fail(candidate: str) -> None:
        if candidate == phase:
            raise RuntimeError("injected sensitive failure")

    result = store.publish(
        FRIGATE_ADAPTER_ID,
        (record(retrieved_at=NOW + timedelta(seconds=1)),),
        failure_hook=fail,
    )
    assert result.status is CachePublishStatus.PUBLISHED
    assert result.maintenance_failed
    assert (
        store.read_current(FRIGATE_ADAPTER_ID).generation.metadata.generation_id
        == result.generation_id
    )


@pytest.mark.parametrize("filename", ["facts.json", "metadata.json", "checksums.json"])
def test_corrupt_or_missing_generation_file_is_isolated(tmp_path: Path, filename: str):
    store = initialized(tmp_path)
    publish(store)
    target = generation_path(store) / filename
    if filename == "checksums.json":
        target.unlink()
    else:
        target.write_bytes(b"corrupt\n")
        target.chmod(0o600)
    result = store.read_current(FRIGATE_ADAPTER_ID)
    assert result.status is CacheReadStatus.CORRUPT
    assert result.generation is None


def test_duplicate_json_and_pointer_digest_mismatch_fail_closed(tmp_path: Path):
    store = initialized(tmp_path)
    publish(store)
    facts = generation_path(store) / "facts.json"
    facts.write_bytes(b'{"schema_version":"x","schema_version":"y"}\n')
    facts.chmod(0o600)
    assert store.read_current(FRIGATE_ADAPTER_ID).status is CacheReadStatus.CORRUPT

    other = initialized(tmp_path / "other")
    publish(other)
    pointer = json.loads(current_path(other).read_text())
    pointer["generation_sha256"] = "0" * 64
    current_path(other).write_text(json.dumps(pointer, separators=(",", ":")) + "\n")
    current_path(other).chmod(0o600)
    assert (
        other.read_current(FRIGATE_ADAPTER_ID).failure_reason
        is CacheFailureReason.CHECKSUM_MISMATCH
    )


def test_semantically_equivalent_noncanonical_pointer_is_rejected(tmp_path: Path):
    store = initialized(tmp_path)
    publish(store)
    pointer = json.loads(current_path(store).read_text())
    current_path(store).write_text(json.dumps(pointer, indent=2) + "\n")
    current_path(store).chmod(0o600)
    result = store.read_current(FRIGATE_ADAPTER_ID)
    assert result.status is CacheReadStatus.CORRUPT
    assert result.failure_reason is CacheFailureReason.MALFORMED


@pytest.mark.parametrize(
    "target", ["format", "current", "metadata", "facts", "checksums"]
)
def test_expected_cache_files_reject_hard_links(tmp_path: Path, target: str):
    store = initialized(tmp_path)
    publish(store)
    generation = generation_path(store)
    paths = {
        "format": store.root / "format.json",
        "current": current_path(store),
        "metadata": generation / "metadata.json",
        "facts": generation / "facts.json",
        "checksums": generation / "checksums.json",
    }
    os.link(paths[target], tmp_path / f"external-{target}")
    if target == "format":
        with pytest.raises(_CacheFault):
            store.initialize()
    else:
        assert store.read_current(FRIGATE_ADAPTER_ID).status is CacheReadStatus.CORRUPT


def test_oversized_file_rejected_before_read(tmp_path: Path):
    store = initialized(tmp_path)
    publish(store)
    facts = generation_path(store) / "facts.json"
    with facts.open("wb") as stream:
        stream.truncate(MAX_FACTS_BYTES + 1)
    facts.chmod(0o600)
    result = store.read_current(FRIGATE_ADAPTER_ID)
    assert result.failure_reason is CacheFailureReason.SIZE_EXCEEDED


@pytest.mark.parametrize(
    "target_kind", ["root", "source", "generation", "file", "pointer"]
)
def test_symlinks_fail_closed(tmp_path: Path, target_kind: str):
    if target_kind == "root":
        real = tmp_path / "real"
        real.mkdir(mode=0o700)
        root = tmp_path / "cache"
        root.symlink_to(real, target_is_directory=True)
        with pytest.raises(_CacheFault):
            DiscoveryCacheStore(root).initialize()
        return

    store = initialized(tmp_path)
    publish(store)
    source = store.sources_path / FRIGATE_ADAPTER_ID
    generation = generation_path(store)
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    if target_kind == "source":
        for path in sorted(source.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        source.rmdir()
        source.symlink_to(outside, target_is_directory=True)
    elif target_kind == "generation":
        for path in generation.iterdir():
            path.unlink()
        generation.rmdir()
        generation.symlink_to(outside, target_is_directory=True)
    elif target_kind == "file":
        target = generation / "facts.json"
        target.unlink()
        target.symlink_to(current_path(store))
    else:
        target = current_path(store)
        target.unlink()
        target.symlink_to(outside / "pointer")
    assert store.read_current(FRIGATE_ADAPTER_ID).status is CacheReadStatus.CORRUPT


def test_fifo_and_hard_link_fail_closed(tmp_path: Path):
    store = initialized(tmp_path)
    publish(store)
    facts = generation_path(store) / "facts.json"
    facts.unlink()
    os.mkfifo(facts, mode=0o600)
    assert store.read_current(FRIGATE_ADAPTER_ID).status is CacheReadStatus.CORRUPT
    facts.unlink()

    other = tmp_path / "linked"
    other.write_bytes(b"external")
    other.chmod(0o600)
    os.link(other, facts)
    assert (
        store.read_current(FRIGATE_ADAPTER_ID).failure_reason
        is CacheFailureReason.UNSAFE_FILESYSTEM
    )
    assert other.read_bytes() == b"external"


def test_unsafe_permissions_fail_closed(tmp_path: Path):
    store = initialized(tmp_path)
    publish(store)
    current_path(store).chmod(0o640)
    assert (
        store.read_current(FRIGATE_ADAPTER_ID).failure_reason
        is CacheFailureReason.UNSAFE_FILESYSTEM
    )


def test_traversal_and_source_mismatch_pointer_fail_closed(tmp_path: Path):
    store = initialized(tmp_path)
    publish(store)
    pointer = json.loads(current_path(store).read_text())
    for update in (
        {"generation_id": "../outside"},
        {"source_id": "external-source"},
    ):
        current_path(store).write_text(json.dumps(pointer | update) + "\n")
        current_path(store).chmod(0o600)
        assert store.read_current(FRIGATE_ADAPTER_ID).status is CacheReadStatus.CORRUPT


def test_generation_and_metadata_source_mismatches_fail_closed(tmp_path: Path):
    store = initialized(tmp_path)
    publish(store)
    original = generation_path(store)
    pointer = json.loads(current_path(store).read_text())
    renamed_id = f"g-20260101T000000000000Z-{'b' * 64}"
    renamed = original.parent / renamed_id
    original.rename(renamed)
    current_path(store).write_text(
        json.dumps(pointer | {"generation_id": renamed_id}, separators=(",", ":"))
        + "\n"
    )
    current_path(store).chmod(0o600)
    assert store.read_current(FRIGATE_ADAPTER_ID).status is CacheReadStatus.CORRUPT

    other = initialized(tmp_path / "other")
    publish(other)
    generation = generation_path(other)
    metadata_path = generation / "metadata.json"
    facts_path = generation / "facts.json"
    checksums_path = generation / "checksums.json"
    metadata = json.loads(metadata_path.read_text()) | {"source_id": "external-source"}
    metadata_bytes = (
        json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    checksums = json.loads(checksums_path.read_text()) | {
        "metadata_sha256": hashlib.sha256(metadata_bytes).hexdigest()
    }
    checksums_bytes = (
        json.dumps(checksums, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    metadata_path.write_bytes(metadata_bytes)
    checksums_path.write_bytes(checksums_bytes)
    pointer = json.loads(current_path(other).read_text()) | {
        "generation_sha256": hashlib.sha256(
            metadata_bytes + facts_path.read_bytes() + checksums_bytes
        ).hexdigest()
    }
    current_path(other).write_text(
        json.dumps(pointer, sort_keys=True, separators=(",", ":")) + "\n"
    )
    for path in (metadata_path, checksums_path, current_path(other)):
        path.chmod(0o600)
    assert other.read_current(FRIGATE_ADAPTER_ID).status is CacheReadStatus.CORRUPT


def test_lock_symlink_and_unregistered_source_fail_closed(tmp_path: Path):
    store = initialized(tmp_path)
    lock = store.sources_path / FRIGATE_ADAPTER_ID / ".lock"
    lock.unlink()
    lock.symlink_to(tmp_path / "outside")
    assert store.read_current(FRIGATE_ADAPTER_ID).status is CacheReadStatus.CORRUPT
    result = store.publish("external-source", (record(),))
    assert result.failure_reason is CacheFailureReason.SOURCE_UNREGISTERED


def test_reader_never_leaks_raw_internal_exception(monkeypatch, tmp_path: Path):
    store = initialized(tmp_path)

    def fail(source_id: str):
        raise OSError("/secret/path?token=credential raw-json")

    monkeypatch.setattr(store, "_read_current_locked", fail)
    result = store.read_current(FRIGATE_ADAPTER_ID)
    serialized = result.model_dump_json()
    assert result.failure_reason is CacheFailureReason.IO_FAILED
    assert "secret" not in serialized
    assert "credential" not in serialized


def test_generation_collision_is_not_overwritten(tmp_path: Path):
    reference = initialized(tmp_path / "reference")
    generation_id = publish(reference).generation_id
    assert generation_id is not None
    store = initialized(tmp_path / "target")
    collision = store.sources_path / FRIGATE_ADAPTER_ID / "generations" / generation_id
    collision.mkdir(mode=0o700)
    marker = collision / "unknown"
    marker.write_text("preserve")
    result = publish(store)
    assert result.status is CachePublishStatus.FAILED
    assert marker.read_text() == "preserve"


def test_incomplete_cleanup_is_exact_and_preserves_unknown_objects(tmp_path: Path):
    store = initialized(tmp_path)
    publish_result = publish(store)
    generations = store.sources_path / FRIGATE_ADAPTER_ID / "generations"
    incomplete = generations / f".{publish_result.generation_id}.incomplete-{'a' * 24}"
    incomplete.mkdir(mode=0o700)
    (incomplete / "partial").write_text("x")
    unknown = generations / ".unknown.incomplete"
    unknown.mkdir(mode=0o700)
    store.initialize()
    assert not incomplete.exists()
    assert unknown.exists()


def test_nested_symlink_in_incomplete_is_not_followed_or_deleted(tmp_path: Path):
    store = initialized(tmp_path)
    reference = publish(store)
    generations = store.sources_path / FRIGATE_ADAPTER_ID / "generations"
    incomplete = generations / f".{reference.generation_id}.incomplete-{'b' * 24}"
    incomplete.mkdir(mode=0o700)
    external = tmp_path / "external"
    external.write_text("preserve")
    (incomplete / "nested").symlink_to(external)
    with pytest.raises(_CacheFault):
        store.initialize()
    assert external.read_text() == "preserve"
    assert incomplete.exists()


def test_unknown_malformed_published_generation_is_not_pruned(tmp_path: Path):
    store = initialized(tmp_path)
    publish(store)
    generations = store.sources_path / FRIGATE_ADAPTER_ID / "generations"
    unknown = generations / f"g-20260101T000000000000Z-{'a' * 64}"
    unknown.mkdir(mode=0o700)
    publish(store, record(retrieved_at=NOW + timedelta(seconds=1)))
    assert unknown.exists()


def test_simultaneous_publication_is_serialized_and_valid(tmp_path: Path):
    store = initialized(tmp_path)
    results = []

    def worker(offset: int) -> None:
        results.append(
            publish(store, record(retrieved_at=NOW + timedelta(seconds=offset)))
        )

    threads = [Thread(target=worker, args=(offset,)) for offset in range(1, 3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert all(
        result.status in {CachePublishStatus.PUBLISHED, CachePublishStatus.NOOP}
        for result in results
    )
    current = store.read_current(FRIGATE_ADAPTER_ID)
    assert current.status is CacheReadStatus.AVAILABLE
    assert current.generation is not None
    assert current.generation.metadata.retrieved_at == NOW + timedelta(seconds=2)
    generations = store.sources_path / FRIGATE_ADAPTER_ID / "generations"
    assert len([path for path in generations.iterdir() if path.is_dir()]) <= 2


def test_multi_process_publication_and_crash_release_kernel_lock(tmp_path: Path):
    store = initialized(tmp_path)
    results: Queue = Queue()
    processes = [
        Process(target=_process_publish, args=(str(store.root), offset, results))
        for offset in (1, 2)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0
    outcomes = [results.get(timeout=2) for _ in processes]
    assert all(status in {"published", "noop"} for status, _ in outcomes)
    current = store.read_current(FRIGATE_ADAPTER_ID)
    assert current.generation is not None
    assert current.generation.metadata.retrieved_at == NOW + timedelta(seconds=2)

    crashing = Process(target=_process_crash_with_lock, args=(str(store.root),))
    crashing.start()
    crashing.join(timeout=10)
    assert crashing.exitcode == 17
    store.initialize()
    recovered = publish(store, record(retrieved_at=NOW + timedelta(seconds=4)))
    assert recovered.status is CachePublishStatus.PUBLISHED


def test_reader_publisher_overlap_never_observes_partial_pointer(tmp_path: Path):
    store = initialized(tmp_path)
    publish(store)
    observations = []

    def reader() -> None:
        for _ in range(50):
            observations.append(store.read_current(FRIGATE_ADAPTER_ID).status)

    thread = Thread(target=reader)
    thread.start()
    for offset in range(1, 6):
        publish(store, record(retrieved_at=NOW + timedelta(seconds=offset)))
    thread.join()
    assert observations
    assert set(observations) == {CacheReadStatus.AVAILABLE}


def test_corrupt_current_is_not_silently_repaired_by_publication(tmp_path: Path):
    store = initialized(tmp_path)
    publish(store)
    current_path(store).write_bytes(b"{broken\n")
    current_path(store).chmod(0o600)
    result = publish(store, record(retrieved_at=NOW + timedelta(seconds=1)))
    assert result.status is CachePublishStatus.FAILED
    assert current_path(store).read_bytes() == b"{broken\n"


def test_unreferenced_complete_orphan_is_not_retained_as_previous(tmp_path: Path):
    store = initialized(tmp_path)
    previous = publish(store).generation_id

    def fail_after_rename(phase: str) -> None:
        if phase == "after_generation_rename":
            raise RuntimeError("injected")

    failed = store.publish(
        FRIGATE_ADAPTER_ID,
        (record(retrieved_at=NOW + timedelta(seconds=20)),),
        failure_hook=fail_after_rename,
    )
    assert failed.status is CachePublishStatus.FAILED
    reopened = DiscoveryCacheStore(store.root)
    reopened.initialize()
    reopened_current = reopened.read_current(FRIGATE_ADAPTER_ID)
    assert reopened_current.generation is not None
    assert reopened_current.generation.metadata.generation_id == previous
    published = publish(reopened, record(retrieved_at=NOW + timedelta(seconds=10)))
    generations = store.sources_path / FRIGATE_ADAPTER_ID / "generations"
    identifiers = {path.name for path in generations.iterdir() if path.is_dir()}
    assert identifiers == {previous, published.generation_id}
