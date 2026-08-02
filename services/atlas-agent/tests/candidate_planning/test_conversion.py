"""Tests for candidate plan to workflow-shell conversion."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from app.approval.repository import ApprovalRepository
from app.candidate_planning.conversion import candidate_plan_fingerprint
from app.candidate_planning.models import (
    CandidatePlan,
    CandidatePlanningSession,
    CandidatePlanningSessionStatus,
    CandidateSnapshot,
    CandidateWorkflowConversionRequest,
    CoreCandidatePlanningIntakeStatus,
)
from app.candidate_planning.planner import RepositoryResolver
from app.candidate_planning.service import CandidatePlanningService
from app.candidate_planning.state import CandidatePlanningStateStore
from app.core_client.models import (
    CoreCandidatePlanningIntakeResponse,
    CoreExecutionCandidateSnapshot,
)
from app.persistence.snapshot import AgentStatePersistenceCoordinator
from app.repository.models import RepositorySnapshot
from app.workflow.models import WorkflowSessionState, WorkflowSource
from app.workflow.state import WorkflowStateStore

NOW = datetime(2026, 8, 2, tzinfo=UTC)


class FakeCoreClient:
    def __init__(self, responses: list[CoreCandidatePlanningIntakeResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str | None]] = []

    async def validate_candidate_planning_intake(
        self,
        candidate_id: str,
        *,
        expected_candidate_fingerprint: str | None = None,
    ) -> CoreCandidatePlanningIntakeResponse:
        self.calls.append((candidate_id, expected_candidate_fingerprint))
        return self.responses.pop(0)


class FakeInspector:
    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root

    def inspect(self) -> RepositorySnapshot:
        return RepositorySnapshot(
            root=self.repository_root,
            branch="feature/atlas-agent",
            head_commit="abc123",
            is_clean=True,
            modified_files=(),
            staged_files=(),
            untracked_files=(),
        )


def run(coro):
    return asyncio.run(coro)


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


def rejected_response(status: str) -> CoreCandidatePlanningIntakeResponse:
    return CoreCandidatePlanningIntakeResponse(
        status=status,
        candidate_id="candidate-1",
        planning_allowed=False,
        reason_codes=("fingerprint_mismatch",),
        current_candidate_fingerprint="candidate-fingerprint-v1:new",
        current_candidate=None,
    )


def persisted_plan(root: Path) -> CandidatePlan:
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
    )


def plan_ready_session(root: Path, *, intent: str = "update-compose-stack") -> CandidatePlanningSession:
    snapshot = CandidateSnapshot(
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fingerprint-v1:aaa",
        source_recommendation_id="finding-1",
        source_subsystem="orion",
        recommendation_class="update_compose_stack",
        catalog_item_id="frigate",
        target_id="atlas-compose",
        target_type="repository",
        execution_category="update",
        execution_intent=intent,
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
    )
    return CandidatePlanningSession(
        identifier="candidate-plan-1",
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fingerprint-v1:aaa",
        status=CandidatePlanningSessionStatus.READY_FOR_PLANNING,
        snapshot=snapshot,
        created_at=NOW,
        planning_status=CandidatePlanningSessionStatus.PLAN_READY,
        plan=persisted_plan(root),
    )


def service_with(
    tmp_path: Path,
    core: FakeCoreClient,
    *,
    session: CandidatePlanningSession | None = None,
    repository_root: Path | None = None,
):
    candidate_state = CandidatePlanningStateStore()
    if session is not None:
        candidate_state.create_session(session)
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = AgentStatePersistenceCoordinator(
        state_dir=tmp_path / "state",
        workflow_state=workflow_state,
        approval_repository=approvals,
        candidate_planning_state=candidate_state,
    )
    service = CandidatePlanningService(
        core_client=core,  # type: ignore[arg-type]
        state_store=candidate_state,
        state_persistence=persistence,
        repository_resolver=RepositoryResolver(
            repository_root=repository_root or tmp_path / "repo"
        ),
        repository_inspector_factory=FakeInspector,
        clock=lambda: NOW,
    )
    return service, candidate_state, workflow_state, approvals, persistence


def test_plan_ready_session_converts_to_candidate_workflow_shell(tmp_path: Path) -> None:
    session = plan_ready_session(tmp_path)
    core = FakeCoreClient([accepted_response()])
    service, candidate_state, workflow_state, approvals, _persistence = service_with(
        tmp_path,
        core,
        session=session,
    )
    expected_plan_fingerprint = candidate_plan_fingerprint(session.plan)  # type: ignore[arg-type]

    response = run(
        service.convert_plan_to_workflow_shell(
            session.identifier,
            CandidateWorkflowConversionRequest(
                expected_candidate_fingerprint=session.candidate_fingerprint,
                expected_plan_fingerprint=expected_plan_fingerprint,
            ),
        )
    )

    assert response.conversion_status is CandidatePlanningSessionStatus.WORKFLOW_CREATED
    assert response.workflow_status == WorkflowSessionState.AWAITING_APPROVAL.value
    assert response.workflow_session_id is not None
    assert response.implementation_approval_request_id == f"approval-{response.workflow_session_id}"
    assert core.calls == [("candidate-1", "candidate-fingerprint-v1:aaa")]
    workflow = workflow_state.get_session(response.workflow_session_id)
    assert workflow is not None
    assert workflow.source is WorkflowSource.CANDIDATE
    assert workflow.request is None
    assert workflow.plan is None
    assert workflow.execution_result is None
    assert workflow.verification_report is None
    assert workflow.review_report is None
    assert workflow.commit_request is None
    assert workflow.candidate_metadata is not None
    assert workflow.candidate_metadata.candidate_plan_fingerprint == expected_plan_fingerprint
    assert workflow.candidate_metadata.execution_intent == "update-compose-stack"
    approval = approvals.get_request(response.implementation_approval_request_id)
    assert approval is not None
    assert approval.decision.request.requested_command == ()
    assert "No executable command" in approval.decision.request.rationale
    updated = candidate_state.get_session(session.identifier)
    assert updated is not None
    assert updated.workflow_session_id == response.workflow_session_id
    assert updated.implementation_approval_request_id == response.implementation_approval_request_id


def test_repeated_conversion_returns_existing_workflow_without_core_call(tmp_path: Path) -> None:
    session = plan_ready_session(tmp_path)
    core = FakeCoreClient([accepted_response()])
    service, _candidate_state, _workflow_state, _approvals, _persistence = service_with(
        tmp_path,
        core,
        session=session,
    )

    first = run(service.convert_plan_to_workflow_shell(session.identifier, CandidateWorkflowConversionRequest()))
    second = run(service.convert_plan_to_workflow_shell(session.identifier, CandidateWorkflowConversionRequest()))

    assert first.workflow_session_id == second.workflow_session_id
    assert core.calls == [("candidate-1", "candidate-fingerprint-v1:aaa")]


def test_stale_candidate_blocks_conversion(tmp_path: Path) -> None:
    session = plan_ready_session(tmp_path)
    core = FakeCoreClient([rejected_response("stale")])
    service, _candidate_state, workflow_state, approvals, _persistence = service_with(
        tmp_path,
        core,
        session=session,
    )

    response = run(service.convert_plan_to_workflow_shell(session.identifier, CandidateWorkflowConversionRequest()))

    assert response.conversion_status is CandidatePlanningSessionStatus.STALE_BEFORE_WORKFLOW
    assert response.reason_codes == ("candidate_stale",)
    assert workflow_state.export_snapshot()[3] == {}
    assert approvals.export_snapshot() == {}


def test_changed_plan_fingerprint_blocks_conversion(tmp_path: Path) -> None:
    session = plan_ready_session(tmp_path)
    core = FakeCoreClient([accepted_response()])
    service, _candidate_state, workflow_state, approvals, _persistence = service_with(
        tmp_path,
        core,
        session=session,
    )

    response = run(
        service.convert_plan_to_workflow_shell(
            session.identifier,
            CandidateWorkflowConversionRequest(expected_plan_fingerprint="candidate-plan-fingerprint-v1:old"),
        )
    )

    assert response.reason_codes == ("plan_fingerprint_mismatch",)
    assert core.calls == []
    assert workflow_state.export_snapshot()[3] == {}
    assert approvals.export_snapshot() == {}


def test_unsafe_plan_content_blocks_conversion(tmp_path: Path) -> None:
    unsafe = replace(
        plan_ready_session(tmp_path),
        plan=replace(persisted_plan(tmp_path), proposed_steps=("Run docker compose up.",)),
    )
    core = FakeCoreClient([accepted_response()])
    service, _candidate_state, workflow_state, approvals, _persistence = service_with(
        tmp_path,
        core,
        session=unsafe,
    )

    response = run(service.convert_plan_to_workflow_shell(unsafe.identifier, CandidateWorkflowConversionRequest()))

    assert response.reason_codes == ("plan_integrity_failed",)
    assert core.calls == []
    assert workflow_state.export_snapshot()[3] == {}
    assert approvals.export_snapshot() == {}


def test_unsupported_intent_does_not_convert(tmp_path: Path) -> None:
    session = plan_ready_session(tmp_path, intent="restart-service")
    core = FakeCoreClient([accepted_response(intent="restart-service")])
    service, _candidate_state, workflow_state, approvals, _persistence = service_with(
        tmp_path,
        core,
        session=session,
    )

    response = run(service.convert_plan_to_workflow_shell(session.identifier, CandidateWorkflowConversionRequest()))

    assert response.reason_codes == ("unsupported_intent",)
    assert workflow_state.export_snapshot()[3] == {}
    assert approvals.export_snapshot() == {}
