"""Focused v0.14 P0 DeploymentBinding model, loader, and isolation tests.

P0 keeps DeploymentBinding strictly internal: no public API exposure, no
execution/Agent/proposal coupling, and no changes to dynamic projection,
cache, sources, refresh, or release evaluation.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.discovery import (
    CATALOG_SCHEMA_VERSION,
    CatalogEntry,
    CatalogProvenance,
    DeploymentBinding,
    DiscoveryCatalogDuplicateError,
    DiscoveryCatalogValidationError,
    DiscoveryItem,
    DiscoveryItemType,
    YamlCatalogLoader,
)
from app.discovery.api_models import DiscoveryCatalogEntryResponse


def item(**overrides: object) -> DiscoveryItem:
    data: dict[str, object] = {
        "id": "postgres",
        "type": DiscoveryItemType.SERVICE,
        "name": "PostgreSQL",
    }
    data.update(overrides)
    return DiscoveryItem(**data)


def provenance(
    *,
    source_type: str = "curated",
    trust_level: str = "curated",
) -> CatalogProvenance:
    return CatalogProvenance(
        source_type=source_type,
        source="app/discovery/catalog/postgres.yaml",
        trust_level=trust_level,
    )


def binding(**overrides: object) -> DeploymentBinding:
    data: dict[str, object] = {
        "compose_file": "compose.synthetic.yaml",
        "compose_service": "synthetic-service",
        "mutable_property": "image",
        "deployment_method": "docker-compose",
    }
    data.update(overrides)
    return DeploymentBinding(**data)


def entry(
    *,
    provenance: CatalogProvenance | None = None,
    deployment_binding: DeploymentBinding | None = ...,  # type: ignore[valid-type]
) -> CatalogEntry:
    data: dict[str, object] = {
        "item": item(),
        "provenance": provenance or CatalogProvenance(source="catalog/postgres.yaml"),
    }
    if deployment_binding is not ...:
        data["deployment_binding"] = deployment_binding
    return CatalogEntry(**data)


def catalog_entry_yaml(item_id: str, *, binding_yaml: str = "") -> str:
    return f"""
schema_version: 1
item:
  id: {item_id}
  type: service
  status: active
  name: {item_id.title()}
  description: Test catalog item.
  capabilities:
    - id: {item_id}-capability
