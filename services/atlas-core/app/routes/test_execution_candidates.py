from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.execution_candidates.models import (
    ApprovalLevel,
    ExecutionCandidate,
    ExecutionCandidateEffectKind,
    ExecutionCandidateStatus,
    ExecutionCategory,
    ExecutionConstraint,
    ExecutionIntent,
    build_execution_candidate_id,
)
from app.intelligence.findings import Finding, Severity
from app.main import app
from app.routes import execution_candidates as routes
from app.services import execution_candidates as service
from app.testing import ASGITestClient

client = ASGITestClient(app)
NOW = datetime(2026, 1, 1, tzinfo=UTC)


def finding(**details: object) -> Finding:
    payload: dict[str, object] = {
        "source_subsystem": "orion",
        "recommendation_class": "restart_service",
        "target_id": "service-frigate",
        "target_type": "service",
    }
    payload.update(details)
    return Finding(
        id="finding-1",
        severity=Severity.WARNING,
        category="test",
        source="orion",
        title="Restart service",
        message="Restart the service after approval.",
        recommendation="Restart service.",
        details=payload,
        affects_health=False,
        score_penalty=0,
    )


def candidate(
    *,
    source_recommendation_id: str = "finding-1",
    target_id: str = "service-frigate",
    status: ExecutionCandidateStatus = ExecutionCandidateStatus.ELIGIBLE,
    category: ExecutionCategory = ExecutionCategory.RESTART,
    intent: ExecutionIntent = ExecutionIntent.RESTART_SERVICE,
    source_subsystem: str = "orion",
) -> ExecutionCandidate:
    return ExecutionCandidate(
        id=build_execution_candidate_id(
            source_subsystem=source_subsystem,
            source_recommendation_id=source_recommendation_id,
            catalog_item_id=None,
            target_id=target_id,
            execution_category=category,
            execution_intent=intent,
        ),
        source_recommendation_id=source_recommendation_id,
        source_subsystem=source_subsystem,
        recommendation_class=intent.value,
        target_id=target_id,
        target_type="service",
        execution_category=category,
        execution_intent=intent,
        effect_kind=(
            ExecutionCandidateEffectKind.OPERATIONAL_ACTION
            if intent is ExecutionIntent.RESTART_SERVICE
            else ExecutionCandidateEffectKind.REPOSITORY_CHANGE
        ),
        status=status,
        required_approval_level=ApprovalLevel.STANDARD,
        rationale="Restart the service after approval.",
        constraints=(ExecutionConstraint.SERVICE_DISRUPTION,) if category == ExecutionCategory.RESTART else (),
        evidence_ids=("evidence-1",),
        created_at=NOW,
    )


@pytest.fixture(autouse=True)
def restore_route_dependencies(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        routes,
        "collect_current_execution_candidates",
        service.collect_current_execution_candidates,
    )
    monkeypatch.setattr(
        routes,
        "get_current_execution_candidate",
        service.get_current_execution_candidate,
    )


@pytest.mark.anyio
async def test_advisory_only_findings_produce_not_eligible_candidate_collection() -> None:
    candidates = await service.collect_current_execution_candidates(
        finding_collector=lambda: (
            finding(recommendation_class="investigate_compatibility", source_subsystem="discovery"),
        ),
        now=NOW,
    )

    assert len(candidates) == 1
    assert candidates[0].execution_category == ExecutionCategory.UNSUPPORTED
    assert candidates[0].execution_intent == ExecutionIntent.UNSUPPORTED_RECOMMENDATION
    assert candidates[0].status == ExecutionCandidateStatus.NOT_ELIGIBLE


@pytest.mark.anyio
async def test_resolved_evidence_allows_eligible_candidate() -> None:
    candidates = await service.collect_current_execution_candidates(
        finding_collector=lambda: (
            finding(
                recommendation_class="update_compose_stack",
                target_id="atlas-compose",
                target_type="repository",
                evidence_ids=("evidence-1",),
            ),
        ),
        available_evidence_ids=("evidence-1",),
        now=NOW,
    )

    assert len(candidates) == 1
    assert candidates[0].status == ExecutionCandidateStatus.ELIGIBLE


