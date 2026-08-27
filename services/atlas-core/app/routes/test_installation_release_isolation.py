"""Atlas v0.17 P5 release-surface and authority-isolation locks."""

from __future__ import annotations

import ast
from pathlib import Path

from fastapi import FastAPI

from app.routes.installation import router

APP_ROOT = Path(__file__).parents[1]
V017_ROOTS = (
    APP_ROOT / "installation_targets",
    APP_ROOT / "installation_assessment",
    APP_ROOT / "routes" / "installation.py",
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


def test_v017_packages_have_no_execution_or_mutation_dependency() -> None:
    violations: list[str] = []
    for path in _production_files():
        for imported in _imports(path):
            if any(term in imported for term in FORBIDDEN_DEPENDENCIES):
                violations.append(f"{path.relative_to(APP_ROOT)} -> {imported}")
    assert violations == []


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
    assert all("installation/destination" not in route.path for route in discovery_router.routes)
