"""Narrow, bounded read adapters for InstallationPlan v1."""

from __future__ import annotations

import errno
import os
import stat
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import (
    AfterValidator,
    Field,
    StrictBool,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from app.discovery.loader import YamlCatalogLoader
from app.discovery.models import CatalogEntry, ImageReleaseEvidence
from app.installation_plan.contract import (
    ArtifactReasonCode,
    ArtifactState,
    CompatibilityFindingInputV1,
    ContractModel,
    Id128,
    OciRepository,
    RawEvidenceObservation,
    RepoPath,
    SafeSourceId,
    Sha256Digest,
    UtcSecond,
    Version,
    _compatibility_source_relation,
    _ordered_unique,
    bounded_id,
    content_digest,
    normalize_oci_reference,
)


class InstallationPlanAdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class CatalogRecord:
    entry: CatalogEntry
    reviewed_content_digest: str


@dataclass(frozen=True)
class CatalogSnapshot:
    selected: CatalogRecord
    records: tuple[CatalogRecord, ...]


class ArtifactObservation(ContractModel):
    """Closed adapter-owned repository observation."""

    state: ArtifactState
    repository_path: RepoPath | None
    service: Annotated[str, AfterValidator(lambda value: bounded_id(value, 1, 255))] | None
    content_digest: Sha256Digest | None
    reason_code: ArtifactReasonCode | None
    image_reference: OciRepository | None = None
    image_digest: Sha256Digest | None = None
    image_mutable: StrictBool = False

    @model_validator(mode="after")
    def relation(self) -> ArtifactObservation:
        allowed = {
            "present": {None}, "missing": {None},
            "invalid": {"content_size", "non_utf8", "invalid_yaml", "ambiguous_service"},
            "unsafe": {"containment_escape", "symlink", "non_regular"},
            "unknown": {"observation_unknown"},
        }
        if self.reason_code not in allowed[self.state]:
            raise ValueError("invalid artifact observation state/reason")
        if self.state in {"present", "missing"} and (
            self.repository_path is None or self.service is None
        ):
            raise ValueError("observed artifact requires binding identity")
        if (self.state == "present") != (self.content_digest is not None):
            raise ValueError("invalid artifact observation digest")
        if self.image_digest is not None and self.image_reference is None:
            raise ValueError("image digest requires repository")
        if self.image_mutable and (
            self.state != "present" or self.image_reference is None
            or self.image_digest is not None
        ):
            raise ValueError("invalid mutable image observation")
        if self.state != "present" and (
            self.image_reference is not None or self.image_digest is not None
            or self.image_mutable
        ):
            raise ValueError("rejected artifact cannot project an image")
        return self


class CompatibilityAdapterInput(ContractModel):
    """Closed, adapter-owned observation consumed by the compatibility projector."""

    source_kind: Literal["released", "absent", "malformed_optional"]
    item_id: Id128
    target_type_present: StrictBool
    status: Literal[
        "compatible", "compatible_with_warnings", "insufficient_information",
        "incompatible", "not_available",
    ]
    findings: tuple[CompatibilityFindingInputV1, ...] = Field(max_length=128)
    unknown_fact_codes: tuple[Id128, ...] = Field(max_length=128)

    @model_validator(mode="after")
    def relation(self) -> CompatibilityAdapterInput:
        if self.source_kind == "absent":
            valid = (
                self.status == "not_available" and not self.target_type_present
                and not self.findings and not self.unknown_fact_codes
            )
        elif self.source_kind == "malformed_optional":
            valid = (
                self.status == "insufficient_information"
                and not self.target_type_present and not self.findings
                and self.unknown_fact_codes
                == ("malformed_optional_compatibility_fact",)
            )
        else:
            finding_keys = tuple(
                (f.id, f.check_type, f.severity, f.status, f.subject, f.evidence_ids)
                for f in self.findings
            )
            _ordered_unique(finding_keys, "compatibility findings")
            _ordered_unique(
                tuple((code,) for code in self.unknown_fact_codes),
                "compatibility unknown fact codes",
            )
            valid = self.status != "not_available" and _compatibility_source_relation(
                self.status, self.findings, self.unknown_fact_codes
            )
        if not valid:
            raise ValueError("invalid compatibility adapter relation")
        return self


def _bounded_regular_bytes(path: Path, maximum: int) -> bytes:
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise InstallationPlanAdapterError("non_regular")
            if info.st_size < 0 or info.st_size > maximum:
                raise InstallationPlanAdapterError("content_size")
            chunks: list[bytes] = []
            total = 0
            while total <= maximum:
                chunk = os.read(descriptor, min(65536, maximum + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            if total > maximum:
                raise InstallationPlanAdapterError("content_size")
            result = b"".join(chunks)
            # A regular file changing underneath the read is uncertain, not a fact.
            after = os.fstat(descriptor)
            if (after.st_dev, after.st_ino) != (info.st_dev, info.st_ino):
                raise InstallationPlanAdapterError("unavailable")
            if after.st_size != len(result):
                raise InstallationPlanAdapterError("unavailable")
            return result
        finally:
            os.close(descriptor)
    except OSError as error:
        raise InstallationPlanAdapterError("unavailable") from error


def _bounded_relative_regular_bytes(
    root: Path, repository_path: str, maximum: int
) -> bytes:
    """Open a repository file without path prechecks or symlink traversal."""
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None:
        raise InstallationPlanAdapterError("unavailable")
    descriptors: list[int] = []
    try:
        descriptors.append(os.open(root, os.O_RDONLY | directory | nofollow))
        root_info = os.fstat(descriptors[0])
        if not stat.S_ISDIR(root_info.st_mode):
            raise InstallationPlanAdapterError("unavailable")
        components = repository_path.split("/")
        for component in components[:-1]:
            component_info = os.stat(
                component, dir_fd=descriptors[-1], follow_symlinks=False
            )
            if stat.S_ISLNK(component_info.st_mode):
                raise InstallationPlanAdapterError("symlink")
            descriptors.append(
                os.open(
                    component,
                    os.O_RDONLY | directory | nofollow,
                    dir_fd=descriptors[-1],
                )
            )
            if not stat.S_ISDIR(os.fstat(descriptors[-1]).st_mode):
                raise InstallationPlanAdapterError("non_regular")
        try:
            descriptor = os.open(
                components[-1], os.O_RDONLY | nofollow, dir_fd=descriptors[-1]
            )
        except FileNotFoundError as error:
            raise InstallationPlanAdapterError("missing") from error
        descriptors.append(descriptor)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise InstallationPlanAdapterError("non_regular")
        if before.st_size < 0 or before.st_size > maximum:
            raise InstallationPlanAdapterError("content_size")
        chunks: list[bytes] = []
        total = 0
        while total <= maximum:
            chunk = os.read(descriptor, min(65536, maximum + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        if total > maximum:
            raise InstallationPlanAdapterError("content_size")
        after = os.fstat(descriptor)
        if (
            (before.st_dev, before.st_ino, before.st_mode)
            != (after.st_dev, after.st_ino, after.st_mode)
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or before.st_ctime_ns != after.st_ctime_ns
            or after.st_size != total
        ):
            raise InstallationPlanAdapterError("unavailable")
        return b"".join(chunks)
    except InstallationPlanAdapterError:
        raise
    except OSError as error:
        if error.errno in {errno.ELOOP, errno.EMLINK}:
            raise InstallationPlanAdapterError("symlink") from error
        if error.errno == errno.ENOENT:
            raise InstallationPlanAdapterError("missing") from error
        if error.errno in {errno.ENOTDIR, errno.EISDIR}:
            raise InstallationPlanAdapterError("non_regular") from error
        raise InstallationPlanAdapterError("unavailable") from error
    finally:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass


class CatalogAdapter:
    def __init__(
        self, catalog_root: Path = Path(__file__).parents[1] / "discovery" / "catalog"
    ) -> None:
        self._root = Path(catalog_root)

    def read(self, item_id: str) -> CatalogSnapshot:
        if not self._root.is_absolute():
            raise InstallationPlanAdapterError("catalog root must be absolute")
        records: list[CatalogRecord] = []
        for path in sorted((*self._root.rglob("*.yaml"), *self._root.rglob("*.yml"))):
            try:
                raw = _bounded_regular_bytes(path, 1024 * 1024)
                raw.decode("utf-8")
                entry = YamlCatalogLoader().load_text(
                    raw.decode(), source="catalog-loader"
                )
            except Exception as error:
                raise InstallationPlanAdapterError("catalog unavailable") from error
            records.append(CatalogRecord(entry, content_digest(raw)))
        matches = [record for record in records if record.entry.item.id == item_id]
        item_ids = [record.entry.item.id for record in records]
        entry_ids = [record.entry.provenance.entry_id for record in records]
        if len(set(item_ids)) != len(item_ids) or len(set(entry_ids)) != len(entry_ids):
            raise InstallationPlanAdapterError("catalog duplicate")
        if len(matches) != 1:
            raise InstallationPlanAdapterError("catalog item not found or ambiguous")
        return CatalogSnapshot(matches[0], tuple(records))


class RepositoryArtifactAdapter:
    def __init__(self, repository_root: Path, *, max_bytes: int = 1024 * 1024) -> None:
        root = Path(repository_root)
        if (
            not root.is_absolute()
            or isinstance(max_bytes, bool)
            or not isinstance(max_bytes, int)
            or max_bytes <= 0
        ):
            raise ValueError(
                "absolute repository root and positive byte bound required"
            )
        self._root, self._max_bytes = root, max_bytes

    def observe(self, entry: CatalogEntry) -> ArtifactObservation:
        binding = entry.deployment_binding
        if binding is None:
            return ArtifactObservation(
                state="unknown", repository_path=None, service=None,
                content_digest=None, reason_code="observation_unknown"
            )
        path, service = binding.compose_file, binding.compose_service
        if _validated(RepoPath, path) is None:
            raise InstallationPlanAdapterError("invalid binding")
        try:
            raw = _bounded_relative_regular_bytes(self._root, path, self._max_bytes)
        except InstallationPlanAdapterError as error:
            if str(error) == "missing":
                return ArtifactObservation(
                    state="missing", repository_path=path, service=service,
                    content_digest=None, reason_code=None,
                )
            if str(error) == "symlink":
                return ArtifactObservation(
                    state="unsafe", repository_path=path, service=service,
                    content_digest=None, reason_code="symlink",
                )
            if str(error) == "content_size":
                return ArtifactObservation(
                    state="invalid", repository_path=path, service=service,
                    content_digest=None, reason_code="content_size",
                )
            if str(error) == "non_regular":
                return ArtifactObservation(
                    state="unsafe", repository_path=path, service=service,
                    content_digest=None, reason_code="non_regular",
                )
            raise
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return ArtifactObservation(
                state="invalid", repository_path=path, service=service,
                content_digest=None, reason_code="non_utf8",
            )
        try:
            document = yaml.safe_load(text)
        except yaml.YAMLError:
            return ArtifactObservation(
                state="invalid", repository_path=path, service=service,
                content_digest=None, reason_code="invalid_yaml",
            )
        if (
            not isinstance(document, dict)
            or not isinstance(document.get("services"), dict)
            or not isinstance(document["services"].get(service), dict)
        ):
            return ArtifactObservation(
                state="invalid", repository_path=path, service=service,
                content_digest=None, reason_code="ambiguous_service",
            )
        image = document["services"][service].get("image")
        reference = digest = None
        mutable = False
        if isinstance(image, str):
            try:
                reference, digest, mutable = normalize_oci_reference(image)
            except ValueError:
                pass
        return ArtifactObservation(
            state="present", repository_path=path, service=service,
            content_digest=content_digest(raw), reason_code=None,
            image_reference=reference, image_digest=digest, image_mutable=mutable,
        )


def adapt_released_evidence(
    row: ImageReleaseEvidence, *, expected_source_id: str | None = None
) -> RawEvidenceObservation:
    source_id = expected_source_id or row.source_id
    return RawEvidenceObservation(
        observation_kind="present",
        expected_source_id=source_id,
        source_class=row.source_class.value,
        subject=row.catalog_item_id,
        release_version=row.release_version,
        image_reference=normalize_oci_reference(row.image_reference)[0],
        image_digest=row.image_digest,
        released_source_id=row.source_id,
        attested_at=row.attested_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        adapter_reason=None,
    )


def adapt_raw_evidence_record(
    raw: bytes | None,
    *,
    expected_source_id: str,
    source_unavailable: bool = False,
) -> RawEvidenceObservation:
    """Classify one already-bounded optional evidence record without retaining raw values."""
    empty = {
        "source_class": None,
        "subject": None,
        "release_version": None,
        "image_reference": None,
        "image_digest": None,
        "released_source_id": None,
        "attested_at": None,
    }
    if source_unavailable:
        return RawEvidenceObservation(
            observation_kind="source_unavailable",
            expected_source_id=expected_source_id,
            adapter_reason="source_read_unavailable",
            **empty,
        )
    if raw is None:
        return RawEvidenceObservation(
            observation_kind="absent",
            expected_source_id=expected_source_id,
            adapter_reason="record_absent",
            **empty,
        )
    try:
        # BaseLoader prevents YAML timestamp/boolean coercion at this string-only boundary.
        document = yaml.load(raw.decode("utf-8"), Loader=yaml.BaseLoader)
    except (UnicodeDecodeError, yaml.YAMLError):
        return RawEvidenceObservation(
            observation_kind="parse_failure",
            expected_source_id=expected_source_id,
            adapter_reason="record_parse_failure",
            **empty,
        )
    if not isinstance(document, dict):
        return RawEvidenceObservation(
            observation_kind="schema_failure",
            expected_source_id=expected_source_id,
            adapter_reason="record_schema_failure",
            **empty,
        )
    keys = {
        "catalog_item_id",
        "release_version",
        "image_reference",
        "image_digest",
        "source_class",
        "source_id",
        "attested_at",
    }
    source_value = document.get("source_class")
    if isinstance(source_value, str) and source_value not in {
        "curated",
        "registry_attested",
        "upstream_signed",
    }:
        released_id = _validated(SafeSourceId, document.get("source_id"))
        return RawEvidenceObservation(
            observation_kind="unsupported_source_class",
            expected_source_id=expected_source_id,
            source_class="unknown",
            subject=None,
            release_version=None,
            image_reference=None,
            image_digest=None,
            released_source_id=released_id,
            attested_at=None,
            adapter_reason="source_class_unsupported",
        )
    structural = bool(set(document) - keys) or any(
        key in document and not isinstance(document[key], str) for key in keys
    )
    normalized_source = (
        source_value
        if isinstance(source_value, str)
        and source_value in {"curated", "registry_attested", "upstream_signed"}
        else None
    )
    subject = _validated(Id128, document.get("catalog_item_id"))
    version = _validated(Version, document.get("release_version"))
    reference = _validated(OciRepository, document.get("image_reference"))
    digest = _validated(Sha256Digest, document.get("image_digest"))
    released_id = _validated(SafeSourceId, document.get("source_id"))
    timestamp = _validated(UtcSecond, document.get("attested_at"))
    values = {
        "source_class": normalized_source,
        "subject": subject,
        "release_version": version,
        "image_reference": reference,
        "image_digest": digest,
        "released_source_id": released_id,
        "attested_at": timestamp,
    }
    if (
        structural
        or (document.get("catalog_item_id") is not None and subject is None)
        or (document.get("release_version") is not None and version is None)
        or (document.get("image_reference") is not None and reference is None)
    ):
        return RawEvidenceObservation(
            observation_kind="schema_failure",
            expected_source_id=expected_source_id,
            adapter_reason="record_schema_failure",
            **values,
        )
    if any(key not in document or document[key] is None for key in keys):
        return RawEvidenceObservation(
            observation_kind="missing_required_field",
            expected_source_id=expected_source_id,
            adapter_reason="required_field_missing",
            **values,
        )
    if timestamp is None:
        return RawEvidenceObservation(
            observation_kind="malformed_timestamp",
            expected_source_id=expected_source_id,
            adapter_reason="timestamp_malformed",
            **values,
        )
    if released_id is None:
        return RawEvidenceObservation(
            observation_kind="malformed_identity",
            expected_source_id=expected_source_id,
            adapter_reason="identity_malformed",
            **values,
        )
    if digest is None:
        return RawEvidenceObservation(
            observation_kind="malformed_digest",
            expected_source_id=expected_source_id,
            adapter_reason="digest_malformed",
            **values,
        )
    return RawEvidenceObservation(
        observation_kind="present",
        expected_source_id=expected_source_id,
        adapter_reason=None,
        **values,
    )


def _validated(annotation: object, value: object) -> object | None:
    try:
        return TypeAdapter(annotation).validate_python(value, strict=True)
    except ValidationError:
        return None
