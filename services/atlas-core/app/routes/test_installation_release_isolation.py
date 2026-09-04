"""Atlas v0.16-v0.28 release-surface and authority-isolation locks."""

from __future__ import annotations

import ast
import inspect
import re
from concurrent.futures import ThreadPoolExecutor
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
        "/api/v1/installation/candidate-records/{candidate_record_id}/readiness-review": {
            "get",
        },
        "/api/v1/installation/candidate-records/{candidate_record_id}/execution-permission-grants": {
            "get",
            "post",
        },
        "/api/v1/installation/candidate-records/{candidate_record_id}/execution-permission-grants/{grant_id}": {
            "get",
        },
        "/api/v1/installation/candidate-records/{candidate_record_id}/execution-admissions": {
            "get",
            "post",
        },
        "/api/v1/installation/candidate-records/{candidate_record_id}/execution-admissions/{admission_id}": {
            "get",
        },
        "/api/v1/installation/candidate-records/{candidate_record_id}/runner-binding-plans": {
            "get",
            "post",
        },
        "/api/v1/installation/candidate-records/{candidate_record_id}/runner-binding-plans/{plan_id}": {
            "get",
        },
        "/api/v1/installation/candidate-records/{candidate_record_id}/worker-admission-stubs": {
            "get",
            "post",
        },
        "/api/v1/installation/candidate-records/{candidate_record_id}/worker-admission-stubs/{stub_id}": {
            "get",
        },
        "/api/v1/installation/candidate-records/{candidate_record_id}/worker-queue-reservations": {
            "get",
            "post",
        },
        "/api/v1/installation/candidate-records/{candidate_record_id}/worker-queue-reservations/{reservation_id}": {
            "get",
        },
        "/api/v1/installation/candidate-records/{candidate_record_id}/worker-intake-admissions": {
            "get",
            "post",
        },
        "/api/v1/installation/candidate-records/{candidate_record_id}/worker-intake-admissions/{admission_id}": {
            "get",
        },
        "/api/v1/installation/candidate-records/{candidate_record_id}/live-enqueue-admissions": {
            "get",
            "post",
        },
        "/api/v1/installation/candidate-records/{candidate_record_id}/live-enqueue-admissions/{admission_id}": {
            "get",
        },
        "/api/v1/installation/candidate-records/{candidate_record_id}/one-shot-live-enqueues": {
            "get",
            "post",
        },
        "/api/v1/installation/candidate-records/{candidate_record_id}/one-shot-live-enqueues/{enqueue_id}": {
            "get",
        },
        "/api/v1/installation/candidate-records/{candidate_record_id}/queue-observations": {
            "get",
            "post",
        },
        "/api/v1/installation/candidate-records/{candidate_record_id}/queue-observations/{observation_id}": {
            "get",
        },
    }
    prohibited = (
        "approve",
        "execute",
        "dispatch",
        "install",
        "deploy",
        "rollback",
        "dequeue",
        "poll",
        "claim",
        "lease",
        "retry",
        "resend",
    )
    assert not any(
        token in path.removeprefix("/api/v1/installation/candidate-records")
        for path in paths
        for token in prohibited
    )


