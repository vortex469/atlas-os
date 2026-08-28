"""P3-P5 surface, authority, and production-isolation locks."""

import ast
from pathlib import Path

APP_ROOT = Path(__file__).parents[2] / "app"
CONTRACT_ROOT = APP_ROOT / "install_container_contract"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports

def test_install_container_has_no_http_or_command_surface(monkeypatch, tmp_path) -> None:
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
    schema = application.openapi()

    assert all("install-container" not in path for path in schema["paths"])
    assert all("install_container" not in path for path in schema["paths"])
    assert not hasattr(application.state.container, "install_container_service")


def test_no_production_module_consumes_validation_service() -> None:
    consumers = []
    for path in APP_ROOT.rglob("*.py"):
        if path.parts[-2:] == ("install_container_contract", "__init__.py"):
            continue
        if path.parts[-2:] == ("install_container_contract", "service.py"):
            continue
        if "InstallContainerValidationService" in path.read_text(encoding="utf-8"):
            consumers.append(path.relative_to(APP_ROOT))

    assert consumers == []


def test_install_container_contract_has_no_runtime_or_mutation_dependency() -> None:
    forbidden = (
        "app.approval",
        "app.candidate_planning",
        "app.container",
        "app.core_client",
        "app.execution",
        "app.persistence",
        "app.repository",
        "app.routes",
        "app.workflow",
        "asyncio",
        "docker",
        "podman",
        "socket",
        "subprocess",
    )
    violations: list[str] = []
    for path in sorted(CONTRACT_ROOT.glob("*.py")):
        for imported in _imports(path):
            if imported.startswith(forbidden):
                violations.append(f"{path.name} -> {imported}")
    assert violations == []


def test_only_static_status_diagnostic_mentions_contract_outside_package() -> None:
    allowed = {APP_ROOT / "routes" / "status.py"}
    markers = (
        "app.install_container_contract",
        "AgentInstallContainerValidationV1",
        "AgentInstallContainerAuditEvidenceV1",
        "agent-install-container-validation-v1",
        "agent-install-container-audit-evidence-v1",
    )
    violations: list[str] = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        if CONTRACT_ROOT in path.parents or path in allowed:
            continue
        source = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker in source:
                violations.append(f"{path.relative_to(APP_ROOT)} -> {marker}")
    assert violations == []


def test_static_diagnostic_cannot_claim_install_authority() -> None:
    source = (APP_ROOT / "routes" / "status.py").read_text(encoding="utf-8")
    required = (
        'mode: Literal["validate-only"]',
        'capability_status: Literal["unsupported"]',
        "default_enabled: Literal[False]",
        "execution_supported: Literal[False]",
        "dispatch_allowed: Literal[False]",
        "mutation_allowed: Literal[False]",
        "replay_allowed: Literal[False]",
        'home_assistant_status: Literal["blocked"]',
        "validation_result_available: Literal[False]",
    )
    assert all(field in source for field in required)