provenance:
  source_type: curated
  source: app/discovery/catalog/{item_id}.yaml
  entry_id: {item_id}
  trust_level: curated
{binding_yaml}"""


def test_deployment_binding_carries_only_frozen_fields() -> None:
    dumped = binding().model_dump()

    assert dumped == {
        "compose_file": "compose.synthetic.yaml",
        "compose_service": "synthetic-service",
        "mutable_property": "image",
        "deployment_method": "docker-compose",
    }


def test_deployment_binding_defaults_are_docker_compose_image() -> None:
    binding_ = DeploymentBinding(
        compose_file="deploy/rest-server/compose.yaml",
        compose_service="rest-server",
    )

    assert binding_.mutable_property == "image"
    assert binding_.deployment_method == "docker-compose"


def test_deployment_binding_rejects_executable_or_unspecified_fields() -> None:
    forbidden = (
        "execution_intent",
        "expected_value",
        "desired_value",
        "image",
        "image_tag",
        "tag",
        "command",
        "target_id",
        "approval_level",
    )
    for field_name in forbidden:
        with pytest.raises(ValidationError):
            binding(**{field_name: "value"})

    with pytest.raises(ValidationError):
        binding(mutable_property="replicas")

    with pytest.raises(ValidationError):
        binding(deployment_method="kubernetes")


@pytest.mark.parametrize(
    "compose_file",
    [
        "compose.production.yaml",
        "deploy/rest-server/compose.yaml",
        "nested/deep/path/to/compose.yml",
    ],
)
def test_valid_compose_file_paths_accepted(compose_file: str) -> None:
    binding_ = DeploymentBinding(compose_file=compose_file, compose_service="svc")

    assert binding_.compose_file == compose_file


@pytest.mark.parametrize(
    "compose_file",
    [
        "../compose.yaml",
        "../../compose.yaml",
        "sub/../compose.yaml",
        "sub/./compose.yaml",
        "sub//compose.yaml",
        "./compose.yaml",
        "/absolute/compose.yaml",
        "~/home/compose.yaml",
        "C:/windows/compose.yaml",
        "c\\windows\\compose.yaml",
        "compose\\production.yaml",
        " compose.yaml",
        "compose.yaml ",
        "compose.yaml\t",
        "compose.yml\n",
        "compose.txt",
        "compose",
        "compose.yamlx",
        "COMPOSE.YAML",
        "deploy/Compose.Yml",
        "a" * 513 + ".yaml",
        "/".join(["seg"] * 33) + "/compose.yaml",
        "",
    ],
)
def test_invalid_compose_file_paths_rejected(compose_file: str) -> None:
    with pytest.raises(ValidationError, match="compose_file"):
        DeploymentBinding(compose_file=compose_file, compose_service="svc")


@pytest.mark.parametrize(
    "compose_service",
    [
        "atlas-agent",
        "atlas_core",
        "svc-2",
        "a.b-c_1",
    ],
)
def test_valid_compose_service_identifiers_accepted(compose_service: str) -> None:
    binding_ = DeploymentBinding(
        compose_file="compose.yaml",
        compose_service=compose_service,
    )

    assert binding_.compose_service == compose_service


@pytest.mark.parametrize(
    "compose_service",
    [
        "Atlas Agent",
        "Atlas-Agent",
        "atlas.agent:latest",
        "atlas-agent/",
        "/atlas-agent",
        "-atlas",
        ".atlas",
        "atlas agent",
        " atlas-agent",
        "atlas-agent ",
        "a" * 256,
        "",
    ],
)
def test_invalid_compose_service_identifiers_rejected(compose_service: str) -> None:
    with pytest.raises(ValidationError, match="compose_service"):
        DeploymentBinding(compose_file="compose.yaml", compose_service=compose_service)


def test_deployment_binding_is_immutable() -> None:
    binding_ = binding()

    with pytest.raises(ValidationError, match="frozen"):
        binding_.compose_file = "other.yaml"  # type: ignore[misc]


def test_catalog_entry_deployment_binding_defaults_to_none() -> None:
    catalog_entry = entry()

    assert catalog_entry.deployment_binding is None


def test_catalog_entry_accepts_valid_deployment_binding() -> None:
    catalog_entry = entry(deployment_binding=binding())

    assert catalog_entry.deployment_binding.compose_file == "compose.synthetic.yaml"
    assert catalog_entry.deployment_binding.compose_service == "synthetic-service"


def test_deployment_binding_not_allowed_on_non_curated_source_type() -> None:
    for source_type, trust_level in (
        ("private", "curated"),
        ("community", "curated"),
        ("dynamic", "curated"),
    ):
        with pytest.raises(
            ValidationError,
            match="source_type and trust_level 'curated'",
        ):
            entry(
                provenance=provenance(
                    source_type=source_type,
                    trust_level=trust_level,
                ),
                deployment_binding=binding(),
            )


def test_deployment_binding_not_allowed_on_non_curated_trust_level() -> None:
    for source_type, trust_level in (
        ("curated", "verified"),
        ("curated", "community"),
        ("curated", "private"),
        ("curated", "dynamic"),
    ):
        with pytest.raises(
            ValidationError,
            match="source_type and trust_level 'curated'",
        ):
            entry(
                provenance=provenance(
                    source_type=source_type,
                    trust_level=trust_level,
                ),
                deployment_binding=binding(),
            )


def test_deployment_binding_allowed_for_curated_curated_entries() -> None:
    catalog_entry = entry(deployment_binding=binding())

    assert catalog_entry.deployment_binding is not None


def test_non_curated_entries_without_binding_remain_valid() -> None:
    for source_type, trust_level in (
        ("private", "private"),
        ("community", "community"),
        ("dynamic", "dynamic"),
        ("curated", "verified"),
    ):
        catalog_entry = entry(
            provenance=provenance(
                source_type=source_type,
                trust_level=trust_level,
            )
        )

        assert catalog_entry.deployment_binding is None


def test_loader_rejects_deployment_binding_extra_fields(tmp_path: Path) -> None:
    catalog_file = tmp_path / "postgres.yaml"
    catalog_file.write_text(
        catalog_entry_yaml(
            "postgres",
            binding_yaml=(
                "deployment_binding:\n"
                "  compose_file: compose.production.yaml\n"
                "  compose_service: atlas-agent\n"
                "  expected_value: latest\n"
            ),
        ),
        encoding="utf-8",
    )

    with pytest.raises(DiscoveryCatalogValidationError, match="expected_value"):
        YamlCatalogLoader(tmp_path).load()


def test_loader_rejects_deployment_binding_on_non_curated_entry(tmp_path: Path) -> None:
    catalog_file = tmp_path / "postgres.yaml"
    text = (
        catalog_entry_yaml(
            "postgres",
            binding_yaml="deployment_binding:\n"
            "  compose_file: compose.yaml\n"
            "  compose_service: svc\n",
        )
        .replace("  source_type: curated", "  source_type: community")
        .replace("  trust_level: curated", "  trust_level: community")
    )
    catalog_file.write_text(text, encoding="utf-8")

    with pytest.raises(DiscoveryCatalogValidationError, match="curated"):
        YamlCatalogLoader(tmp_path).load()


def test_loader_rejects_duplicate_deployment_bindings_deterministically(
    tmp_path: Path,
) -> None:
    binding_yaml = (
        "deployment_binding:\n"
        "  compose_file: compose.production.yaml\n"
        "  compose_service: atlas-agent\n"
        "  mutable_property: image\n"
        "  deployment_method: docker-compose\n"
    )
    first = tmp_path / "a" / "postgres.yaml"
    second = tmp_path / "b" / "redis.yaml"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text(
        catalog_entry_yaml("postgres", binding_yaml=binding_yaml), encoding="utf-8"
    )
    second.write_text(
        catalog_entry_yaml("redis", binding_yaml=binding_yaml), encoding="utf-8"
    )

    with pytest.raises(DiscoveryCatalogDuplicateError) as error_info:
        YamlCatalogLoader(tmp_path).load()

    message = str(error_info.value)
    assert "compose_file='compose.production.yaml'" in message
    assert "compose_service='atlas-agent'" in message
    assert str(first) in message
    assert str(second) in message


def test_loader_allows_distinct_deployment_bindings(tmp_path: Path) -> None:
    first = tmp_path / "a" / "postgres.yaml"
    second = tmp_path / "b" / "redis.yaml"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text(
        catalog_entry_yaml(
            "postgres",
            binding_yaml=(
                "deployment_binding:\n"
                "  compose_file: compose.a.yaml\n"
                "  compose_service: shared-service\n"
            ),
        ),
        encoding="utf-8",
    )
    second.write_text(
        catalog_entry_yaml(
            "redis",
            binding_yaml=(
                "deployment_binding:\n"
                "  compose_file: compose.a.yaml\n"
                "  compose_service: other-service\n"
            ),
        ),
        encoding="utf-8",
    )

    catalog = YamlCatalogLoader(tmp_path).load()

    assert [entry.item.id for entry in catalog.entries] == ["postgres", "redis"]
    assert all(entry.deployment_binding is not None for entry in catalog.entries)


def test_loader_rejects_traversal_compose_file(tmp_path: Path) -> None:
    catalog_file = tmp_path / "postgres.yaml"
    catalog_file.write_text(
        catalog_entry_yaml(
            "postgres",
            binding_yaml=(
                "deployment_binding:\n"
                "  compose_file: ../compose.yaml\n"
                "  compose_service: svc\n"
            ),
        ),
        encoding="utf-8",
    )

    with pytest.raises(DiscoveryCatalogValidationError, match="compose_file"):
        YamlCatalogLoader(tmp_path).load()


def test_existing_unbound_catalog_yaml_remains_valid() -> None:
    document = yaml.safe_load(catalog_entry_yaml("postgres").rstrip() + "\n")

    catalog_entry = CatalogEntry.model_validate(document)

    assert catalog_entry.deployment_binding is None
    assert catalog_entry.schema_version == CATALOG_SCHEMA_VERSION


def test_p0_public_api_projection_has_no_deployment_binding() -> None:
    assert "deployment_binding" not in DiscoveryCatalogEntryResponse.model_fields
    assert "deployment_binding" not in DiscoveryCatalogEntryResponse.model_json_schema()

    projected = entry(deployment_binding=binding()).model_dump()
    assert "deployment_binding" in projected
    # The public API projection consumes only the P0 public entry fields.
    projected.pop("deployment_binding")
    projected.pop("release_claim")

    response = DiscoveryCatalogEntryResponse.model_validate(projected)

    assert "deployment_binding" not in response.model_dump()


def test_p0_deployment_binding_has_no_execution_agent_or_planning_coupling() -> None:
    # Module names are assembled at runtime so that this test file itself is
    # not picked up by the per-module reference scans in the dynamic
    # isolation test suite.
    dynamic_prefix = "dynamic"
    modules_with_expected_isolation = (
        f"app.discovery.{dynamic_prefix}_projection",
        f"app.discovery.{dynamic_prefix}_cache",
        f"app.discovery.{dynamic_prefix}_sources",
        f"app.discovery.{dynamic_prefix}_refresh",
        "app.discovery.release_evaluation",
        "app.discovery.proposals",
        "app.discovery.api_models",
        "app.discovery.repository",
        "app.discovery.search",
        "app.services.discovery_proposals",
        "app.routes.discovery",
    )
    for module_name in modules_with_expected_isolation:
        source = Path(importlib.import_module(module_name).__file__).read_text(
            encoding="utf-8"
        )
        assert "deployment_binding" not in source, module_name
        assert "DeploymentBinding" not in source, module_name

    assert "deployment_binding" not in DiscoveryCatalogEntryResponse.model_fields

    import app.api.v1 as v1_package

    v1_source = Path(v1_package.__file__).read_text(encoding="utf-8")
    assert "deployment_binding" not in v1_source


def test_shipped_builtin_catalog_has_only_reviewed_home_assistant_binding() -> None:
    """Regression guard: all other catalog entries remain unbound."""
    catalog = YamlCatalogLoader().load()

    assert len(catalog.entries) > 0
    for entry in catalog.entries:
        if entry.item.id == "home-assistant":
            assert entry.deployment_binding is not None
        else:
            assert entry.deployment_binding is None, entry.item.id


def test_catalog_entry_release_baseline_stays_unchanged() -> None:
    catalog_entry = YamlCatalogLoader().load_file(
        Path(__file__).parent / "catalog" / "services" / "atlas-agent.yaml"
    )

    assert catalog_entry.release_claim is None
    assert catalog_entry.item.version is None