def test_mission_control_v020_surface_adds_only_review_and_permission_evidence() -> None:
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
        Path("api/installationReadinessReview.ts"),
        Path("api/executionPermissionGrant.ts"),
        Path("api/installationExecutionAdmission.ts"),
        Path("api/runnerBindingPlan.ts"),
        Path("api/workerAdmissionStub.ts"),
        Path("api/workerQueueReservation.ts"),
        Path("api/workerIntakeAdmission.ts"),
        Path("api/liveEnqueueAdmission.ts"),
        Path("api/oneShotLiveEnqueue.ts"),
        Path("api/queueObservation.ts"),
        Path("features/discovery/InstallationCandidateLifecycle.tsx"),
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
    assert "<Link" not in component_source
    assert "<form" not in component_source
    assert "navigate(" not in component_source
    assert re.findall(r'href=\{`([^`]+)`\}', component_source) == [
        (
            "/installation/candidate-records/"
            "${encodeURIComponent(record.candidate_record_id)}/readiness-review"
        )
    ]
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
    live_send_contract_root = APP_ROOT / "live_delivery_send_boundary"
    inert_receipt_contract_root = APP_ROOT / "end_to_end_inert_delivery_receipt"
    readiness_contract_root = APP_ROOT / "installation_readiness_review"
    permission_grant_contract_root = APP_ROOT / "execution_permission_grant"
    execution_admission_contract_root = APP_ROOT / "installation_execution_admission"
    for path in _production_python_files(APP_ROOT):
        if (
            path in V024_ALLOWED_CONSUMERS
            or dormant_wiring_root in path.parents
            or preflight_contract_root in path.parents
            or live_send_contract_root in path.parents
            or inert_receipt_contract_root in path.parents
            or readiness_contract_root in path.parents
            or permission_grant_contract_root in path.parents
            or execution_admission_contract_root in path.parents
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
    readiness_contract_root = APP_ROOT / "installation_readiness_review"
    delivery_agent_root = agent_root / "installation_handoff_simulated_delivery"
    violations: list[str] = []

    for path in _production_python_files(APP_ROOT):
        if (
            delivery_core_root in path.parents
            or readiness_contract_root in path.parents
        ):
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
    # Later releases may expose these historical evidence field names in a
    # non-transport schema. V0.26's invariant is absence of an HTTP route.
    openapi_paths = str(application.openapi()["paths"]).lower()
    settings = (APP_ROOT / "config" / "settings.py").read_text(encoding="utf-8")
    main = (APP_ROOT / "main.py").read_text(encoding="utf-8")

    for marker in (
        "handoff-simulated-delivery",
        "handoff_simulated_delivery",
        "simulated-delivery",
        "simulated_delivery",
    ):
        assert marker not in openapi_paths
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
    v032_agent_package = agent_root / "agent_live_intake_admission"
    isolated_core_package = APP_ROOT / "dormant_agent_intake_delivery_wiring"
    live_send_contract_package = APP_ROOT / "live_delivery_send_boundary"
    inert_receipt_contract_package = APP_ROOT / "end_to_end_inert_delivery_receipt"
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
        if (
            isolated_core_package in path.parents
            or live_send_contract_package in path.parents
            or inert_receipt_contract_package in path.parents
        ):
            continue
        source = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker in source:
                violations.append(f"atlas-core/{path.relative_to(APP_ROOT)} -> {marker}")
    for path in _production_python_files(agent_root):
        if isolated_agent_package in path.parents or v032_agent_package in path.parents:
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
    live_send_contract_root = APP_ROOT / "live_delivery_send_boundary"
    inert_receipt_contract_root = APP_ROOT / "end_to_end_inert_delivery_receipt"
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
            if (
                isolated in path.parents
                or preflight_contract_root in path.parents
                or live_send_contract_root in path.parents
                or inert_receipt_contract_root in path.parents
            ):
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
    core_inspected = (
        APP_ROOT / "main.py",
        APP_ROOT / "api" / "v1" / "router.py",
        APP_ROOT / "config" / "settings.py",
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
        for path in core_inspected
        for marker in forbidden
        if marker in path.read_text(encoding="utf-8").lower()
    ] == []
    agent_registration_source = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in (
            agent_root / "main.py",
            agent_root / "container" / "application.py",
            agent_root / "config" / "settings.py",
        )
    )
    assert "dormant_agent_intake_delivery_wiring" not in agent_registration_source
    assert "dormant-agent-intake-delivery" not in agent_registration_source


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


def test_v029_service_and_store_are_evidence_only_without_authority_bridge() -> None:
    from app.delivery_activation_preflight.service import (
        DeliveryActivationPreflightService,
    )

    assert {
        name
        for name in dir(DeliveryActivationPreflightService)
        if not name.startswith("_")
    } == {"configuration", "create", "get", "list"}
    package = APP_ROOT / "delivery_activation_preflight"
    forbidden_import_roots = {
        "aiohttp", "docker", "http", "httpx", "podman", "requests",
        "socket", "ssl", "subprocess", "urllib",
    }
    forbidden_calls = {
        "activate", "send", "deliver", "dispatch", "consume", "execute",
        "install", "deploy", "rollback", "connect", "request", "run",
    }
    violations: list[str] = []
    for path in _production_python_files(package):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        violations.extend(
            f"{path.relative_to(APP_ROOT)} -> import {imported}"
            for imported in _imports(path)
            if imported.split(".")[0] in forbidden_import_roots
        )
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in forbidden_calls:
                violations.append(f"{path.relative_to(APP_ROOT)} -> def {node.name}")
    store = (package / "store.py").read_text(encoding="utf-8")
    assert "UPDATE delivery_activation_preflights" not in store
    assert "DELETE FROM delivery_activation_preflights" not in store
    assert violations == []


