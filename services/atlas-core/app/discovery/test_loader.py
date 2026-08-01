from __future__ import annotations

from pathlib import Path

import pytest

from app.discovery import (
    DiscoveryCatalogDocumentError,
    DiscoveryCatalogDuplicateError,
    DiscoveryCatalogPathError,
    DiscoveryCatalogValidationError,
    DiscoveryCatalogYamlError,
    LoadedCatalog,
    YamlCatalogLoader,
)


def catalog_entry_yaml(
    item_id: str,
    *,
    entry_id: str | None = None,
    relationship_target: str | None = None,
) -> str:
    entry_id_value = entry_id if entry_id is not None else item_id
    relationships = "[]"
    if relationship_target is not None:
        relationships = f"""
      - type: depends_on
        target: {relationship_target}
        required: true
        minimum_version: "14"
        maximum_version: "17"
        description: Related catalog item.
"""

    return f"""
schema_version: 1
item:
  id: {item_id}
  type: service
  status: active
  name: {item_id.title()}
  description: Test catalog item.
  documentation_url: https://example.test/{item_id}
  capabilities:
    - id: {item_id}-capability
  requirements:
    resources:
      cpu_cores_min: 1
      memory_mb_min: 256
    platform:
      runtimes:
        - docker
    network:
      ports:
        - port: 1234
          protocol: tcp
          direction: inbound
          required: true
          description: Test port.
  relationships: {relationships}
  metadata:
    image: example/{item_id}
provenance:
  source_type: curated
  source: app/discovery/catalog/{item_id}.yaml
  entry_id: {entry_id_value}
  trust_level: curated
metadata:
  catalog_namespace: atlas-test
"""


