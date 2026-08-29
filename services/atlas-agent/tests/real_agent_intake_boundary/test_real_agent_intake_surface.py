"""P3 locks for the frozen store-only real Agent intake phase."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Literal

from app.real_agent_intake_boundary import (
    AgentInstallationIntakeAdmissionV1,
    AgentInstallationIntakeAuditEvidenceV1,
    AgentRealIntakeEvidenceService,
)

AGENT_ROOT = Path(__file__).parents[2]
APP_ROOT = AGENT_ROOT / "app"
PACKAGE_ROOT = APP_ROOT / "real_agent_intake_boundary"
REPOSITORY_ROOT = AGENT_ROOT.parents[1]
FROZEN_CONTRACT = REPOSITORY_ROOT / "docs/architecture/real-agent-intake-boundary-v1.md"
INTAKE_PATH = "/api/v1/internal/installation-intake"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_frozen_p3_selects_store_only_and_defers_route_factory() -> None:
    contract = FROZEN_CONTRACT.read_text(encoding="utf-8")
    p3 = contract.split("### P3", 1)[1].split("### P4", 1)[0]
    p4 = contract.split("### P4", 1)[1].split("### P5", 1)[0]
    assert "append-only store" in p3
    assert "Add no consumer or authority bridge" in p3
    assert "Dormant route factory" in p4
    assert "explicitly constructed test application" in p4


def test_production_http_openapi_and_container_have_no_real_intake_surface(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    from app.config.settings import Settings
    from app.main import create_app

    monkeypatch.setattr(
        "app.main.load_settings",
        lambda: Settings(
            repository_root=REPOSITORY_ROOT,
            state_dir=tmp_path / "agent-state",
        ),
    )
    application = create_app()
    paths = application.openapi()["paths"]
    assert INTAKE_PATH not in paths
    assert all("installation-intake" not in path for path in paths)
    assert not any("real_intake" in name for name in dir(application.state.container))

    production_sources = {
        name: (APP_ROOT / name).read_text(encoding="utf-8").lower()
        for name in (
            "main.py",
            "container/application.py",
            "config/settings.py",
            "core_client/client.py",
        )
    }
    for source in production_sources.values():
        assert "real_agent_intake_boundary" not in source
        assert "installation-intake" not in source
        assert "install_intake" not in source


def test_no_route_command_listener_or_settings_enablement_exists() -> None:
    assert not (PACKAGE_ROOT / "routes.py").exists()
    assert not (PACKAGE_ROOT / "router.py").exists()
    assert not (PACKAGE_ROOT / "api.py").exists()
    assert not (PACKAGE_ROOT / "__main__.py").exists()
    assert all(
        not (_imports(path) & {"argparse", "click", "fastapi", "starlette", "typer"})
        for path in sorted(PACKAGE_ROOT.glob("*.py"))
    )
    package_text = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in sorted(PACKAGE_ROOT.glob("*.py"))
    )
    for prohibited_surface in (
        "@router.",
        "add_api_route",
        "include_router",
        "create_subprocess",
        "listen(",
        "start_server",
        "uvicorn",
    ):
        assert prohibited_surface not in package_text


def test_service_remains_explicitly_default_disabled() -> None:
    assert inspect.signature(AgentRealIntakeEvidenceService).parameters[
        "enabled"
    ].default is False


def test_admission_and_audit_authority_fields_remain_closed() -> None:
    for model, fields in (
        (
            AgentInstallationIntakeAdmissionV1,
            (
                "execution_admission_granted",
                "execution_authorized",
                "worker_allowed",
                "mutation_allowed",
                "replay_allowed",
            ),
        ),
        (
            AgentInstallationIntakeAuditEvidenceV1,
            (
                "default_enabled",
                "execution_admission_granted",
                "execution_authorized",
                "worker_allowed",
                "mutation_allowed",
                "replay_allowed",
            ),
        ),
    ):
        for field in fields:
            assert model.model_fields[field].annotation == Literal[False]


def test_no_production_module_consumes_real_intake_evidence() -> None:
    markers = (
        "app.real_agent_intake_boundary",
        "AgentRealIntakeEvidenceService",
        "AgentRealIntakeEvidenceStore",
        "agent-installation-intake-request-v1",
        "agent-installation-intake-admission-v1",
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


def test_package_has_no_transport_runtime_worker_or_authority_consumer() -> None:
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
        "fastapi",
        "http.client",
        "httpx",
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


def test_no_deployment_or_core_delivery_configuration() -> None:
    candidates = [
        path
        for path in REPOSITORY_ROOT.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and path.suffix.lower() in {".yaml", ".yml", ".toml"}
    ]
    violations: list[str] = []
    for path in candidates:
        source = path.read_text(encoding="utf-8", errors="ignore").lower()
        if "installation-intake" in source or "install_intake" in source:
            violations.append(str(path.relative_to(REPOSITORY_ROOT)))
    assert violations == []