@pytest.mark.anyio
async def test_unresolved_evidence_produces_not_eligible_candidate() -> None:
    candidates = await service.collect_current_execution_candidates(
        finding_collector=lambda: (
            finding(
                recommendation_class="update_compose_stack",
                target_id="atlas-compose",
                target_type="repository",
                evidence_ids=("evidence-1",),
            ),
        ),
        available_evidence_ids=(),
        now=NOW,
    )

    assert len(candidates) == 1
    assert candidates[0].status == ExecutionCandidateStatus.NOT_ELIGIBLE


def test_list_endpoint_returns_empty_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    async def empty_candidates():
        return ()

    monkeypatch.setattr(routes, "collect_current_execution_candidates", empty_candidates)

    response = client.get("/api/v1/execution-candidates")

    assert response.status_code == 200
    assert response.json() == {
        "candidates": [],
        "total": 0,
        "limit": 50,
        "offset": 0,
        "has_more": False,
    }


def test_list_endpoint_distinguishes_eligible_and_not_eligible(monkeypatch: pytest.MonkeyPatch) -> None:
    async def candidates():
        return (
            candidate(source_recommendation_id="finding-b", status=ExecutionCandidateStatus.NOT_ELIGIBLE),
            candidate(source_recommendation_id="finding-a", status=ExecutionCandidateStatus.ELIGIBLE),
        )

    monkeypatch.setattr(routes, "collect_current_execution_candidates", candidates)

    response = client.get("/api/v1/execution-candidates")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["candidates"]] == sorted(
        item["id"] for item in body["candidates"]
    )
    assert {item["status"] for item in body["candidates"]} == {"eligible", "not_eligible"}


@pytest.mark.anyio
async def test_duplicate_candidate_ids_are_deduplicated_in_service() -> None:
    duplicate = finding(evidence_ids=("evidence-1",))

    candidates = await service.collect_current_execution_candidates(
        available_evidence_ids=("evidence-1",),
        now=NOW,
        finding_collector=lambda: (duplicate, duplicate),
    )

    assert len(candidates) == 1


