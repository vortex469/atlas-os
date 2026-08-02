"""Tests for candidate-planning HTTP route."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.candidate_planning.models import (
    CandidateImplementationTranslationResponse,
    CandidatePlan,
    CandidatePlanningFailureCode,
    CandidatePlanningSession,
    CandidatePlanningSessionStatus,
    CandidatePlanResponse,
    CandidateSnapshot,
    CandidateWorkflowConversionResponse,
    CoreCandidatePlanningIntakeStatus,
)
from app.candidate_planning.service import CandidatePlanningServiceError
from app.config.settings import Settings
from app.main import create_app


class FakeCandidatePlanningService:
    def __init__(self, response: CandidatePlanResponse | None = None) -> None:
        self.response = response
        self.error: CandidatePlanningServiceError | None = None
        self.requests = []
        self.session = None
        self.plan = None
        self.workflow_response = None
        self.implementation_response = None

    async def create_planning_session(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.response

    def get_session(self, session_id: str):
        return self.session if self.session and self.session.identifier == session_id else None

    def get_plan(self, session_id: str):
        return self.plan if self.session and self.session.identifier == session_id else None

    async def generate_plan(self, session_id: str):
        self.requests.append(session_id)
        if self.error is not None:
            raise self.error
        return self.response

    async def convert_plan_to_workflow_shell(self, session_id: str, request):
        self.requests.append((session_id, request))
        if self.error is not None:
            raise self.error
        return self.workflow_response

    async def translate_workflow_shell_to_implementation(self, session_id: str, request):
        self.requests.append((session_id, request))
        if self.error is not None:
            raise self.error
        return self.implementation_response


def make_client(monkeypatch, tmp_path: Path, service: FakeCandidatePlanningService) -> TestClient:
    monkeypatch.setattr(
        "app.main.load_settings",
        lambda: Settings(
            repository_root=Path.cwd().resolve(),
            state_dir=tmp_path / "state",
        ),
    )
    application = create_app()
    application.state.container = replace(
        application.state.container,
        candidate_planning_service=service,
    )
    return TestClient(application)


def ready_response() -> CandidatePlanResponse:
    return CandidatePlanResponse(
        session_id="candidate-plan-1",
        candidate_id="candidate-1",
        status=CandidatePlanningSessionStatus.READY_FOR_PLANNING,
        planning_allowed=True,
        intake_status=CoreCandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING,
        intake_reason_codes=(),
        candidate_fingerprint="candidate-fingerprint-v1:aaa",
    )


def planned_response(tmp_path: Path) -> CandidatePlanResponse:
    plan = CandidatePlan(
        identifier="candidate-plan-output-candidate-plan-1",
        session_id="candidate-plan-1",
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fingerprint-v1:aaa",
        title="Prepare compose stack update proposal",
        objective="Create a minimal repository change proposal.",
        assumptions=("Planning is read-only.",),
        constraints=("requires-current-evidence",),
        proposed_steps=("Inspect trusted compose definitions.",),
        likely_affected_components=("atlas-compose",),
        likely_affected_files=(Path("compose.production.yaml"),),
        verification_strategy=("Validate later after workflow conversion.",),
        rollback_considerations=("Use version control rollback.",),
        unresolved_questions=(),
        evidence_ids=("evidence-1",),
        created_at=datetime(2026, 8, 2, tzinfo=UTC),
        repository_root=tmp_path,
        repository_branch="feature/atlas-agent",
        repository_head="abc123",
        revalidated_candidate_fingerprint="candidate-fingerprint-v1:aaa",
    )
    return CandidatePlanResponse(
        session_id="candidate-plan-1",
        candidate_id="candidate-1",
        status=CandidatePlanningSessionStatus.PLAN_READY,
        planning_allowed=False,
        intake_status=CoreCandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING,
        intake_reason_codes=(),
        candidate_fingerprint="candidate-fingerprint-v1:aaa",
        plan=plan,
    )


def workflow_response(tmp_path: Path) -> CandidateWorkflowConversionResponse:
    plan = planned_response(tmp_path).plan
    assert plan is not None
    return CandidateWorkflowConversionResponse(
        candidate_planning_session_id="candidate-plan-1",
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fingerprint-v1:aaa",
        candidate_plan_id=plan.identifier,
        candidate_plan_fingerprint="candidate-plan-fingerprint-v1:abc",
        workflow_session_id="candidate-workflow-1",
        workflow_status="awaiting_approval",
        implementation_approval_request_id="approval-candidate-workflow-1",
        conversion_status=CandidatePlanningSessionStatus.WORKFLOW_CREATED,
        core_revalidation_status=CoreCandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING,
        reason_codes=(),
    )


def implementation_response() -> CandidateImplementationTranslationResponse:
    return CandidateImplementationTranslationResponse(
        candidate_planning_session_id="candidate-plan-1",
        workflow_session_id="candidate-workflow-1",
        translation_status=CandidatePlanningSessionStatus.IMPLEMENTATION_READY,
        implementation_request_id="candidate-implementation-v1-abc",
        exact_approval_request_id="approval-candidate-workflow-1",
        candidate_fingerprint="candidate-fingerprint-v1:aaa",
        plan_fingerprint="candidate-plan-fingerprint-v1:abc",
        repository_head="abc123",
        translator_version="candidate-update-compose-stack-v1",
        reason_codes=(),
    )


def session_with_plan(tmp_path: Path) -> CandidatePlanningSession:
    timestamp = datetime(2026, 8, 2, tzinfo=UTC)
    return CandidatePlanningSession(
        identifier="candidate-plan-1",
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fingerprint-v1:aaa",
        status=CandidatePlanningSessionStatus.READY_FOR_PLANNING,
        snapshot=CandidateSnapshot(
            candidate_id="candidate-1",
            candidate_fingerprint="candidate-fingerprint-v1:aaa",
            source_recommendation_id="finding-1",
            source_subsystem="orion",
            recommendation_class="update_compose_stack",
            catalog_item_id="frigate",
            target_id="atlas-compose",
            target_type="repository",
            execution_category="update",
            execution_intent="update-compose-stack",
            required_approval_level="standard",
            rationale="Update compose stack.",
            constraints=("requires-current-evidence",),
            evidence_ids=("evidence-1",),
            compatibility_assessment_id="assessment-1",
            compatibility_status="compatible",
            relationship_ids=(),
            expires_at=None,
            intake_status=CoreCandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING,
            intake_reason_codes=(),
            intake_timestamp=timestamp,
        ),
        created_at=timestamp,
        planning_status=CandidatePlanningSessionStatus.PLAN_READY,
        plan=planned_response(tmp_path).plan,
    )


def test_candidate_planning_route_accepts_only_id_and_optional_fingerprint(monkeypatch, tmp_path: Path) -> None:
    service = FakeCandidatePlanningService(ready_response())
    client = make_client(monkeypatch, tmp_path, service)

    response = client.post(
        "/candidate-planning",
        json={
            "candidate_id": "candidate-1",
            "expected_candidate_fingerprint": "candidate-fingerprint-v1:old",
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["session_id"] == "candidate-plan-1"
    assert payload["status"] == "ready_for_planning"
    assert payload["planning_allowed"] is True
    assert service.requests[0].candidate_id == "candidate-1"
    assert service.requests[0].expected_candidate_fingerprint == "candidate-fingerprint-v1:old"


def test_candidate_planning_route_rejects_caller_supplied_payload(monkeypatch, tmp_path: Path) -> None:
    client = make_client(monkeypatch, tmp_path, FakeCandidatePlanningService(ready_response()))

    response = client.post(
        "/candidate-planning",
        json={
            "candidate_id": "candidate-1",
            "execution_intent": "update-compose-stack",
        },
    )

    assert response.status_code == 422


def test_candidate_planning_route_sanitizes_service_failure(monkeypatch, tmp_path: Path) -> None:
    service = FakeCandidatePlanningService()
    service.error = CandidatePlanningServiceError(
        CandidatePlanningFailureCode.ATLAS_CORE_UNAVAILABLE,
        "Atlas Core planning intake is unavailable.",
    )
    client = make_client(monkeypatch, tmp_path, service)

    response = client.post("/candidate-planning", json={"candidate_id": "candidate-1"})

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "atlas_core_unavailable",
        "message": "Atlas Core planning intake is unavailable.",
    }


def test_openapi_exposes_planning_only_endpoint(monkeypatch, tmp_path: Path) -> None:
    client = make_client(monkeypatch, tmp_path, FakeCandidatePlanningService(ready_response()))

    schema = client.get("/openapi.json").json()

    assert set(schema["paths"]["/candidate-planning"]) == {"post"}
    assert set(schema["paths"]["/candidate-planning/{session_id}"]) == {"get"}
    assert set(schema["paths"]["/candidate-planning/{session_id}/plan"]) == {"get", "post"}
    assert set(schema["paths"]["/candidate-planning/{session_id}/workflow"]) == {"post"}
    assert set(schema["paths"]["/candidate-planning/{session_id}/implementation"]) == {"post"}
    route_schema = schema["paths"]["/candidate-planning"]["post"]
    assert "workflow" not in route_schema["operationId"].lower()


def test_generate_plan_route_accepts_empty_body_only(monkeypatch, tmp_path: Path) -> None:
    service = FakeCandidatePlanningService(planned_response(tmp_path))
    client = make_client(monkeypatch, tmp_path, service)

    response = client.post("/candidate-planning/candidate-plan-1/plan")

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "plan_ready"
    assert payload["plan"]["likely_affected_files"] == ["compose.production.yaml"]
    assert service.requests == ["candidate-plan-1"]


def test_get_plan_route_returns_existing_plan_without_generation(monkeypatch, tmp_path: Path) -> None:
    service = FakeCandidatePlanningService(planned_response(tmp_path))
    service.session = session_with_plan(tmp_path)
    service.plan = service.session.plan
    client = make_client(monkeypatch, tmp_path, service)

    response = client.get("/candidate-planning/candidate-plan-1/plan")

    assert response.status_code == 200
    assert response.json()["identifier"] == "candidate-plan-output-candidate-plan-1"
    assert service.requests == []


def test_workflow_conversion_route_accepts_only_expected_fingerprints(monkeypatch, tmp_path: Path) -> None:
    service = FakeCandidatePlanningService()
    service.workflow_response = workflow_response(tmp_path)
    client = make_client(monkeypatch, tmp_path, service)

    response = client.post(
        "/candidate-planning/candidate-plan-1/workflow",
        json={
            "expected_candidate_fingerprint": "candidate-fingerprint-v1:aaa",
            "expected_plan_fingerprint": "candidate-plan-fingerprint-v1:abc",
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["conversion_status"] == "workflow_created"
    assert payload["workflow_session_id"] == "candidate-workflow-1"
    assert service.requests[0][0] == "candidate-plan-1"
    assert service.requests[0][1].expected_candidate_fingerprint == "candidate-fingerprint-v1:aaa"
    assert service.requests[0][1].expected_plan_fingerprint == "candidate-plan-fingerprint-v1:abc"


def test_workflow_conversion_route_rejects_caller_commands(monkeypatch, tmp_path: Path) -> None:
    service = FakeCandidatePlanningService()
    service.workflow_response = workflow_response(tmp_path)
    client = make_client(monkeypatch, tmp_path, service)

    response = client.post(
        "/candidate-planning/candidate-plan-1/workflow",
        json={"execution_argv": ["docker", "compose", "up"]},
    )

    assert response.status_code == 422


def test_implementation_route_accepts_only_expected_fingerprints(monkeypatch, tmp_path: Path) -> None:
    service = FakeCandidatePlanningService()
    service.implementation_response = implementation_response()
    client = make_client(monkeypatch, tmp_path, service)

    response = client.post(
        "/candidate-planning/candidate-plan-1/implementation",
        json={
            "expected_candidate_fingerprint": "candidate-fingerprint-v1:aaa",
            "expected_plan_fingerprint": "candidate-plan-fingerprint-v1:abc",
            "expected_repository_head": "abc123",
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["translation_status"] == "implementation_ready"
    assert payload["implementation_request_id"] == "candidate-implementation-v1-abc"
    assert service.requests[0][0] == "candidate-plan-1"
    assert service.requests[0][1].expected_repository_head == "abc123"


def test_implementation_route_rejects_caller_commands_and_paths(monkeypatch, tmp_path: Path) -> None:
    service = FakeCandidatePlanningService()
    service.implementation_response = implementation_response()
    client = make_client(monkeypatch, tmp_path, service)

    response = client.post(
        "/candidate-planning/candidate-plan-1/implementation",
        json={"argv": ["codex", "implement"], "repository_root": "/opt/atlas"},
    )

    assert response.status_code == 422
