from __future__ import annotations

import ast
import inspect
from pathlib import Path

from app.discovery import home_assistant_registry_attested as integration
from app.discovery.image_release_collector import (
    _COLLECTOR_SOURCE_CLASS,
    PRODUCTION_DESCRIPTORS,
    PRODUCTION_SOURCE_ADAPTERS,
)
from app.discovery.models import ImageReleaseEvidenceSourceClass


def test_integration_is_private_unregistered_and_generic_authority_unchanged() -> None:
    package = Path(__file__).parent
    assert (
        "home_assistant_registry_attested" not in (package / "__init__.py").read_text()
    )
    assert dict(PRODUCTION_DESCRIPTORS) == {}
    assert dict(PRODUCTION_SOURCE_ADAPTERS) == {}
    assert _COLLECTOR_SOURCE_CLASS is ImageReleaseEvidenceSourceClass.UPSTREAM_SIGNED


def test_import_and_construction_do_not_invoke_acquisition(monkeypatch) -> None:
    called = False

    async def forbidden(self):
        nonlocal called
        called = True
        raise AssertionError

    monkeypatch.setattr(integration._HomeAssistantGHCRAcquirer, "acquire", forbidden)
    assert integration.HomeAssistantRegistryAttestedAdapter() is not None
    assert not called


def test_no_forbidden_wiring_process_credentials_or_filesystem() -> None:
    source = inspect.getsource(integration)
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not imported & {"subprocess", "pathlib", "os", "docker", "requests"}
    for forbidden in (
        "curl",
        "getenv",
        "environ",
        "ImageReleaseEvidenceLoader",
        "image_grounding",
        "DeploymentBinding",
    ):
        assert forbidden not in source


def test_authority_values_are_module_owned_not_call_parameters() -> None:
    signature = inspect.signature(integration.HomeAssistantRegistryAttestedAdapter)
    assert not signature.parameters
    collect_signature = inspect.signature(
        integration.HomeAssistantRegistryAttestedAdapter.collect_async
    )
    assert list(collect_signature.parameters) == ["self"]


def test_no_production_acquirer_or_verifier_selection_mechanism() -> None:
    tree = ast.parse(inspect.getsource(integration))
    assert not any(
        isinstance(node, (ast.ClassDef, ast.FunctionDef))
        and any(word in node.name.lower() for word in ("factory", "protocol"))
        for node in ast.walk(tree)
    )
    assigned_names = {
        target.id.lower()
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name)
    }
    assert not any("registry" in name or "factory" in name for name in assigned_names)
    assert not hasattr(integration.HomeAssistantRegistryAttestedAdapter(), "_acquirer")
    assert not hasattr(integration.HomeAssistantRegistryAttestedAdapter(), "_verifier")
    source = inspect.getsource(
        integration.HomeAssistantRegistryAttestedAdapter.collect_async
    )
    assert "_HomeAssistantGHCRAcquirer().acquire()" in source
    assert "verify_home_assistant_2026_8_3_bundle(bundle_bytes=bundle_bytes)" in source
