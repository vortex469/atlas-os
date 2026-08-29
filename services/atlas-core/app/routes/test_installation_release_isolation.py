"""Atlas v0.16-v0.28 release-surface and authority-isolation locks."""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path
from typing import Literal

import pytest
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
V020_ROOTS = (
    APP_ROOT / "installation_candidate_lifecycle",
    APP_ROOT / "routes" / "installation_candidate_lifecycle.py",
)
V021_ROOTS = (
    APP_ROOT / "installation_approval_intent",
    APP_ROOT / "routes" / "installation_approval_intent.py",
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
V020_RECORD_MARKERS = (
    "app.installation_candidate_lifecycle",
    "InstallationCandidateRecordEnvelopeV1",
    "installation-candidate-record-envelope-v1",
)
V021_RECORD_MARKERS = (
    "app.installation_approval_intent",
    "InstallationApprovalIntentV1",
    "installation-approval-intent-v1",
    "candidate-approval-intents",
)
V022_RECORD_MARKERS = (
    "app.install_container_contract",
    "AgentInstallContainerValidationV1",
    "AgentInstallContainerAuditEvidenceV1",
    "agent-install-container-validation-v1",
    "agent-install-container-audit-evidence-v1",
)
V023_RECORD_MARKERS = (
    "app.installation_execution_request",
    "InstallationExecutionRequestV1",
    "installation-execution-request-v1",
    "installation/execution-requests",
)
V024_RECORD_MARKERS = (
    "app.installation_dispatch_handoff",
    "InstallationDispatchEnvelopeV1",
    "AgentInstallationDispatchIntakeV1",
    "AgentInstallationDispatchAdmissionV1",
    "installation-dispatch-envelope-v1",
    "agent-installation-dispatch-intake-v1",
    "installation/dispatch-handoffs",
)
V024_ALLOWED_CONSUMERS = {
    APP_ROOT / "api" / "v1" / "router.py",
    APP_ROOT / "installation_dispatch_handoff" / "__init__.py",
    APP_ROOT / "installation_dispatch_handoff" / "contract.py",
    APP_ROOT / "installation_dispatch_handoff" / "service.py",
    APP_ROOT / "installation_dispatch_handoff" / "store.py",
    APP_ROOT / "main.py",
    APP_ROOT / "routes" / "installation_dispatch_handoff.py",
    APP_ROOT / "installation_handoff_simulated_delivery" / "__init__.py",
    APP_ROOT / "installation_handoff_simulated_delivery" / "contract.py",
}
V025_RECORD_MARKERS = (
    "app.agent_intake_simulation",
    "AgentIntakeSimulationService",
    "AgentIntakeSimulationStore",
    "AgentInstallationIntakeSimulation",
    "agent-installation-intake-simulation",
    "agent_intake_simulation",
)
V026_RECORD_MARKERS = (
    "app.installation_handoff_simulated_delivery",
    "AgentInstallationHandoffSimulatedAcknowledgement",
    "InstallationHandoffSimulatedDelivery",
    "agent-installation-handoff-simulated-acknowledgement",
    "installation-handoff-simulated-delivery",
    "installation_handoff_simulated_delivery",
)
V023_ALLOWED_CONSUMERS = {
    APP_ROOT / "api" / "v1" / "router.py",
    APP_ROOT / "config" / "settings.py",
    APP_ROOT / "installation_execution_request" / "__init__.py",
    APP_ROOT / "installation_execution_request" / "contract.py",
    APP_ROOT / "installation_execution_request" / "service.py",
    APP_ROOT / "installation_execution_request" / "store.py",
    APP_ROOT / "main.py",
    APP_ROOT / "routes" / "installation_execution_request.py",
    APP_ROOT / "installation_dispatch_handoff" / "contract.py",
    APP_ROOT / "installation_dispatch_handoff" / "store.py",
}
V020_ALLOWED_CONSUMERS = {
    APP_ROOT / "api" / "v1" / "router.py",
    APP_ROOT / "installation_candidate_lifecycle" / "__init__.py",
    APP_ROOT / "installation_candidate_lifecycle" / "contract.py",
    APP_ROOT / "installation_candidate_lifecycle" / "service.py",
    APP_ROOT / "installation_candidate_lifecycle" / "store.py",
    APP_ROOT / "main.py",
    APP_ROOT / "routes" / "installation_candidate_lifecycle.py",
    APP_ROOT / "installation_approval_intent" / "contract.py",
    APP_ROOT / "installation_approval_intent" / "service.py",
    APP_ROOT / "installation_approval_intent" / "store.py",
    APP_ROOT / "installation_execution_request" / "contract.py",
    APP_ROOT / "installation_execution_request" / "service.py",
    APP_ROOT / "installation_execution_request" / "store.py",
    APP_ROOT / "routes" / "installation_execution_request.py",
    APP_ROOT / "installation_dispatch_handoff" / "contract.py",
    APP_ROOT / "installation_dispatch_handoff" / "service.py",
    APP_ROOT / "installation_dispatch_handoff" / "store.py",
}
V021_ALLOWED_CONSUMERS = {
    APP_ROOT / "api" / "v1" / "router.py",
    APP_ROOT / "config" / "settings.py",
    APP_ROOT / "installation_approval_intent" / "__init__.py",
    APP_ROOT / "installation_approval_intent" / "contract.py",
    APP_ROOT / "installation_approval_intent" / "service.py",
    APP_ROOT / "installation_approval_intent" / "store.py",
    APP_ROOT / "installation_execution_request" / "contract.py",
    APP_ROOT / "installation_execution_request" / "service.py",
    APP_ROOT / "installation_execution_request" / "store.py",
    APP_ROOT / "routes" / "installation_execution_request.py",
    APP_ROOT / "main.py",
    APP_ROOT / "routes" / "installation_approval_intent.py",
    APP_ROOT / "installation_dispatch_handoff" / "contract.py",
    APP_ROOT / "installation_dispatch_handoff" / "store.py",
}
V022_ALLOWED_CONSUMERS = {
    APP_ROOT / "installation_execution_request" / "__init__.py",
    APP_ROOT / "installation_execution_request" / "contract.py",
}

V021_V019_ALLOWED_CONSUMERS = {
    APP_ROOT / "installation_approval_intent" / "contract.py",
    APP_ROOT / "installation_approval_intent" / "store.py",
}

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
        if path in V019_ALLOWED_CONSUMERS | V021_V019_ALLOWED_CONSUMERS:
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


def test_v020_is_non_authorizing_and_older_installation_packages_do_not_import_it() -> None:
    violations: list[str] = []
    for root in V020_ROOTS:
        paths = (root,) if root.is_file() else _production_python_files(root)
        for path in paths:
            for imported in _imports(path):
                if any(term in imported for term in FORBIDDEN_DEPENDENCIES):
                    violations.append(f"{path.relative_to(APP_ROOT)} -> {imported}")
    for root in (*V016_ROOTS, *V017_ROOTS, *V018_ROOTS, *V019_ROOTS):
        paths = (root,) if root.is_file() else _production_python_files(root)
        for path in paths:
            for imported in _imports(path):
                if imported.startswith("app.installation_candidate_lifecycle"):
                    violations.append(f"{path.relative_to(APP_ROOT)} -> {imported}")
    assert violations == []


def test_no_core_or_agent_authority_or_mutation_path_consumes_v020_records() -> None:
    violations: list[str] = []
    for path in _production_python_files(APP_ROOT):
        if path in V020_ALLOWED_CONSUMERS:
            continue
        source = path.read_text(encoding="utf-8")
        for marker in V020_RECORD_MARKERS:
            if marker in source:
                violations.append(f"{path.relative_to(APP_ROOT)} -> {marker}")

    agent_root = APP_ROOT.parents[1] / "atlas-agent" / "app"
    for path in _production_python_files(agent_root):
        source = path.read_text(encoding="utf-8")
        for marker in V020_RECORD_MARKERS:
            if marker in source:
                violations.append(f"atlas-agent/{path.relative_to(agent_root)} -> {marker}")
    assert violations == []


def test_v020_openapi_is_lifecycle_only_with_no_authority_route() -> None:
    from app.api.v1.router import router as api_v1_router

    application = FastAPI()
    application.include_router(api_v1_router)
    paths = {
        path: set(methods)
        for path, methods in application.openapi()["paths"].items()
        if "candidate-records" in path
    }
    assert paths == {
        "/api/v1/installation/candidate-records": {"get", "post"},
        "/api/v1/installation/candidate-records/{candidate_record_id}": {
            "delete",
            "get",
        },
    }
    prohibited = ("approve", "execute", "dispatch", "install", "deploy", "rollback")
    assert not any(
        token in path.removeprefix("/api/v1/installation/candidate-records")
        for path in paths
        for token in prohibited
    )


def test_mission_control_v020_surface_is_preserve_review_delete_only() -> None:
    mission_control = APP_ROOT.parents[1] / "mission-control" / "src"
    api_source = (
        mission_control / "api" / "installationCandidateLifecycle.ts"
    ).read_text(encoding="utf-8")
    component_source = (
        mission_control
        / "features"
        / "discovery"
        / "InstallationCandidateLifecycle.tsx"
    ).read_text(encoding="utf-8")

    route_consumers = {
        path.relative_to(mission_control)
        for path in mission_control.rglob("*.ts*")
        if ".test." not in path.name
        and "/installation/candidate-records" in path.read_text(encoding="utf-8")
    }
    assert route_consumers == {
        Path("api/installationCandidateLifecycle.ts"),
    }

    assert len(re.findall(r"atlas\s*\.\s*get(?:<[^>]+>)?\s*\(", api_source)) == 2
    assert len(re.findall(r"atlas\s*\.\s*post(?:<[^>]+>)?\s*\(", api_source)) == 1
    assert len(re.findall(r"atlas\s*\.\s*delete(?:<[^>]+>)?\s*\(", api_source)) == 1
    assert not any(
        re.search(rf"atlas\s*\.\s*{method}(?:<[^>]+>)?\s*\(", api_source)
        for method in ("put", "patch")
    )
    assert set(re.findall(r"\b(?:preserve|get|list|delete)InstallationCandidateRecord(?:s)?\b", component_source)) == {
        "deleteInstallationCandidateRecord",
        "getInstallationCandidateRecord",
        "listInstallationCandidateRecords",
        "preserveInstallationCandidateRecord",
    }
    assert not any(token in component_source for token in ("<a ", "<Link", "<form", "navigate(", "href="))
    button_labels = set(re.findall(r">([^<>]+)</button>", component_source))
    assert button_labels == {
        "Delete saved record",
        "Preserve candidate record",
        "Review saved record",
    }


def test_home_assistant_v019_result_cannot_cross_v020_preservation_boundary() -> None:
    from app.installation_candidate_admission.test_admission import admit
    from app.installation_candidate_lifecycle.contract import (
        validate_preservable_admission,
    )
    from app.installation_capability.test_assessment import assess, plan

    home_plan = plan(ready=False)
    admission = admit(plan=home_plan, capability_assessment=assess(home_plan))
    assert admission.status == "not_admitted"
    assert admission.candidate_record is None
    with pytest.raises(ValueError, match="not currently preservable"):
        validate_preservable_admission(
            admission, created_at="2026-08-27T12:00:01Z"
        )


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


def test_v021_is_append_only_evidence_with_no_authority_dependency() -> None:
    allowed_imports = (
        "app.installation_approval_intent",
        "app.installation_candidate_admission.contract",
        "app.installation_candidate_lifecycle.contract",
        "app.installation_candidate_lifecycle.store",
        "app.installation_plan.contract",
        "app.installation_targets.contract",
        "app.models.contracts",
        "app.operator_auth",
    )
    violations: list[str] = []
    for root in V021_ROOTS:
        paths = (root,) if root.is_file() else _production_python_files(root)
        for path in paths:
            for imported in _imports(path):
                if imported.startswith("app.") and not imported.startswith(
                    allowed_imports
                ):
                    violations.append(f"{path.relative_to(APP_ROOT)} -> {imported}")
    store_source = (V021_ROOTS[0] / "store.py").read_text(encoding="utf-8")
    service_source = (V021_ROOTS[0] / "service.py").read_text(encoding="utf-8")
    assert violations == []
    assert not re.search(
        r"\b(?:update|delete|consume|execute|dispatch|deploy|rollback)\b",
        service_source,
    )
    assert "UPDATE installation_approval_intents" not in store_source
    assert "DELETE FROM installation_approval_intents" not in store_source


def test_no_core_or_agent_production_consumer_recognizes_v021_intents() -> None:
    violations: list[str] = []
    for path in _production_python_files(APP_ROOT):
        if path in V021_ALLOWED_CONSUMERS:
            continue
        source = path.read_text(encoding="utf-8")
        for marker in V021_RECORD_MARKERS:
            if marker in source:
                violations.append(f"{path.relative_to(APP_ROOT)} -> {marker}")

    agent_root = APP_ROOT.parents[1] / "atlas-agent" / "app"
    for path in _production_python_files(agent_root):
        source = path.read_text(encoding="utf-8")
        for marker in V021_RECORD_MARKERS:
            if marker in source:
                violations.append(
                    f"atlas-agent/{path.relative_to(agent_root)} -> {marker}"
                )
    assert violations == []


def test_v021_openapi_is_exactly_append_list_get_with_no_authority_route() -> None:
    from app.api.v1.router import router as api_v1_router

    application = FastAPI()
    application.include_router(api_v1_router)
    paths = {
        path: set(methods)
        for path, methods in application.openapi()["paths"].items()
        if "candidate-approval-intents" in path
    }
    assert paths == {
        "/api/v1/installation/candidate-approval-intents": {"get", "post"},
        "/api/v1/installation/candidate-approval-intents/{approval_intent_id}": {
            "get"
        },
    }
    prohibited = ("install", "execute", "dispatch", "deploy", "rollback", "replay")
    assert not any(
        token in path.removeprefix(
            "/api/v1/installation/candidate-approval-intents"
        )
        for path in paths
        for token in prohibited
    )


def test_mission_control_v021_surface_has_only_append_list_get_calls() -> None:
    mission_control = APP_ROOT.parents[1] / "mission-control" / "src"
    api_source = (mission_control / "api" / "installationApprovalIntent.ts").read_text(
        encoding="utf-8"
    )
    component_source = (
        mission_control / "features" / "discovery" / "InstallationApprovalIntents.tsx"
    ).read_text(encoding="utf-8")
    route_consumers = {
        path.relative_to(mission_control)
        for path in mission_control.rglob("*.ts*")
        if ".test." not in path.name
        and "/installation/candidate-approval-intents" in path.read_text(
            encoding="utf-8"
        )
    }
    assert route_consumers == {Path("api/installationApprovalIntent.ts")}
    assert len(re.findall(r"atlas\s*\.\s*get(?:<[^>]+>)?\s*\(", api_source)) == 2
    assert len(re.findall(r"atlas\s*\.\s*post(?:<[^>]+>)?\s*\(", api_source)) == 1
    assert not any(
        re.search(rf"atlas\s*\.\s*{method}(?:<[^>]+>)?\s*\(", api_source)
        for method in ("put", "patch", "delete")
    )
    assert not any(
        token in component_source
        for token in ("<a ", "<Link", "<form", "navigate(", "href=")
    )
    prohibited = (
        "install now",
        "execute now",
        "dispatch now",
        "deploy now",
        "start workflow",
        "rollback now",
    )
    assert not any(action in component_source.lower() for action in prohibited)


def test_home_assistant_cannot_be_preserved_or_approved_in_v021() -> None:
    from app.installation_candidate_admission.test_admission import admit
    from app.installation_candidate_lifecycle.contract import (
        validate_preservable_admission,
    )
    from app.installation_capability.test_assessment import assess, plan

    home_plan = plan(ready=False)
    admission = admit(plan=home_plan, capability_assessment=assess(home_plan))
    assert admission.status == "not_admitted"
    assert admission.candidate_record is None
    with pytest.raises(ValueError, match="not currently preservable"):
        validate_preservable_admission(
            admission, created_at="2026-08-27T12:00:01Z"
        )


def test_no_core_production_path_consumes_v022_validation_records() -> None:
    violations: list[str] = []
    for path in _production_python_files(APP_ROOT):
        if path in V022_ALLOWED_CONSUMERS:
            continue
        source = path.read_text(encoding="utf-8")
        for marker in V022_RECORD_MARKERS:
            if marker in source:
                violations.append(f"{path.relative_to(APP_ROOT)} -> {marker}")
    assert violations == []


def test_agent_authority_and_mutation_paths_do_not_consume_v022_records() -> None:
    agent_root = APP_ROOT.parents[1] / "atlas-agent" / "app"
    allowed = {
        agent_root / "install_container_contract" / "__init__.py",
        agent_root / "install_container_contract" / "models.py",
        agent_root / "install_container_contract" / "service.py",
        agent_root / "routes" / "status.py",
    }
    violations: list[str] = []
    for path in _production_python_files(agent_root):
        if path in allowed:
            continue
        source = path.read_text(encoding="utf-8")
        for marker in V022_RECORD_MARKERS:
            if marker in source:
                violations.append(
                    f"atlas-agent/{path.relative_to(agent_root)} -> {marker}"
                )
    assert violations == []


def test_v022_adds_no_core_route_or_core_to_agent_bridge() -> None:
    from app.api.v1.router import router as api_v1_router

    application = FastAPI()
    application.include_router(api_v1_router)
    assert not any(
        "install-container" in path or "install_container" in path
        for path in application.openapi()["paths"]
    )

    consumer_roots = (
        APP_ROOT / "core_client",
        APP_ROOT / "operational_dispatch",
        APP_ROOT / "execution_candidates",
        APP_ROOT / "deploy",
    )
    violations: list[str] = []
    for root in consumer_roots:
        if not root.exists():
            continue
        for path in _production_python_files(root):
            source = path.read_text(encoding="utf-8")
            if "install_container_contract" in source:
                violations.append(str(path.relative_to(APP_ROOT)))
    assert violations == []


def test_v023_records_have_no_authority_or_external_mutation_consumer() -> None:
    violations: list[str] = []
    for path in _production_python_files(APP_ROOT):
        if path in V023_ALLOWED_CONSUMERS:
            continue
        source = path.read_text(encoding="utf-8")
        for marker in V023_RECORD_MARKERS:
            if marker in source:
                violations.append(f"{path.relative_to(APP_ROOT)} -> {marker}")

    agent_root = APP_ROOT.parents[1] / "atlas-agent" / "app"
    for path in _production_python_files(agent_root):
        source = path.read_text(encoding="utf-8")
        for marker in V023_RECORD_MARKERS:
            if marker in source:
                violations.append(
                    f"atlas-agent/{path.relative_to(agent_root)} -> {marker}"
                )
    assert violations == []


def test_v023_is_record_only_default_disabled_and_non_authorizing() -> None:
    from app.config.settings import OperatorAuthSettings
    from app.installation_execution_request.contract import (
        InstallationExecutionRequestV1,
    )
    from app.installation_execution_request.service import (
        InstallationExecutionRequestService,
    )

    assert OperatorAuthSettings().installation_execution_request_enabled is False
    assert InstallationExecutionRequestService.__init__.__kwdefaults__ == {
        "enabled": False
    }
    authority_fields = {
        "execution_authorized",
        "dispatch_allowed",
        "agent_invocation_allowed",
        "mutation_allowed",
        "replay_allowed",
    }
    for field in authority_fields:
        annotation = InstallationExecutionRequestV1.model_fields[field].annotation
        assert annotation == Literal[False]

    package = APP_ROOT / "installation_execution_request"
    forbidden_runtime_dependencies = tuple(
        dependency for dependency in FORBIDDEN_DEPENDENCIES if dependency != "approval"
    )
    imports: list[str] = []
    for path in _production_python_files(package):
        imports.extend(
            f"{path.relative_to(APP_ROOT)} -> {imported}"
            for imported in _imports(path)
            if any(term in imported for term in forbidden_runtime_dependencies)
        )
    assert imports == []


def test_v023_route_has_only_create_list_and_owned_item_read() -> None:
    from app.routes.installation_execution_request import (
        router as execution_request_router,
    )

    application = FastAPI()
    application.include_router(execution_request_router, prefix="/api/v1")
    paths = {
        path: set(methods)
        for path, methods in application.openapi()["paths"].items()
    }
    assert paths == {
        "/api/v1/installation/execution-requests": {"get", "post"},
        "/api/v1/installation/execution-requests/{execution_request_id}": {
            "get"
        },
    }
    prohibited = (
        "install",
        "execute",
        "deploy",
        "dispatch",
        "send-to-agent",
        "start-workflow",
        "rollback",
    )
    assert not any(
        segment in prohibited
        for path in paths
        for segment in path.removeprefix(
            "/api/v1/installation/execution-requests"
        ).split("/")
    )


def test_v024_records_have_no_core_or_agent_runtime_consumer() -> None:
    violations: list[str] = []
    dormant_wiring_root = APP_ROOT / "dormant_agent_intake_delivery_wiring"
    preflight_contract_root = APP_ROOT / "delivery_activation_preflight"
    for path in _production_python_files(APP_ROOT):
        if (
            path in V024_ALLOWED_CONSUMERS
            or dormant_wiring_root in path.parents
            or preflight_contract_root in path.parents
        ):
            continue
        source = path.read_text(encoding="utf-8")
        for marker in V024_RECORD_MARKERS:
            if marker in source:
                violations.append(f"{path.relative_to(APP_ROOT)} -> {marker}")

    agent_root = APP_ROOT.parents[1] / "atlas-agent" / "app"
    simulation_root = agent_root / "agent_intake_simulation"
    delivery_model_root = agent_root / "installation_handoff_simulated_delivery"
    real_intake_root = agent_root / "real_agent_intake_boundary"
    for path in _production_python_files(agent_root):
        if (
            simulation_root in path.parents
            or delivery_model_root in path.parents
            or real_intake_root in path.parents
        ):
            continue
        source = path.read_text(encoding="utf-8")
        for marker in V024_RECORD_MARKERS:
            if marker in source:
                violations.append(
                    f"atlas-agent/{path.relative_to(agent_root)} -> {marker}"
                )
    assert violations == []


def test_v024_is_record_only_default_disabled_and_non_authorizing() -> None:
    from app.config.settings import OperatorAuthSettings
    from app.installation_dispatch_handoff.contract import (
        AgentInstallationDispatchAdmissionV1,
        InstallationDispatchEnvelopeV1,
    )
    from app.installation_dispatch_handoff.service import (
        InstallationDispatchHandoffService,
    )

    assert OperatorAuthSettings().installation_dispatch_handoff_enabled is False
    assert InstallationDispatchHandoffService.__init__.__kwdefaults__ == {
        "enabled": False
    }
    for model, fields in (
        (
            InstallationDispatchEnvelopeV1,
            (
                "delivery_authorized",
                "agent_admission_authorized",
                "execution_authorized",
                "mutation_authorized",
                "replay_allowed",
            ),
        ),
        (
            AgentInstallationDispatchAdmissionV1,
            (
                "delivery_accepted",
                "execution_admitted",
                "worker_allowed",
                "mutation_allowed",
                "replay_allowed",
            ),
        ),
    ):
        for field in fields:
            assert model.model_fields[field].annotation == Literal[False]

    package = APP_ROOT / "installation_dispatch_handoff"
    prohibited_imports = (
        "agent_client",
        "core_client",
        "deploy",
        "execution_candidates",
        "operational_dispatch",
        "provider_intents",
        "repository",
        "subprocess",
        "workflow",
        "worker",
    )
    violations = [
        f"{path.relative_to(APP_ROOT)} -> {imported}"
        for path in _production_python_files(package)
        for imported in _imports(path)
        if any(term in imported for term in prohibited_imports)
    ]
    service_source = (package / "service.py").read_text(encoding="utf-8")
    store_source = (package / "store.py").read_text(encoding="utf-8")
    assert violations == []
    assert not re.search(
        r"\b(?:consume|deliver|dispatch|execute|invoke|install|replay|send|start)\s*\(",
        service_source,
    )
    assert "UPDATE installation_dispatch_handoffs" not in store_source
    assert "DELETE FROM installation_dispatch_handoffs" not in store_source


def test_v024_core_surface_is_only_guarded_create_list_and_owned_get() -> None:
    from app.api.v1.router import router as api_v1_router

    application = FastAPI()
    application.include_router(api_v1_router)
    base = "/api/v1/installation/dispatch-handoffs"
    paths = {
        path: set(methods)
        for path, methods in application.openapi()["paths"].items()
        if path.startswith(base)
    }
    assert paths == {
        base: {"get", "post"},
        base + "/{dispatch_envelope_id}": {"get"},
    }
    prohibited = (
        "install",
        "execute",
        "dispatch",
        "deliver",
        "deploy",
        "send-to-agent",
        "start-workflow",
        "rollback",
        "replay",
    )
    assert not any(
        segment in prohibited
        for path in paths
        for segment in path.removeprefix(base).split("/")
    )


def test_v024_home_assistant_remains_non_installable_and_non_executable() -> None:
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
    assert "install-container" not in agent_models


def test_v025_simulation_has_no_core_or_agent_production_consumer() -> None:
    """Only isolated v0.25/v0.26 model packages may recognize simulation records."""
    repository_root = APP_ROOT.parents[2]
    agent_root = repository_root / "services" / "atlas-agent" / "app"
    simulation_root = agent_root / "agent_intake_simulation"
    delivery_core_root = APP_ROOT / "installation_handoff_simulated_delivery"
    delivery_agent_root = agent_root / "installation_handoff_simulated_delivery"
    violations: list[str] = []

    for path in _production_python_files(APP_ROOT):
        if delivery_core_root in path.parents:
            continue
        source = path.read_text(encoding="utf-8")
        for marker in V025_RECORD_MARKERS:
            if marker in source:
                violations.append(f"atlas-core/{path.relative_to(APP_ROOT)} -> {marker}")

    for path in _production_python_files(agent_root):
        if simulation_root in path.parents or delivery_agent_root in path.parents:
            continue
        source = path.read_text(encoding="utf-8")
        for marker in V025_RECORD_MARKERS:
            if marker in source:
                violations.append(f"atlas-agent/{path.relative_to(agent_root)} -> {marker}")

    assert violations == []


def test_v025_keeps_install_container_unsupported_and_home_assistant_blocked() -> None:
    repository_root = APP_ROOT.parents[2]
    agent_root = repository_root / "services" / "atlas-agent" / "app"
    status_source = (agent_root / "routes" / "status.py").read_text(encoding="utf-8")
    candidate_source = (agent_root / "candidate_planning" / "models.py").read_text(
        encoding="utf-8"
    )

    assert 'capability_status: Literal["unsupported"]' in status_source
    assert (
        'SUPPORTED_EXECUTION_INTENTS = frozenset({"update-compose-stack"})'
        in candidate_source
    )
    assert "install-container" not in candidate_source
    assert not (repository_root / "compose" / "home-assistant.yaml").exists()
    assert not (repository_root / "compose" / "home-assistant.yml").exists()


def test_v026_evidence_has_no_core_or_agent_production_consumer() -> None:
    """Only the two isolated in-process evidence packages recognize v0.26."""
    repository_root = APP_ROOT.parents[2]
    agent_root = repository_root / "services" / "atlas-agent" / "app"
    core_package = APP_ROOT / "installation_handoff_simulated_delivery"
    agent_package = agent_root / "installation_handoff_simulated_delivery"
    violations: list[str] = []

    for path in _production_python_files(APP_ROOT):
        if core_package in path.parents:
            continue
        source = path.read_text(encoding="utf-8")
        for marker in V026_RECORD_MARKERS:
            if marker in source:
                violations.append(f"atlas-core/{path.relative_to(APP_ROOT)} -> {marker}")

    for path in _production_python_files(agent_root):
        if agent_package in path.parents:
            continue
        source = path.read_text(encoding="utf-8")
        for marker in V026_RECORD_MARKERS:
            if marker in source:
                violations.append(f"atlas-agent/{path.relative_to(agent_root)} -> {marker}")

    assert violations == []


def test_v026_has_zero_http_surface_and_no_production_enablement() -> None:
    from app.api.v1.router import router as api_v1_router

    application = FastAPI()
    application.include_router(api_v1_router)
    openapi = str(application.openapi()).lower()
    settings = (APP_ROOT / "config" / "settings.py").read_text(encoding="utf-8")
    main = (APP_ROOT / "main.py").read_text(encoding="utf-8")

    for marker in (
        "handoff-simulated-delivery",
        "handoff_simulated_delivery",
        "simulated-delivery",
        "simulated_delivery",
    ):
        assert marker not in openapi
        assert marker not in settings.lower()
        assert marker not in main.lower()


def test_v026_keeps_install_container_unsupported_and_home_assistant_blocked() -> None:
    repository_root = APP_ROOT.parents[2]
    agent_root = repository_root / "services" / "atlas-agent" / "app"
    status_source = (agent_root / "routes" / "status.py").read_text(encoding="utf-8")
    candidate_source = (agent_root / "candidate_planning" / "models.py").read_text(
        encoding="utf-8"
    )

    assert 'capability_status: Literal["unsupported"]' in status_source
    assert (
        'SUPPORTED_EXECUTION_INTENTS = frozenset({"update-compose-stack"})'
        in candidate_source
    )
    assert "install-container" not in candidate_source
    assert not (repository_root / "compose" / "home-assistant.yaml").exists()
    assert not (repository_root / "compose" / "home-assistant.yml").exists()


def test_v027_real_intake_has_no_core_or_agent_production_consumer() -> None:
    repository_root = APP_ROOT.parents[2]
    agent_root = repository_root / "services" / "atlas-agent" / "app"
    isolated_agent_package = agent_root / "real_agent_intake_boundary"
    isolated_core_package = APP_ROOT / "dormant_agent_intake_delivery_wiring"
    markers = (
        "app.real_agent_intake_boundary",
        "AgentRealIntakeEvidenceService",
        "AgentRealIntakeEvidenceStore",
        "agent-installation-intake-request-v1",
        "agent-installation-intake-admission-v1",
        "/api/v1/internal/installation-intake",
    )
    violations: list[str] = []
    for path in _production_python_files(APP_ROOT):
        if isolated_core_package in path.parents:
            continue
        source = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker in source:
                violations.append(f"atlas-core/{path.relative_to(APP_ROOT)} -> {marker}")
    for path in _production_python_files(agent_root):
        if isolated_agent_package in path.parents:
            continue
        source = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker in source:
                violations.append(f"atlas-agent/{path.relative_to(agent_root)} -> {marker}")
    assert violations == []


def test_v027_has_no_core_delivery_or_production_agent_http_surface() -> None:
    from app.api.v1.router import router as api_v1_router

    repository_root = APP_ROOT.parents[2]
    agent_root = repository_root / "services" / "atlas-agent" / "app"
    application = FastAPI()
    application.include_router(api_v1_router)
    assert "/api/v1/internal/installation-intake" not in application.openapi()["paths"]

    inspected = (
        APP_ROOT / "main.py",
        APP_ROOT / "api" / "v1" / "router.py",
        APP_ROOT / "config" / "settings.py",
        agent_root / "main.py",
        agent_root / "container" / "application.py",
        agent_root / "config" / "settings.py",
        agent_root / "core_client" / "client.py",
    )
    forbidden = (
        "real_agent_intake_boundary",
        "installation-intake",
        "install_intake",
        "AgentRealIntake",
    )
    assert [
        f"{path.relative_to(repository_root)} -> {marker}"
        for path in inspected
        for marker in forbidden
        if marker in path.read_text(encoding="utf-8")
    ] == []


def test_v027_capability_parity_and_home_assistant_remain_blocked() -> None:
    repository_root = APP_ROOT.parents[2]
    agent_root = repository_root / "services" / "atlas-agent" / "app"
    candidate_source = (agent_root / "candidate_planning" / "models.py").read_text(
        encoding="utf-8"
    )
    status_source = (agent_root / "routes" / "status.py").read_text(encoding="utf-8")
    assert 'SUPPORTED_EXECUTION_INTENTS = frozenset({"update-compose-stack"})' in candidate_source
    assert 'OPERATIONAL_EXECUTION_INTENTS = frozenset({"restart-service"})' in candidate_source
    assert "install-container" not in candidate_source
    assert 'capability_status: Literal["unsupported"]' in status_source

    deployment_roots = (repository_root / "compose", repository_root / "deploy")
    artifacts = [
        path.relative_to(repository_root)
        for root in deployment_roots
        if root.exists()
        for path in root.rglob("*")
        if path.is_file()
        and "home-assistant" in path.name.lower()
        and path.suffix.lower() in {".yaml", ".yml", ".json", ".toml"}
    ]
    assert artifacts == []


def test_v028_client_is_explicit_disabled_no_send_and_non_authorizing() -> None:
    from app.dormant_agent_intake_delivery_wiring import (
        DormantAgentIntakeDeliveryClient,
        DormantAgentIntakeDeliveryConfigurationV1,
        create_dormant_agent_intake_delivery_client,
    )

    assert list(
        inspect.signature(create_dormant_agent_intake_delivery_client).parameters
    ) == [
        "configuration",
        "evidence_reader",
        "preparation_store",
        "clock",
        "id_factory",
    ]
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        and parameter.default is inspect.Parameter.empty
        for parameter in inspect.signature(
            create_dormant_agent_intake_delivery_client
        ).parameters.values()
    )
    assert {
        name
        for name in dir(DormantAgentIntakeDeliveryClient)
        if not name.startswith("_")
    } == {"configuration", "get_preparation", "prepare", "validate_response"}
    for field in (
        "enabled",
        "agent_route_registered",
        "production_transport_registered",
        "production_delivery_allowed",
        "execution_authorized",
        "worker_allowed",
        "mutation_allowed",
        "replay_allowed",
    ):
        assert DormantAgentIntakeDeliveryConfigurationV1.model_fields[field].annotation == Literal[
            False
        ]


