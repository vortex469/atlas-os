from __future__ import annotations

import ast
import importlib
from pathlib import Path

from app.services import image_grounding_read_model as read_model

MODULE = "app.services.image_grounding_read_model"


def _tree() -> ast.Module:
    module = importlib.import_module(MODULE)
    return ast.parse(Path(module.__file__).read_text(encoding="utf-8"))


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_import_and_construction_perform_no_io(monkeypatch, tmp_path: Path) -> None:
    module = importlib.reload(importlib.import_module(MODULE))

    def forbidden(*args, **kwargs):
        raise AssertionError("construction performed I/O")

    monkeypatch.setattr(module.ImageReleaseEvidenceLoader, "load", forbidden)
    monkeypatch.setattr(module.YamlCatalogLoader, "load", forbidden)
    monkeypatch.setattr(
        module.RepositoryComposeImageObservationAcquirer,
        "observe",
        forbidden,
    )
    assert module.BindingDrivenImageGroundingService(tmp_path) is not None


def test_read_model_imports_only_reviewed_local_readers_and_contracts() -> None:
    imports = {
        node.module or ""
        for node in ast.walk(_tree())
        if isinstance(node, ast.ImportFrom)
    }
    assert imports == {
        "__future__",
        "enum",
        "pathlib",
        "pydantic",
        "app.discovery.image_grounding",
        "app.discovery.image_release_evidence_loader",
        "app.discovery.loader",
        "app.discovery.models",
        "app.discovery.repository_compose_observation",
    }


def test_no_network_collector_verifier_acquisition_or_authority_capability() -> None:
    tree = _tree()
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not calls & {
        "connect",
        "create_connection",
        "urlopen",
        "request",
        "run",
        "Popen",
        "collect",
        "collect_async",
        "verify",
        "refresh",
        "commit",
        "flush",
        "write_text",
        "write_bytes",
        "open",
    }


def test_evaluation_performs_no_persistence_or_filesystem_writes(
    monkeypatch, tmp_path: Path
) -> None:
    compose = tmp_path / "compose/home-assistant.yaml"
    compose.parent.mkdir()
    compose.write_text(
        "services:\n  home-assistant:\n    image: "
        "ghcr.io/home-assistant/home-assistant@sha256:"
        "14931c6b13756317849f46da1d01b45937a1150db66c081cfe529d48215943fe\n",
        encoding="utf-8",
    )
    before = _snapshot(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("read model attempted a filesystem write")

    monkeypatch.setattr(Path, "write_text", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    result = read_model.BindingDrivenImageGroundingService(tmp_path).get(
        "home-assistant"
    )

    assert result.grounding.status.value == "grounded"
    assert _snapshot(tmp_path) == before


def test_read_model_is_not_wired_to_routes_startup_or_public_exports() -> None:
    app_dir = Path(read_model.__file__).parents[1]
    module_name = MODULE.rsplit(".", 1)[-1]
    for directory in (app_dir / "routes", app_dir / "api"):
        if directory.is_dir():
            for path in directory.rglob("*.py"):
                assert module_name not in path.read_text(encoding="utf-8")
    assert module_name not in (app_dir / "main.py").read_text(encoding="utf-8")
    assert module_name not in (app_dir / "services/__init__.py").read_text(
        encoding="utf-8"
    )
