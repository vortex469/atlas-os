from __future__ import annotations

import ast
import inspect
from pathlib import Path

import app.discovery.home_assistant_ghcr_acquisition as acquisition


def test_module_is_private_and_unregistered() -> None:
    package = Path(__file__).parent
    assert (
        "home_assistant_ghcr_acquisition" not in (package / "__init__.py").read_text()
    )
    assert acquisition.__all__ if hasattr(acquisition, "__all__") else True
    assert not any(name.startswith("HomeAssistant") for name in vars(acquisition))


def test_no_import_or_construction_io(monkeypatch) -> None:
    called = False

    async def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError

    monkeypatch.setattr(acquisition, "_resolve", forbidden)
    instance = acquisition._HomeAssistantGHCRAcquirer()
    assert instance is not None
    assert not called


def test_no_forbidden_process_filesystem_or_credentials() -> None:
    source = inspect.getsource(acquisition)
    tree = ast.parse(source)
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not imported & {"subprocess", "requests", "docker", "pathlib", "os"}
    for forbidden in (
        "cosign",
        "curl",
        "getenv",
        "environ",
        "ImageReleaseEvidence",
        "CollectionResult",
    ):
        assert forbidden not in source


def test_no_generic_collector_or_verifier_dependency() -> None:
    source = inspect.getsource(acquisition)
    assert "image_release_" + "collector" not in source
    imports = [
        node.module or ""
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
    ]
    assert not any("sigstore" in name for name in imports)