def test_v029_is_default_absent_from_production_construction_and_has_no_consumer() -> None:
    repository_root = APP_ROOT.parents[2]
    agent_root = repository_root / "services" / "atlas-agent" / "app"
    package = APP_ROOT / "delivery_activation_preflight"
    allowed_core = {
        APP_ROOT / "routes" / "delivery_activation_preflight.py",
        APP_ROOT / "api" / "v1" / "router.py",
        APP_ROOT / "operator_controlled_delivery_enablement" / "contract.py",
    }
    markers = (
        "DeliveryActivationPreflightResultV1",
        "DeliveryActivationPreflightService",
        "create_delivery_activation_preflight_service",
        "delivery-activation-preflight-result-v1",
        "core_delivery_activation_preflight_v1",
    )
    violations: list[str] = []
    for path in _production_python_files(APP_ROOT):
        if package in path.parents or path in allowed_core:
            continue
        source = path.read_text(encoding="utf-8")
        violations.extend(
            f"{path.relative_to(repository_root)} -> {marker}"
            for marker in markers if marker in source
        )
    for path in _production_python_files(agent_root):
        source = path.read_text(encoding="utf-8")
        violations.extend(
            f"{path.relative_to(repository_root)} -> {marker}"
            for marker in markers if marker in source
        )
    main = (APP_ROOT / "main.py").read_text(encoding="utf-8")
    assert "delivery_activation_preflight" not in main
    assert violations == []


def test_v029_openapi_is_exact_without_activation_or_delivery_sibling() -> None:
    from app.api.v1.router import router as api_v1_router

    application = FastAPI()
    application.include_router(api_v1_router)
    paths = application.openapi()["paths"]
    collection = "/api/v1/installation-delivery-preflights"
    item = f"{collection}/{{preflight_id}}"
    preflight_paths = {path: value for path, value in paths.items() if "delivery-preflight" in path}
    assert set(preflight_paths) == {collection, item}
    assert set(preflight_paths[collection]) == {"get", "post"}
    assert set(preflight_paths[item]) == {"get"}
    for path in preflight_paths:
        normalized = path.lower().replace("installation-delivery-preflights", "")
        assert all(word not in normalized for word in (
            "activate", "send", "deliver", "execute", "deploy",
        ))


def test_v029_capability_parity_and_home_assistant_remain_blocked() -> None:
    repository_root = APP_ROOT.parents[2]
    agent_root = repository_root / "services" / "atlas-agent" / "app"
    candidate_source = (agent_root / "candidate_planning" / "models.py").read_text(encoding="utf-8")
    status_source = (agent_root / "routes" / "status.py").read_text(encoding="utf-8")
    assert 'SUPPORTED_EXECUTION_INTENTS = frozenset({"update-compose-stack"})' in candidate_source
    assert 'OPERATIONAL_EXECUTION_INTENTS = frozenset({"restart-service"})' in candidate_source
    assert "install-container" not in candidate_source
    assert 'capability_status: Literal["unsupported"]' in status_source
    assert [
        path.relative_to(repository_root)
        for root in (repository_root / "compose", repository_root / "deploy")
        if root.exists()
        for path in root.rglob("*")
        if path.is_file()
        and "home-assistant" in path.name.lower()
        and path.suffix.lower() in {".yaml", ".yml", ".json", ".toml"}
    ] == []


