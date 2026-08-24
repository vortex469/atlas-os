"""v0.14 P1c repository compose-observation isolation tests.

P1c ships a core-only acquirer with no production consumer and no public
export. These AST-level guards pin that contract: filesystem reads only,
no network, clock, subprocess, cache, write, or Agent/execution/planning/
provider/proposal coupling, and no shipped deployment bindings.
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.discovery.loader import YamlCatalogLoader
from app.discovery.models import DeploymentBinding, RepositoryComposeImageObservation

_MODULE_NAME = "repository_compose_observation"
_MODULE_TEST_NAMES = {
    "test_repository_compose_observation.py",
    "test_repository_compose_observation_isolation.py",
    "home_assistant_image_grounding.py",
    "test_home_assistant_image_grounding.py",
    "test_home_assistant_image_grounding_isolation.py",
    "image_grounding_read_model.py",
    "test_image_grounding_read_model.py",
    "test_image_grounding_read_model_isolation.py",
}


def _module_tree() -> ast.Module:
    path = Path(__file__).with_name(f"{_MODULE_NAME}.py")
    return ast.parse(path.read_text(encoding="utf-8"))


def _imported_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names.update(alias.name for alias in node.names if alias.name != "*")
    return names


def test_module_imports_are_filesystem_and_contract_only() -> None:
    """The acquirer may only import the standard library, yaml, and
    Discovery contract modules."""

    tree = _module_tree()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name in {
                    "__future__",
                    "pathlib",
                    "typing",
                    "yaml",
                }, f"unexpected acquirer import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert module.startswith("app.discovery.") or module in {
                "yaml",
                "yaml.nodes",
                "__future__",
                "pathlib",
                "typing",
            }, f"unexpected acquirer import: {module}"


def test_module_has_no_forbidden_runtime_capabilities() -> None:
    """AST-level guard: no network, clock, subprocess, write, cache, or
    Agent/execution/planning/proposal/provider-intent/backup capability
    references in the acquirer module."""

    tree = _module_tree()
    imported_names = _imported_names(tree)

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
        "shutil",
        "tempfile",
        "sqlite",
        "cache",
        "oci",
        "ghcr",
        "agent",
        "execution",
        "planning",
        "proposal",
        "routes",
        "api",
        "backup",
        "recovery",
        "provider_intent",
        "providers",
        "credential",
        "secrets",
    }
    for name in imported_names:
        lowered = name.lower()
        for forbidden in forbidden_substrings:
            assert forbidden not in lowered, (
                f"acquirer references forbidden capability: {forbidden!r} in "
                f"import {name!r}"
            )

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
            raise AssertionError(
                f"acquirer references forbidden attribute {node.attr!r}"
            )

    # The module never opens a file for writing of any kind.
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "open"
        ):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    assert "w" not in arg.value and "a" not in arg.value, (
                        "acquirer must not open files for writing or appending"
                    )


def test_module_is_not_wired_into_any_production_module() -> None:
    """No production module outside the P1c acquirer and its tests
    references it: P1c has no production consumer."""

    app_dir = Path(__file__).parents[1]
    references = []
    for path in app_dir.rglob("*.py"):
        if path.name in _MODULE_TEST_NAMES or path.name == f"{_MODULE_NAME}.py":
            continue
        if _MODULE_NAME in path.read_text(encoding="utf-8"):
            references.append(path.relative_to(app_dir).as_posix())
    assert references == []


def test_module_is_not_exported_from_public_api() -> None:
    """app/discovery/__init__.py is unmodified: the P1c acquirer remains
    unexported, and no public API module references it."""

    init_path = Path(__file__).with_name("__init__.py")
    init_source = init_path.read_text(encoding="utf-8")
    assert _MODULE_NAME not in init_source
    assert "RepositoryComposeImageObservationAcquirer" not in init_source
    assert "MAX_COMPOSE_FILE_BYTES" not in init_source

    api_dir = Path(__file__).parents[1] / "api"
    if api_dir.is_dir():
        for path in api_dir.rglob("*.py"):
            assert _MODULE_NAME not in path.read_text(encoding="utf-8")

    routes_dir = Path(__file__).parents[1] / "routes"
    if routes_dir.is_dir():
        for path in routes_dir.rglob("*.py"):
            assert _MODULE_NAME not in path.read_text(encoding="utf-8")


def test_only_reviewed_home_assistant_deployment_binding_is_shipped() -> None:
    """P1c remains unchanged; composition adds one reviewed consumer."""

    catalog = YamlCatalogLoader().load()
    assert len(catalog.entries) > 0
    for entry in catalog.entries:
        if entry.item.id == "home-assistant":
            assert entry.deployment_binding is not None
        else:
            assert entry.deployment_binding is None, entry.item.id


def test_observable_contract_field_sets_remain_unchanged() -> None:
    """The P1a observation model and P0 binding model keep their exact
    frozen field sets: no schema_version or deployment_method is added to
    the observation, and no runtime conditional compatibility layer exists."""

    assert list(RepositoryComposeImageObservation.model_fields) == [
        "compose_file",
        "compose_service",
        "image",
    ]
    assert "schema_version" not in RepositoryComposeImageObservation.model_fields
    assert "deployment_method" not in RepositoryComposeImageObservation.model_fields

    assert list(DeploymentBinding.model_fields) == [
        "compose_file",
        "compose_service",
        "mutable_property",
        "deployment_method",
    ]
