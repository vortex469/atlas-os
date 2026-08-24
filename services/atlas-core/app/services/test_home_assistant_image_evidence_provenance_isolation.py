from __future__ import annotations

import ast
import importlib
import socket
import subprocess
from pathlib import Path

from app.discovery import (
    home_assistant_registry_attested,
    home_assistant_sigstore_verifier,
    image_grounding,
)
from app.discovery.image_grounding import ImageGroundingResult
from app.discovery.image_release_evidence_loader import (
    DEFAULT_IMAGE_RELEASE_EVIDENCE_DIR,
)
from app.discovery.loader import DEFAULT_DISCOVERY_CATALOG_DIR

MODULE = "app.services.home_assistant_image_evidence_provenance"


def _tree() -> ast.Module:
    module = importlib.import_module(MODULE)
    return ast.parse(Path(module.__file__).read_text(encoding="utf-8"))


def _snapshot(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def test_import_and_construction_perform_no_io(monkeypatch) -> None:
    module = importlib.reload(importlib.import_module(MODULE))

    def forbidden(*args, **kwargs):
        raise AssertionError("import or construction performed I/O")

    monkeypatch.setattr(module.ImageReleaseEvidenceLoader, "load", forbidden)
    assert module.HomeAssistantImageEvidenceProvenanceService() is not None


def test_projection_has_no_external_or_operational_capabilities() -> None:
    tree = _tree()
    imports = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert imports == {
        "__future__",
        "datetime",
        "enum",
        "pydantic",
        "app.discovery.image_release_evidence_loader",
        "app.discovery.models",
    }
    source = ast.unparse(tree).lower()
    for forbidden in (
        "subprocess",
        "socket",
        "docker",
        "curl",
        "credential",
        "environ",
        "getenv",
        "secret",
        "collector.",
        "homeassistantregistryattestedadapter",
        "_homeassistantghcracquirer",
        "verify_home_assistant",
        "proposal",
        "execution_candidate",
        "provider_intent",
        "restart",
        "pull",
        "write_text",
        "write_bytes",
        "datetime.now",
    ):
        assert forbidden not in source


def test_get_performs_only_the_reviewed_local_read(monkeypatch) -> None:
    module = importlib.import_module(MODULE)
    evidence_before = _snapshot(DEFAULT_IMAGE_RELEASE_EVIDENCE_DIR)
    catalog_before = _snapshot(DEFAULT_DISCOVERY_CATALOG_DIR)

    def forbidden(*args, **kwargs):
        raise AssertionError("projection crossed an isolation boundary")

    for name in ("socket", "create_connection", "getaddrinfo", "gethostbyname"):
        monkeypatch.setattr(socket, name, forbidden)
    for name in ("run", "Popen", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, forbidden)
    monkeypatch.setattr(
        home_assistant_sigstore_verifier,
        "verify_home_assistant_2026_8_3_bundle",
        forbidden,
    )
    monkeypatch.setattr(
        home_assistant_registry_attested.HomeAssistantRegistryAttestedAdapter,
        "collect",
        forbidden,
    )
    monkeypatch.setattr(image_grounding, "ground_deployment_image", forbidden)

    result = module.HomeAssistantImageEvidenceProvenanceService().get()

    assert result.verification_profile_id == ("home-assistant-ghcr-cosign-2026.8.3-v1")
    assert _snapshot(DEFAULT_IMAGE_RELEASE_EVIDENCE_DIR) == evidence_before
    assert _snapshot(DEFAULT_DISCOVERY_CATALOG_DIR) == catalog_before


def test_grounding_contract_is_unchanged_and_projection_has_no_authority() -> None:
    assert set(ImageGroundingResult.model_fields) == {
        "schema_version",
        "status",
        "catalog_item_id",
        "release_version",
        "image_reference",
        "image_digest",
        "reason",
    }
    module = importlib.import_module(MODULE)
    fields = set(module.HomeAssistantImageEvidenceProvenance.model_fields)
    assert not fields.intersection(
        {"action", "deploy", "update", "restart", "pull", "proposal", "candidate"}
    )


def test_projection_is_not_wired_to_startup_scheduler_routes_or_exports() -> None:
    app_dir = Path(__file__).parents[1]
    module_name = MODULE.rsplit(".", 1)[-1]
    for directory in (app_dir / "routes", app_dir / "api"):
        if directory.is_dir():
            for path in directory.rglob("*.py"):
                assert module_name not in path.read_text(encoding="utf-8")
    assert module_name not in (app_dir / "services/__init__.py").read_text(
        encoding="utf-8"
    )
    assert module_name not in (app_dir / "main.py").read_text(encoding="utf-8")