def test_v030_service_store_and_route_are_evidence_only() -> None:
    from app.operator_controlled_delivery_enablement.service import (
        OperatorControlledDeliveryEnablementService,
    )

    assert {
        name
        for name in dir(OperatorControlledDeliveryEnablementService)
        if not name.startswith("_")
    } == {"configuration", "create", "get", "list"}
    package = APP_ROOT / "operator_controlled_delivery_enablement"
    forbidden_import_roots = {
        "aiohttp", "docker", "http", "httpx", "podman", "requests",
        "socket", "ssl", "subprocess", "urllib",
    }
    forbidden_calls = {
        "activate", "send", "deliver", "dispatch", "consume", "execute",
        "install", "deploy", "rollback", "connect", "request", "run",
    }
    violations: list[str] = []
    for path in _production_python_files(package):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        violations.extend(
            f"{path.relative_to(APP_ROOT)} -> import {imported}"
            for imported in _imports(path)
            if imported.split(".")[0] in forbidden_import_roots
        )
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in forbidden_calls
            ):
                violations.append(f"{path.relative_to(APP_ROOT)} -> def {node.name}")
    store = (package / "store.py").read_text(encoding="utf-8")
    assert "UPDATE operator_delivery_enablements" not in store
    assert "DELETE FROM operator_delivery_enablements" not in store
    assert violations == []


def test_v030_is_default_absent_and_has_no_production_consumer() -> None:
    repository_root = APP_ROOT.parents[2]
    agent_root = repository_root / "services" / "atlas-agent" / "app"
    package = APP_ROOT / "operator_controlled_delivery_enablement"
    live_send_contract_root = APP_ROOT / "live_delivery_send_boundary"
    allowed_core = {
        APP_ROOT / "routes" / "delivery_enablement.py",
        APP_ROOT / "api" / "v1" / "router.py",
    }
    markers = (
        "OperatorControlledDeliveryEnablementService",
        "OperatorControlledDeliveryEnablementRecordV1",
        "create_operator_controlled_delivery_enablement_service",
        "operator-controlled-delivery-enablement-record-v1",
        "core_operator_controlled_delivery_enablement_v1",
    )
    violations: list[str] = []
    for path in _production_python_files(APP_ROOT):
        if (
            package in path.parents
            or live_send_contract_root in path.parents
            or path in allowed_core
        ):
            continue
        source = path.read_text(encoding="utf-8")
        violations.extend(
            f"{path.relative_to(repository_root)} -> {marker}"
            for marker in markers
            if marker in source
        )
    for path in _production_python_files(agent_root):
        source = path.read_text(encoding="utf-8")
        violations.extend(
            f"{path.relative_to(repository_root)} -> {marker}"
            for marker in markers
            if marker in source
        )
    main = (APP_ROOT / "main.py").read_text(encoding="utf-8")
    assert "operator_controlled_delivery_enablement" not in main
    assert violations == []


def test_v030_openapi_is_exact_without_authority_sibling() -> None:
    from app.api.v1.router import router as api_v1_router

    application = FastAPI()
    application.include_router(api_v1_router)
    paths = application.openapi()["paths"]
    collection = "/api/v1/installation-delivery-enablements"
    item = f"{collection}/{{enablement_id}}"
    enablement_paths = {
        path: value for path, value in paths.items() if "delivery-enablement" in path
    }
    assert set(enablement_paths) == {collection, item}
    assert set(enablement_paths[collection]) == {"get", "post"}
    assert set(enablement_paths[item]) == {"get"}
    for path in enablement_paths:
        normalized = path.lower().replace("installation-delivery-enablements", "")
        assert all(
            word not in normalized
            for word in (
                "send", "deliver", "activate", "install", "execute", "deploy",
            )
        )


def test_v030_concurrent_exact_retry_creates_one_permanent_record(
    tmp_path: Path,
) -> None:
    from app.operator_controlled_delivery_enablement.store import (
        OperatorControlledDeliveryEnablementStore,
    )
    from app.operator_controlled_delivery_enablement.test_contract import (
        OPERATOR,
        _create,
    )
    from app.operator_controlled_delivery_enablement.test_service import _service

    database = tmp_path / "enablement.sqlite3"
    service, _, _, evidence = _service(tmp_path, database=database)
    create = _create(evidence)

    def submit(correlation: str):
        return service.create(
            create,
            authenticated_operator_id=OPERATOR,
            idempotency_key="concurrent-enable",
            correlation_id=correlation,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(submit, ("concurrent-1", "concurrent-2")))
    assert {outcome.disposition for outcome in outcomes} == {
        "created",
        "exact_replay",
    }
    assert outcomes[0].record == outcomes[1].record
    assert outcomes[0].record is not None
    assert not any(outcome.replay_allowed for outcome in outcomes)
    assert OperatorControlledDeliveryEnablementStore(database).list_owned(
        operator_id=OPERATOR
    ) == (outcomes[0].record,)


