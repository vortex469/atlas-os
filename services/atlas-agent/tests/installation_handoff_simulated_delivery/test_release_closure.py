"""P5 production-surface and authority locks for v0.26 acknowledgement evidence."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Literal

from app.installation_handoff_simulated_delivery import (
    AgentInstallationHandoffSimulatedAcknowledgementAuditEvidenceV1,
    AgentInstallationHandoffSimulatedAcknowledgementV1,
    AgentSimulatedAcknowledgementService,
    InstallationHandoffSimulatedDeliveryV1,
)

AGENT_ROOT = Path(__file__).parents[2]
APP_ROOT = AGENT_ROOT / "app"
PACKAGE_ROOT = APP_ROOT / "installation_handoff_simulated_delivery"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_acknowledgement_adapter_is_explicitly_default_disabled() -> None:
    assert inspect.signature(AgentSimulatedAcknowledgementService).parameters[
        "enabled"
    ].default is False


def test_delivery_and_acknowledgement_authority_is_fixed_false() -> None:
    models_and_fields = (
        (
            InstallationHandoffSimulatedDeliveryV1,
            (
                "delivery_authorized",
                "live_admission_authorized",
                "execution_authorized",
                "worker_allowed",
                "mutation_allowed",
                "replay_allowed",
            ),
        ),
        (
            AgentInstallationHandoffSimulatedAcknowledgementV1,
            (
                "delivery_received",
                "live_admission_granted",
                "execution_authorized",
                "worker_allowed",
                "mutation_allowed",
                "replay_allowed",
            ),
        ),
        (
            AgentInstallationHandoffSimulatedAcknowledgementAuditEvidenceV1,
            (
                "default_enabled",
                "delivery_received",
                "live_admission_granted",
                "execution_authorized",
                "worker_allowed",
                "mutation_allowed",
                "replay_allowed",
            ),
        ),
    )
    for model, fields in models_and_fields:
        for field in fields:
            assert model.model_fields[field].annotation == Literal[False]


def test_no_http_openapi_container_setting_or_command_surface(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    from app.config.settings import Settings
    from app.main import create_app

    monkeypatch.setattr(
        "app.main.load_settings",
        lambda: Settings(
            repository_root=Path(__file__).parents[4],
            state_dir=tmp_path / "agent-state",
        ),
    )
    application = create_app()
    openapi = str(application.openapi()).lower()
    settings_source = (APP_ROOT / "config" / "settings.py").read_text(encoding="utf-8")

    for marker in (
        "handoff-simulated",
        "handoff_simulated",
        "simulated-acknowledgement",
        "simulated_acknowledgement",
    ):
        assert marker not in openapi
        assert marker not in settings_source.lower()
    assert not any(
        "simulated" in name and "handoff" in name
        for name in dir(application.state.container)
    )
    assert not (PACKAGE_ROOT / "__main__.py").exists()
    assert all(
        not (_imports(path) & {"argparse", "click", "typer"})
        for path in sorted(PACKAGE_ROOT.glob("*.py"))
    )


def test_no_production_agent_module_consumes_acknowledgement_evidence() -> None:
    markers = (
        "app.installation_handoff_simulated_delivery",
        "AgentInstallationHandoffSimulatedAcknowledgement",
        "AgentSimulatedAcknowledgementService",
        "agent-installation-handoff-simulated-acknowledgement",
        "installation_handoff_simulated_delivery",
    )
    violations: list[str] = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        if PACKAGE_ROOT in path.parents:
            continue
        source = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker in source:
                violations.append(f"{path.relative_to(APP_ROOT)} -> {marker}")
    assert violations == []


def test_package_has_no_network_process_runtime_or_authority_dependency() -> None:
    forbidden = (
        "app.approval",
        "app.candidate_planning",
        "app.container",
        "app.core_client",
        "app.execution",
        "app.model_providers",
        "app.repository",
        "app.routes",
        "app.workflow",
        "asyncio",
        "docker",
        "http.client",
        "httpx",
        "os",
        "podman",
        "requests",
        "shlex",
        "socket",
        "subprocess",
        "urllib",
    )
    violations = [
        f"{path.name} -> {imported}"
        for path in sorted(PACKAGE_ROOT.glob("*.py"))
        for imported in _imports(path)
        if imported.startswith(forbidden)
    ]
    assert violations == []


def test_readback_is_only_owned_direct_store_access() -> None:
    tree = ast.parse((PACKAGE_ROOT / "service.py").read_text(encoding="utf-8"))
    for method_name, store_method in (("get", "get"), ("lifecycle", "lifecycle")):
        method = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == method_name
        )
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
        assert len(calls) == 1
        call = calls[0]
        assert isinstance(call.func, ast.Attribute)
        assert call.func.attr == store_method
        assert isinstance(call.func.value, ast.Attribute)
        assert call.func.value.attr == "_store"
        assert {keyword.arg for keyword in call.keywords} == {
            "operator_id",
            "simulated_delivery_id",
        }