def write_entry(path: Path, item_id: str, *, entry_id: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(catalog_entry_yaml(item_id, entry_id=entry_id), encoding="utf-8")


def test_load_text_returns_catalog_entry_without_mutating_source() -> None:
    entry = YamlCatalogLoader().load_text(
        catalog_entry_yaml("postgres"),
        source="fixture.yaml",
    )

    assert entry.item.id == "postgres"
    assert entry.provenance.source == "app/discovery/catalog/postgres.yaml"


def test_missing_implicit_catalog_path_returns_empty_catalog(tmp_path: Path) -> None:
    loader = YamlCatalogLoader(tmp_path / "missing-default-catalog")
    loader._explicit_catalog_path = False

    catalog = loader.load()

    assert catalog == LoadedCatalog()


def test_explicit_missing_catalog_path_raises() -> None:
    missing_path = Path("/definitely/missing/discovery/catalog")

    with pytest.raises(DiscoveryCatalogPathError, match=str(missing_path)):
        YamlCatalogLoader(missing_path).load()


def test_explicit_non_directory_catalog_path_raises(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text("schema_version: 1", encoding="utf-8")

    with pytest.raises(DiscoveryCatalogPathError, match=str(catalog_path)):
        YamlCatalogLoader(catalog_path).load()


def test_loads_yaml_and_yml_recursively_in_deterministic_order(tmp_path: Path) -> None:
    write_entry(tmp_path / "z" / "redis.yml", "redis")
    write_entry(tmp_path / "a" / "postgres.yaml", "postgres")
    (tmp_path / "ignored.txt").write_text("ignored", encoding="utf-8")

    catalog = YamlCatalogLoader(tmp_path).load()

    assert [entry.item.id for entry in catalog.entries] == ["postgres", "redis"]
    assert catalog.source_paths == (
        str(tmp_path / "a" / "postgres.yaml"),
        str(tmp_path / "z" / "redis.yml"),
    )


def test_non_recursive_loading_only_reads_top_level_yaml(tmp_path: Path) -> None:
    write_entry(tmp_path / "postgres.yaml", "postgres")
    write_entry(tmp_path / "nested" / "redis.yaml", "redis")

    catalog = YamlCatalogLoader(tmp_path, recursive=False).load()

    assert [entry.item.id for entry in catalog.entries] == ["postgres"]
    assert catalog.source_paths == (str(tmp_path / "postgres.yaml"),)


def test_empty_explicit_catalog_directory_returns_empty_catalog(tmp_path: Path) -> None:
    catalog = YamlCatalogLoader(tmp_path).load()

    assert catalog.entries == ()
    assert catalog.source_paths == ()


def test_load_file_rejects_unsupported_extension(tmp_path: Path) -> None:
    catalog_file = tmp_path / "postgres.txt"
    catalog_file.write_text(catalog_entry_yaml("postgres"), encoding="utf-8")

    with pytest.raises(DiscoveryCatalogPathError, match=str(catalog_file)):
        YamlCatalogLoader().load_file(catalog_file)


def test_malformed_yaml_identifies_source_and_chains_error() -> None:
    with pytest.raises(DiscoveryCatalogYamlError, match="broken.yaml") as error_info:
        YamlCatalogLoader().load_text("item: [", source="broken.yaml")

    assert error_info.value.__cause__ is not None


def test_non_mapping_yaml_identifies_source() -> None:
    with pytest.raises(DiscoveryCatalogDocumentError, match="list.yaml"):
        YamlCatalogLoader().load_text("- one\n- two\n", source="list.yaml")


def test_invalid_model_yaml_identifies_source_and_chains_error() -> None:
    with pytest.raises(DiscoveryCatalogValidationError, match="invalid.yaml") as error_info:
        YamlCatalogLoader().load_text(
            """
schema_version: 1
item:
  id: Invalid
  type: service
  name: Invalid
provenance:
  source: app/discovery/catalog/invalid.yaml
""",
            source="invalid.yaml",
        )

    assert error_info.value.__cause__ is not None


def test_unsupported_schema_version_is_validation_error() -> None:
    with pytest.raises(DiscoveryCatalogValidationError, match="schema.yaml"):
        YamlCatalogLoader().load_text(
            catalog_entry_yaml("postgres").replace("schema_version: 1", "schema_version: 2"),
            source="schema.yaml",
        )


def test_duplicate_item_id_identifies_both_sources(tmp_path: Path) -> None:
    first = tmp_path / "a.yaml"
    second = tmp_path / "b.yaml"
    write_entry(first, "postgres", entry_id="postgres-a")
    write_entry(second, "postgres", entry_id="postgres-b")

    with pytest.raises(DiscoveryCatalogDuplicateError) as error_info:
        YamlCatalogLoader(tmp_path).load()

    message = str(error_info.value)
    assert "item.id 'postgres'" in message
    assert str(first) in message
    assert str(second) in message


def test_duplicate_non_null_entry_id_identifies_both_sources(tmp_path: Path) -> None:
    first = tmp_path / "a.yaml"
    second = tmp_path / "b.yaml"
    write_entry(first, "postgres", entry_id="shared-entry")
    write_entry(second, "redis", entry_id="shared-entry")

    with pytest.raises(DiscoveryCatalogDuplicateError) as error_info:
        YamlCatalogLoader(tmp_path).load()

    message = str(error_info.value)
    assert "provenance.entry_id 'shared-entry'" in message
    assert str(first) in message
    assert str(second) in message


def test_null_entry_ids_are_not_considered_duplicates(tmp_path: Path) -> None:
    first = tmp_path / "a.yaml"
    second = tmp_path / "b.yaml"
    first.write_text(catalog_entry_yaml("postgres").replace("  entry_id: postgres\n", ""), encoding="utf-8")
    second.write_text(catalog_entry_yaml("redis").replace("  entry_id: redis\n", ""), encoding="utf-8")

    catalog = YamlCatalogLoader(tmp_path).load()

    assert [entry.item.id for entry in catalog.entries] == ["postgres", "redis"]


def test_relationship_targets_are_not_cross_file_validated_in_d2() -> None:
    entry = YamlCatalogLoader().load_text(
        catalog_entry_yaml("app", relationship_target="missing-service"),
        source="relationship.yaml",
    )

    assert entry.item.relationships[0].target == "missing-service"
