"""Inactive, rebuildable D10 cache generation store.

This module has no application wiring. Constructing a store performs no I/O;
callers must explicitly initialize a caller-supplied disposable or runtime root.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.discovery.dynamic_sources import (
    FRIGATE_ADAPTER_ID,
    DynamicReleaseFact,
    DynamicSourceProvenance,
)
from app.discovery.models import DISCOVERY_ID_PATTERN

CACHE_FORMAT = "atlas-discovery-cache-v1"
GENERATION_FORMAT = "atlas-discovery-generation-v1"
REGISTERED_SOURCE_IDS = (FRIGATE_ADAPTER_ID,)
MAX_REGISTERED_SOURCES = 16
MAX_GENERATIONS_PER_SOURCE = 2
MAX_FACTS_PER_GENERATION = 32
MAX_RECORD_BYTES = 64 * 1024
MAX_FACTS_BYTES = 128 * 1024
MAX_METADATA_BYTES = 16 * 1024
MAX_CHECKSUMS_BYTES = 8 * 1024
MAX_CURRENT_BYTES = 4 * 1024
MAX_GENERATION_BYTES = 192 * 1024

_DIGEST_PATTERN = r"^[a-f0-9]{64}$"
_GENERATION_PATTERN = re.compile(r"^g-\d{8}T\d{12}Z-[a-f0-9]{64}$")
_INCOMPLETE_PATTERN = re.compile(
    r"^\.g-\d{8}T\d{12}Z-[a-f0-9]{64}\.incomplete-[a-f0-9]{24}$"
)
_POINTER_TEMP_PATTERN = re.compile(r"^\.current\.json\.tmp-[a-f0-9]{24}$")
_DIRECTORY_MODE = 0o700
_FILE_MODE = 0o600
_EXPECTED_GENERATION_FILES = frozenset(
    {"metadata.json", "facts.json", "checksums.json"}
)


class CacheModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class CacheFormatMetadata(CacheModel):
    schema_version: Literal["atlas-discovery-cache-v1"]
    registered_source_ids: tuple[str, ...] = Field(
        min_length=1, max_length=MAX_REGISTERED_SOURCES
    )

    @field_validator("registered_source_ids")
    @classmethod
    def validate_registered_sources(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("registered source IDs must be unique and sorted")
        if value != tuple(sorted(REGISTERED_SOURCE_IDS)):
            raise ValueError("cache source registry must match code-owned sources")
        if any(
            re.fullmatch(DISCOVERY_ID_PATTERN, source_id) is None for source_id in value
        ):
            raise ValueError("registered source ID is not canonical")
        return value


class CachedFactRecord(CacheModel):
    fact: DynamicReleaseFact
    provenance: DynamicSourceProvenance

    @model_validator(mode="after")
    def validate_identity(self) -> CachedFactRecord:
        if self.provenance.source_id not in REGISTERED_SOURCE_IDS:
            raise ValueError("fact provenance source is not registered")
        return self


class CachedFactsDocument(CacheModel):
    schema_version: Literal["atlas-discovery-generation-v1"]
    source_id: str = Field(pattern=DISCOVERY_ID_PATTERN)
    records: tuple[CachedFactRecord, ...] = Field(max_length=MAX_FACTS_PER_GENERATION)

    @model_validator(mode="after")
    def validate_records(self) -> CachedFactsDocument:
        if self.source_id not in REGISTERED_SOURCE_IDS:
            raise ValueError("source is not registered")
        if not self.records:
            raise ValueError("a cache generation requires at least one fact")
        if any(
            record.provenance.source_id != self.source_id for record in self.records
        ):
            raise ValueError("record provenance does not match source")
        retrieved = {record.provenance.retrieved_at for record in self.records}
        if len(retrieved) != 1:
            raise ValueError("generation records must share one retrieval timestamp")
        keys = [
            (record.fact.catalog_item_id, record.fact.fact_kind)
            for record in self.records
        ]
        if keys != sorted(set(keys)):
            raise ValueError("generation fact keys must be unique and sorted")
        return self


class GenerationMetadata(CacheModel):
    cache_schema_version: Literal["atlas-discovery-cache-v1"]
    schema_version: Literal["atlas-discovery-generation-v1"]
    source_id: str = Field(pattern=DISCOVERY_ID_PATTERN)
    generation_id: str
    canonical_content_sha256: str = Field(pattern=_DIGEST_PATTERN)
    retrieved_at: datetime
    fact_count: int = Field(ge=1, le=MAX_FACTS_PER_GENERATION)

    @field_validator("generation_id")
    @classmethod
    def validate_generation_id(cls, value: str) -> str:
        if _GENERATION_PATTERN.fullmatch(value) is None:
            raise ValueError("generation ID is not canonical")
        return value

    @field_validator("retrieved_at")
    @classmethod
    def validate_retrieved_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return value.astimezone(UTC)


class GenerationChecksums(CacheModel):
    schema_version: Literal["atlas-discovery-generation-v1"]
    metadata_sha256: str = Field(pattern=_DIGEST_PATTERN)
    facts_sha256: str = Field(pattern=_DIGEST_PATTERN)


class CurrentGenerationPointer(CacheModel):
    schema_version: Literal["atlas-discovery-cache-v1"]
    source_id: str = Field(pattern=DISCOVERY_ID_PATTERN)
    generation_id: str
    generation_sha256: str = Field(pattern=_DIGEST_PATTERN)

    @field_validator("generation_id")
    @classmethod
    def validate_generation_id(cls, value: str) -> str:
        if _GENERATION_PATTERN.fullmatch(value) is None:
            raise ValueError("generation ID is not canonical")
        return value


class ValidatedCacheGeneration(CacheModel):
    metadata: GenerationMetadata
    records: tuple[CachedFactRecord, ...]
    checksums: GenerationChecksums
    generation_sha256: str = Field(pattern=_DIGEST_PATTERN)


class CacheReadStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    CORRUPT = "corrupt"


class CacheFailureReason(StrEnum):
    NOT_INITIALIZED = "not_initialized"
    SOURCE_UNREGISTERED = "source_unregistered"
    CURRENT_MISSING = "current_missing"
    LOCK_FAILED = "lock_failed"
    UNSAFE_FILESYSTEM = "unsafe_filesystem"
    MALFORMED = "malformed"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    SIZE_EXCEEDED = "size_exceeded"
    IO_FAILED = "io_failed"
    PUBLICATION_FAILED = "publication_failed"


class CacheReadResult(CacheModel):
    status: CacheReadStatus
    generation: ValidatedCacheGeneration | None = None
    failure_reason: CacheFailureReason | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> CacheReadResult:
        available = self.status is CacheReadStatus.AVAILABLE
        if available != (self.generation is not None):
            raise ValueError("available reads require a generation")
        if available == (self.failure_reason is not None):
            raise ValueError("unavailable reads require a controlled reason")
        return self


class CachePublishStatus(StrEnum):
    PUBLISHED = "published"
    NOOP = "noop"
    FAILED = "failed"


class CachePublishResult(CacheModel):
    status: CachePublishStatus
    generation_id: str | None = None
    failure_reason: CacheFailureReason | None = None
    maintenance_failed: bool = False

    @model_validator(mode="after")
    def validate_shape(self) -> CachePublishResult:
        succeeded = self.status in {
            CachePublishStatus.PUBLISHED,
            CachePublishStatus.NOOP,
        }
        if succeeded != (self.generation_id is not None):
            raise ValueError("successful publication requires a generation ID")
        if succeeded == (self.failure_reason is not None):
            raise ValueError("failed publication requires a controlled reason")
        if self.maintenance_failed and self.status is not CachePublishStatus.PUBLISHED:
            raise ValueError("maintenance failure requires a published generation")
        return self


FailureHook = Callable[[str], None]


class _CacheFault(RuntimeError):
    def __init__(self, reason: CacheFailureReason) -> None:
        self.reason = reason
        super().__init__(reason.value)


def canonical_json(model: BaseModel) -> bytes:
    payload = model.model_dump(mode="json")
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _parse_json(value: bytes) -> Any:
    return json.loads(value.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs)


class DiscoveryCacheStore:
    """Explicit, inactive cache store for registered normalized sources."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    @property
    def sources_path(self) -> Path:
        return self.root / "sources"

    def initialize(self) -> None:
        try:
            self._initialize()
        except _CacheFault:
            raise
        except (OSError, ValueError, ValidationError) as exc:
            raise _CacheFault(CacheFailureReason.UNSAFE_FILESYSTEM) from exc

    def _initialize(self) -> None:
        if self.root.exists() or self.root.is_symlink():
            self._require_directory(self.root)
        else:
            parent = self.root.parent
            self._require_directory(parent)
            if parent.resolve() != parent.absolute():
                raise _CacheFault(CacheFailureReason.UNSAFE_FILESYSTEM)
            self._mkdir_private(parent, self.root.name)
        os.chmod(self.root, _DIRECTORY_MODE)
        self._ensure_private_directory(self.sources_path)

        format_path = self.root / "format.json"
        expected = CacheFormatMetadata(
            schema_version=CACHE_FORMAT,
            registered_source_ids=tuple(sorted(REGISTERED_SOURCE_IDS)),
        )
        if format_path.exists() or format_path.is_symlink():
            actual = self._read_model(
                format_path, MAX_METADATA_BYTES, CacheFormatMetadata
            )
            if actual != expected:
                raise _CacheFault(CacheFailureReason.MALFORMED)
        else:
            self._write_new_file(format_path, canonical_json(expected))
            self._fsync_directory(self.root)

        for source_id in REGISTERED_SOURCE_IDS:
            source_path = self.sources_path / source_id
            self._ensure_private_directory(source_path)
            self._ensure_private_directory(source_path / "generations")
            self._ensure_lock_file(source_path / ".lock")
            with self._source_lock(source_id, exclusive=True):
                self._cleanup_incomplete(source_id)

    def publish(
        self,
        source_id: str,
        records: tuple[CachedFactRecord, ...],
        *,
        failure_hook: FailureHook | None = None,
    ) -> CachePublishResult:
        if source_id not in REGISTERED_SOURCE_IDS:
            return CachePublishResult(
                status=CachePublishStatus.FAILED,
                failure_reason=CacheFailureReason.SOURCE_UNREGISTERED,
            )
        pointer_published = False
        generation_id: str | None = None
        incomplete: Path | None = None
        pointer_temp: Path | None = None
        try:
            self._validate_initialized()
            document = CachedFactsDocument(
                schema_version=GENERATION_FORMAT,
                source_id=source_id,
                records=records,
            )
            facts_bytes = canonical_json(document)
            self._validate_document_bounds(document, facts_bytes)
            identity = {
                "cache_schema_version": CACHE_FORMAT,
                "generation_schema_version": GENERATION_FORMAT,
                "source_id": source_id,
                "facts": document.model_dump(mode="json"),
            }
            identity_bytes = (
                json.dumps(
                    identity, sort_keys=True, separators=(",", ":"), allow_nan=False
                )
                + "\n"
            ).encode()
            content_digest = _sha256(identity_bytes)
            retrieved_at = records[0].provenance.retrieved_at.astimezone(UTC)
            stamp = retrieved_at.strftime("%Y%m%dT%H%M%S%fZ")
            generation_id = f"g-{stamp}-{content_digest}"
            metadata = GenerationMetadata(
                cache_schema_version=CACHE_FORMAT,
                schema_version=GENERATION_FORMAT,
                source_id=source_id,
                generation_id=generation_id,
                canonical_content_sha256=content_digest,
                retrieved_at=retrieved_at,
                fact_count=len(records),
            )
            metadata_bytes = canonical_json(metadata)
            checksums = GenerationChecksums(
                schema_version=GENERATION_FORMAT,
                metadata_sha256=_sha256(metadata_bytes),
                facts_sha256=_sha256(facts_bytes),
            )
            checksums_bytes = canonical_json(checksums)
            self._validate_generation_sizes(
                metadata_bytes, facts_bytes, checksums_bytes
            )
            generation_digest = _sha256(metadata_bytes + facts_bytes + checksums_bytes)
            pointer = CurrentGenerationPointer(
                schema_version=CACHE_FORMAT,
                source_id=source_id,
                generation_id=generation_id,
                generation_sha256=generation_digest,
            )
            pointer_bytes = canonical_json(pointer)
            if len(pointer_bytes) > MAX_CURRENT_BYTES:
                raise _CacheFault(CacheFailureReason.SIZE_EXCEEDED)

            with self._source_lock(source_id, exclusive=True):
                current = self._read_current_locked(source_id)
                if current.status is CacheReadStatus.CORRUPT:
                    return CachePublishResult(
                        status=CachePublishStatus.FAILED,
                        failure_reason=current.failure_reason
                        or CacheFailureReason.MALFORMED,
                    )
                if (
                    current.status is CacheReadStatus.AVAILABLE
                    and current.generation is not None
                    and current.generation.metadata.generation_id == generation_id
                    and current.generation.generation_sha256 == generation_digest
                ):
                    return CachePublishResult(
                        status=CachePublishStatus.NOOP, generation_id=generation_id
                    )
                if (
                    current.status is CacheReadStatus.AVAILABLE
                    and current.generation is not None
                    and (
                        retrieved_at,
                        generation_id,
                    )
                    < (
                        current.generation.metadata.retrieved_at,
                        current.generation.metadata.generation_id,
                    )
                ):
                    return CachePublishResult(
                        status=CachePublishStatus.NOOP,
                        generation_id=current.generation.metadata.generation_id,
                    )
                previous_id = (
                    current.generation.metadata.generation_id
                    if current.status is CacheReadStatus.AVAILABLE
                    and current.generation is not None
                    else None
                )

                generations = self._generations_path(source_id)
                nonce = secrets.token_hex(12)
                incomplete = generations / f".{generation_id}.incomplete-{nonce}"
                self._mkdir_private(generations, incomplete.name)
                self._hook(failure_hook, "after_incomplete_creation")
                self._hook(failure_hook, "before_facts_write")
                self._write_new_file(incomplete / "facts.json", facts_bytes)
                self._hook(failure_hook, "after_facts_write")
                self._write_new_file(incomplete / "metadata.json", metadata_bytes)
                self._hook(failure_hook, "after_metadata_write")
                self._write_new_file(incomplete / "checksums.json", checksums_bytes)
                self._hook(failure_hook, "after_checksums_write")
                self._fsync_directory(incomplete)
                self._hook(failure_hook, "after_incomplete_directory_fsync")

                final_path = generations / generation_id
                if final_path.exists() or final_path.is_symlink():
                    existing = self._read_generation(source_id, generation_id)
                    if existing.generation_sha256 != generation_digest:
                        raise _CacheFault(CacheFailureReason.PUBLICATION_FAILED)
                    self._remove_incomplete(incomplete)
                    incomplete = None
                else:
                    self._rename_within(generations, incomplete.name, final_path.name)
                    incomplete = None
                self._hook(failure_hook, "after_generation_rename")
                self._fsync_directory(generations)
                self._hook(failure_hook, "after_generations_directory_fsync")

                pointer_temp = (
                    self._source_path(source_id) / f".current.json.tmp-{nonce}"
                )
                self._write_new_file(pointer_temp, pointer_bytes)
                self._hook(failure_hook, "after_pointer_temp_fsync")
                self._hook(failure_hook, "before_current_pointer_replace")
                self._replace_within(
                    self._source_path(source_id), pointer_temp.name, "current.json"
                )
                pointer_temp = None
                pointer_published = True
                self._hook(failure_hook, "after_current_pointer_replace")
                self._fsync_directory(self._source_path(source_id))
                self._hook(failure_hook, "after_source_directory_fsync")
                try:
                    self._hook(failure_hook, "during_pruning")
                    self._prune(source_id, generation_id, previous_id)
                    self._fsync_directory(generations)
                except Exception:  # noqa: BLE001 - bounded maintenance boundary
                    return CachePublishResult(
                        status=CachePublishStatus.PUBLISHED,
                        generation_id=generation_id,
                        maintenance_failed=True,
                    )
            return CachePublishResult(
                status=CachePublishStatus.PUBLISHED, generation_id=generation_id
            )
        except _CacheFault as exc:
            if pointer_published and generation_id is not None:
                return CachePublishResult(
                    status=CachePublishStatus.PUBLISHED,
                    generation_id=generation_id,
                    maintenance_failed=True,
                )
            return CachePublishResult(
                status=CachePublishStatus.FAILED, failure_reason=exc.reason
            )
        except Exception:  # noqa: BLE001 - filesystem and injected failure boundary
            if pointer_published and generation_id is not None:
                return CachePublishResult(
                    status=CachePublishStatus.PUBLISHED,
                    generation_id=generation_id,
                    maintenance_failed=True,
                )
            return CachePublishResult(
                status=CachePublishStatus.FAILED,
                failure_reason=CacheFailureReason.PUBLICATION_FAILED,
            )
        finally:
            if incomplete is not None:
                self._best_effort_remove_incomplete(incomplete)
            if pointer_temp is not None:
                self._best_effort_unlink(pointer_temp)

    def read_current(self, source_id: str) -> CacheReadResult:
        if source_id not in REGISTERED_SOURCE_IDS:
            return CacheReadResult(
                status=CacheReadStatus.UNAVAILABLE,
                failure_reason=CacheFailureReason.SOURCE_UNREGISTERED,
            )
        try:
            self._validate_initialized()
            with self._source_lock(source_id, exclusive=False):
                return self._read_current_locked(source_id)
        except _CacheFault as exc:
            return CacheReadResult(
                status=CacheReadStatus.CORRUPT,
                failure_reason=exc.reason,
            )
        except Exception:  # noqa: BLE001 - bounded reader boundary
            return CacheReadResult(
                status=CacheReadStatus.CORRUPT,
                failure_reason=CacheFailureReason.IO_FAILED,
            )

    def _read_current_locked(self, source_id: str) -> CacheReadResult:
        pointer_path = self._source_path(source_id) / "current.json"
        if not pointer_path.exists() and not pointer_path.is_symlink():
            return CacheReadResult(
                status=CacheReadStatus.UNAVAILABLE,
                failure_reason=CacheFailureReason.CURRENT_MISSING,
            )
        try:
            pointer = self._read_model(
                pointer_path, MAX_CURRENT_BYTES, CurrentGenerationPointer
            )
            if pointer.source_id != source_id:
                raise _CacheFault(CacheFailureReason.MALFORMED)
            generation = self._read_generation(source_id, pointer.generation_id)
            if generation.generation_sha256 != pointer.generation_sha256:
                raise _CacheFault(CacheFailureReason.CHECKSUM_MISMATCH)
            return CacheReadResult(
                status=CacheReadStatus.AVAILABLE, generation=generation
            )
        except _CacheFault as exc:
            return CacheReadResult(
                status=CacheReadStatus.CORRUPT, failure_reason=exc.reason
            )
        except (OSError, ValueError, ValidationError, UnicodeError):
            return CacheReadResult(
                status=CacheReadStatus.CORRUPT,
                failure_reason=CacheFailureReason.MALFORMED,
            )

    def _read_generation(
        self, source_id: str, generation_id: str
    ) -> ValidatedCacheGeneration:
        if _GENERATION_PATTERN.fullmatch(generation_id) is None:
            raise _CacheFault(CacheFailureReason.MALFORMED)
        generations = self._generations_path(source_id)
        generation_path = generations / generation_id
        if generation_path.parent != generations:
            raise _CacheFault(CacheFailureReason.UNSAFE_FILESYSTEM)
        self._require_directory(generation_path)
        entries = {entry.name for entry in os.scandir(generation_path)}
        if entries != _EXPECTED_GENERATION_FILES:
            raise _CacheFault(CacheFailureReason.MALFORMED)

        metadata_bytes = self._read_bounded_file(
            generation_path / "metadata.json", MAX_METADATA_BYTES
        )
        facts_bytes = self._read_bounded_file(
            generation_path / "facts.json", MAX_FACTS_BYTES
        )
        checksums_bytes = self._read_bounded_file(
            generation_path / "checksums.json", MAX_CHECKSUMS_BYTES
        )
        self._validate_generation_sizes(metadata_bytes, facts_bytes, checksums_bytes)
        checksums = self._validate_json_model(checksums_bytes, GenerationChecksums)
        if checksums.metadata_sha256 != _sha256(metadata_bytes):
            raise _CacheFault(CacheFailureReason.CHECKSUM_MISMATCH)
        if checksums.facts_sha256 != _sha256(facts_bytes):
            raise _CacheFault(CacheFailureReason.CHECKSUM_MISMATCH)

        metadata = self._validate_json_model(metadata_bytes, GenerationMetadata)
        if metadata.source_id != source_id or metadata.generation_id != generation_id:
            raise _CacheFault(CacheFailureReason.MALFORMED)
        document = self._validate_json_model(facts_bytes, CachedFactsDocument)
        if document.source_id != source_id or metadata.fact_count != len(
            document.records
        ):
            raise _CacheFault(CacheFailureReason.MALFORMED)
        self._validate_document_bounds(document, facts_bytes)
        identity = {
            "cache_schema_version": CACHE_FORMAT,
            "generation_schema_version": GENERATION_FORMAT,
            "source_id": source_id,
            "facts": document.model_dump(mode="json"),
        }
        identity_bytes = (
            json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False)
            + "\n"
        ).encode()
        content_digest = _sha256(identity_bytes)
        expected_stamp = (
            document.records[0]
            .provenance.retrieved_at.astimezone(UTC)
            .strftime("%Y%m%dT%H%M%S%fZ")
        )
        if metadata.canonical_content_sha256 != content_digest:
            raise _CacheFault(CacheFailureReason.CHECKSUM_MISMATCH)
        if generation_id != f"g-{expected_stamp}-{content_digest}":
            raise _CacheFault(CacheFailureReason.MALFORMED)
        if metadata.retrieved_at != document.records[0].provenance.retrieved_at:
            raise _CacheFault(CacheFailureReason.MALFORMED)
        generation_digest = _sha256(metadata_bytes + facts_bytes + checksums_bytes)
        return ValidatedCacheGeneration(
            metadata=metadata,
            records=document.records,
            checksums=checksums,
            generation_sha256=generation_digest,
        )

    def _validate_document_bounds(
        self, document: CachedFactsDocument, facts_bytes: bytes
    ) -> None:
        if len(facts_bytes) > MAX_FACTS_BYTES:
            raise _CacheFault(CacheFailureReason.SIZE_EXCEEDED)
        for record in document.records:
            if len(canonical_json(record)) > MAX_RECORD_BYTES:
                raise _CacheFault(CacheFailureReason.SIZE_EXCEEDED)

    @staticmethod
    def _validate_generation_sizes(
        metadata: bytes, facts: bytes, checksums: bytes
    ) -> None:
        if (
            len(metadata) > MAX_METADATA_BYTES
            or len(facts) > MAX_FACTS_BYTES
            or len(checksums) > MAX_CHECKSUMS_BYTES
            or len(metadata) + len(facts) + len(checksums) > MAX_GENERATION_BYTES
        ):
            raise _CacheFault(CacheFailureReason.SIZE_EXCEEDED)

    def _validate_initialized(self) -> None:
        self._require_directory(self.root)
        self._require_directory(self.sources_path)
        expected = CacheFormatMetadata(
            schema_version=CACHE_FORMAT,
            registered_source_ids=tuple(sorted(REGISTERED_SOURCE_IDS)),
        )
        actual = self._read_model(
            self.root / "format.json", MAX_METADATA_BYTES, CacheFormatMetadata
        )
        if actual != expected:
            raise _CacheFault(CacheFailureReason.NOT_INITIALIZED)

    @contextmanager
    def _source_lock(self, source_id: str, *, exclusive: bool) -> Iterator[None]:
        source_path = self._source_path(source_id)
        self._require_directory(source_path)
        self._require_directory(source_path / "generations")
        lock_path = source_path / ".lock"
        descriptor = self._open_private_regular(lock_path, os.O_RDWR)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            except OSError as exc:
                raise _CacheFault(CacheFailureReason.LOCK_FAILED) from exc
            yield
        finally:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)

    def _cleanup_incomplete(self, source_id: str) -> None:
        generations = self._generations_path(source_id)
        for entry in os.scandir(generations):
            if _INCOMPLETE_PATTERN.fullmatch(entry.name) is None:
                continue
            path = generations / entry.name
            details = os.lstat(path)
            if not stat.S_ISDIR(details.st_mode) or stat.S_ISLNK(details.st_mode):
                continue
            self._remove_incomplete(path)

    def _prune(self, source_id: str, current_id: str, previous_id: str | None) -> None:
        generations = self._generations_path(source_id)
        valid: list[ValidatedCacheGeneration] = []
        for entry in os.scandir(generations):
            if _GENERATION_PATTERN.fullmatch(entry.name) is None:
                continue
            try:
                valid.append(self._read_generation(source_id, entry.name))
            except (OSError, ValueError, ValidationError, _CacheFault):
                continue
        keep = {current_id}
        if previous_id is not None:
            keep.add(previous_id)
        for generation in valid:
            generation_id = generation.metadata.generation_id
            if generation_id not in keep:
                self._remove_valid_generation(generations / generation_id)

    def _remove_valid_generation(self, path: Path) -> None:
        self._require_directory(path)
        if {entry.name for entry in os.scandir(path)} != _EXPECTED_GENERATION_FILES:
            raise _CacheFault(CacheFailureReason.UNSAFE_FILESYSTEM)
        for name in sorted(_EXPECTED_GENERATION_FILES):
            file_path = path / name
            descriptor = self._open_private_regular(file_path, os.O_RDONLY)
            os.close(descriptor)
            os.unlink(file_path)
        os.rmdir(path)

    def _remove_incomplete(self, path: Path) -> None:
        if _INCOMPLETE_PATTERN.fullmatch(path.name) is None:
            raise _CacheFault(CacheFailureReason.UNSAFE_FILESYSTEM)
        self._require_directory(path)
        for entry in os.scandir(path):
            child = path / entry.name
            details = os.lstat(child)
            if stat.S_ISDIR(details.st_mode) and not stat.S_ISLNK(details.st_mode):
                self._remove_private_tree(child)
            elif stat.S_ISREG(details.st_mode) and not stat.S_ISLNK(details.st_mode):
                os.unlink(child)
            else:
                raise _CacheFault(CacheFailureReason.UNSAFE_FILESYSTEM)
        os.rmdir(path)

    def _remove_private_tree(self, path: Path) -> None:
        self._require_directory(path)
        for entry in os.scandir(path):
            child = path / entry.name
            details = os.lstat(child)
            if stat.S_ISDIR(details.st_mode) and not stat.S_ISLNK(details.st_mode):
                self._remove_private_tree(child)
            elif stat.S_ISREG(details.st_mode) and not stat.S_ISLNK(details.st_mode):
                os.unlink(child)
            else:
                raise _CacheFault(CacheFailureReason.UNSAFE_FILESYSTEM)
        os.rmdir(path)

    def _best_effort_remove_incomplete(self, path: Path) -> None:
        try:
            self._remove_incomplete(path)
        except (OSError, _CacheFault):
            pass

    @staticmethod
    def _best_effort_unlink(path: Path) -> None:
        try:
            details = os.lstat(path)
            if stat.S_ISREG(details.st_mode) and not stat.S_ISLNK(details.st_mode):
                os.unlink(path)
        except OSError:
            pass

    def _source_path(self, source_id: str) -> Path:
        if source_id not in REGISTERED_SOURCE_IDS:
            raise _CacheFault(CacheFailureReason.SOURCE_UNREGISTERED)
        return self.sources_path / source_id

    def _generations_path(self, source_id: str) -> Path:
        return self._source_path(source_id) / "generations"

    @staticmethod
    def _hook(hook: FailureHook | None, phase: str) -> None:
        if hook is not None:
            hook(phase)

    @staticmethod
    def _require_directory(path: Path) -> None:
        try:
            details = os.lstat(path)
        except FileNotFoundError as exc:
            raise _CacheFault(CacheFailureReason.NOT_INITIALIZED) from exc
        if not stat.S_ISDIR(details.st_mode) or stat.S_ISLNK(details.st_mode):
            raise _CacheFault(CacheFailureReason.UNSAFE_FILESYSTEM)
        if (
            stat.S_IMODE(details.st_mode) != _DIRECTORY_MODE
            or details.st_uid != os.geteuid()
            or path.resolve() != path.absolute()
        ):
            raise _CacheFault(CacheFailureReason.UNSAFE_FILESYSTEM)

    @classmethod
    def _ensure_private_directory(cls, path: Path) -> None:
        if path.exists() or path.is_symlink():
            cls._require_directory(path)
            return
        cls._mkdir_private(path.parent, path.name)

    @classmethod
    def _ensure_lock_file(cls, path: Path) -> None:
        if path.exists() or path.is_symlink():
            descriptor = cls._open_private_regular(path, os.O_RDWR)
            os.close(descriptor)
            return
        cls._write_new_file(path, b"")

    @staticmethod
    def _open_private_regular(path: Path, flags: int) -> int:
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        parent_descriptor = DiscoveryCacheStore._open_directory_descriptor(path.parent)
        try:
            descriptor = os.open(
                path.name,
                flags | nofollow | os.O_NONBLOCK,
                dir_fd=parent_descriptor,
            )
        finally:
            os.close(parent_descriptor)
        details = os.fstat(descriptor)
        if (
            not stat.S_ISREG(details.st_mode)
            or details.st_nlink != 1
            or stat.S_IMODE(details.st_mode) != _FILE_MODE
            or details.st_uid != os.geteuid()
        ):
            os.close(descriptor)
            raise _CacheFault(CacheFailureReason.UNSAFE_FILESYSTEM)
        try:
            DiscoveryCacheStore._require_descriptor_path(descriptor, path)
        except _CacheFault:
            os.close(descriptor)
            raise
        return descriptor

    @classmethod
    def _read_bounded_file(cls, path: Path, maximum: int) -> bytes:
        descriptor = cls._open_private_regular(path, os.O_RDONLY)
        try:
            details = os.fstat(descriptor)
            if details.st_size > maximum:
                raise _CacheFault(CacheFailureReason.SIZE_EXCEEDED)
            value = os.read(descriptor, maximum + 1)
            if len(value) > maximum:
                raise _CacheFault(CacheFailureReason.SIZE_EXCEEDED)
            if os.read(descriptor, 1):
                raise _CacheFault(CacheFailureReason.SIZE_EXCEEDED)
            final_details = os.fstat(descriptor)
            if (
                final_details.st_size != details.st_size
                or final_details.st_dev != details.st_dev
                or final_details.st_ino != details.st_ino
            ):
                raise _CacheFault(CacheFailureReason.UNSAFE_FILESYSTEM)
            return value
        finally:
            os.close(descriptor)

    @classmethod
    def _read_model(
        cls, path: Path, maximum: int, model: type[CacheModel]
    ) -> CacheModel:
        return cls._validate_json_model(cls._read_bounded_file(path, maximum), model)

    @staticmethod
    def _validate_json_model(value: bytes, model: type[CacheModel]) -> CacheModel:
        _parse_json(value)
        validated = model.model_validate_json(value)
        if canonical_json(validated) != value:
            raise _CacheFault(CacheFailureReason.MALFORMED)
        return validated

    @classmethod
    def _write_new_file(cls, path: Path, value: bytes) -> None:
        parent_descriptor = cls._open_directory_descriptor(path.parent)
        try:
            descriptor = os.open(
                path.name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                _FILE_MODE,
                dir_fd=parent_descriptor,
            )
        finally:
            os.close(parent_descriptor)
        try:
            os.fchmod(descriptor, _FILE_MODE)
            cls._require_descriptor_path(descriptor, path)
            view = memoryview(value)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("short cache write")
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = DiscoveryCacheStore._open_directory_descriptor(path)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _mkdir_private(parent: Path, name: str) -> None:
        descriptor = DiscoveryCacheStore._open_directory_descriptor(parent)
        try:
            os.mkdir(name, mode=_DIRECTORY_MODE, dir_fd=descriptor)
            os.chmod(name, _DIRECTORY_MODE, dir_fd=descriptor, follow_symlinks=False)
        finally:
            os.close(descriptor)

    @staticmethod
    def _rename_within(parent: Path, source: str, destination: str) -> None:
        descriptor = DiscoveryCacheStore._open_directory_descriptor(parent)
        try:
            os.rename(
                source,
                destination,
                src_dir_fd=descriptor,
                dst_dir_fd=descriptor,
            )
        finally:
            os.close(descriptor)

    @staticmethod
    def _replace_within(parent: Path, source: str, destination: str) -> None:
        descriptor = DiscoveryCacheStore._open_directory_descriptor(parent)
        try:
            os.replace(
                source,
                destination,
                src_dir_fd=descriptor,
                dst_dir_fd=descriptor,
            )
        finally:
            os.close(descriptor)

    @staticmethod
    def _open_directory_descriptor(path: Path) -> int:
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        details = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(details.st_mode)
            or stat.S_IMODE(details.st_mode) != _DIRECTORY_MODE
            or details.st_uid != os.geteuid()
        ):
            os.close(descriptor)
            raise _CacheFault(CacheFailureReason.UNSAFE_FILESYSTEM)
        try:
            DiscoveryCacheStore._require_descriptor_path(descriptor, path)
        except _CacheFault:
            os.close(descriptor)
            raise
        return descriptor

    @staticmethod
    def _require_descriptor_path(descriptor: int, path: Path) -> None:
        descriptor_path = Path(f"/proc/self/fd/{descriptor}")
        if not descriptor_path.exists() or descriptor_path.resolve() != path.absolute():
            raise _CacheFault(CacheFailureReason.UNSAFE_FILESYSTEM)
