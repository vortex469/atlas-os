"""P3 locks for the frozen in-process-only simulation intake boundary."""

from __future__ import annotations

import ast
from pathlib import Path

AGENT_ROOT = Path(__file__).parents[2]
APP_ROOT = AGENT_ROOT / "app"
PACKAGE_ROOT = APP_ROOT / "agent_intake_simulation"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_simulation_has_no_http_openapi_or_container_surface(
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
    schema_text = str(application.openapi()).lower()

    assert "agent_intake_simulation" not in schema_text
    assert "agent-intake-simulation" not in schema_text
    assert "intake-simulation" not in schema_text
    assert not hasattr(application.state.container, "agent_intake_simulation")
    assert not hasattr(application.state.container, "agent_intake_simulation_service")
    assert not hasattr(application.state.container, "agent_intake_simulation_store")


def test_simulation_has_no_setting_or_command_entrypoint() -> None:
    from app.config.settings import Settings

    settings_source = (APP_ROOT / "config" / "settings.py").read_text(encoding="utf-8")
    settings_fields = Settings.__dataclass_fields__

    assert not any(
        ("intake" in field or "simulation" in field)
        and not field.startswith("agent_live_intake_")
        for field in settings_fields
    )
    assert "ATLAS_AGENT_INTAKE" not in settings_source
    assert "ATLAS_AGENT_SIMULATION" not in settings_source
    assert not (APP_ROOT / "__main__.py").exists()
    assert not (PACKAGE_ROOT / "__main__.py").exists()

    command_frameworks = {"argparse", "click", "typer"}
    assert all(
        not (_imports(path) & command_frameworks)
        for path in sorted(PACKAGE_ROOT.glob("*.py"))
    )


def test_no_production_module_consumes_or_registers_simulation() -> None:
    markers = (
        "app.agent_intake_simulation",
        "AgentIntakeSimulationService",
        "AgentIntakeSimulationStore",
        "AgentInstallationIntakeSimulation",
        "agent-installation-intake-simulation",
    )
    violations: list[str] = []
    delivery_model_root = APP_ROOT / "installation_handoff_simulated_delivery"
    for path in sorted(APP_ROOT.rglob("*.py")):
        if PACKAGE_ROOT in path.parents or delivery_model_root in path.parents:
            continue
        source = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker in source:
                violations.append(f"{path.relative_to(APP_ROOT)} -> {marker}")

    assert violations == []


def test_simulation_package_has_no_effect_or_external_io_dependency() -> None:
    forbidden = (
        "app.approval",
        "app.candidate_planning",
        "app.container",
        "app.core_client",
        "app.execution",
        "app.model_providers",
        "app.persistence",
        "app.repository",
        "app.routes",
        "app.workflow",
        "asyncio",
        "docker",
        "os",
        "http.client",
        "httpx",
        "podman",
        "requests",
        "shlex",
        "socket",
        "subprocess",
        "urllib",
    )
    violations: list[str] = []
    for path in sorted(PACKAGE_ROOT.glob("*.py")):
        for imported in _imports(path):
            if imported.startswith(forbidden):
                violations.append(f"{path.name} -> {imported}")

    assert violations == []


def test_only_store_owns_a_filesystem_dependency() -> None:
    filesystem_importers = {
        path.name
        for path in sorted(PACKAGE_ROOT.glob("*.py"))
        if _imports(path) & {"pathlib", "sqlite3"}
    }

    assert filesystem_importers == {"store.py"}


def test_readback_is_only_an_owned_in_process_store_operation() -> None:
    service_tree = ast.parse(
        (PACKAGE_ROOT / "service.py").read_text(encoding="utf-8"),
        filename="service.py",
    )
    public_methods = {
        node.name
        for node in ast.walk(service_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    assert public_methods == {"simulate", "get", "lifecycle"}

    for method_name, store_method in (("get", "get"), ("lifecycle", "lifecycle")):
        method = next(
            node
            for node in ast.walk(service_tree)
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
            "intake_record_id",
        }
