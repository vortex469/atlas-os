from pathlib import Path

import pytest

from app.deploy.loaders import (
    InvalidDocumentError,
    InvalidYamlError,
    YamlLoader,
)


def test_load_yaml_text() -> None:
    loader = YamlLoader()

    document = loader.load_text(
        """
services:
  web:
    image: nginx:latest
"""
    )

    assert document["services"]["web"]["image"] == "nginx:latest"


def test_load_empty_yaml_returns_empty_mapping() -> None:
    loader = YamlLoader()

    assert loader.load_text("") == {}


def test_invalid_yaml_raises() -> None:
    loader = YamlLoader()

    with pytest.raises(InvalidYamlError):
        loader.load_text(
            """
services:
  web:
    image: [
"""
        )


def test_non_mapping_document_raises() -> None:
    loader = YamlLoader()

    with pytest.raises(InvalidDocumentError):
        loader.load_text(
            """
- one
- two
"""
        )


def test_load_yaml_file(tmp_path: Path) -> None:
    compose_file = tmp_path / "compose.yml"

    compose_file.write_text(
        """
services:
  database:
    image: postgres:16
""",
        encoding="utf-8",
    )

    loader = YamlLoader()

    document = loader.load_file(compose_file)

    assert document["services"]["database"]["image"] == "postgres:16"