def test_filters_combine_with_and(monkeypatch: pytest.MonkeyPatch) -> None:
    async def candidates():
        return (
            candidate(source_recommendation_id="finding-a", target_id="service-frigate"),
            candidate(
                source_recommendation_id="finding-b",
                target_id="service-ollama",
                category=ExecutionCategory.UPDATE,
                intent=ExecutionIntent.UPDATE_CONTAINER_IMAGE,
            ),
        )

    monkeypatch.setattr(routes, "collect_current_execution_candidates", candidates)

    response = client.get(
        "/api/v1/execution-candidates",
        params={
            "status": "eligible",
            "category": "restart",
            "intent": "restart-service",
            "source_subsystem": "orion",
            "target_id": "service-frigate",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["candidates"][0]["target_id"] == "service-frigate"


def test_pagination_uses_total_before_slicing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def candidates():
        return tuple(candidate(source_recommendation_id=f"finding-{index}") for index in range(3))

    monkeypatch.setattr(routes, "collect_current_execution_candidates", candidates)

    response = client.get("/api/v1/execution-candidates", params={"limit": 2, "offset": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["candidates"]) == 2
    assert body["has_more"] is False


def test_offset_beyond_total_returns_empty_page(monkeypatch: pytest.MonkeyPatch) -> None:
    async def candidates():
        return (candidate(),)

    monkeypatch.setattr(routes, "collect_current_execution_candidates", candidates)

    response = client.get("/api/v1/execution-candidates", params={"offset": 99})

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["candidates"] == []


def test_detail_endpoint_returns_current_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    current = candidate()

    async def get_candidate(candidate_id: str):
        assert candidate_id == current.id
        return current

    monkeypatch.setattr(routes, "get_current_execution_candidate", get_candidate)

    response = client.get(f"/api/v1/execution-candidates/{current.id}")

    assert response.status_code == 200
    assert response.json()["id"] == current.id


def test_detail_endpoint_returns_current_state_404(monkeypatch: pytest.MonkeyPatch) -> None:
    async def get_candidate(candidate_id: str):
        raise service.ExecutionCandidateNotFoundError("missing")

    monkeypatch.setattr(routes, "get_current_execution_candidate", get_candidate)

    response = client.get("/api/v1/execution-candidates/candidate-missing")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["message"] == "Execution candidate is not present in the current projection."


def test_collection_failure_returns_sanitized_503(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_candidates():
        raise service.ExecutionCandidateCollectionError("/private/path secret token")

    monkeypatch.setattr(routes, "collect_current_execution_candidates", failing_candidates)

    response = client.get("/api/v1/execution-candidates")

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["message"] == "Execution candidates are unavailable."
    assert "/private/path" not in response.text
    assert "secret token" not in response.text


def test_public_dto_excludes_internal_projection_and_secret_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    current = candidate()

    async def candidates():
        return (current,)

    monkeypatch.setattr(routes, "collect_current_execution_candidates", candidates)

    response = client.get("/api/v1/execution-candidates")

    assert response.status_code == 200
    body = response.text
    assert "ProjectionResult" not in body
    assert "reason_code" not in body
    assert "eligibility" not in body
    assert "token" not in body
    assert "rm -rf" not in body
    item = response.json()["candidates"][0]
    assert set(item) == {
        "id",
        "source_recommendation_id",
        "source_subsystem",
        "recommendation_class",
        "catalog_item_id",
        "target_id",
        "target_type",
        "execution_category",
            "execution_intent",
            "effect_kind",
        "status",
        "required_approval_level",
        "rationale",
        "constraints",
        "evidence_ids",
        "compatibility_assessment_id",
        "compatibility_status",
        "relationship_ids",
        "created_at",
        "expires_at",
    }


def test_ace_summary_shape_remains_unchanged() -> None:
    schema = app.openapi()["components"]["schemas"]["AceSummary"]

    assert set(schema["properties"]) == {
        "score",
        "status",
        "summary",
        "findings",
        "assessments",
        "recommendations",
        "telemetry",
    }


def test_intelligence_routes_remain_registered() -> None:
    paths = app.openapi()["paths"]

    assert "/api/v1/intelligence/telemetry/history" in paths
    assert "/api/v1/intelligence/telemetry/history/export" in paths


def test_execution_candidate_openapi_exposes_only_reviewed_methods() -> None:
    paths = {
        path: methods
        for path, methods in app.openapi()["paths"].items()
        if path.startswith("/api/v1/execution-candidates")
    }

    assert set(paths) == {
        "/api/v1/execution-candidates",
        "/api/v1/execution-candidates/{candidate_id}",
        "/api/v1/execution-candidates/{candidate_id}/planning-intake",
        "/api/v1/execution-candidates/operator-intents",
        "/api/v1/execution-candidates/operator-intents/capabilities",
        "/api/v1/execution-candidates/operator-intents/capabilities/{selector_id}/resources",
        "/api/v1/execution-candidates/operator-intents/resources",
    }
    assert set(paths["/api/v1/execution-candidates"]) == {"get"}
    assert set(paths["/api/v1/execution-candidates/{candidate_id}"]) == {"get"}
    assert set(paths["/api/v1/execution-candidates/{candidate_id}/planning-intake"]) == {"post"}
    assert set(paths["/api/v1/execution-candidates/operator-intents"]) == {"post"}
    assert set(
        paths["/api/v1/execution-candidates/operator-intents/capabilities"]
    ) == {"get"}
    assert set(
        paths[
            "/api/v1/execution-candidates/operator-intents/capabilities/"
            "{selector_id}/resources"
        ]
    ) == {"get"}
    assert set(paths["/api/v1/execution-candidates/operator-intents/resources"]) == {
        "get"
    }


def test_execution_candidate_openapi_uses_public_dtos_only() -> None:
    schema_names = set(app.openapi()["components"]["schemas"])

    assert "ExecutionCandidate" not in schema_names
    assert "ProjectionResult" not in schema_names
    assert "ExecutionEligibilityResult" not in schema_names
    assert "ExecutionCandidateResponse" in schema_names
    assert "ExecutionCandidatePageResponse" in schema_names
    assert "CandidatePlanningExecutionCandidateResponse" in schema_names
