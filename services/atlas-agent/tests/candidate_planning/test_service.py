"""Tests for candidate-planning service behavior."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.approval.repository import ApprovalRepository
from app.candidate_planning.models import (
    CandidatePlan,
    CandidatePlanningFailureCode,
    CandidatePlanningSessionStatus,
    CandidatePlanRequest,
    CandidateSnapshot,
    ComposeMutationSpecification,
    CoreCandidatePlanningIntakeStatus,
)
from app.candidate_planning.planner import RepositoryResolver
from app.candidate_planning.service import (
    CandidatePlanningPredecessorNotFoundError,
    CandidatePlanningService,
    CandidatePlanningServiceError,
)
from app.candidate_planning.state import CandidatePlanningStateStore
from app.core_client.exceptions import AtlasCoreTimeoutError
from app.core_client.models import (
    CoreCandidatePlanningIntakeResponse,
    CoreComposeMutationSpecification,
    CoreExecutionCandidateSnapshot,
)
from app.persistence.snapshot import (
    AgentStatePersistenceCoordinator,
    StatePersistenceError,
)
from app.repository.models import RepositorySnapshot
from app.workflow.state import WorkflowStateStore

NOW = datetime(2026, 8, 1, 23, 45, tzinfo=UTC)


class FakeCoreClient:
    def __init__(
        self,
        responses: list[CoreCandidatePlanningIntakeResponse] | None = None,
        *,
        delay_seconds: float = 0.0,
    ) -> None:
        self.responses = responses or []
        self.calls: list[tuple[str, str | None]] = []
        self.error: Exception | None = None
        self.delay_seconds = delay_seconds
        self._active_calls = 0
        self.max_active_calls = 0

    async def validate_candidate_planning_intake(
        self,
        candidate_id: str,
        *,
        expected_candidate_fingerprint: str | None = None,
    ) -> CoreCandidatePlanningIntakeResponse:
        self._active_calls += 1
        self.max_active_calls = max(self.max_active_calls, self._active_calls)
        self.calls.append((candidate_id, expected_candidate_fingerprint))
        try:
            if self.delay_seconds:
                await asyncio.sleep(self.delay_seconds)
            if self.error is not None:
                raise self.error
            return self.responses.pop(0)
        finally:
            self._active_calls -= 1


class FailingPersistence:
    def mutate_candidate_planning(self, mutation):
        raise StatePersistenceError("boom")


class FakeInspector:
    def __init__(
        self,
        repository_root: Path,
        *,
        heads: list[str] | tuple[str, ...] | None = None,
        head: str = "abc123",
    ) -> None:
        self.repository_root = repository_root
        self._heads = tuple(heads) if heads is not None else (head,)
        self._index = 0

    def inspect(self) -> RepositorySnapshot:
        head = self._heads[min(self._index, len(self._heads) - 1)]
        self._index += 1
        return RepositorySnapshot(
            root=self.repository_root,
            branch="feature/atlas-agent",
            head_commit=head,
            is_clean=True,
            modified_files=(),
            staged_files=(),
            untracked_files=(),
        )


class RaisingPlanner:
    def create_plan(self, *, context, snapshot):
        raise ValueError("synthetic planner rejection")


def _candidate_plan(root: Path) -> CandidatePlan:
    return CandidatePlan(
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
        created_at=NOW,
        repository_root=root,
        repository_branch="feature/atlas-agent",
        repository_head="abc123",
        revalidated_candidate_fingerprint="candidate-fingerprint-v1:aaa",
        mutation=ComposeMutationSpecification(file=Path("compose.production.yaml"), service="atlas-agent", property="image", operation="update", expected_value="atlas-agent:old", desired_value="atlas-agent:new", preservation_constraints=("preserve-unrelated-services",)),
    )


def _candidate_snapshot() -> CandidateSnapshot:
    return CandidateSnapshot(
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
        relationship_ids=("relationship-1",),
        expires_at=None,
        intake_status=CoreCandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING,
        intake_reason_codes=(),
        intake_timestamp=NOW,
        mutation=ComposeMutationSpecification(file=Path("compose.production.yaml"), service="atlas-agent", property="image", operation="update", expected_value="atlas-agent:old", desired_value="atlas-agent:new", preservation_constraints=("preserve-unrelated-services",)),
    )


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
        mutation={"file":"compose.production.yaml","service":"atlas-agent","property":"image","operation":"update","expected_value":"atlas-agent:old","desired_value":"atlas-agent:new","preservation_constraints":("preserve-unrelated-services",)},
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


def rc1_accepted_response() -> CoreCandidatePlanningIntakeResponse:
    candidate = candidate_snapshot(intent="rc1-validation-smoke").model_copy(
        update={
            "recommendation_class": "rc1-validation-smoke",
            "target_id": "atlas-repository",
            "mutation": CoreComposeMutationSpecification(
                file="services/atlas-agent/tests/test_execution_engine.py",
                service="atlas-agent",
                property="rc1-validation-marker",
                operation="append-fixed-marker",
                expected_value=None,
                desired_value="# Atlas RC1 execution smoke marker",
                preservation_constraints=(
                    "no-deployment-files",
                    "no-commit",
                    "rc1-validation-only",
                ),
            ),
        }
    )
    return CoreCandidatePlanningIntakeResponse(
        status="accepted_for_planning",
        candidate_id="candidate-1",
        planning_allowed=True,
        reason_codes=(),
        current_candidate_fingerprint="candidate-fingerprint-v1:aaa",
        current_candidate=candidate,
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
    repository_root: Path | None = None,
    repository_inspector_factory=FakeInspector,
    planner=None,
) -> CandidatePlanningService:
    return CandidatePlanningService(
        core_client=core,  # type: ignore[arg-type]
        state_store=store or CandidatePlanningStateStore(),
        state_persistence=persistence,
        repository_resolver=RepositoryResolver(repository_root=repository_root)
        if repository_root is not None
        else None,
        repository_inspector_factory=repository_inspector_factory,
        planner=planner,
        clock=lambda: NOW,
    )


def test_planner_value_error_is_sanitized_and_logged(caplog, tmp_path: Path) -> None:
    service = service_with(
        FakeCoreClient([accepted_response(), accepted_response()]),
        repository_root=tmp_path,
        planner=RaisingPlanner(),
    )
    session = run(
        service.create_planning_session(CandidatePlanRequest(candidate_id="candidate-1"))
    )

    with caplog.at_level("WARNING", logger="app.candidate_planning.service"):
        response = run(service.generate_plan(session.session_id))

    assert response.planning_failure is not None
    assert response.planning_failure.code is CandidatePlanningFailureCode.UNSAFE_PLAN_CONTENT
    assert response.planning_failure.message == "Candidate plan contained unsafe content."
    record = next(
        record
        for record in caplog.records
        if record.message == "Candidate planner rejected a plan"
    )
    assert record.exception_type == "ValueError"
    assert record.exception_message == "synthetic planner rejection"
    assert not hasattr(record, "mutation_desired_value")


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


def test_rc1_mutation_survives_core_intake_to_planner(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ATLAS_ENABLE_RC1_VALIDATION_SMOKE", "true")
    service = service_with(
        FakeCoreClient([rc1_accepted_response(), rc1_accepted_response()]),
        repository_root=tmp_path,
    )

    session = run(
        service.create_planning_session(CandidatePlanRequest(candidate_id="candidate-1"))
    )
    response = run(service.generate_plan(session.session_id))

    assert response.status is CandidatePlanningSessionStatus.PLAN_READY
    assert response.planning_failure is None
    plan = response.plan
    assert plan is not None
    assert plan.mutation is not None
    assert plan.mutation.file == Path("services/atlas-agent/tests/test_execution_engine.py")
    assert plan.mutation.operation == "append-fixed-marker"


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


def test_successor_session_links_to_predecessor() -> None:
    core = FakeCoreClient([accepted_response(), accepted_response(fingerprint="candidate-fingerprint-v1:b")])
    service = service_with(core)

    parent = run(
        service.create_planning_session(CandidatePlanRequest(candidate_id="candidate-1"))
    )
    child = run(
        service.create_successor_planning_session(
            parent.session_id or "",
            CandidatePlanRequest(candidate_id="candidate-1"),
        )
    )

    assert child.session_id is not None
    assert parent.session_id is not None
    assert child.predecessor_session_id == parent.session_id

    successor = service.get_session(child.session_id)
    parent_session = service.get_session(parent.session_id)
    assert successor is not None
    assert parent_session is not None
    assert parent_session.successor_session_id == child.session_id


def test_successor_session_reuses_existing_child() -> None:
    core = FakeCoreClient(
        [
            accepted_response(),
            accepted_response(),
            accepted_response(),
        ]
    )
    service = service_with(core)

    parent = run(
        service.create_planning_session(CandidatePlanRequest(candidate_id="candidate-1"))
    )
    first = run(
        service.create_successor_planning_session(
            parent.session_id or "",
            CandidatePlanRequest(candidate_id="candidate-1"),
        )
    )
    second = run(
        service.create_successor_planning_session(
            parent.session_id or "",
            CandidatePlanRequest(candidate_id="candidate-1"),
        )
    )

    assert first.session_id == second.session_id


def test_successor_session_requires_predecessor() -> None:
    service = service_with(FakeCoreClient([accepted_response()]))

    with pytest.raises(CandidatePlanningPredecessorNotFoundError):
        run(
            service.create_successor_planning_session(
                "candidate-plan-1",
                CandidatePlanRequest(candidate_id="candidate-1"),
            )
        )


def test_successor_session_is_distinct_from_parent_and_preserves_parent_plan(tmp_path: Path) -> None:
    store = CandidatePlanningStateStore()
    parent_service = service_with(
        FakeCoreClient([accepted_response(), accepted_response(), accepted_response()]),
        store=store,
        persistence=AgentStatePersistenceCoordinator(
            state_dir=tmp_path,
            workflow_state=WorkflowStateStore(),
            approval_repository=ApprovalRepository(),
            candidate_planning_state=store,
        ),
        repository_root=tmp_path,
        repository_inspector_factory=lambda _: FakeInspector(
            tmp_path,
            heads=("abc123", "def456"),
        ),
    )

    parent_response = run(
        parent_service.create_planning_session(CandidatePlanRequest(candidate_id="candidate-1"))
    )
    run(parent_service.generate_plan(parent_response.session_id))

    successor_response = run(
        parent_service.create_successor_planning_session(
            parent_response.session_id or "",
            CandidatePlanRequest(candidate_id="candidate-1", expected_candidate_fingerprint="candidate-fingerprint-v1:aaa"),
        )
    )

    assert successor_response.session_id is not None
    assert successor_response.session_id != parent_response.session_id
    assert successor_response.status is CandidatePlanningSessionStatus.READY_FOR_PLANNING
    assert successor_response.plan is None

    parent_after = parent_service.get_session(parent_response.session_id or "")
    child_after = parent_service.get_session(successor_response.session_id)
    assert parent_after is not None
    assert child_after is not None
    assert parent_after.plan is not None
    assert parent_after.plan.identifier == f"candidate-plan-output-{parent_response.session_id}"
    assert parent_after.workflow_session_id is None
    assert child_after.plan is None
    assert child_after.workflow_session_id is None
    assert parent_after.successor_session_id == child_after.identifier
    assert child_after.predecessor_session_id == parent_after.identifier


def test_successor_lineage_concurrency_with_persistence_uses_single_successor(tmp_path: Path) -> None:
    store = CandidatePlanningStateStore()
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = AgentStatePersistenceCoordinator(
        state_dir=tmp_path,
        workflow_state=workflow_state,
        approval_repository=approvals,
        candidate_planning_state=store,
    )
    persistence.initialize()
    core = FakeCoreClient(
        [
            accepted_response(),
            accepted_response(),
            accepted_response(),
        ],
        delay_seconds=0.001,
    )
    service = service_with(
        core,
        store=store,
        persistence=persistence,
        repository_root=tmp_path,
        repository_inspector_factory=lambda _: FakeInspector(tmp_path, head="def456"),
    )

    parent = run(service.create_planning_session(CandidatePlanRequest(candidate_id="candidate-1")))

    async def invoke() -> tuple[str | None, CandidatePlanningSessionStatus]:
        response = await service.create_successor_planning_session(
            parent.session_id or "",
            CandidatePlanRequest(candidate_id="candidate-1"),
        )
        return response.session_id, response.status

    async def run_both() -> tuple[tuple[str | None, CandidatePlanningSessionStatus], ...]:
        return tuple(await asyncio.gather(invoke(), invoke()))

    results = asyncio.run(run_both())

    assert {session_id for session_id, _status in results} == {results[0][0]}
    assert {status for _session_id, status in results} == {
        CandidatePlanningSessionStatus.READY_FOR_PLANNING
    }
    assert core.max_active_calls == 1
    assert len(store.export_snapshot()) == 2
    parent_session = store.get_session(parent.session_id or "")
    successor_session = store.get_session(results[0][0] or "")
    assert parent_session is not None
    assert successor_session is not None
    assert parent_session.successor_session_id == successor_session.identifier
    assert successor_session.predecessor_session_id == parent_session.identifier


def test_successor_lineage_survives_restart_and_reuses_id(tmp_path: Path) -> None:
    store = CandidatePlanningStateStore()
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = AgentStatePersistenceCoordinator(
        state_dir=tmp_path,
        workflow_state=workflow_state,
        approval_repository=approvals,
        candidate_planning_state=store,
    )
    persistence.initialize()
    service = service_with(
        FakeCoreClient([accepted_response(), accepted_response()]),
        store=store,
        persistence=persistence,
        repository_root=tmp_path,
        repository_inspector_factory=lambda _: FakeInspector(tmp_path, head="ghi789"),
    )

    parent = run(service.create_planning_session(CandidatePlanRequest(candidate_id="candidate-1")))
    first = run(
        service.create_successor_planning_session(
            parent.session_id or "",
            CandidatePlanRequest(candidate_id="candidate-1", expected_candidate_fingerprint="candidate-fingerprint-v1:aaa"),
        )
    )

    restarted_store = CandidatePlanningStateStore()
    restarted_persistence = AgentStatePersistenceCoordinator(
        state_dir=tmp_path,
        workflow_state=WorkflowStateStore(),
        approval_repository=ApprovalRepository(),
        candidate_planning_state=restarted_store,
    )
    restarted_persistence.initialize()
    restarted_service = service_with(
        FakeCoreClient([accepted_response()]),
        store=restarted_store,
        persistence=restarted_persistence,
        repository_root=tmp_path,
        repository_inspector_factory=lambda _: FakeInspector(tmp_path, head="ghi789"),
    )

    second = run(
        restarted_service.create_successor_planning_session(
            parent.session_id or "",
            CandidatePlanRequest(candidate_id="candidate-1", expected_candidate_fingerprint="candidate-fingerprint-v1:aaa"),
        )
    )

    assert second.session_id == first.session_id
    assert second.session_id is not None
    assert len(restarted_store.export_snapshot()) == 2


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


def test_generate_plan_revalidates_and_persists_plan(tmp_path: Path) -> None:
    store = CandidatePlanningStateStore()
    core = FakeCoreClient([accepted_response(), accepted_response()])
    service = service_with(core, store=store, repository_root=tmp_path)
    intake = run(service.create_planning_session(CandidatePlanRequest(candidate_id="candidate-1")))

    response = run(service.generate_plan(intake.session_id))

    assert response.status is CandidatePlanningSessionStatus.PLAN_READY
    assert response.plan is not None
    assert response.plan.candidate_id == "candidate-1"
    assert response.plan.repository_root == tmp_path
    assert core.calls == [("candidate-1", None), ("candidate-1", "candidate-fingerprint-v1:aaa")]
    stored = store.get_session(intake.session_id)
    assert stored is not None
    assert stored.plan == response.plan
    assert stored.planning_status is CandidatePlanningSessionStatus.PLAN_READY


def test_generate_plan_is_idempotent_after_plan_ready(tmp_path: Path) -> None:
    core = FakeCoreClient([accepted_response(), accepted_response()])
    service = service_with(core, repository_root=tmp_path)
    intake = run(service.create_planning_session(CandidatePlanRequest(candidate_id="candidate-1")))

    first = run(service.generate_plan(intake.session_id))
    second = run(service.generate_plan(intake.session_id))

    assert first.plan == second.plan
    assert core.calls == [("candidate-1", None), ("candidate-1", "candidate-fingerprint-v1:aaa")]


def test_generate_plan_blocks_stale_core_revalidation(tmp_path: Path) -> None:
    core = FakeCoreClient([accepted_response(), rejected_response("stale")])
    service = service_with(core, repository_root=tmp_path)
    intake = run(service.create_planning_session(CandidatePlanRequest(candidate_id="candidate-1")))

    response = run(service.generate_plan(intake.session_id))

    assert response.status is CandidatePlanningSessionStatus.STALE_BEFORE_PLANNING
    assert response.plan is None
    assert response.planning_failure is not None
    assert response.planning_failure.code is CandidatePlanningFailureCode.CANDIDATE_STALE


def test_generate_plan_requires_trusted_repository_mapping() -> None:
    core = FakeCoreClient([accepted_response(), accepted_response()])
    service = service_with(core)
    intake = run(service.create_planning_session(CandidatePlanRequest(candidate_id="candidate-1")))

    response = run(service.generate_plan(intake.session_id))

    assert response.status is CandidatePlanningSessionStatus.PLANNING_NOT_SUPPORTED
    assert response.plan is None
    assert response.planning_failure is not None
    assert response.planning_failure.code is CandidatePlanningFailureCode.REPOSITORY_MAPPING_UNAVAILABLE


def test_generate_plan_rejects_evidence_unavailable(tmp_path: Path) -> None:
    core = FakeCoreClient([accepted_response(), rejected_response("evidence_unavailable")])
    service = service_with(core, repository_root=tmp_path)
    intake = run(service.create_planning_session(CandidatePlanRequest(candidate_id="candidate-1")))

    response = run(service.generate_plan(intake.session_id))

    assert response.status is CandidatePlanningSessionStatus.STALE_BEFORE_PLANNING
    assert response.planning_failure is not None
    assert response.planning_failure.code is CandidatePlanningFailureCode.EVIDENCE_UNAVAILABLE


def test_generate_plan_does_not_create_workflow_or_approval(tmp_path: Path) -> None:
    store = CandidatePlanningStateStore()
    service = service_with(
        FakeCoreClient([accepted_response(), accepted_response()]),
        store=store,
        repository_root=tmp_path,
    )
    intake = run(service.create_planning_session(CandidatePlanRequest(candidate_id="candidate-1")))

    response = run(service.generate_plan(intake.session_id))

    assert response.status is CandidatePlanningSessionStatus.PLAN_READY
    assert len(store.export_snapshot()) == 1
