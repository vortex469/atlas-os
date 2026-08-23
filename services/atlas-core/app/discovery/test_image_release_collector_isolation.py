"""v0.14 P1b-collector first-slice isolation tests.

The image-release acquisition boundary ships as an unexported, un-wired module
with EMPTY production descriptor and adapter registries. These AST- and import-
level guards pin that contract so a future edit cannot quietly introduce:

* a filesystem write, cache, persistence, or clock dependency;
* a subprocess, credential, or secret path;
* coupling to the Agent / execution / planning / proposal / provider pipeline;
* coupling to the loader, grounding, dynamic-source, or registry machinery;
* a production wiring point or a public export;
* a change to the immutable ``ImageReleaseEvidence`` contract field set.

The collector is network-capable BY DESIGN (that is the point of the slice);
the transport module is therefore allowed its narrow stdlib + pydantic import
set. Everything else is forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.discovery.image_release_collector import (
    PRODUCTION_DESCRIPTORS,
    PRODUCTION_SOURCE_ADAPTERS,
    ImageReleaseCollector,
)
from app.discovery.models import (
    ImageReleaseEvidence,
    ImageReleaseEvidenceSourceClass,
)

_COLLECTOR_MODULE = "image_release_collector"
_TRANSPORT_MODULE = "image_release_collector_transport"

# Every file this first slice owns, plus this test module. Nothing outside this
# set may reference the collector.
_OWNED_FILE_NAMES = {
    f"{_COLLECTOR_MODULE}.py",
    f"{_TRANSPORT_MODULE}.py",
    "test_image_release_collector.py",
    "test_image_release_collector_isolation.py",
}


def _module_tree(module_name: str) -> ast.Module:
    path = Path(__file__).with_name(f"{module_name}.py")
    return ast.parse(path.read_text(encoding="utf-8"))


def _import_origins(tree: ast.Module) -> set[str]:
    """The set of every module the file imports (Import names + ImportFrom
    modules)."""

    origins: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            origins.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            origins.add(node.module or "")
    return origins


# ---------------------------------------------------------------------------
# Collector module: import allowlist + capability guards
# ---------------------------------------------------------------------------


def test_collector_module_imports_are_contract_only() -> None:
    """The collector may import only the standard library, pydantic, and the
    three Discovery contract modules it legitimately depends on (exceptions,
    models, and its own transport). Nothing else."""

    allowed = {
        "__future__",
        "asyncio",
        "re",
        "collections.abc",
        "datetime",
        "enum",
        "typing",
        "pydantic",
        "app.discovery.exceptions",
        "app.discovery.models",
        f"app.discovery.{_TRANSPORT_MODULE}",
    }
    for origin in _import_origins(_module_tree(_COLLECTOR_MODULE)):
        assert origin in allowed, f"unexpected collector import: {origin!r}"


def test_collector_has_no_forbidden_capability_substrings() -> None:
    """No import in the collector may name a loader, grounding, dynamic-source,
    registry, Agent/execution/planning/proposal, provider, route, backup,
    credential, secret, subprocess, cache, persistence, or third-party
    network-library capability."""

    forbidden_substrings = {
        "loader",
        "grounding",
        "dynamic",
        "registry",
        "catalog",
        "routes",
        "api",
        "agent",
        "execution",
        "planning",
        "proposal",
        "approval",
        "policy",
        "backup",
        "recovery",
        "migration",
        "credential",
        "secret",
        "provider",
        "subprocess",
        "shutil",
        "tempfile",
        "sqlite",
        "database",
        "cache",
        "os",
        "urllib",
        "requests",
        "httpx",
        "aiohttp",
        "websocket",
    }
    for origin in _import_origins(_module_tree(_COLLECTOR_MODULE)):
        lowered = origin.lower()
        for forbidden in forbidden_substrings:
            assert forbidden not in lowered, (
                f"collector references forbidden capability {forbidden!r} via "
                f"import {origin!r}"
            )


def _assert_no_filesystem_writes(module_name: str) -> None:
    """The module must never open a file for writing or touch the filesystem.
    Network sockets are written through the async stream API (``write``), which
    is distinct from the filesystem-write attributes below."""

    tree = _module_tree(module_name)
    # NOTE: subprocess.run is already pinned out at the import level (both
    # modules forbid importing subprocess); the ``asyncio.run`` used by the
    # collector's sync API is legitimate, so a bare ``run`` attribute is not
    # treated as a write here.
    forbidden_attributes = {
        "write_text",
        "write_bytes",
        "writestr",
        "writelines",
        "mkdir",
        "makedirs",
        "rmdir",
        "unlink",
        "rename",
        "replace",
        "rmtree",
        "move",
        "copy",
        "copytree",
        "Popen",
        "popen",
        "check_call",
        "check_output",
        "create_connection",
        "urlopen",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr not in forbidden_attributes, (
                f"{module_name} references forbidden attribute {node.attr!r}"
            )
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "open"
        ):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    assert "w" not in arg.value and "a" not in arg.value, (
                        f"{module_name} opens a file for writing or appending"
                    )


def test_collector_module_has_no_filesystem_writes() -> None:
    _assert_no_filesystem_writes(_COLLECTOR_MODULE)


# ---------------------------------------------------------------------------
# Transport module: import allowlist + capability guards
# ---------------------------------------------------------------------------


def test_transport_module_imports_are_stdlib_and_pydantic_only() -> None:
    """The transport may import only the standard library (the narrow set it
    needs for a bounded HTTPS GET) and pydantic. No Discovery module, no
    third-party network library, no filesystem, clock, or subprocess module."""

    allowed = {
        "__future__",
        "asyncio",
        "ipaddress",
        "json",
        "re",
        "socket",
        "ssl",
        "collections.abc",
        "typing",
        "pydantic",
    }
    for origin in _import_origins(_module_tree(_TRANSPORT_MODULE)):
        assert origin in allowed, f"unexpected transport import: {origin!r}"


def test_transport_has_no_forbidden_capability_substrings() -> None:
    """No import in the transport may name a clock, filesystem-write,
    subprocess, credential, secret, cache, persistence, Agent/execution/
    planning/proposal, provider, route, or third-party-network capability."""

    forbidden_substrings = {
        "time",
        "datetime",
        "calendar",
        "loader",
        "grounding",
        "dynamic",
        "registry",
        "routes",
        "api",
        "agent",
        "execution",
        "planning",
        "proposal",
        "approval",
        "policy",
        "backup",
        "recovery",
        "migration",
        "credential",
        "secret",
        "provider",
        "subprocess",
        "shutil",
        "tempfile",
        "sqlite",
        "database",
        "cache",
        "os",
        "urllib",
        "requests",
        "httpx",
        "aiohttp",
        "websocket",
        "pathlib",
    }
    for origin in _import_origins(_module_tree(_TRANSPORT_MODULE)):
        lowered = origin.lower()
        for forbidden in forbidden_substrings:
            assert forbidden not in lowered, (
                f"transport references forbidden capability {forbidden!r} via "
                f"import {origin!r}"
            )


def test_transport_module_has_no_filesystem_writes() -> None:
    _assert_no_filesystem_writes(_TRANSPORT_MODULE)


# ---------------------------------------------------------------------------
# No production wiring, no public export
# ---------------------------------------------------------------------------


def test_collector_is_not_wired_into_any_production_module() -> None:
    """No module outside the first-slice file set references the collector or
    its transport: there is no production consumer in this slice."""

    app_dir = Path(__file__).parents[1]
    references = []
    for path in app_dir.rglob("*.py"):
        if path.name in _OWNED_FILE_NAMES:
            continue
        source = path.read_text(encoding="utf-8")
        if _COLLECTOR_MODULE in source or _TRANSPORT_MODULE in source:
            references.append(path.relative_to(app_dir).as_posix())
    assert references == []


def test_collector_is_not_exported_from_public_api() -> None:
    """app/discovery/__init__.py is unmodified, and no api/ or routes/ module
    references the collector."""

    init_source = Path(__file__).with_name("__init__.py").read_text(encoding="utf-8")
    assert _COLLECTOR_MODULE not in init_source
    assert _TRANSPORT_MODULE not in init_source
    assert "ImageReleaseCollector" not in init_source
    assert "PinnedHTTPS" not in init_source

    for sub in ("api", "routes"):
        sub_dir = Path(__file__).parents[1] / sub
        if sub_dir.is_dir():
            for path in sub_dir.rglob("*.py"):
                source = path.read_text(encoding="utf-8")
                assert _COLLECTOR_MODULE not in source
                assert _TRANSPORT_MODULE not in source


# ---------------------------------------------------------------------------
# Behavioral pins: empty production registries, stable contract
# ---------------------------------------------------------------------------


def test_production_registries_are_empty() -> None:
    """The shipped production descriptor and adapter registries are empty; the
    production collector therefore has nothing to fetch and no I/O path."""

    assert dict(PRODUCTION_DESCRIPTORS) == {}
    assert dict(PRODUCTION_SOURCE_ADAPTERS) == {}

    collector = ImageReleaseCollector.production()
    assert dict(collector._descriptors) == {}
    assert dict(collector._adapters) == {}


def test_contract_field_sets_remain_unchanged() -> None:
    """The collector must not reshape the immutable ImageReleaseEvidence
    contract or its source-class vocabulary: it only produces rows against the
    existing model."""

    assert list(ImageReleaseEvidence.model_fields) == [
        "catalog_item_id",
        "release_version",
        "image_reference",
        "image_digest",
        "source_class",
        "source_id",
        "attested_at",
    ]

    assert [cls.value for cls in ImageReleaseEvidenceSourceClass] == [
        "curated",
        "registry_attested",
        "upstream_signed",
    ]
