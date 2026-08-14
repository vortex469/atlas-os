from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.execution_candidates.fingerprint import build_candidate_fingerprint
from app.execution_candidates.intake import (
    CandidatePlanningIntakeRequest,
    CandidatePlanningIntakeStatus,
)
from app.execution_candidates.models import (
    ApprovalLevel,
    ExecutionCandidate,
    ExecutionCandidateEffectKind,
    ExecutionCandidateStatus,
    ExecutionCategory,
    ExecutionConstraint,
    ExecutionIntent,
    OperationalTargetReference,
    build_execution_candidate_id,
)
from app.main import app
from app.routes import execution_candidate_intake as route
from app.services import execution_candidate_intake as service

client = TestClient(app)
NOW = datetime(2026, 1, 1, tzinfo=UTC)


def candidate() -> ExecutionCandidate:
    source_recommendation_id = "finding-1"
    target_id = "service-frigate"
    return ExecutionCandidate(
        id=build_execution_candidate_id(
            source_subsystem="orion",
            source_recommendation_id=source_recommendation_id,
            catalog_item_id=None,
            target_id=target_id,
            execution_category=ExecutionCategory.RESTART,
            execution_intent=ExecutionIntent.RESTART_SERVICE,
        ),
        source_recommendation_id=source_recommendation_id,
        source_subsystem="orion",
        recommendation_class="restart-service",
        target_id=target_id,
        target_type="service",
        execution_category=ExecutionCategory.RESTART,
        execution_intent=ExecutionIntent.RESTART_SERVICE,
        effect_kind=ExecutionCandidateEffectKind.OPERATIONAL_ACTION,
        status=ExecutionCandidateStatus.ELIGIBLE,
        required_approval_level=ApprovalLevel.STANDARD,
        rationale="Restart the service after approval.",
        constraints=(ExecutionConstraint.SERVICE_DISRUPTION,),
        evidence_ids=("evidence-1",),
        created_at=NOW,
        operational_target=OperationalTargetReference(
            provider_id="docker",
            resource_id=target_id,
            resource_type="service",
            resource_fingerprint="operational-target-v1:abc",
            expected_state="running",
        ),
    )


@pytest.fixture(autouse=True)
def restore_route_dependencies(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(route, "validate_candidate_planning_intake", service.validate_candidate_planning_intake)


def test_planning_intake_endpoint_accepts_current_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    current = candidate()

    async def fake_intake(candidate_id: str, request: CandidatePlanningIntakeRequest):
        assert candidate_id == current.id
        assert request.expected_candidate_fingerprint == build_candidate_fingerprint(current)
        return await service.validate_candidate_planning_intake(
            candidate_id,
            request,
            now=NOW,
            candidate_resolver=lambda candidate_id, **kwargs: current,
            evidence_resolver=lambda candidate: candidate.evidence_ids,
        )

    monkeypatch.setattr(route, "validate_candidate_planning_intake", fake_intake)

    response = client.post(
        f"/api/v1/execution-candidates/{current.id}/planning-intake",
        json={
            "expected_candidate_fingerprint": build_candidate_fingerprint(current),
            "requested_by": "operator",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted_for_planning"
    assert body["planning_allowed"] is True
    assert body["current_candidate"]["id"] == current.id
    assert "mutation" in body["current_candidate"]
    assert body["current_candidate"]["mutation"] is None
    assert body["current_candidate_fingerprint"] == build_candidate_fingerprint(current)


def test_planning_intake_request_rejects_arbitrary_candidate_fields() -> None:
    current = candidate()

    response = client.post(
        f"/api/v1/execution-candidates/{current.id}/planning-intake",
        json={"execution_intent": "restart-service"},
    )

    assert response.status_code == 422


def test_global_collection_failure_maps_to_sanitized_503(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_intake(candidate_id: str, request: CandidatePlanningIntakeRequest):
        del candidate_id, request
        raise service.ExecutionCandidatePlanningIntakeError("/private/path/catalog.yaml failed")

    monkeypatch.setattr(route, "validate_candidate_planning_intake", failing_intake)

    response = client.post("/api/v1/execution-candidates/candidate-missing/planning-intake", json={})

    assert response.status_code == 503
    body = response.json()
    rendered = str(body)
    assert "Execution candidate planning intake is unavailable." in rendered
    assert "/private/path" not in rendered
    assert "catalog.yaml" not in rendered


def test_planning_intake_endpoint_returns_typed_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    async def not_found(candidate_id: str, request: CandidatePlanningIntakeRequest):
        return await service.validate_candidate_planning_intake(
            candidate_id,
            request,
            now=NOW,
            candidate_resolver=lambda candidate_id, **kwargs: (_ for _ in ()).throw(
                service.ExecutionCandidateNotFoundError("missing")
            ),
        )

    monkeypatch.setattr(route, "validate_candidate_planning_intake", not_found)

    response = client.post("/api/v1/execution-candidates/candidate-missing/planning-intake", json={})

    assert response.status_code == 200
    assert response.json()["status"] == CandidatePlanningIntakeStatus.NOT_FOUND.value
