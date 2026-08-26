"""Server-owned, bounded, read-only InstallationPlan assembly dependency."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import yaml
from pydantic import TypeAdapter, ValidationError

from app.installation_plan.adapters import (
    CatalogAdapter,
    CatalogItemNotFoundError,
    InstallationPlanAdapterError,
    RepositoryArtifactAdapter,
    _bounded_relative_regular_bytes,
    adapt_raw_evidence_record,
)
from app.installation_plan.contract import (
    Id128,
    InstallationPlan,
    RawEvidenceObservation,
    SafeSourceId,
    UtcSecond,
)
from app.installation_plan.evaluator import InstallationPlanAssembler

# Implementation bound shared with the already accepted bounded catalog and
# repository readers. It is not a new wire-contract cardinality or byte bound.
DEFAULT_EVIDENCE_MAX_BYTES = 1024 * 1024
MAX_EVIDENCE_OBSERVATIONS = 128


class InstallationPlanReadError(RuntimeError):
    """Sanitized base failure at the future HTTP mapping boundary."""


class InstallationPlanItemNotFound(InstallationPlanReadError):
    pass


class InstallationPlanSourceUnavailable(InstallationPlanReadError):
    pass


class InstallationPlanClockUnavailable(InstallationPlanReadError):
    pass


class InstallationPlanContractFailure(InstallationPlanReadError):
    pass


@dataclass(frozen=True)
class ReleasedEvidenceRecordSource:
    """One server-configured optional or required released evidence record."""

    item_id: str
    relative_path: str
    expected_source_id: str
    required: bool = False


class BoundedReleasedEvidenceSource:
    """Read only an explicit finite set of server-controlled evidence files."""

    def __init__(
        self,
        root: Path,
        records: tuple[ReleasedEvidenceRecordSource, ...],
        *,
        max_bytes: int = DEFAULT_EVIDENCE_MAX_BYTES,
    ) -> None:
        root = Path(root)
        if not root.is_absolute() or isinstance(max_bytes, bool) or max_bytes <= 0:
            raise ValueError("invalid evidence source configuration")
        for record in records:
            path = PurePosixPath(record.relative_path)
            try:
                valid_ids = (
                    TypeAdapter(Id128).validate_python(record.item_id) == record.item_id
                    and TypeAdapter(SafeSourceId).validate_python(
                        record.expected_source_id
                    )
                    == record.expected_source_id
                )
            except ValidationError:
                valid_ids = False
            if not valid_ids or (
                path.is_absolute()
                or not path.parts
                or any(part in {"", ".", ".."} for part in path.parts)
                or "\\" in record.relative_path
            ):
                raise ValueError("invalid evidence source configuration")
        self._root = root
        self._records = records
        self._max_bytes = max_bytes

    def observe(self, item_id: str) -> tuple[RawEvidenceObservation, ...]:
        configured = tuple(row for row in self._records if row.item_id == item_id)
        if len(configured) > MAX_EVIDENCE_OBSERVATIONS:
            raise InstallationPlanAdapterError("evidence cardinality")
        observations: list[RawEvidenceObservation] = []
        for source in configured:
            try:
                raw = _bounded_relative_regular_bytes(
                    self._root, source.relative_path, self._max_bytes
                )
            except InstallationPlanAdapterError as error:
                reason = str(error)
                if reason == "missing" and not source.required:
                    observations.append(
                        adapt_raw_evidence_record(
                            None, expected_source_id=source.expected_source_id
                        )
                    )
                    continue
                if reason == "unavailable" and not source.required:
                    observations.append(
                        adapt_raw_evidence_record(
                            None,
                            expected_source_id=source.expected_source_id,
                            source_unavailable=True,
                        )
                    )
                    continue
                raise InstallationPlanAdapterError("evidence read uncertain") from error
            observations.append(
                adapt_raw_evidence_record(
                    _released_record_bytes(raw),
                    expected_source_id=source.expected_source_id,
                )
            )
        return tuple(observations)


def _released_record_bytes(raw: bytes) -> bytes:
    """Remove the reviewed on-disk publication envelope, retaining classification."""

    try:
        document = yaml.load(raw.decode("utf-8"), Loader=yaml.BaseLoader)
    except (UnicodeDecodeError, yaml.YAMLError):
        return raw
    if (
        isinstance(document, dict)
        and set(document) == {"schema_version", "evidence"}
        and document.get("schema_version") == "1"
        and isinstance(document.get("evidence"), dict)
    ):
        return yaml.safe_dump(document["evidence"], sort_keys=False).encode("utf-8")
    return raw


def utc_server_clock() -> datetime:
    """Default server clock; callers of assembly cannot supply its value."""

    return datetime.now(UTC).replace(microsecond=0)


class InstallationPlanReadDependency:
    """Assemble exactly one ephemeral item-scoped InstallationPlan."""

    def __init__(
        self,
        *,
        catalog: CatalogAdapter,
        repository: RepositoryArtifactAdapter,
        evidence: BoundedReleasedEvidenceSource,
        clock: Callable[[], datetime] = utc_server_clock,
        assembler: InstallationPlanAssembler | None = None,
    ) -> None:
        self._catalog = catalog
        self._repository = repository
        self._evidence = evidence
        self._clock = clock
        self._assembler = assembler or InstallationPlanAssembler()

    def assemble(self, item_id: str) -> InstallationPlan:
        try:
            catalog = self._catalog.read(item_id)
        except CatalogItemNotFoundError:
            raise InstallationPlanItemNotFound(
                "installation plan item not found"
            ) from None
        except Exception:  # noqa: BLE001 - sanitize the dependency boundary
            raise InstallationPlanSourceUnavailable(
                "installation plan required source unavailable"
            ) from None

        try:
            artifact = self._repository.observe(catalog.selected.entry)
            evidence = self._evidence.observe(item_id)
        except Exception:  # noqa: BLE001 - sanitize the dependency boundary
            raise InstallationPlanSourceUnavailable(
                "installation plan required source unavailable"
            ) from None

        try:
            instant = self._clock()  # The sole clock read for an assembly.
            if (
                not isinstance(instant, datetime)
                or instant.tzinfo is None
                or instant.utcoffset() is None
                or instant.utcoffset().total_seconds() != 0
                or instant.microsecond
            ):
                raise ValueError("invalid clock value")
            utc_second = instant.strftime("%Y-%m-%dT%H:%M:%SZ")
            TypeAdapter(UtcSecond).validate_python(utc_second)
        except Exception:  # noqa: BLE001 - clocks are injected server dependencies
            raise InstallationPlanClockUnavailable(
                "installation plan clock unavailable"
            ) from None

        try:
            return self._assembler.assemble(
                catalog=catalog,
                artifact_observation=artifact,
                evidence_observations=evidence,
                evaluation_instant=utc_second,
                compatibility_observation=None,
            )
        except (ValueError, ValidationError):
            raise InstallationPlanContractFailure(
                "installation plan contract failure"
            ) from None
        except Exception:  # noqa: BLE001 - no lower-layer text crosses this boundary
            raise InstallationPlanContractFailure(
                "installation plan contract failure"
            ) from None


def default_installation_plan_dependency(
    *, repository_root: Path, clock: Callable[[], datetime] = utc_server_clock
) -> InstallationPlanReadDependency:
    """Construct the server dependency; repository root is never request-derived."""

    evidence_root = Path(__file__).parents[1] / "discovery" / "image_release_evidence"
    return InstallationPlanReadDependency(
        catalog=CatalogAdapter(),
        repository=RepositoryArtifactAdapter(repository_root),
        evidence=BoundedReleasedEvidenceSource(
            evidence_root,
            (
                ReleasedEvidenceRecordSource(
                    item_id="home-assistant",
                    relative_path="home-assistant/2026.8.3-registry-attested.yaml",
                    expected_source_id="collector:home-assistant-ghcr-cosign",
                ),
            ),
        ),
        clock=clock,
    )
