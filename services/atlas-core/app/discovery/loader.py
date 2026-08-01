from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.discovery.exceptions import (
    DiscoveryCatalogDocumentError,
    DiscoveryCatalogDuplicateError,
    DiscoveryCatalogPathError,
    DiscoveryCatalogValidationError,
    DiscoveryCatalogYamlError,
)
from app.discovery.models import CatalogEntry, DiscoveryCenterModel

DEFAULT_DISCOVERY_CATALOG_DIR = Path(__file__).parent / "catalog"
_YAML_SUFFIXES = {".yaml", ".yml"}


class LoadedCatalog(DiscoveryCenterModel):
    """Deterministically loaded Discovery Center catalog entries."""

    entries: tuple[CatalogEntry, ...] = ()
    source_paths: tuple[str, ...] = ()


class YamlCatalogLoader:
    """Load Discovery Center CatalogEntry YAML files deterministically."""

    def __init__(
        self,
        catalog_path: Path | None = None,
        *,
        recursive: bool = True,
    ) -> None:
        self._catalog_path = catalog_path or DEFAULT_DISCOVERY_CATALOG_DIR
        self._explicit_catalog_path = catalog_path is not None
        self._recursive = recursive

    def load(self) -> LoadedCatalog:
        """Load every YAML entry from the configured catalog directory."""

        if not self._catalog_path.exists():
            if self._explicit_catalog_path:
                raise DiscoveryCatalogPathError(
                    f"Discovery catalog path does not exist: {self._catalog_path}",
                )
            return LoadedCatalog()

        if not self._catalog_path.is_dir():
            raise DiscoveryCatalogPathError(
                f"Discovery catalog path is not a directory: {self._catalog_path}",
            )

        catalog_files = self._discover_catalog_files(self._catalog_path)
        entries: list[CatalogEntry] = []
        source_paths: list[str] = []

        for catalog_file in catalog_files:
            entries.append(self.load_file(catalog_file))
            source_paths.append(str(catalog_file))

        self._validate_no_duplicates(entries, source_paths)
        return LoadedCatalog(entries=tuple(entries), source_paths=tuple(source_paths))

    def load_file(self, path: Path) -> CatalogEntry:
        """Load one YAML file into a CatalogEntry."""

        file_path = Path(path)
        if file_path.suffix.lower() not in _YAML_SUFFIXES:
            raise DiscoveryCatalogPathError(
                f"Discovery catalog file has unsupported extension: {file_path}",
            )
        if not file_path.exists():
            raise DiscoveryCatalogPathError(
                f"Discovery catalog file does not exist: {file_path}",
            )
        if not file_path.is_file():
            raise DiscoveryCatalogPathError(
                f"Discovery catalog path is not a file: {file_path}",
            )

        try:
            catalog_text = file_path.read_text(encoding="utf-8")
        except OSError as error:
            raise DiscoveryCatalogPathError(
                f"Unable to read Discovery catalog file {file_path}: {error}",
            ) from error

        return self.load_text(catalog_text, source=str(file_path))

    def load_text(self, text: str, *, source: str = "<memory>") -> CatalogEntry:
        """Load one YAML CatalogEntry document from text."""

        try:
            document: Any = yaml.safe_load(text)
        except yaml.YAMLError as error:
            raise DiscoveryCatalogYamlError(
                f"Unable to parse Discovery catalog YAML from {source}: {error}",
            ) from error

        if not isinstance(document, dict):
            raise DiscoveryCatalogDocumentError(
                f"Discovery catalog document root must be a mapping in {source}.",
            )

        try:
            return CatalogEntry.model_validate(document)
        except ValidationError as error:
            raise DiscoveryCatalogValidationError(
                f"Discovery catalog entry failed validation in {source}: {error}",
            ) from error

    def _discover_catalog_files(self, catalog_path: Path) -> tuple[Path, ...]:
        try:
            candidates = catalog_path.rglob("*") if self._recursive else catalog_path.glob("*")
            return tuple(
                sorted(
                    (
                        candidate
                        for candidate in candidates
                        if candidate.is_file() and candidate.suffix.lower() in _YAML_SUFFIXES
                    ),
                    key=lambda path: path.as_posix(),
                ),
            )
        except OSError as error:
            raise DiscoveryCatalogPathError(
                f"Unable to read Discovery catalog directory {catalog_path}: {error}",
            ) from error

    def _validate_no_duplicates(
        self,
        entries: list[CatalogEntry],
        source_paths: list[str],
    ) -> None:
        item_sources: dict[str, str] = {}
        entry_sources: dict[str, str] = {}

        for entry, source_path in zip(entries, source_paths, strict=True):
            self._validate_unique_identifier(
                identifier=entry.item.id,
                source_path=source_path,
                seen_sources=item_sources,
                label="item.id",
            )
            if entry.provenance.entry_id is not None:
                self._validate_unique_identifier(
                    identifier=entry.provenance.entry_id,
                    source_path=source_path,
                    seen_sources=entry_sources,
                    label="provenance.entry_id",
                )

    @staticmethod
    def _validate_unique_identifier(
        *,
        identifier: str,
        source_path: str,
        seen_sources: dict[str, str],
        label: str,
    ) -> None:
        previous_source_path = seen_sources.get(identifier)
        if previous_source_path is not None:
            raise DiscoveryCatalogDuplicateError(
                "Duplicate Discovery catalog "
                f"{label} '{identifier}' in {previous_source_path} and {source_path}.",
            )
        seen_sources[identifier] = source_path
