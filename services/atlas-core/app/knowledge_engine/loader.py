from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.knowledge_engine.models import (
    ApplicationDefinition,
)


class KnowledgeCatalogLoader:
    """Load application definitions from YAML files."""

    def __init__(
        self,
        applications_path: Path | None = None,
    ) -> None:
        self._applications_path = (
            applications_path
            if applications_path is not None
            else Path(__file__).parent / "applications"
        )

    def load_applications(
        self,
    ) -> list[ApplicationDefinition]:
        """Load all application definitions in the catalog."""

        if not self._applications_path.exists():
            return []

        definitions: list[ApplicationDefinition] = []

        for file_path in sorted(
            self._applications_path.glob("*.yaml")
        ):
            definitions.append(
                self._load_application(file_path)
            )

        for file_path in sorted(
            self._applications_path.glob("*.yml")
        ):
            definitions.append(
                self._load_application(file_path)
            )

        return definitions

    def _load_application(
        self,
        file_path: Path,
    ) -> ApplicationDefinition:
        with file_path.open(
            "r",
            encoding="utf-8",
        ) as knowledge_file:
            document: Any = yaml.safe_load(
                knowledge_file
            )

        if not isinstance(document, dict):
            raise ValueError(
                f"Knowledge file '{file_path}' "
                "must contain a YAML mapping."
            )

        return ApplicationDefinition.model_validate(
            document
        )