"""P5 authority and effect-isolation locks for v0.26 delivery evidence."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Literal

from app.installation_handoff_simulated_delivery.contract import (
    AgentInstallationHandoffSimulatedAcknowledgementV1,
    InstallationHandoffSimulatedDeliveryAuditEvidenceV1,
    InstallationHandoffSimulatedDeliveryRecordV1,
    InstallationHandoffSimulatedDeliveryV1,
)
from app.installation_handoff_simulated_delivery.service import (
    InstallationHandoffSimulatedDeliveryService,
)

APP_ROOT = Path(__file__).parents[1]
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


def test_coordinator_is_explicitly_default_disabled() -> None:
    assert inspect.signature(InstallationHandoffSimulatedDeliveryService).parameters[
        "enabled"
    ].default is False


def test_all_delivery_and_acknowledgement_authority_is_fixed_false() -> None:
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
            InstallationHandoffSimulatedDeliveryRecordV1,
            (
                "live_delivery_claimed",
                "agent_admission_claimed",
                "execution_authorized",
                "mutation_authorized",
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
            InstallationHandoffSimulatedDeliveryAuditEvidenceV1,
            (
                "default_enabled",
                "live_delivery_claimed",
                "delivery_received",
                "agent_admission_claimed",
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


def test_package_has_no_network_process_runtime_or_authority_dependency() -> None:
    forbidden = (
        "app.api",
        "app.container",
        "app.deploy",
        "app.execution_candidates",
        "app.main",
        "app.operational_dispatch",
        "app.provider_intents",
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
    for method_name, store_method in (
        ("get_attempt", "get_attempt"),
        ("get_acknowledgement", "get_acknowledgement"),
        ("lifecycle", "lifecycle"),
    ):
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


def test_no_command_or_registration_module_exists() -> None:
    assert not (PACKAGE_ROOT / "__main__.py").exists()
    assert all(
        not (_imports(path) & {"argparse", "click", "typer"})
        for path in sorted(PACKAGE_ROOT.glob("*.py"))
    )
