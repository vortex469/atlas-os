"""Atlas v0.16-v0.19 release-surface and authority-isolation locks."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from fastapi import FastAPI

from app.routes.installation import router

APP_ROOT = Path(__file__).parents[1]
V016_ROOTS = (
    APP_ROOT / "installation_plan",
)
V017_ROOTS = (
    APP_ROOT / "installation_targets",
    APP_ROOT / "installation_assessment",
    APP_ROOT / "routes" / "installation.py",
)
V018_ROOTS = (
    APP_ROOT / "installation_capability",
    APP_ROOT / "routes" / "installation_capability.py",
)
V019_ROOTS = (
    APP_ROOT / "installation_candidate_admission",
    APP_ROOT / "routes" / "installation_candidate_admission.py",
)

# These are the production subsystems that could turn an advisory record into
# authority or an external side effect.  Application/router wiring is
# deliberately not included: it may import the read-only route, but it may not
# become a consumer of the record itself.
AUTHORITY_CONSUMER_ROOTS = (
    APP_ROOT / "execution_candidates",
    APP_ROOT / "operational_dispatch",
    APP_ROOT / "provider_intents",
    APP_ROOT / "deploy",
)
V019_ALLOWED_CONSUMERS = {
    APP_ROOT / "installation_candidate_admission" / "__init__.py",
    APP_ROOT / "installation_candidate_admission" / "assembly.py",
    APP_ROOT / "installation_candidate_admission" / "contract.py",
    APP_ROOT / "installation_candidate_admission" / "evaluation.py",
    APP_ROOT / "main.py",
    APP_ROOT / "routes" / "installation_candidate_admission.py",
    APP_ROOT / "installation_candidate_lifecycle" / "__init__.py",
    APP_ROOT / "installation_candidate_lifecycle" / "contract.py",
    APP_ROOT / "installation_candidate_lifecycle" / "service.py",
    APP_ROOT / "installation_candidate_lifecycle" / "store.py",
    APP_ROOT / "routes" / "installation_candidate_lifecycle.py",
}
V018_RECORD_MARKERS = (
    "app.installation_capability",
    "InstallationCapabilityAssessmentV1",
    "ProviderInstallationCapabilityFactsV1",
    "installation-capability-assessment-v1",
    "provider-installation-capability-facts-v1",
    "capability-assessments/",
)
V019_RECORD_MARKERS = (
    "app.installation_candidate_admission",
    "InstallationCandidateAdmissionV1",
    "InstallationCandidateRecordV1",
    "installation-candidate-admission-v1",
    "installation-candidate-record-v1",
    "candidate-admissions/",
)

FORBIDDEN_DEPENDENCIES = (
    "approval",
    "candidate_planning",
    "deploy.execution",
    "execution_candidates",
    "execution_worker",
    "operational_dispatch",
    "provider_intents",
    "repository",
    "workflow",
)


def _production_files() -> tuple[Path, ...]:
    files: list[Path] = []
    for root in V017_ROOTS:
        if root.is_file():
            files.append(root)
        else:
            files.extend(
                path
                for path in root.glob("*.py")
                if not path.name.startswith("test_")
            )
    return tuple(sorted(files))


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def _production_python_files(root: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for path in root.rglob("*.py")
            if not path.name.startswith("test_")
        )
    )


def test_v017_packages_have_no_execution_or_mutation_dependency() -> None:
    violations: list[str] = []
    for path in _production_files():
        for imported in _imports(path):
            if any(term in imported for term in FORBIDDEN_DEPENDENCIES):
                violations.append(f"{path.relative_to(APP_ROOT)} -> {imported}")
    assert violations == []


def test_v016_plan_and_projection_remain_non_authorizing() -> None:
    violations: list[str] = []
    for root in V016_ROOTS:
        paths = (root,) if root.is_file() else _production_python_files(root)
        for path in paths:
            for imported in _imports(path):
                if any(term in imported for term in FORBIDDEN_DEPENDENCIES):
                    violations.append(f"{path.relative_to(APP_ROOT)} -> {imported}")
    projection = (
        APP_ROOT / "execution_candidates" / "installation_plan_projection.py"
    ).read_text(encoding="utf-8")
    assert violations == []
    assert "candidate_created: Literal[False] = False" in projection
    assert "planning_allowed: Literal[False] = False" in projection
    assert "candidate: ExecutionCandidate | None = None" in projection
    assert "if self.candidate is not None:" in projection


def test_no_execution_subsystem_imports_v017_records() -> None:
    consumers = (
        APP_ROOT / "execution_candidates",
        APP_ROOT / "operational_dispatch",
        APP_ROOT / "provider_intents",
        APP_ROOT / "deploy",
    )
    violations: list[str] = []
    for root in consumers:
        for path in root.rglob("*.py"):
            if path.name.startswith("test_"):
                continue
            imports = _imports(path)
            for imported in imports:
                if imported.startswith(
                    ("app.installation_targets", "app.installation_assessment")
                ):
                    violations.append(f"{path.relative_to(APP_ROOT)} -> {imported}")
    assert violations == []


def test_openapi_contains_only_the_frozen_installation_authority() -> None:
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    installation_paths = {
        path: set(methods)
        for path, methods in application.openapi()["paths"].items()
        if path.startswith("/api/v1/installation/")
    }
    assert installation_paths == {
        "/api/v1/installation/destinations": {"get"},
        "/api/v1/installation/destination-selections": {"post"},
        "/api/v1/installation/destination-selections/{selection_id}": {
            "delete",
            "get",
        },
        "/api/v1/installation/admission-assessments": {"post"},
    }
    prohibited = ("install", "execute", "approve", "plan", "convert", "dispatch")
    assert not any(
        segment in prohibited
        for path in installation_paths
        for segment in path.removeprefix("/api/v1/installation/").split("/")
    )


def test_discovery_route_remains_get_only_and_separate() -> None:
    from app.routes.discovery import router as discovery_router

    assert all(route.methods == {"GET"} for route in discovery_router.routes)
    assert all(
        "installation/destination" not in route.path
        for route in discovery_router.routes
    )


def test_v018_is_read_only_and_has_no_authority_dependency() -> None:
    violations: list[str] = []
    for root in V018_ROOTS:
        paths = (root,) if root.is_file() else _production_python_files(root)
        for path in paths:
            for imported in _imports(path):
                if any(term in imported for term in FORBIDDEN_DEPENDENCIES):
                    violations.append(f"{path.relative_to(APP_ROOT)} -> {imported}")
    assert violations == []


def test_no_authority_or_mutation_subsystem_consumes_v018_records() -> None:
    violations: list[str] = []
    for root in AUTHORITY_CONSUMER_ROOTS:
        for path in _production_python_files(root):
            source = path.read_text(encoding="utf-8")
            for marker in V018_RECORD_MARKERS:
                if marker in source:
                    violations.append(f"{path.relative_to(APP_ROOT)} -> {marker}")

    agent_root = APP_ROOT.parents[1] / "atlas-agent" / "app"
    for path in _production_python_files(agent_root):
        source = path.read_text(encoding="utf-8")
        for marker in V018_RECORD_MARKERS:
            if marker in source:
                violations.append(f"atlas-agent/{path.relative_to(agent_root)} -> {marker}")
    assert violations == []


def test_v019_is_read_only_and_has_no_authority_dependency() -> None:
    violations: list[str] = []
    for root in V019_ROOTS:
        paths = (root,) if root.is_file() else _production_python_files(root)
        for path in paths:
            for imported in _imports(path):
                if any(term in imported for term in FORBIDDEN_DEPENDENCIES):
                    violations.append(f"{path.relative_to(APP_ROOT)} -> {imported}")
    assert violations == []


def test_no_authority_or_mutation_subsystem_consumes_v019_records() -> None:
    violations: list[str] = []
    for path in _production_python_files(APP_ROOT):
        if path in V019_ALLOWED_CONSUMERS:
            continue
        source = path.read_text(encoding="utf-8")
        for marker in V019_RECORD_MARKERS:
            if marker in source:
                violations.append(f"{path.relative_to(APP_ROOT)} -> {marker}")

    agent_root = APP_ROOT.parents[1] / "atlas-agent" / "app"
    for path in _production_python_files(agent_root):
        source = path.read_text(encoding="utf-8")
        for marker in V019_RECORD_MARKERS:
            if marker in source:
                violations.append(f"atlas-agent/{path.relative_to(agent_root)} -> {marker}")
    assert violations == []


def test_mission_control_v019_surface_is_get_only_and_has_no_actions() -> None:
    mission_control = APP_ROOT.parents[1] / "mission-control" / "src"
    api_source = (
        mission_control / "api" / "installationCandidateAdmission.ts"
    ).read_text(encoding="utf-8")
    component_source = (
        mission_control
        / "features"
        / "discovery"
        / "InstallationCandidateAdmission.tsx"
    ).read_text(encoding="utf-8")

    assert re.search(r"atlas\s*\.\s*get(?:<[^>]+>)?\s*\(", api_source)
    assert not any(
        re.search(rf"atlas\s*\.\s*{method}(?:<[^>]+>)?\s*\(", api_source)
        for method in ("post", "put", "patch", "delete")
    )
    assert not any(
        token in component_source
        for token in ("<button", "<a ", "<Link", "<form", "navigate(", "href=")
    )
    prohibited = (
        "create candidate",
        "start workflow",
        "approve now",
        "install now",
        "prepare now",
        "execute now",
        "dispatch now",
        "deploy now",
        "retry action",
        "rollback now",
    )
    lowered = component_source.lower()
    assert not any(action in lowered for action in prohibited)


def test_v018_openapi_has_exactly_one_get_and_no_mutation_sibling() -> None:
    from app.api.v1.router import router as api_v1_router

    application = FastAPI()
    application.include_router(api_v1_router)
    paths = {
        path: set(methods)
        for path, methods in application.openapi()["paths"].items()
        if "capability-assessments" in path
    }
    assert paths == {
        "/api/v1/installation/capability-assessments/{item_id}/{selection_id}": {
            "get"
        }
    }


def test_v019_openapi_has_exactly_one_get_and_no_mutation_sibling() -> None:
    from app.api.v1.router import router as api_v1_router

    application = FastAPI()
    application.include_router(api_v1_router)
    paths = {
        path: set(methods)
        for path, methods in application.openapi()["paths"].items()
        if "candidate-admissions" in path
    }
    assert paths == {
        "/api/v1/installation/candidate-admissions/{item_id}/{selection_id}": {
            "get"
        }
    }


def test_home_assistant_and_agent_install_boundary_remain_closed() -> None:
    repository_root = APP_ROOT.parents[2]
    assert not (repository_root / "compose" / "home-assistant.yaml").exists()

    agent_models = (
        repository_root
        / "services"
        / "atlas-agent"
        / "app"
        / "candidate_planning"
        / "models.py"
    ).read_text(encoding="utf-8")
    assert (
        'SUPPORTED_EXECUTION_INTENTS = frozenset({"update-compose-stack"})'
        in agent_models
    )
    assert "install-container" not in agent_models