def test_v030_capability_parity_and_home_assistant_remain_blocked() -> None:
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


def test_v031_live_send_is_explicit_default_off_one_shot_and_non_authorizing() -> None:
    from app.live_delivery_send_boundary.contract import (
        LiveDeliverySendReceiptV1,
        LiveDeliverySendTransportResultV1,
        LiveDeliveryTransportConfigurationV1,
    )
    from app.live_delivery_send_boundary.transport import LiveDeliverySendCoordinator

    assert LiveDeliveryTransportConfigurationV1.model_fields["enabled"].default is False
    assert set(inspect.signature(LiveDeliverySendCoordinator).parameters) == {
        "reservation_service",
        "store",
        "credential_resolver",
        "transport",
        "clock",
    }
    assert inspect.signature(LiveDeliverySendCoordinator).parameters[
        "transport"
    ].default is inspect.Parameter.empty
    for model in (LiveDeliverySendReceiptV1, LiveDeliverySendTransportResultV1):
        for field in (
            "execution_authorized",
            "installation_allowed",
            "worker_allowed",
            "workflow_allowed",
            "deployment_allowed",
            "mutation_allowed",
            "replay_allowed",
        ):
            if field in model.model_fields:
                assert model.model_fields[field].annotation == Literal[False]
    assert LiveDeliverySendTransportResultV1.model_fields[
        "automatic_retries"
    ].default == 0
    assert LiveDeliverySendTransportResultV1.model_fields["one_shot_only"].default is True
    for field in (
        "execution_attempted",
        "installation_attempted",
        "worker_attempted",
        "workflow_attempted",
        "deployment_attempted",
        "mutation_attempted",
    ):
        assert LiveDeliverySendTransportResultV1.model_fields[field].annotation == Literal[
            False
        ]


def test_v031_live_send_has_no_route_registration_or_authority_consumer() -> None:
    repository_root = APP_ROOT.parents[2]
    package = APP_ROOT / "live_delivery_send_boundary"
    inert_receipt_contract_root = APP_ROOT / "end_to_end_inert_delivery_receipt"
    agent_root = repository_root / "services" / "atlas-agent" / "app"
    worker_root = repository_root / "services" / "atlas-execution-worker"
    markers = (
        "app.live_delivery_send_boundary",
        "LiveDeliverySendAttemptV1",
        "LiveDeliverySendReceiptV1",
        "LiveDeliverySendTransportResultV1",
        "live-delivery-send-receipt-v1",
        "live_delivery_send_attempts",
    )
    violations: list[str] = []
    for root in (APP_ROOT, agent_root, worker_root):
        for path in _production_python_files(root):
            if package in path.parents or inert_receipt_contract_root in path.parents:
                continue
            source = path.read_text(encoding="utf-8")
            violations.extend(
                f"{path.relative_to(repository_root)} -> {marker}"
                for marker in markers
                if marker in source
            )
    for path in (
        APP_ROOT / "main.py",
        APP_ROOT / "api" / "v1" / "router.py",
    ):
        source = path.read_text(encoding="utf-8")
        assert "installation-delivery-sends" not in source
        assert "live_delivery_send_boundary" not in source
    assert violations == []


def test_v031_secret_is_not_persisted_and_exact_retry_performs_zero_io(
    tmp_path: Path,
) -> None:
    from app.live_delivery_send_boundary.test_transport import (
        _admitted_body,
        _coordinator,
        _send,
    )
    from app.live_delivery_send_boundary.transport import LiveDeliveryHttpResponse

    database = tmp_path / "release-live-send.sqlite3"
    coordinator, resolver, transport, evidence, _ = _coordinator(
        tmp_path,
        LiveDeliveryHttpResponse(200, _admitted_body(tmp_path)),
        database=database,
    )
    first = _send(coordinator, evidence)
    second = _send(coordinator, evidence)
    assert first.disposition == "admitted_evidence_only"
    assert second.disposition == "exact_replay"
    assert first.receipt == second.receipt
    assert resolver.calls == 1
    assert len(transport.calls) == 1
    persisted = b"".join(
        path.read_bytes()
        for path in tmp_path.glob("release-live-send.sqlite3*")
        if path.is_file()
    )
    assert b"super-secret-token" not in persisted
    assert b"Authorization" not in persisted
    assert not first.replay_allowed


