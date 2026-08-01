"""Tests for candidate-planning service behavior."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from app.candidate_planning.models import (
    CandidatePlanningFailureCode,
    CandidatePlanningSessionStatus,
    CandidatePlanRequest,
)
from app.candidate_planning.service import (
    CandidatePlanningService,
    CandidatePlanningServiceError,
)
from app.candidate_planning.state import CandidatePlanningStateStore
from app.core_client.exceptions import AtlasCoreTimeoutError
from app.core_client.models import (
    CoreCandidatePlanningIntakeResponse,
    CoreExecutionCandidateSnapshot,
)
from app.persistence.snapshot import StatePersistenceError

NOW = datetime(2026, 8, 1, 23, 45, tzinfo=UTC)


class FakeCoreClient:
    def __init__(self, responses: list[CoreCandidatePlanningIntakeResponse] | None = None) -> None:
        self.responses = responses or []
        self.calls: list[tuple[str, str | None]] = []
        self.error: Exception | None = None

    async def validate_candidate_planning_intake(
        self,
        candidate_id: str,
        *,
        expected_candidate_fingerprint: str | None = None,
    ) -> CoreCandidatePlanningIntakeResponse:
        self.calls.append((candidate_id, expected_candidate_fingerprint))
        if self.error is not None:
            raise self.error
        return self.responses.pop(0)


class FailingPersistence:
    def mutate_candidate_planning(self, mutation):
        raise StatePersistenceError("boom")


def candidate_snapshot(*, intent: str = "update-compose-stack") -> CoreExecutionCandidateSnapshot:
    return CoreExecutionCandidateSnapshot(
        id="candidate-1",
        source_recommendation_id="finding-1",
        source_subsystem="orion",
        recommendation_class="update_compose_stack",
        catalog_item_id="frigate",
        target_id="atlas-compose",
        target_type="repository",
        execution_category="update",
        execution_intent=intent,
        status="eligible",
        required_approval_level="standard",
        rationale="Update the compose stack.",
        constraints=("requires-current-evidence",),
        evidence_ids=("evidence-1",),
        compatibility_assessment_id="assessment-1",
        compatibility_status="compatible",
        relationship_ids=("relationship-1",),
        created_at=NOW,
        expires_at=None,
    )


def accepted_response(
    *,
    fingerprint: str = "candidate-fingerprint-v1:aaa",
    intent: str = "update-compose-stack",
) -> CoreCandidatePlanningIntakeResponse:
    return CoreCandidatePlanningIntakeResponse(
        status="accepted_for_planning",
        candidate_id="candidate-1",
        planning_allowed=True,
        reason_codes=(),
        current_candidate_fingerprint=fingerprint,
        current_candidate=candidate_snapshot(intent=intent),
    )


def rejected_response(status: str = "stale") -> CoreCandidatePlanningIntakeResponse:
    return CoreCandidatePlanningIntakeResponse(
        status=status,
        candidate_id="candidate-1",
        planning_allowed=False,
        reason_codes=("fingerprint_mismatch",),
        current_candidate_fingerprint="candidate-fingerprint-v1:new",
        current_candidate=None,
    )


def run(coro):
    return asyncio.run(coro)


def service_with(
    core: FakeCoreClient,
    *,
    store: CandidatePlanningStateStore | None = None,
    persistence=None,
) -> CandidatePlanningService:
    return CandidatePlanningService(
        core_client=core,  # type: ignore[arg-type]
        state_store=store or CandidatePlanningStateStore(),
        state_persistence=persistence,
        clock=lambda: NOW,
    )


def test_agent_sends_only_candidate_id_and_fingerprint_to_core() -> None:
    core = FakeCoreClient([accepted_response()])
    service = service_with(core)

    run(
        service.create_planning_session(
            CandidatePlanRequest(
                candidate_id="candidate-1",
                expected_candidate_fingerprint="candidate-fingerprint-v1:old",
            )
        )
    )

    assert core.calls == [("candidate-1", "candidate-fingerprint-v1:old")]


def test_accepted_supported_candidate_creates_ready_session() -> None:
    store = CandidatePlanningStateStore()
    service = service_with(FakeCoreClient([accepted_response()]), store=store)

    response = run(
        service.create_planning_session(CandidatePlanRequest(candidate_id="candidate-1"))
    )

    assert response.status is CandidatePlanningSessionStatus.READY_FOR_PLANNING
    assert response.planning_allowed is True
    assert response.session_id is not None
    sessions = store.export_snapshot()
    assert tuple(sessions) == (response.session_id,)
    snapshot = sessions[response.session_id].snapshot
    assert snapshot.execution_intent == "update-compose-stack"
    assert snapshot.evidence_ids == ("evidence-1",)


def test_accepted_unsupported_intent_returns_unsupported_without_session() -> None:
    store = CandidatePlanningStateStore()
    service = service_with(
        FakeCoreClient([accepted_response(intent="restart-service")]),
        store=store,
    )

    response = run(
        service.create_planning_session(CandidatePlanRequest(candidate_id="candidate-1"))
    )

    assert response.status is CandidatePlanningSessionStatus.UNSUPPORTED_INTENT
    assert response.planning_allowed is False
    assert store.export_snapshot() == {}


def test_rejected_core_intake_creates_no_session() -> None:
    store = CandidatePlanningStateStore()
    service = service_with(FakeCoreClient([rejected_response()]), store=store)

    response = run(
        service.create_planning_session(CandidatePlanRequest(candidate_id="candidate-1"))
    )

    assert response.status is CandidatePlanningSessionStatus.INTAKE_REJECTED
    assert response.intake_status.value == "stale"
    assert store.export_snapshot() == {}


def test_core_timeout_is_sanitized_and_creates_no_session() -> None:
    core = FakeCoreClient()
    core.error = AtlasCoreTimeoutError("timed out")
    store = CandidatePlanningStateStore()
    service = service_with(core, store=store)

    with pytest.raises(CandidatePlanningServiceError) as error:
        run(
            service.create_planning_session(
                CandidatePlanRequest(candidate_id="candidate-1")
            )
        )

    assert error.value.code is CandidatePlanningFailureCode.ATLAS_CORE_UNAVAILABLE
    assert store.export_snapshot() == {}


def test_same_candidate_and_fingerprint_is_idempotent() -> None:
    core = FakeCoreClient([accepted_response(), accepted_response()])
    service = service_with(core)
    request = CandidatePlanRequest(candidate_id="candidate-1")

    first = run(service.create_planning_session(request))
    second = run(service.create_planning_session(request))

    assert first.session_id == second.session_id
    assert first.status is CandidatePlanningSessionStatus.READY_FOR_PLANNING
    assert second.status is CandidatePlanningSessionStatus.READY_FOR_PLANNING


def test_same_candidate_changed_fingerprint_is_rejected_while_active() -> None:
    core = FakeCoreClient(
        [accepted_response(fingerprint="candidate-fingerprint-v1:a"), accepted_response(fingerprint="candidate-fingerprint-v1:b")]
    )
    service = service_with(core)
    request = CandidatePlanRequest(candidate_id="candidate-1")

    first = run(service.create_planning_session(request))
    second = run(service.create_planning_session(request))

    assert first.session_id is not None
    assert second.session_id is None
    assert second.status is CandidatePlanningSessionStatus.INTAKE_REJECTED
    assert second.intake_reason_codes == (
        CandidatePlanningFailureCode.CONFLICTING_ACTIVE_SESSION.value,
    )


def test_persistence_failure_leaves_no_partial_session() -> None:
    store = CandidatePlanningStateStore()
    service = service_with(
        FakeCoreClient([accepted_response()]),
        store=store,
        persistence=FailingPersistence(),
    )

    with pytest.raises(CandidatePlanningServiceError) as error:
        run(
            service.create_planning_session(
                CandidatePlanRequest(candidate_id="candidate-1")
            )
        )

    assert error.value.code is CandidatePlanningFailureCode.PERSISTENCE_FAILED
    assert store.export_snapshot() == {}


def test_concurrent_duplicate_requests_create_one_session() -> None:
    core = FakeCoreClient([accepted_response(), accepted_response()])
    service = service_with(core)
    request = CandidatePlanRequest(candidate_id="candidate-1")

    async def invoke() -> tuple[str | None, CandidatePlanningSessionStatus]:
        response = await service.create_planning_session(request)
        return response.session_id, response.status

    async def run_both() -> tuple[tuple[str | None, CandidatePlanningSessionStatus], ...]:
        return tuple(await asyncio.gather(invoke(), invoke()))

    results = asyncio.run(run_both())

    assert {session_id for session_id, _status in results} == {results[0][0]}
    assert {status for _session_id, status in results} == {
        CandidatePlanningSessionStatus.READY_FOR_PLANNING
    }
