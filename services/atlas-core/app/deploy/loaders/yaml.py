from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.deploy.loaders.exceptions import (
    InvalidDocumentError,
    InvalidYamlError,
)


class YamlLoader:
    """Load YAML text or files into mapping documents."""

    def load_file(
        self,
        path: str | Path,
    ) -> dict[str, Any]:
        """Load a YAML document from a filesystem path."""

        file_path = Path(path)

        return self.load_text(
            file_path.read_text(encoding="utf-8")
        )

    def load_text(
        self,
        text: str,
    ) -> dict[str, Any]:
        """Load a YAML document from text."""

        try:
            document = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise InvalidYamlError(
                "Unable to parse YAML document."
            ) from exc

        if document is None:
            return {}

        if not isinstance(document, dict):
            raise InvalidDocumentError(
                "YAML document root must be a mapping."
            )

        return document
