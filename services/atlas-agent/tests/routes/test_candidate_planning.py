"""Tests for candidate-planning HTTP route."""

from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from app.candidate_planning.models import (
    CandidatePlanningFailureCode,
    CandidatePlanningSessionStatus,
    CandidatePlanResponse,
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

    async def create_planning_session(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.response


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
    route_schema = schema["paths"]["/candidate-planning"]["post"]
    assert "workflow" not in route_schema["operationId"].lower()
