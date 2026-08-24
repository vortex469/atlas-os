from __future__ import annotations

import ast
from pathlib import Path

from app.discovery import DEFAULT_DISCOVERY_CATALOG_DIR
from app.discovery.image_release_evidence_loader import (
    DEFAULT_IMAGE_RELEASE_EVIDENCE_DIR,
    ImageReleaseEvidenceLoader,
)
from app.discovery.loader import YamlCatalogLoader

_LOADER_NAME = "image_release_evidence_loader"
_LOADER_TEST_NAMES = {
    "home_assistant_image_grounding.py",
    "home_assistant_image_evidence_provenance.py",
    "test_home_assistant_image_evidence_provenance.py",
    "test_home_assistant_image_evidence_provenance_isolation.py",
    "test_home_assistant_image_grounding.py",
    "test_home_assistant_image_grounding_isolation.py",
    "test_home_assistant_registry_attested_promotion.py",
    "test_image_release_evidence_loader.py",
    "test_image_release_evidence_isolation.py",
}


def _loader_tree() -> ast.Module:
    path = Path(__file__).with_name(f"{_LOADER_NAME}.py")
    return ast.parse(path.read_text(encoding="utf-8"))


def test_loader_imports_are_filesystem_and_contract_only() -> None:
    """The loader may only import the standard library, yaml, pydantic,
    and Discovery contract modules."""

    tree = _loader_tree()
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")

    allowed_prefixes = ("app.discovery.",)
    allowed_exact = {
        "__future__",
        "pathlib",
        "typing",
        "yaml",
        "pydantic",
    }
    for name in imports:
        assert name in allowed_exact or name.startswith(allowed_prefixes), (
            f"unexpected loader import: {name}"
        )


def test_loader_has_no_forbidden_runtime_capabilities() -> None:
    """AST-level guard: no network, clock, subprocess, write, cache, or
    execution/planning/route/proposal/agent/provider-intent/backup
    capability references in the loader module."""

    tree = _loader_tree()
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_names.add(node.module or "")
            imported_names.update(
                alias.name for alias in node.names if alias.name != "*"
            )

    forbidden_substrings = {
        "socket",
        "urllib",
        "http",
        "requests",
        "httpx",
        "aiohttp",
        "websocket",
        "time",
        "datetime",
        "calendar",
        "subprocess",
        "os",
        "shutil",
        "tempfile",
        "sqlite",
        "cache",
        "oci",
        "ghcr",
        "github",
        "agent",
        "execution",
        "planning",
        "proposals",
        "proposals_",
        "routes",
        "api",
        "backup",
        "recovery",
        "provider_intent",
        "providers",
        "registry",
        "credential",
        "secrets",
    }
    for name in imported_names:
        lowered = name.lower()
        for forbidden in forbidden_substrings:
            assert forbidden not in lowered, (
                f"loader references forbidden capability: {forbidden!r} in "
                f"import {name!r}"
            )

    # No write-capable call attributes anywhere in the loader module.
    forbidden_call_attributes = {
        "write_text",
        "write_bytes",
        "mkdir",
        "rmdir",
        "unlink",
        "rename",
        "rmtree",
        "move",
        "copy",
        "copytree",
        "run",
        "Popen",
        "connect",
        "create_connection",
        "urlopen",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in forbidden_call_attributes:
            raise AssertionError(f"loader references forbidden attribute {node.attr!r}")


def test_loader_has_only_reviewed_read_only_composition_consumers() -> None:
    """Only separately reviewed local read-only compositions consume it."""

    app_dir = Path(__file__).parents[1]
    references = []
    for path in app_dir.rglob("*.py"):
        if path.name in _LOADER_TEST_NAMES or path.name == f"{_LOADER_NAME}.py":
            continue
        if _LOADER_NAME in path.read_text(encoding="utf-8"):
            references.append(path.relative_to(app_dir).as_posix())
    assert references == []


def test_loader_is_not_exported_from_public_api() -> None:
    """app/discovery/__init__.py is unmodified: the P1b loader remains
    unexported and inert, and no public API module imports it."""

    init_path = Path(__file__).with_name("__init__.py")
    init_source = init_path.read_text(encoding="utf-8")
    assert _LOADER_NAME not in init_source
    assert "ImageReleaseEvidenceLoader" not in init_source
    assert "CuratedImageReleaseEvidenceDocument" not in init_source
    assert "LoadedImageReleaseEvidence" not in init_source
    assert "DEFAULT_IMAGE_RELEASE_EVIDENCE_DIR" not in init_source

    api_dir = Path(__file__).parents[1] / "api"
    if api_dir.is_dir():
        for path in api_dir.rglob("*.py"):
            assert _LOADER_NAME not in path.read_text(encoding="utf-8")


def test_default_evidence_directory_ships_only_promoted_row() -> None:
    """The shipped directory contains only the reviewed promotion."""

    assert DEFAULT_IMAGE_RELEASE_EVIDENCE_DIR.is_dir()
    yaml_files = [
        path
        for path in DEFAULT_IMAGE_RELEASE_EVIDENCE_DIR.rglob("*")
        if path.suffix.lower() in {".yaml", ".yml"}
    ]
    assert [path.name for path in yaml_files] == ["2026.8.3-registry-attested.yaml"]

    result = ImageReleaseEvidenceLoader().load()
    assert len(result.rows) == 1
    assert result.rows[0].source_id == "collector:home-assistant-ghcr-cosign"
    assert result.rows[0].source_class.value == "registry_attested"


def test_ordinary_load_performs_no_filesystem_writes(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("ordinary evidence loading crossed an isolation boundary")

    monkeypatch.setattr(Path, "write_text", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)

    result = ImageReleaseEvidenceLoader().load()
    assert len(result.rows) == 1


def test_evidence_loader_remains_independent_of_reviewed_binding() -> None:
    """P1b remains unchanged by the sole reviewed composition binding."""

    catalog = YamlCatalogLoader().load()
    assert len(catalog.entries) > 0
    for entry in catalog.entries:
        if entry.item.id == "home-assistant":
            assert entry.deployment_binding is not None
        else:
            assert entry.deployment_binding is None, entry.item.id


def test_no_frigate_evidence_row_is_shipped() -> None:
    """P1b ships no curated evidence for any item, and specifically no
    Frigate evidence row or reference may appear in the evidence
    directory."""

    for path in DEFAULT_IMAGE_RELEASE_EVIDENCE_DIR.rglob("*"):
        if path.is_file():
            content = path.read_text(encoding="utf-8")
            assert "frigate" not in content.lower()

    result = ImageReleaseEvidenceLoader().load()
    assert all(row.catalog_item_id != "frigate" for row in result.rows)


def test_default_catalog_and_evidence_dirs_are_distinct() -> None:
    assert DEFAULT_IMAGE_RELEASE_EVIDENCE_DIR != DEFAULT_DISCOVERY_CATALOG_DIR
    assert (
        DEFAULT_IMAGE_RELEASE_EVIDENCE_DIR.resolve()
        != DEFAULT_DISCOVERY_CATALOG_DIR.resolve()
    )
