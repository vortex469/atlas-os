from __future__ import annotations

import ast
import importlib
from pathlib import Path

from app.discovery.image_grounding import ImageGroundingResult

MODULE = "app.services.home_assistant_image_grounding"


def _tree() -> ast.Module:
    module = importlib.import_module(MODULE)
    return ast.parse(Path(module.__file__).read_text(encoding="utf-8"))


def test_import_and_construction_perform_no_io(monkeypatch, tmp_path: Path) -> None:
    module = importlib.reload(importlib.import_module(MODULE))

    def forbidden(*args, **kwargs):
        raise AssertionError("construction performed I/O")

    monkeypatch.setattr(module.ImageReleaseEvidenceLoader, "load", forbidden)
    monkeypatch.setattr(module.YamlCatalogLoader, "load", forbidden)
    monkeypatch.setattr(
        module.RepositoryComposeImageObservationAcquirer, "observe", forbidden
    )
    service = module.HomeAssistantImageGroundingService(tmp_path)
    assert service is not None


def test_composition_has_no_operational_or_external_capabilities() -> None:
    tree = _tree()
    imports = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert imports == {
        "__future__",
        "pathlib",
        "app.discovery.image_grounding",
        "app.discovery.image_release_evidence_loader",
        "app.discovery.loader",
        "app.discovery.repository_compose_observation",
    }
    source = ast.unparse(tree).lower()
    for forbidden in (
        "subprocess",
        "socket",
        "http",
        "docker",
        "cosign",
        "curl",
        "credential",
        "collector",
        "sigstore",
        "proposal",
        "execution_candidate",
        "provider_intent",
        "restart",
        "pull",
        "write_text",
        "write_bytes",
    ):
        assert forbidden not in source


def test_service_returns_only_the_existing_informational_model(tmp_path: Path) -> None:
    target = tmp_path / "compose/home-assistant.yaml"
    target.parent.mkdir()
    target.write_text(
        "services:\n  home-assistant:\n    image: ghcr.io/home-assistant/home-assistant@sha256:14931c6b13756317849f46da1d01b45937a1150db66c081cfe529d48215943fe\n",
        encoding="utf-8",
    )
    result = (
        importlib.import_module(MODULE)
        .HomeAssistantImageGroundingService(tmp_path)
        .ground()
    )
    assert type(result) is ImageGroundingResult
    assert set(type(result).model_fields) == {
        "schema_version",
        "status",
        "catalog_item_id",
        "release_version",
        "image_reference",
        "image_digest",
        "reason",
    }


def test_composition_is_not_wired_to_startup_scheduler_routes_or_public_exports() -> (
    None
):
    app_dir = Path(__file__).parents[1]
    for directory in (app_dir / "routes", app_dir / "api"):
        if directory.is_dir():
            for path in directory.rglob("*.py"):
                assert MODULE.rsplit(".", 1)[-1] not in path.read_text(encoding="utf-8")
    assert MODULE.rsplit(".", 1)[-1] not in (
        app_dir / "services/__init__.py"
    ).read_text(encoding="utf-8")
    assert MODULE.rsplit(".", 1)[-1] not in (app_dir / "main.py").read_text(
        encoding="utf-8"
    )