def test_v031_home_assistant_remains_non_installable_and_has_no_artifact() -> None:
    repository_root = APP_ROOT.parents[2]
    agent_root = repository_root / "services" / "atlas-agent" / "app"
    candidate_source = (agent_root / "candidate_planning" / "models.py").read_text(
        encoding="utf-8"
    )
    assert "install-container" not in candidate_source
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


def test_v032_agent_admission_does_not_widen_core_live_send_or_gain_consumers() -> None:
    repository_root = APP_ROOT.parents[2]
    agent_package = (
        repository_root
        / "services"
        / "atlas-agent"
        / "app"
        / "agent_live_intake_admission"
    )
    core_markers = (
        "agent_live_intake_admission",
        "AgentLiveIntakeAdmissionV1",
        "AgentLiveIntakeAcknowledgementV1",
        "agent-live-intake-admission-v1",
    )
    inert_receipt_contract_root = APP_ROOT / "end_to_end_inert_delivery_receipt"
    readiness_contract_root = APP_ROOT / "installation_readiness_review"
    violations = [
        f"{path.relative_to(repository_root)} -> {marker}"
        for path in _production_python_files(APP_ROOT)
        if (
            inert_receipt_contract_root not in path.parents
            and readiness_contract_root not in path.parents
        )
        for marker in core_markers
        if marker in path.read_text(encoding="utf-8")
    ]
    assert violations == []
    assert agent_package.is_dir()

    contract_source = (
        APP_ROOT / "live_delivery_send_boundary" / "contract.py"
    ).read_text(encoding="utf-8")
    transport_source = (
        APP_ROOT / "live_delivery_send_boundary" / "transport.py"
    ).read_text(encoding="utf-8")
    assert 'automatic_retries: Literal[0] = 0' in contract_source
    assert 'one_shot_only: Literal[True] = True' in contract_source
    assert "for attempt in" not in transport_source
    assert "while " not in transport_source
    assert all(
        marker not in transport_source.lower()
        for marker in ("scheduler", "daemon", "retry queue", "background task")
    )


def test_v033_receipt_composition_is_explicit_internal_and_unregistered() -> None:
    from app.end_to_end_inert_delivery_receipt.composition import (
        EndToEndInertDeliveryComposition,
    )

    assert set(inspect.signature(EndToEndInertDeliveryComposition).parameters) == {
        "configuration",
        "authenticity",
        "credential_resolver",
        "transport",
        "prior_receipt_writer",
        "store",
        "clock",
        "receipt_id_factory",
    }
    repository_root = APP_ROOT.parents[2]
    package = APP_ROOT / "end_to_end_inert_delivery_receipt"
    readiness_contract_root = APP_ROOT / "installation_readiness_review"
    markers = (
        "app.end_to_end_inert_delivery_receipt",
        "EndToEndInertDeliveryComposition",
        "EndToEndInertDeliveryReceiptV1",
        "end-to-end-inert-delivery-receipt-v1",
        "inert_delivery_receipts",
    )
    violations = [
        f"{path.relative_to(repository_root)} -> {marker}"
        for root in (
            APP_ROOT,
            repository_root / "services" / "atlas-agent" / "app",
            repository_root / "services" / "atlas-execution-worker",
        )
        for path in _production_python_files(root)
        if (
            package not in path.parents
            and readiness_contract_root not in path.parents
        )
        for marker in markers
        if marker in path.read_text(encoding="utf-8")
    ]
    assert violations == []
    for path in (APP_ROOT / "main.py", APP_ROOT / "api" / "v1" / "router.py"):
        source = path.read_text(encoding="utf-8")
        assert "inert-delivery-receipt" not in source
        assert "end_to_end_inert_delivery_receipt" not in source


