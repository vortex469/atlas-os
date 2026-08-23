from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import ValidationError

from app.discovery.exceptions import (
    ImageReleaseEvidenceConflictError,
    ImageReleaseEvidenceDocumentError,
    ImageReleaseEvidenceDuplicateError,
    ImageReleaseEvidencePathError,
    ImageReleaseEvidenceValidationError,
    ImageReleaseEvidenceYamlError,
)
from app.discovery.models import DiscoveryCenterModel, ImageReleaseEvidence

DEFAULT_IMAGE_RELEASE_EVIDENCE_DIR = Path(__file__).parent / "image_release_evidence"
_YAML_SUFFIXES = {".yaml", ".yml"}


class CuratedImageReleaseEvidenceDocument(DiscoveryCenterModel):
    """Envelope for one curated image-release evidence row.

    The envelope is data only. It is inert in v0.14 P1b and has no
    production consumer: nothing in the application loads or consumes
    this directory at runtime. A future P1b-collector, if ever built,
    will be reviewed separately.
    """

    schema_version: Literal[1]
    evidence: ImageReleaseEvidence


class LoadedImageReleaseEvidence(DiscoveryCenterModel):
    """Deterministically loaded curated image-release evidence rows."""

    rows: tuple[ImageReleaseEvidence, ...] = ()
    source_paths: tuple[str, ...] = ()


class ImageReleaseEvidenceLoader:
    """Load curated image-release evidence YAML files deterministically.

    The loader performs local filesystem reads only. It never performs
    network access, registry lookups, credential handling, subprocess
    execution, or writes. Any missing or malformed source fails the
    entire load: the loader never returns partial results.
    """

    def __init__(
        self,
        evidence_path: Path | None = None,
        *,
        recursive: bool = True,
    ) -> None:
        self._evidence_path = evidence_path or DEFAULT_IMAGE_RELEASE_EVIDENCE_DIR
        self._explicit_evidence_path = evidence_path is not None
        self._recursive = recursive

    def load(self) -> LoadedImageReleaseEvidence:
        """Load every YAML evidence row from the configured directory."""

        if not self._evidence_path.exists():
            if self._explicit_evidence_path:
                raise ImageReleaseEvidencePathError(
                    f"Image release evidence path does not exist: {self._evidence_path}",
                )
            return LoadedImageReleaseEvidence()

        if not self._evidence_path.is_dir():
            raise ImageReleaseEvidencePathError(
                f"Image release evidence path is not a directory: {self._evidence_path}",
            )

        evidence_files = self._discover_evidence_files(self._evidence_path)
        rows: list[ImageReleaseEvidence] = []
        source_paths: list[str] = []

        for evidence_file in evidence_files:
            document = self.load_file(evidence_file)
            rows.append(document.evidence)
            source_paths.append(str(evidence_file))

        self._validate_agreement(rows, source_paths)
        return LoadedImageReleaseEvidence(
            rows=tuple(rows),
            source_paths=tuple(source_paths),
        )

    def load_file(self, path: Path) -> CuratedImageReleaseEvidenceDocument:
        """Load one YAML file into a curated evidence envelope."""

        file_path = Path(path)
        if file_path.suffix.lower() not in _YAML_SUFFIXES:
            raise ImageReleaseEvidencePathError(
                f"Image release evidence file has unsupported extension: {file_path}",
            )
        if not file_path.exists():
            raise ImageReleaseEvidencePathError(
                f"Image release evidence file does not exist: {file_path}",
            )
        if not file_path.is_file():
            raise ImageReleaseEvidencePathError(
                f"Image release evidence path is not a file: {file_path}",
            )

        try:
            evidence_text = file_path.read_text(encoding="utf-8")
        except OSError as error:
            raise ImageReleaseEvidencePathError(
                f"Unable to read image release evidence file {file_path}: {error}",
            ) from error

        return self.load_text(evidence_text, source=str(file_path))

    def load_text(
        self,
        text: str,
        *,
        source: str = "<memory>",
    ) -> CuratedImageReleaseEvidenceDocument:
        """Load one YAML curated evidence envelope from text."""

        try:
            document: Any = yaml.safe_load(text)
        except yaml.YAMLError as error:
            raise ImageReleaseEvidenceYamlError(
                f"Unable to parse image release evidence YAML from {source}: {error}",
            ) from error

        if not isinstance(document, dict):
            raise ImageReleaseEvidenceDocumentError(
                f"Image release evidence document root must be a mapping in {source}.",
            )

        try:
            return CuratedImageReleaseEvidenceDocument.model_validate(document)
        except ValidationError as error:
            raise ImageReleaseEvidenceValidationError(
                f"Image release evidence envelope failed validation in {source}: {error}",
            ) from error

    def _discover_evidence_files(self, evidence_path: Path) -> tuple[Path, ...]:
        try:
            candidates = (
                evidence_path.rglob("*")
                if self._recursive
                else evidence_path.glob("*")
            )
            return tuple(
                sorted(
                    (
                        candidate
                        for candidate in candidates
                        if candidate.is_file()
                        and candidate.suffix.lower() in _YAML_SUFFIXES
                    ),
                    key=lambda path: path.as_posix(),
                ),
            )
        except OSError as error:
            raise ImageReleaseEvidencePathError(
                f"Unable to read image release evidence directory {evidence_path}: {error}",
            ) from error

    @staticmethod
    def _validate_agreement(
        rows: list[ImageReleaseEvidence],
        source_paths: list[str],
    ) -> None:
        source_id_paths: dict[str, str] = {}
        release_identities: dict[tuple[str, str], tuple[tuple[str, str], str]] = {}

        for row, source_path in zip(rows, source_paths, strict=True):
            previous_source_path = source_id_paths.get(row.source_id)
            if previous_source_path is not None:
                raise ImageReleaseEvidenceDuplicateError(
                    "Duplicate image release evidence source_id "
                    f"'{row.source_id}' in {previous_source_path} and {source_path}.",
                )
            source_id_paths[row.source_id] = source_path

            key = (row.catalog_item_id, row.release_version)
            identity = (row.image_reference, row.image_digest)
            previous = release_identities.get(key)
            if previous is not None and previous[0] != identity:
                raise ImageReleaseEvidenceConflictError(
                    f"Conflicting image release evidence for item "
                    f"'{row.catalog_item_id}' release {row.release_version!r}: "
                    f"image reference/digest in {previous[1]} differs from "
                    f"{source_path}.",
                )
            if previous is None:
                release_identities[key] = (identity, source_path)