def test_v028_package_cannot_load_credentials_or_open_network_runtime() -> None:
    package = APP_ROOT / "dormant_agent_intake_delivery_wiring"
    forbidden_import_roots = {
        "aiohttp",
        "docker",
        "http",
        "httpx",
        "podman",
        "requests",
        "socket",
        "ssl",
        "subprocess",
        "urllib",
    }
    violations: list[str] = []
    for path in _production_python_files(package):
        for imported in _imports(path):
            if imported.split(".")[0] in forbidden_import_roots:
                violations.append(f"{path.relative_to(APP_ROOT)} -> {imported}")
    for path in (package / "contract.py", package / "client.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "open":
                violations.append(f"{path.relative_to(APP_ROOT)} -> open")
            if isinstance(node.func, ast.Attribute) and node.func.attr in {
                "read_bytes",
                "read_text",
                "send",
                "request",
                "connect",
            }:
                violations.append(
                    f"{path.relative_to(APP_ROOT)} -> {node.func.attr}"
                )
        assert "Authorization: Bearer" not in source
    assert violations == []


def test_v028_store_is_append_only_evidence_not_outbox_or_replay_bridge() -> None:
    store = (
        APP_ROOT / "dormant_agent_intake_delivery_wiring" / "store.py"
    ).read_text(encoding="utf-8")
    assert "UPDATE dormant_agent_intake_delivery" not in store
    assert "DELETE FROM dormant_agent_intake_delivery" not in store
    assert {
        node.name
        for node in ast.walk(ast.parse(store))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }.isdisjoint(
        {"send", "deliver", "retry", "reconcile", "consume", "execute", "install", "deploy", "rollback"}
    )


def test_v028_has_no_production_core_agent_or_authority_consumer() -> None:
    repository_root = APP_ROOT.parents[2]
    agent_root = repository_root / "services" / "atlas-agent" / "app"
    isolated_core = APP_ROOT / "dormant_agent_intake_delivery_wiring"
    preflight_contract_root = APP_ROOT / "delivery_activation_preflight"
    isolated_agent = agent_root / "real_agent_intake_boundary"
    markers = (
        "app.dormant_agent_intake_delivery_wiring",
        "DormantAgentIntakeDeliveryClient",
        "DormantAgentIntakeDeliveryPreparationStore",
        "create_dormant_agent_intake_delivery_client",
        "core-agent-intake-delivery-preparation-v1",
        "dormant-agent-intake-delivery-configuration-v1",
    )
    violations: list[str] = []
    for root, isolated in ((APP_ROOT, isolated_core), (agent_root, isolated_agent)):
        for path in _production_python_files(root):
            if isolated in path.parents or preflight_contract_root in path.parents:
                continue
            source = path.read_text(encoding="utf-8")
            violations.extend(
                f"{path.relative_to(repository_root)} -> {marker}"
                for marker in markers
                if marker in source
            )
    assert violations == []


def test_v028_has_no_production_settings_route_or_agent_registration() -> None:
    from app.api.v1.router import router as api_v1_router

    repository_root = APP_ROOT.parents[2]
    agent_root = repository_root / "services" / "atlas-agent" / "app"
    application = FastAPI()
    application.include_router(api_v1_router)
    openapi = str(application.openapi()).lower()
    inspected = (
        APP_ROOT / "main.py",
        APP_ROOT / "api" / "v1" / "router.py",
        APP_ROOT / "config" / "settings.py",
        agent_root / "main.py",
        agent_root / "container" / "application.py",
        agent_root / "config" / "settings.py",
    )
    forbidden = (
        "dormant_agent_intake_delivery_wiring",
        "dormant-agent-intake-delivery",
        "installation-intake",
        "agent_intake_credential",
        "credential_file",
    )
    assert all(marker not in openapi for marker in forbidden)
    assert [
        f"{path.relative_to(repository_root)} -> {marker}"
        for path in inspected
        for marker in forbidden
        if marker in path.read_text(encoding="utf-8").lower()
    ] == []


def test_v028_capability_parity_and_home_assistant_remain_blocked() -> None:
    repository_root = APP_ROOT.parents[2]
    agent_root = repository_root / "services" / "atlas-agent" / "app"
    candidate_source = (agent_root / "candidate_planning" / "models.py").read_text(
        encoding="utf-8"
    )
    status_source = (agent_root / "routes" / "status.py").read_text(
        encoding="utf-8"
    )
    assert 'SUPPORTED_EXECUTION_INTENTS = frozenset({"update-compose-stack"})' in candidate_source
    assert 'OPERATIONAL_EXECUTION_INTENTS = frozenset({"restart-service"})' in candidate_source
    assert "install-container" not in candidate_source
    assert 'capability_status: Literal["unsupported"]' in status_source
    artifacts = [
        path.relative_to(repository_root)
        for root in (repository_root / "compose", repository_root / "deploy")
        if root.exists()
        for path in root.rglob("*")
        if path.is_file()
        and "home-assistant" in path.name.lower()
        and path.suffix.lower() in {".yaml", ".yml", ".json", ".toml"}
    ]
    assert artifacts == []