def test_v033_exact_duplicate_is_zero_io_and_persistence_is_secret_free(
    tmp_path: Path,
) -> None:
    from app.end_to_end_inert_delivery_receipt.test_composition import (
        _compose,
        _composition,
    )

    request, composition, resolver, transport, writer = _composition(tmp_path)
    first = _compose(composition, request)
    duplicate = _compose(composition, request)
    assert first.disposition == "verified_inert_receipt"
    assert duplicate.disposition == "exact_duplicate"
    assert first.receipt == duplicate.receipt
    assert resolver.calls == writer.calls == len(transport.calls) == 1
    persisted = b"".join(
        path.read_bytes()
        for path in tmp_path.glob("v33.sqlite3*")
        if path.is_file()
    )
    for forbidden in (
        b"transient-test-secret",
        b"Authorization",
        b"Bearer ",
        b"/run/secrets",
    ):
        assert forbidden not in persisted
    rendered = first.model_dump_json().encode()
    assert b"transient-test-secret" not in rendered
    assert b"Authorization" not in rendered
    assert not first.replay_allowed


def test_v033_receipt_models_and_composition_grant_no_effect_authority() -> None:
    from app.end_to_end_inert_delivery_receipt.contract import (
        EndToEndInertDeliveryAuditEvidenceV1,
        EndToEndInertDeliveryReceiptV1,
        EndToEndInertDeliveryResultV1,
        EndToEndInertDeliveryVerificationV1,
    )

    for model in (
        EndToEndInertDeliveryVerificationV1,
        EndToEndInertDeliveryReceiptV1,
        EndToEndInertDeliveryAuditEvidenceV1,
        EndToEndInertDeliveryResultV1,
    ):
        for field in (
            "execution_admission_granted",
            "execution_authorized",
            "installation_allowed",
            "worker_allowed",
            "workflow_allowed",
            "deployment_allowed",
            "mutation_allowed",
            "replay_allowed",
        ):
            assert model.model_fields[field].annotation == Literal[False]

    composition_source = (
        APP_ROOT / "end_to_end_inert_delivery_receipt" / "composition.py"
    ).read_text(encoding="utf-8")
    assert "automatic_retries" not in composition_source
    assert "while " not in composition_source
    assert "subprocess" not in composition_source
    assert "docker" not in composition_source.lower()
    assert all(
        marker not in composition_source.lower()
        for marker in (
            "start_workflow",
            "dispatch_worker",
            "provider mutation",
            "repository mutation",
            "in-guest mutation",
            "rollback",
        )
    )


def test_v033_preserves_v031_one_shot_and_v032_admission_only_boundaries() -> None:
    live_contract = (
        APP_ROOT / "live_delivery_send_boundary" / "contract.py"
    ).read_text(encoding="utf-8")
    live_transport = (
        APP_ROOT / "live_delivery_send_boundary" / "transport.py"
    ).read_text(encoding="utf-8")
    assert 'automatic_retries: Literal[0] = 0' in live_contract
    assert 'one_shot_only: Literal[True] = True' in live_contract
    assert "while " not in live_transport

    repository_root = APP_ROOT.parents[2]
    agent_package = (
        repository_root
        / "services"
        / "atlas-agent"
        / "app"
        / "agent_live_intake_admission"
    )
    agent_contract = (agent_package / "contract.py").read_text(encoding="utf-8")
    agent_route = (agent_package / "route.py").read_text(encoding="utf-8")
    assert 'evidence_only: Literal[True] = True' in agent_contract
    assert 'execution_authorized: Literal[False] = False' in agent_contract
    assert 'INTAKE_PATH = "/api/v1/internal/installation-intake"' in agent_contract
    assert "INTAKE_PATH" in agent_route
    for marker in ("install-container", "execute", "deploy", "start-workflow"):
        assert f'"{marker}"' not in agent_route


def test_v033_home_assistant_remains_blocked_without_deployment_artifact() -> None:
    repository_root = APP_ROOT.parents[2]
    agent_models = (
        repository_root
        / "services"
        / "atlas-agent"
        / "app"
        / "candidate_planning"
        / "models.py"
    ).read_text(encoding="utf-8")
    assert "install-container" not in agent_models
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
