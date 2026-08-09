"""Tests for candidate execution validation."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.approval.models import (
    ApprovalDecision,
    ApprovalPurpose,
    ApprovalRequest,
    ApprovalResult,
    ApprovalStatus,
)
from app.candidate_planning.conversion import candidate_plan_fingerprint
from app.candidate_planning.execution import (
    CandidateExecutionFailureCode,
    CandidateExecutionValidator,
)
from app.candidate_planning.implementation import TRANSLATOR_VERSION
from app.candidate_planning.models import (
    CandidateImplementationRequest,
    CandidatePlan,
    CandidatePlanningSession,
    CandidatePlanningSessionStatus,
    CandidateSnapshot,
    CoreCandidatePlanningIntakeStatus,
)
from app.candidate_planning.planner import RepositoryResolver
from app.candidate_planning.state import CandidatePlanningStateStore
from app.core_client.exceptions import AtlasCoreClientError
from app.core_client.models import (
    CoreCandidatePlanningIntakeResponse,
    CoreExecutionCandidateSnapshot,
)
from app.repository.models import RepositorySnapshot
from app.workflow.models import (
    CandidateWorkflowMetadata,
    WorkflowSession,
    WorkflowSessionState,
    WorkflowSource,
)

NOW = datetime(2026, 8, 2, tzinfo=UTC)


class FakeCoreClient:
    def __init__(self, response: CoreCandidatePlanningIntakeResponse | Exception) -> None:
        self.response = response
        self.calls: list[tuple[str, str | None]] = []

    async def validate_candidate_planning_intake(
        self,
        candidate_id: str,
        *,
        expected_candidate_fingerprint: str | None = None,
    ) -> CoreCandidatePlanningIntakeResponse:
        self.calls.append((candidate_id, expected_candidate_fingerprint))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeInspector:
    snapshot: RepositorySnapshot

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root

    def inspect(self) -> RepositorySnapshot:
        return self.snapshot


def core_response(*, fingerprint: str = "candidate-fingerprint-v1:aaa", target_id: str = "atlas-compose") -> CoreCandidatePlanningIntakeResponse:
    return CoreCandidatePlanningIntakeResponse(
        status="accepted_for_planning",
        candidate_id="candidate-1",
        planning_allowed=True,
        current_candidate_fingerprint=fingerprint,
        current_candidate=CoreExecutionCandidateSnapshot(
            id="candidate-1",
            source_recommendation_id="finding-1",
            source_subsystem="orion",
            recommendation_class="update_compose_stack",
            catalog_item_id="frigate",
            target_id=target_id,
            target_type="repository",
            execution_category="update",
            execution_intent="update-compose-stack",
            status="proposed",
            required_approval_level="standard",
            rationale="Update compose stack.",
            constraints=("requires-current-evidence",),
            evidence_ids=("evidence-1",),
            compatibility_assessment_id="assessment-1",
            compatibility_status="compatible",
            relationship_ids=("relationship-1",),
            created_at=NOW,
            expires_at=NOW + timedelta(days=1),
        ),
    )


def candidate_plan(root: Path) -> CandidatePlan:
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


def planning_session(root: Path) -> CandidatePlanningSession:
    plan = candidate_plan(root)
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
            relationship_ids=("relationship-1",),
            expires_at=NOW + timedelta(days=1),
            intake_status=CoreCandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING,
            intake_reason_codes=(),
            intake_timestamp=NOW,
        ),
        created_at=NOW,
        planning_status=CandidatePlanningSessionStatus.PLAN_READY,
        plan=plan,
        candidate_plan_fingerprint=candidate_plan_fingerprint(plan),
        workflow_session_id="candidate-workflow-1",
        implementation_request_id="candidate-implementation-v1-aaa",
        exact_implementation_approval_request_id="approval-candidate-workflow-1",
        implementation_translation_status=CandidatePlanningSessionStatus.IMPLEMENTATION_READY,
        implementation_translation_completed_at=NOW,
    )


def implementation_request(root: Path, plan_fingerprint: str) -> CandidateImplementationRequest:
    return CandidateImplementationRequest(
        identifier="candidate-implementation-v1-aaa",
        workflow_session_id="candidate-workflow-1",
        candidate_planning_session_id="candidate-plan-1",
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fingerprint-v1:aaa",
        candidate_plan_id="candidate-plan-output-candidate-plan-1",
        candidate_plan_fingerprint=plan_fingerprint,
        execution_intent="update-compose-stack",
        repository_root=root,
        repository_branch="feature/atlas-agent",
        repository_head="abc123",
        argv=("codex", "exec", "approved prompt"),
        working_directory=root,
        affected_files=(Path("compose.production.yaml"),),
        evidence_ids=("evidence-1",),
        compatibility_assessment_id="assessment-1",
        compatibility_status="compatible",
        translator_version=TRANSLATOR_VERSION,
        generated_at=NOW,
    )


def workflow(root: Path) -> WorkflowSession:
    session = planning_session(root)
    assert session.candidate_plan_fingerprint is not None
    request = implementation_request(root, session.candidate_plan_fingerprint)
    return WorkflowSession(
        identifier="candidate-workflow-1",
        request=None,
        plan=None,
        state=WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL,
        source=WorkflowSource.CANDIDATE,
        candidate_metadata=CandidateWorkflowMetadata(
            candidate_planning_session_id="candidate-plan-1",
            candidate_id="candidate-1",
            candidate_fingerprint="candidate-fingerprint-v1:aaa",
            candidate_plan_id="candidate-plan-output-candidate-plan-1",
            candidate_plan_fingerprint=session.candidate_plan_fingerprint,
            source_recommendation_id="finding-1",
            source_subsystem="orion",
            catalog_item_id="frigate",
            target_id="atlas-compose",
            target_type="repository",
            execution_category="update",
            execution_intent="update-compose-stack",
            evidence_ids=("evidence-1",),
            compatibility_assessment_id="assessment-1",
            compatibility_status="compatible",
            relationship_ids=("relationship-1",),
            conversion_timestamp=NOW,
            core_revalidation_status="accepted_for_planning",
            core_revalidation_fingerprint="candidate-fingerprint-v1:aaa",
        ),
        candidate_implementation_request=request,
        candidate_implementation_approval_id="approval-candidate-workflow-1",
    )


def approval(request: CandidateImplementationRequest, *, status: ApprovalStatus = ApprovalStatus.APPROVED) -> ApprovalResult:
    return ApprovalResult(
        decision=ApprovalDecision(
            request=ApprovalRequest(
                identifier="approval-candidate-workflow-1",
                workflow_id="candidate-workflow-1",
                checkpoint_id=request.identifier,
                title="Approve exact candidate implementation request",
                requested_tool=request.argv[0] if request.argv else "codex",
                requested_command=request.argv,
                requested_working_directory=request.working_directory,
                rationale="Human context only.",
                purpose=ApprovalPurpose.IMPLEMENTATION,
            ),
            status=status,
            reviewer="operator" if status is not ApprovalStatus.PENDING else None,
            reason="no" if status is ApprovalStatus.REJECTED else None,
        )
    )


def validator(root: Path, state: CandidatePlanningStateStore, core: FakeCoreClient) -> CandidateExecutionValidator:
    FakeInspector.snapshot = RepositorySnapshot(
        root=root.resolve(strict=False),
        branch="feature/atlas-agent",
        head_commit="abc123",
        is_clean=True,
        modified_files=(),
        staged_files=(),
        untracked_files=(),
    )
    return CandidateExecutionValidator(
        core_client=core,
        candidate_state=state,
        repository_resolver=RepositoryResolver(repository_root=root),
        repository_inspector_factory=FakeInspector,
        clock=lambda: NOW,
    )


def state_with_session(root: Path) -> CandidatePlanningStateStore:
    state = CandidatePlanningStateStore()
    state.create_session(planning_session(root))
    return state


def test_approved_candidate_request_validates_to_exact_execution_request(tmp_path: Path) -> None:
    state = state_with_session(tmp_path)
    candidate_workflow = workflow(tmp_path)
    core = FakeCoreClient(core_response())

    result = validator(tmp_path, state, core).validate(
        workflow=candidate_workflow,
        approval_result=approval(candidate_workflow.candidate_implementation_request),
    )

    assert result.approved is True
    assert result.execution_request is not None
    assert result.execution_request.argv == ("codex", "exec", "approved prompt")
    assert result.execution_request.working_directory == tmp_path
    assert core.calls == [("candidate-1", "candidate-fingerprint-v1:aaa")]


def test_pending_approval_is_retryable_and_does_not_validate(tmp_path: Path) -> None:
    state = state_with_session(tmp_path)
    candidate_workflow = workflow(tmp_path)

    result = validator(tmp_path, state, FakeCoreClient(core_response())).validate(
        workflow=candidate_workflow,
        approval_result=approval(
            candidate_workflow.candidate_implementation_request,
            status=ApprovalStatus.PENDING,
        ),
    )

    assert result.approved is False
    assert result.failure_code is CandidateExecutionFailureCode.APPROVAL_NOT_GRANTED
    assert result.retryable is True
    assert result.should_block is False


def test_exact_approval_mismatch_blocks(tmp_path: Path) -> None:
    state = state_with_session(tmp_path)
    candidate_workflow = workflow(tmp_path)
    request = candidate_workflow.candidate_implementation_request
    bad_approval = approval(replace(request, argv=("codex", "different")))

    result = validator(tmp_path, state, FakeCoreClient(core_response())).validate(
        workflow=candidate_workflow,
        approval_result=bad_approval,
    )

    assert result.approved is False
    assert result.failure_code is CandidateExecutionFailureCode.APPROVAL_EVIDENCE_MISMATCH
    assert result.message is not None
    assert "approval requested command" in result.message
    assert result.should_block is True


def test_translator_version_mismatch_blocks(tmp_path: Path) -> None:
    state = state_with_session(tmp_path)
    candidate_workflow = replace(
        workflow(tmp_path),
        candidate_implementation_request=replace(
            workflow(tmp_path).candidate_implementation_request,
            translator_version="old-translator",
        ),
    )

    result = validator(tmp_path, state, FakeCoreClient(core_response())).validate(
        workflow=candidate_workflow,
        approval_result=approval(candidate_workflow.candidate_implementation_request),
    )

    assert result.failure_code is CandidateExecutionFailureCode.APPROVAL_EVIDENCE_MISMATCH


def test_metadata_mismatch_blocks_with_field_detail(tmp_path: Path) -> None:
    state = state_with_session(tmp_path)
    candidate_workflow = replace(
        workflow(tmp_path),
        candidate_metadata=replace(
            workflow(tmp_path).candidate_metadata,
            candidate_fingerprint="different",
        ),
    )

    result = validator(tmp_path, state, FakeCoreClient(core_response())).validate(
        workflow=candidate_workflow,
        approval_result=approval(candidate_workflow.candidate_implementation_request),
    )

    assert result.approved is False
    assert result.failure_code is CandidateExecutionFailureCode.APPROVAL_EVIDENCE_MISMATCH
    assert result.message is not None
    assert "candidate fingerprint" in result.message


def test_core_unavailable_is_retryable(tmp_path: Path) -> None:
    state = state_with_session(tmp_path)
    candidate_workflow = workflow(tmp_path)

    result = validator(
        tmp_path,
        state,
        FakeCoreClient(AtlasCoreClientError("boom")),
    ).validate(
        workflow=candidate_workflow,
        approval_result=approval(candidate_workflow.candidate_implementation_request),
    )

    assert result.failure_code is CandidateExecutionFailureCode.CORE_UNAVAILABLE
    assert result.retryable is True
    assert result.should_block is False


def test_stale_core_candidate_blocks(tmp_path: Path) -> None:
    state = state_with_session(tmp_path)
    candidate_workflow = workflow(tmp_path)

    result = validator(
        tmp_path,
        state,
        FakeCoreClient(core_response(target_id="other-target")),
    ).validate(
        workflow=candidate_workflow,
        approval_result=approval(candidate_workflow.candidate_implementation_request),
    )

    assert result.failure_code is CandidateExecutionFailureCode.CANDIDATE_STALE
    assert result.should_block is True


def test_stale_plan_blocks(tmp_path: Path) -> None:
    state = CandidatePlanningStateStore()
    state.create_session(
        replace(
            planning_session(tmp_path),
            candidate_plan_fingerprint="different",
        )
    )
    candidate_workflow = workflow(tmp_path)

    result = validator(tmp_path, state, FakeCoreClient(core_response())).validate(
        workflow=candidate_workflow,
        approval_result=approval(candidate_workflow.candidate_implementation_request),
    )

    assert result.failure_code is CandidateExecutionFailureCode.PLAN_STALE


def test_repository_drift_blocks(tmp_path: Path) -> None:
    state = state_with_session(tmp_path)
    candidate_workflow = workflow(tmp_path)
    candidate_validator = validator(tmp_path, state, FakeCoreClient(core_response()))
    FakeInspector.snapshot = replace(FakeInspector.snapshot, head_commit="def456")

    result = candidate_validator.validate(
        workflow=candidate_workflow,
        approval_result=approval(candidate_workflow.candidate_implementation_request),
    )

    assert result.failure_code is CandidateExecutionFailureCode.REPOSITORY_STALE


def test_tool_policy_denies_invalid_persisted_request(tmp_path: Path) -> None:
    state = state_with_session(tmp_path)
    candidate_workflow = replace(
        workflow(tmp_path),
        candidate_implementation_request=replace(
            workflow(tmp_path).candidate_implementation_request,
            argv=("sh", "-c", "echo nope"),
        ),
    )

    result = validator(tmp_path, state, FakeCoreClient(core_response())).validate(
        workflow=candidate_workflow,
        approval_result=approval(candidate_workflow.candidate_implementation_request),
    )

    assert result.failure_code is CandidateExecutionFailureCode.TOOL_POLICY_DENIED
    assert result.should_block is True
