"""Tests for file-backed Atlas Agent state persistence."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import pytest

from app.approval.models import (
    ApprovalDecision,
    ApprovalPurpose,
    ApprovalRequest,
    ApprovalStatus,
    CommitApprovalMetadata,
)
from app.approval.repository import ApprovalRepository
from app.candidate_planning.models import (
    CandidatePlan,
    CandidatePlanningSession,
    CandidatePlanningSessionStatus,
    CandidateSnapshot,
    CoreCandidatePlanningIntakeStatus,
)
from app.candidate_planning.state import CandidatePlanningStateStore
from app.context.models import ActionHistoryContext, ActionHistoryEntry, AgentContext
from app.execution.models import EnvironmentVariable
from app.model_providers.models import ModelResponse
from app.persistence.snapshot import (
    AgentStatePersistenceCoordinator,
    StatePersistenceError,
)
from app.planning.models import ImplementationPlan, RoadmapCheckpoint
from app.repository.models import CommitRequest
from app.review.models import ReviewReport, ReviewStatus
from app.verification.models import (
    VerificationCheck,
    VerificationReport,
    VerificationStatus,
)
from app.workflow.engine import WorkflowEngine
from app.workflow.models import (
    CandidateWorkflowMetadata,
    WorkflowRequest,
    WorkflowSession,
    WorkflowSessionState,
    WorkflowSource,
)
from app.workflow.state import WorkflowStateStore
from tests.candidate_planning.test_audit import (
    _complete_workflow,
    _planning_session_with_plan,
)


def checkpoint() -> RoadmapCheckpoint:
    return RoadmapCheckpoint(
        identifier="A15.1",
        title="File-backed recovery",
        goal="Recover workflow state.",
        affected_files=(Path("app/workflow/engine.py"),),
        required_tests=("pytest",),
    )


def plan(root: Path) -> ImplementationPlan:
    return ImplementationPlan(
        checkpoint_id="A15.1",
        title="File-backed recovery",
        goal="Recover workflow state.",
        repository_root=root,
        branch="feature/atlas-agent",
        head_commit="abc123",
        scope_items=(),
        affected_files=(Path("app/workflow/engine.py"),),
        required_tests=("pytest",),
        risks=(),
    )


def request(root: Path, *, env_value: str = "secret-token") -> WorkflowRequest:
    return WorkflowRequest(
        checkpoint=checkpoint(),
        repository_root=root,
        execution_identifier="execution-a15",
        execution_argv=("codex", "implement"),
        execution_workdir=root,
        verification_checks=(
            VerificationCheck(
                identifier="pytest",
                argv=("python", "-m", "pytest"),
                working_directory=root,
                environment=(
                    EnvironmentVariable(name="ATLAS_TEST_SECRET", value=env_value),
                ),
            ),
        ),
        review_identifier="review-a15",
    )


def session(
    root: Path,
    state: WorkflowSessionState,
    *,
    identifier: str = "workflow-a15",
) -> WorkflowSession:
    return WorkflowSession(
        identifier=identifier,
        request=request(root),
        plan=plan(root),
        state=state,
    )


def approval_request(
    workflow_id: str,
    purpose: ApprovalPurpose,
    *,
    root: Path,
    fingerprint: str = "a" * 64,
) -> ApprovalRequest:
    if purpose is ApprovalPurpose.IMPLEMENTATION:
        return ApprovalRequest(
            identifier=f"approval-{workflow_id}",
            workflow_id=workflow_id,
            checkpoint_id="A15.1",
            title="Approve implementation",
            requested_tool="codex",
            requested_command=("codex", "implement"),
            requested_working_directory=root,
            rationale="Approve implementation.",
        )
    if purpose is ApprovalPurpose.VERIFICATION:
        return ApprovalRequest(
            identifier=f"approval-verification-{workflow_id}",
            workflow_id=workflow_id,
            checkpoint_id="A15.1",
            title="Approve verification",
            requested_tool="verification",
            requested_command=("verification-suite", "pytest"),
            requested_working_directory=root,
            rationale="Approve verification.",
            purpose=ApprovalPurpose.VERIFICATION,
        )
    return ApprovalRequest(
        identifier=f"approval-commit-{workflow_id}",
        workflow_id=workflow_id,
        checkpoint_id="A15.1",
        title="Approve commit",
        requested_tool="git",
        requested_command=("git-commit", "app/workflow/engine.py"),
        requested_working_directory=root,
        rationale="Approve commit.",
        purpose=ApprovalPurpose.COMMIT,
        commit_metadata=None,
    )


def coordinator(
    state_dir: Path,
    workflow_state: WorkflowStateStore | None = None,
    approvals: ApprovalRepository | None = None,
    candidate_planning: CandidatePlanningStateStore | None = None,
) -> AgentStatePersistenceCoordinator:
    return AgentStatePersistenceCoordinator(
        state_dir=state_dir,
        workflow_state=workflow_state or WorkflowStateStore(),
        approval_repository=approvals or ApprovalRepository(),
        candidate_planning_state=candidate_planning,
    )


def candidate_planning_session() -> CandidatePlanningSession:
    timestamp = datetime(2026, 8, 1, 23, 45, tzinfo=timezone.utc)
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
        intake_timestamp=timestamp,
    )
    return CandidatePlanningSession(
        identifier="candidate-plan-1",
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fingerprint-v1:aaa",
        status=CandidatePlanningSessionStatus.READY_FOR_PLANNING,
        snapshot=snapshot,
        created_at=timestamp,
    )


def candidate_plan(root: Path) -> CandidatePlan:
    timestamp = datetime(2026, 8, 1, 23, 46, tzinfo=timezone.utc)
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
        created_at=timestamp,
        repository_root=root,
        repository_branch="feature/atlas-agent",
        repository_head="abc123",
        revalidated_candidate_fingerprint="candidate-fingerprint-v1:aaa",
    )


def test_missing_snapshot_starts_empty(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)

    persistence.initialize()

    assert workflow_state.get_sprint() is None
    assert approvals.get_pending_requests() == []


def test_candidate_planning_session_round_trips_without_workflow_side_effects(
    tmp_path: Path,
) -> None:
    candidate_state = CandidatePlanningStateStore()
    persistence = coordinator(
        tmp_path,
        WorkflowStateStore(),
        ApprovalRepository(),
        candidate_state,
    )
    persistence.initialize()
    stored_session = candidate_planning_session()

    persistence.mutate_candidate_planning(
        lambda state: state.create_session(stored_session)
    )

    raw_json = persistence.snapshot_path.read_text()
    assert "candidate_planning" in raw_json
    assert "secret" not in raw_json.lower()
    assert "command" not in raw_json.lower()

    recovered_candidate_state = CandidatePlanningStateStore()
    recovered_workflow_state = WorkflowStateStore()
    recovered_approvals = ApprovalRepository()
    recovered = coordinator(
        tmp_path,
        recovered_workflow_state,
        recovered_approvals,
        recovered_candidate_state,
    )
    recovered.initialize()

    assert recovered_candidate_state.get_session(stored_session.identifier) == stored_session
    assert recovered_workflow_state.export_snapshot()[3] == {}
    assert recovered_approvals.get_pending_requests() == []


def test_candidate_plan_round_trips_after_restart(tmp_path: Path) -> None:
    candidate_state = CandidatePlanningStateStore()
    persistence = coordinator(
        tmp_path,
        WorkflowStateStore(),
        ApprovalRepository(),
        candidate_state,
    )
    persistence.initialize()
    stored_session = replace(
        candidate_planning_session(),
        planning_status=CandidatePlanningSessionStatus.PLAN_READY,
        plan=candidate_plan(tmp_path),
        planning_completed_at=datetime(2026, 8, 1, 23, 47, tzinfo=timezone.utc),
        last_revalidation_fingerprint="candidate-fingerprint-v1:aaa",
        last_revalidation_status=CoreCandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING,
    )

    persistence.mutate_candidate_planning(
        lambda state: state.create_session(stored_session)
    )

    recovered_candidate_state = CandidatePlanningStateStore()
    recovered = coordinator(
        tmp_path,
        WorkflowStateStore(),
        ApprovalRepository(),
        recovered_candidate_state,
    )
    recovered.initialize()

    recovered_session = recovered_candidate_state.get_session(stored_session.identifier)
    assert recovered_session == stored_session
    assert recovered_session is not None
    assert recovered_session.plan == stored_session.plan
    assert recovered_session.planning_status is CandidatePlanningSessionStatus.PLAN_READY


def test_candidate_planning_lineage_fields_round_trip(tmp_path: Path) -> None:
    candidate_state = CandidatePlanningStateStore()
    persistence = coordinator(
        tmp_path,
        WorkflowStateStore(),
        ApprovalRepository(),
        candidate_state,
    )
    persistence.initialize()
    stored_session = replace(
        candidate_planning_session(),
        predecessor_session_id="candidate-plan-0",
        successor_session_id="candidate-plan-2",
    )

    persistence.mutate_candidate_planning(
        lambda state: state.create_session(stored_session)
    )

    recovered_candidate_state = CandidatePlanningStateStore()
    coordinator(
        tmp_path,
        WorkflowStateStore(),
        ApprovalRepository(),
        recovered_candidate_state,
    ).initialize()

    recovered = recovered_candidate_state.get_session(stored_session.identifier)
    assert recovered is not None
    assert recovered.predecessor_session_id == "candidate-plan-0"
    assert recovered.successor_session_id == "candidate-plan-2"


@pytest.mark.parametrize("status", tuple(CandidatePlanningSessionStatus))
def test_candidate_planning_status_matrix_round_trips(
    tmp_path: Path,
    status: CandidatePlanningSessionStatus,
) -> None:
    candidate_state = CandidatePlanningStateStore()
    persistence = coordinator(
        tmp_path,
        WorkflowStateStore(),
        ApprovalRepository(),
        candidate_state,
    )
    persistence.initialize()
    base = candidate_planning_session()
    stored_session = replace(
        base,
        status=status,
        planning_status=status,
        plan=candidate_plan(tmp_path)
        if status
        in {
            CandidatePlanningSessionStatus.PLAN_READY,
            CandidatePlanningSessionStatus.WORKFLOW_CREATED,
            CandidatePlanningSessionStatus.IMPLEMENTATION_READY,
        }
        else None,
    )

    persistence.mutate_candidate_planning(
        lambda state: state.create_session(stored_session)
    )

    recovered_candidate_state = CandidatePlanningStateStore()
    coordinator(
        tmp_path,
        WorkflowStateStore(),
        ApprovalRepository(),
        recovered_candidate_state,
    ).initialize()

    assert recovered_candidate_state.get_session(stored_session.identifier) == stored_session


def test_candidate_workflow_shell_linkage_round_trips_after_restart(tmp_path: Path) -> None:
    candidate_state = CandidatePlanningStateStore()
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals, candidate_state)
    persistence.initialize()
    stored_plan = candidate_plan(tmp_path)
    converted_at = datetime(2026, 8, 1, 23, 48, tzinfo=timezone.utc)
    plan_fingerprint = "candidate-plan-fingerprint-v1:" + "b" * 64
    workflow_id = "candidate-workflow-1"
    approval_id = f"approval-{workflow_id}"
    stored_session = replace(
        candidate_planning_session(),
        planning_status=CandidatePlanningSessionStatus.PLAN_READY,
        plan=stored_plan,
        workflow_session_id=workflow_id,
        implementation_approval_request_id=approval_id,
        candidate_plan_fingerprint=plan_fingerprint,
        workflow_conversion_status=CandidatePlanningSessionStatus.WORKFLOW_CREATED,
        workflow_conversion_completed_at=converted_at,
    )
    metadata = CandidateWorkflowMetadata(
        candidate_planning_session_id=stored_session.identifier,
        candidate_id=stored_session.candidate_id,
        candidate_fingerprint=stored_session.candidate_fingerprint,
        candidate_plan_id=stored_plan.identifier,
        candidate_plan_fingerprint=plan_fingerprint,
        source_recommendation_id=stored_session.snapshot.source_recommendation_id,
        source_subsystem=stored_session.snapshot.source_subsystem,
        catalog_item_id=stored_session.snapshot.catalog_item_id,
        target_id=stored_session.snapshot.target_id,
        target_type=stored_session.snapshot.target_type,
        execution_category=stored_session.snapshot.execution_category,
        execution_intent=stored_session.snapshot.execution_intent,
        evidence_ids=stored_session.snapshot.evidence_ids,
        compatibility_assessment_id=stored_session.snapshot.compatibility_assessment_id,
        compatibility_status=stored_session.snapshot.compatibility_status,
        relationship_ids=stored_session.snapshot.relationship_ids,
        conversion_timestamp=converted_at,
        core_revalidation_status="accepted_for_planning",
        core_revalidation_fingerprint=stored_session.candidate_fingerprint,
    )
    workflow = WorkflowSession(
        identifier=workflow_id,
        request=None,
        plan=None,
        state=WorkflowSessionState.AWAITING_APPROVAL,
        source=WorkflowSource.CANDIDATE,
        candidate_metadata=metadata,
    )
    approval = ApprovalRequest(
        identifier=approval_id,
        workflow_id=workflow_id,
        checkpoint_id=stored_plan.identifier,
        title="Approve candidate workflow shell",
        requested_tool="atlas-agent",
        requested_command=(),
        requested_working_directory=tmp_path,
        rationale="No executable command is approved by this request.",
    )

    persistence.mutate_aggregate(
        lambda workflow_tx, approvals_tx, candidate_tx: (
            candidate_tx.create_session(stored_session),
            workflow_tx.create_session(workflow),
            approvals_tx.save_request(approval),
        )
    )

    recovered_candidate_state = CandidatePlanningStateStore()
    recovered_workflow_state = WorkflowStateStore()
    recovered_approvals = ApprovalRepository()
    recovered = coordinator(
        tmp_path,
        recovered_workflow_state,
        recovered_approvals,
        recovered_candidate_state,
    )
    recovered.initialize()

    assert recovered_candidate_state.get_session(stored_session.identifier) == stored_session
    recovered_workflow = recovered_workflow_state.get_session(workflow_id)
    assert recovered_workflow == workflow
    assert recovered_workflow is not None
    assert recovered_workflow.source is WorkflowSource.CANDIDATE
    assert recovered_workflow.request is None
    assert recovered_workflow.plan is None
    recovered_approval = recovered_approvals.get_request(approval_id)
    assert recovered_approval is not None
    assert recovered_approval.decision.request.requested_command == ()


def test_full_workflow_and_approval_round_trip_redacts_env(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()
    stored_session = session(tmp_path, WorkflowSessionState.AWAITING_APPROVAL)
    approval = approval_request(
        stored_session.identifier,
        ApprovalPurpose.IMPLEMENTATION,
        root=tmp_path,
    )

    persistence.mutate_aggregate(
        lambda workflow, approval_repo: (
            workflow.create_session(stored_session),
            approval_repo.save_request(approval),
        )
    )

    raw_json = persistence.snapshot_path.read_text()
    assert "secret-token" not in raw_json
    assert "value_sha256" in raw_json
    assert json.loads(raw_json) == json.loads(raw_json)

    recovered_workflow = WorkflowStateStore()
    recovered_approvals = ApprovalRepository()
    recovered = coordinator(tmp_path, recovered_workflow, recovered_approvals)
    recovered.initialize()

    recovered_session = recovered_workflow.get_session(stored_session.identifier)
    assert recovered_session == replace(
        stored_session,
        request=replace(
            stored_session.request,
            verification_checks=(
                replace(
                    stored_session.request.verification_checks[0],
                    environment=(
                        EnvironmentVariable(
                            name="ATLAS_TEST_SECRET",
                            value="",
                            value_digest=sha256(b"secret-token").hexdigest(),
                            redacted=True,
                        ),
                    ),
                ),
            ),
        ),
    )
    assert recovered_approvals.get_request(approval.identifier) is not None


def test_legacy_verification_env_payload_recovers_on_restart(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    persistence = coordinator(tmp_path, workflow_state, ApprovalRepository())
    persistence.initialize()
    stored_session = session(tmp_path, WorkflowSessionState.COMPLETED)

    persistence.mutate_workflow(lambda workflow: workflow.create_session(stored_session))

    payload = json.loads(persistence.snapshot_path.read_text(encoding="utf-8"))
    checks = payload["workflow_state"]["sessions"][stored_session.identifier]["request"][
        "verification_checks"
    ]
    checks[0]["environment"] = [
        {
            "name": "ATLAS_TEST_SECRET",
            "value": "secret-token",
        }
    ]
    persistence.snapshot_path.write_text(json.dumps(payload), encoding="utf-8")

    recovered_workflow = WorkflowStateStore()
    coordinator(tmp_path, recovered_workflow, ApprovalRepository()).initialize()
    recovered_session = recovered_workflow.get_session(stored_session.identifier)
    assert recovered_session is not None
    recovery = recovered_session.request.verification_checks[0].environment[0]
    assert recovery.redacted is True
    assert recovery.value == ""
    assert recovery.value_digest == sha256(b"secret-token").hexdigest()


def test_action_history_context_round_trips_in_workflow_snapshot(
    tmp_path: Path,
) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()
    timestamp = datetime(2026, 7, 31, 16, 0, tzinfo=timezone.utc)
    context = AgentContext(
        atlas="atlas",
        assistant="orion",
        engine="atlas-core",
        release="test",
        services={},
        action_history=ActionHistoryContext(
            entries=(
                ActionHistoryEntry(
                    identifier="entry-1",
                    provider_id="docker",
                    provider_name="Docker",
                    action_id="restart-container",
                    action_label="Restart Container",
                    status="failed",
                    success=False,
                    message="Container restart failed after bounded timeout.",
                    confirmed=True,
                    destructive=True,
                    parameter_names=("container",),
                    request_id="request-1",
                    started_at=timestamp,
                    completed_at=timestamp,
                    duration_ms=12.5,
                ),
            ),
        ),
    )
    stored_session = replace(
        session(tmp_path, WorkflowSessionState.COMPLETED),
        context=context,
    )
    persistence.mutate_workflow(lambda workflow: workflow.create_session(stored_session))

    recovered_workflow = WorkflowStateStore()
    coordinator(tmp_path, recovered_workflow, ApprovalRepository()).initialize()

    recovered_session = recovered_workflow.get_session(stored_session.identifier)
    assert recovered_session is not None
    assert recovered_session.context == context


def test_review_analysis_round_trips_in_workflow_snapshot(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    persistence = coordinator(tmp_path, workflow_state, ApprovalRepository())
    persistence.initialize()
    analysis = ModelResponse(
        text="Advisory review analysis.",
        model="test-model",
        provider_id="test-provider",
    )
    stored_session = replace(
        session(tmp_path, WorkflowSessionState.AWAITING_COMMIT_APPROVAL),
        review_report=ReviewReport(
            request_id="review-a15",
            checkpoint_id="A15.1",
            status=ReviewStatus.APPROVED,
            findings=(),
            recommendations=(),
        ),
        review_analysis=analysis,
        commit_request=CommitRequest(
            repository_root=tmp_path,
            expected_branch="feature/atlas-agent",
            expected_head="abc123",
            paths=(Path("app/workflow/engine.py"),),
            message="feat(agent): workflow recovery",
        ),
        reviewed_files=(Path("app/workflow/engine.py"),),
        expected_branch="feature/atlas-agent",
        expected_head="abc123",
        reviewed_content_fingerprint="a" * 64,
    )
    approval = approval_request(
        stored_session.identifier,
        ApprovalPurpose.COMMIT,
        root=tmp_path,
    )
    approval = replace(
        approval,
        commit_metadata=CommitApprovalMetadata(
            expected_branch="feature/atlas-agent",
            expected_head="abc123",
            reviewed_files=(Path("app/workflow/engine.py"),),
            reviewed_content_fingerprint="a" * 64,
            commit_message="feat(agent): workflow recovery",
        ),
    )

    persistence.mutate_aggregate(
        lambda workflow, approvals: (
            workflow.create_session(stored_session),
            approvals.save_request(approval),
        )
    )

    recovered_workflow = WorkflowStateStore()
    coordinator(tmp_path, recovered_workflow, ApprovalRepository()).initialize()

    recovered_session = recovered_workflow.get_session(stored_session.identifier)
    assert recovered_session is not None
    assert recovered_session.review_analysis == analysis


def test_old_snapshot_without_review_analysis_loads_none(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    persistence = coordinator(tmp_path, workflow_state, ApprovalRepository())
    persistence.initialize()
    stored_session = session(tmp_path, WorkflowSessionState.COMPLETED)
    persistence.mutate_workflow(lambda workflow: workflow.create_session(stored_session))
    payload = json.loads(persistence.snapshot_path.read_text())
    del payload["workflow_state"]["sessions"][stored_session.identifier]["review_analysis"]
    persistence.snapshot_path.write_text(json.dumps(payload), encoding="utf-8")

    recovered_workflow = WorkflowStateStore()
    coordinator(tmp_path, recovered_workflow, ApprovalRepository()).initialize()

    recovered_session = recovered_workflow.get_session(stored_session.identifier)
    assert recovered_session is not None
    assert recovered_session.review_analysis is None


def test_old_snapshot_without_candidate_planning_loads_empty_candidate_state(
    tmp_path: Path,
) -> None:
    workflow_state = WorkflowStateStore()
    persistence = coordinator(tmp_path, workflow_state, ApprovalRepository())
    persistence.initialize()
    stored_session = session(tmp_path, WorkflowSessionState.COMPLETED)
    persistence.mutate_workflow(lambda workflow: workflow.create_session(stored_session))
    payload = json.loads(persistence.snapshot_path.read_text())
    del payload["candidate_planning"]
    persistence.snapshot_path.write_text(json.dumps(payload), encoding="utf-8")

    recovered_candidate_state = CandidatePlanningStateStore()
    coordinator(
        tmp_path,
        WorkflowStateStore(),
        ApprovalRepository(),
        recovered_candidate_state,
    ).initialize()

    assert recovered_candidate_state.export_snapshot() == {}


def test_old_snapshot_without_candidate_planning_still_recovers_orphaned_workflow_metadata(
    tmp_path: Path,
) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()

    workflow = WorkflowSession(
        identifier="candidate-workflow-1",
        request=None,
        plan=None,
        state=WorkflowSessionState.AWAITING_APPROVAL,
        source=WorkflowSource.CANDIDATE,
        candidate_metadata=CandidateWorkflowMetadata(
            candidate_planning_session_id="candidate-plan-1",
            candidate_id="candidate-1",
            candidate_fingerprint="candidate-fingerprint-v1:aaa",
            candidate_plan_id="candidate-plan-output-candidate-plan-1",
            candidate_plan_fingerprint="candidate-plan-fingerprint-v1:abc",
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
            conversion_timestamp=datetime(2026, 8, 2, tzinfo=timezone.utc),
            core_revalidation_status="accepted_for_planning",
            core_revalidation_fingerprint="candidate-fingerprint-v1:aaa",
        ),
    )
    persistence.mutate_aggregate(
        lambda workflow_tx, approvals_tx, _candidate_tx: (
            workflow_tx.create_session(workflow),
            approvals_tx.save_request(
                approval_request(
                    workflow.identifier,
                    ApprovalPurpose.IMPLEMENTATION,
                    root=tmp_path,
                )
            ),
        )
    )

    payload = json.loads(persistence.snapshot_path.read_text())
    del payload["candidate_planning"]
    persistence.snapshot_path.write_text(json.dumps(payload), encoding="utf-8")

    recovered_candidate = CandidatePlanningStateStore()
    recovered_workflow = WorkflowStateStore()
    coordinator(
        tmp_path,
        recovered_workflow,
        ApprovalRepository(),
        recovered_candidate,
    ).initialize()

    assert recovered_candidate.export_snapshot() == {}

    recovered = recovered_workflow.get_session("candidate-workflow-1")
    assert recovered is not None
    assert recovered.candidate_metadata is not None
    assert recovered.candidate_metadata.candidate_planning_session_id == "candidate-plan-1"
    assert recovered.source is WorkflowSource.CANDIDATE


def test_completed_candidate_workflow_artifacts_recover_after_restart(
    tmp_path: Path,
) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    candidate_state = CandidatePlanningStateStore()
    persistence = coordinator(tmp_path, workflow_state, approvals, candidate_state)
    persistence.initialize()
    workflow = _complete_workflow(tmp_path)
    planning = _planning_session_with_plan(tmp_path, workflow)

    persistence.mutate_aggregate(
        lambda workflow_tx, approvals_tx, candidate_tx: (
            candidate_tx.create_session(planning),
            workflow_tx.create_session(workflow),
        )
    )

    recovered_workflow = WorkflowStateStore()
    recovered_candidate = CandidatePlanningStateStore()
    coordinator(
        tmp_path,
        recovered_workflow,
        ApprovalRepository(),
        recovered_candidate,
    ).initialize()

    recovered = recovered_workflow.get_session(workflow.identifier)
    assert recovered is not None
    assert recovered.state is WorkflowSessionState.COMPLETED
    assert recovered.candidate_metadata == workflow.candidate_metadata
    assert recovered.candidate_implementation_request == workflow.candidate_implementation_request
    assert recovered.execution_result == workflow.execution_result
    assert recovered.candidate_verification_plan == workflow.candidate_verification_plan
    assert recovered.candidate_verification_evidence == workflow.candidate_verification_evidence
    assert recovered.candidate_review_result == workflow.candidate_review_result
    assert recovered.commit_request == workflow.commit_request
    assert recovered.commit_result == workflow.commit_result
    assert recovered_candidate.get_session(planning.identifier) == planning


def test_claimed_state_recovers_to_blocked_and_persists(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()
    claimed = session(tmp_path, WorkflowSessionState.EXECUTING)
    persistence.mutate_workflow(lambda workflow: workflow.create_session(claimed))

    recovered_state = WorkflowStateStore()
    recovered_approvals = ApprovalRepository()
    recovered = coordinator(tmp_path, recovered_state, recovered_approvals)
    recovered.initialize()

    recovered_session = recovered_state.get_session(claimed.identifier)
    assert recovered_session is not None
    assert recovered_session.state is WorkflowSessionState.BLOCKED
    assert recovered_session.blocked_reason == "implementation interrupted by process restart"
    persisted = json.loads(recovered.snapshot_path.read_text())
    assert persisted["workflow_state"]["sessions"][claimed.identifier]["state"] == "blocked"


@pytest.mark.parametrize(
    ("state", "expected_state"),
    (
        (WorkflowSessionState.AWAITING_APPROVAL, WorkflowSessionState.AWAITING_APPROVAL),
        (
            WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL,
            WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL,
        ),
        (WorkflowSessionState.EXECUTING, WorkflowSessionState.BLOCKED),
        (
            WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
            WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
        ),
        (WorkflowSessionState.VERIFYING, WorkflowSessionState.BLOCKED),
        (
            WorkflowSessionState.AWAITING_COMMIT_APPROVAL,
            WorkflowSessionState.AWAITING_COMMIT_APPROVAL,
        ),
        (WorkflowSessionState.COMMITTING, WorkflowSessionState.BLOCKED),
        (WorkflowSessionState.BLOCKED, WorkflowSessionState.BLOCKED),
        (WorkflowSessionState.COMPLETED, WorkflowSessionState.COMPLETED),
    ),
)
def test_workflow_recovery_state_matrix(
    tmp_path: Path,
    state: WorkflowSessionState,
    expected_state: WorkflowSessionState,
) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()
    stored_session = _session_for_recovery_matrix(tmp_path, state)

    def mutate(workflow_tx, approvals_tx):
        workflow_tx.create_session(stored_session)
        approval = _approval_for_recovery_state(stored_session, state, tmp_path)
        if approval is not None:
            approvals_tx.save_request(approval)

    persistence.mutate_aggregate(mutate)

    recovered_state = WorkflowStateStore()
    recovered_approvals = ApprovalRepository()
    coordinator(tmp_path, recovered_state, recovered_approvals).initialize()

    recovered_session = recovered_state.get_session(stored_session.identifier)
    assert recovered_session is not None
    assert recovered_session.state is expected_state
    if expected_state is state and _approval_for_recovery_state(stored_session, state, tmp_path) is not None:
        assert recovered_approvals.get_request(
            _approval_for_recovery_state(stored_session, state, tmp_path).identifier
        ) is not None


def _session_for_recovery_matrix(
    root: Path,
    state: WorkflowSessionState,
) -> WorkflowSession:
    base = session(root, state)
    if state is WorkflowSessionState.AWAITING_COMMIT_APPROVAL:
        return replace(
            base,
            review_report=ReviewReport(
                request_id="review-a15",
                checkpoint_id="A15.1",
                status=ReviewStatus.APPROVED,
                findings=(),
                recommendations=(),
            ),
            commit_request=CommitRequest(
                repository_root=root,
                expected_branch="feature/atlas-agent",
                expected_head="abc123",
                paths=(Path("app/workflow/engine.py"),),
                message="feat(agent): workflow recovery",
            ),
            reviewed_files=(Path("app/workflow/engine.py"),),
            expected_branch="feature/atlas-agent",
            expected_head="abc123",
            reviewed_content_fingerprint="a" * 64,
        )
    return base


def _approval_for_recovery_state(
    stored_session: WorkflowSession,
    state: WorkflowSessionState,
    root: Path,
) -> ApprovalRequest | None:
    if state in {
        WorkflowSessionState.AWAITING_APPROVAL,
        WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL,
    }:
        return approval_request(stored_session.identifier, ApprovalPurpose.IMPLEMENTATION, root=root)
    if state is WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL:
        return approval_request(stored_session.identifier, ApprovalPurpose.VERIFICATION, root=root)
    if state is WorkflowSessionState.AWAITING_COMMIT_APPROVAL:
        approval = approval_request(stored_session.identifier, ApprovalPurpose.COMMIT, root=root)
        return replace(
            approval,
            commit_metadata=CommitApprovalMetadata(
                expected_branch="feature/atlas-agent",
                expected_head="abc123",
                reviewed_files=(Path("app/workflow/engine.py"),),
                reviewed_content_fingerprint="a" * 64,
                commit_message="feat(agent): workflow recovery",
            ),
        )
    return None


def test_pending_approved_rejected_and_standalone_approvals_recover(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()
    standalone = ApprovalRequest(
        identifier="approval-standalone",
        checkpoint_id="A15.1",
        title="Standalone",
        requested_tool="tool",
        requested_command=("tool",),
        rationale="Standalone approval.",
    )
    rejected = ApprovalRequest(
        identifier="approval-standalone-rejected",
        checkpoint_id="A15.1",
        title="Standalone rejected",
        requested_tool="tool",
        requested_command=("tool",),
        rationale="Standalone approval.",
    )
    persistence.mutate_approval(
        lambda repo: (
            repo.save_request(standalone),
            repo.save_request(rejected),
            repo.update_decision(
                standalone.identifier,
                ApprovalDecision(
                    request=standalone,
                    status=ApprovalStatus.APPROVED,
                ),
            ),
            repo.update_decision(
                rejected.identifier,
                ApprovalDecision(
                    request=rejected,
                    status=ApprovalStatus.REJECTED,
                ),
            ),
        )
    )

    recovered_approvals = ApprovalRepository()
    recovered = coordinator(tmp_path, WorkflowStateStore(), recovered_approvals)
    recovered.initialize()

    assert recovered_approvals.get_request(standalone.identifier).approved is True
    assert recovered_approvals.get_request(rejected.identifier).decision.status is ApprovalStatus.REJECTED
    assert recovered_approvals.update_decision(
        standalone.identifier,
        ApprovalDecision(request=standalone, status=ApprovalStatus.REJECTED),
    ) is False


def test_waiting_workflow_without_approval_fails_startup(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()
    workflow_state.create_session(session(tmp_path, WorkflowSessionState.AWAITING_APPROVAL))
    payload = persistence._encode_payload(workflow_state.export_snapshot(), {})
    persistence.snapshot_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(StatePersistenceError):
        coordinator(tmp_path).initialize()


def test_corrupt_and_unsupported_snapshots_fail_startup(tmp_path: Path) -> None:
    path = tmp_path / "atlas-agent-state.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(StatePersistenceError):
        coordinator(tmp_path).initialize()

    path.write_text(
        json.dumps(
            {
                "application": "atlas-agent",
                "schema_version": 999,
                "workflow_state": {"sessions": {}, "sprint": None, "verification": None, "review": None},
                "approvals": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(StatePersistenceError):
        coordinator(tmp_path).initialize()


def test_failed_persistence_leaves_live_and_durable_state_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()
    baseline = session(tmp_path, WorkflowSessionState.BLOCKED, identifier="baseline")
    persistence.mutate_workflow(lambda workflow: workflow.create_session(baseline))
    before = persistence.snapshot_path.read_text()

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("app.persistence.snapshot.os.replace", fail_replace)
    with pytest.raises(StatePersistenceError):
        persistence.mutate_workflow(
            lambda workflow: workflow.create_session(
                session(tmp_path, WorkflowSessionState.BLOCKED, identifier="new")
            )
        )

    assert workflow_state.get_session("new") is None
    assert persistence.snapshot_path.read_text() == before


def test_rehydrate_matching_env_permits_verification_without_persisting_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATLAS_TEST_SECRET", "secret-token")
    check = VerificationCheck(
        identifier="pytest",
        argv=("python", "-m", "pytest"),
        working_directory=tmp_path,
        environment=(
            EnvironmentVariable(
                name="ATLAS_TEST_SECRET",
                value="",
                value_digest=sha256(b"secret-token").hexdigest(),
                redacted=True,
            ),
        ),
    )

    rehydrated = WorkflowEngine._rehydrate_verification_checks((check,))

    assert rehydrated[0].environment[0].value == "secret-token"
    assert rehydrated[0].environment[0].redacted is False


def test_missing_or_mismatched_rehydrated_env_blocks_before_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    check = VerificationCheck(
        identifier="pytest",
        argv=("python", "-m", "pytest"),
        working_directory=tmp_path,
        environment=(
            EnvironmentVariable(
                name="ATLAS_TEST_SECRET",
                value="",
                value_digest=sha256(b"secret-token").hexdigest(),
                redacted=True,
            ),
        ),
    )

    monkeypatch.delenv("ATLAS_TEST_SECRET", raising=False)
    with pytest.raises(ValueError, match="unavailable"):
        WorkflowEngine._rehydrate_verification_checks((check,))

    monkeypatch.setenv("ATLAS_TEST_SECRET", "different")
    with pytest.raises(ValueError, match="digest mismatch"):
        WorkflowEngine._rehydrate_verification_checks((check,))


def test_commit_waiting_requires_matching_commit_metadata(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()
    commit_request = CommitRequest(
        repository_root=tmp_path,
        expected_branch="feature/atlas-agent",
        expected_head="abc123",
        paths=(Path("app/workflow/engine.py"),),
        message="feat(agent): file-backed recovery",
    )
    waiting = replace(
        session(tmp_path, WorkflowSessionState.AWAITING_COMMIT_APPROVAL),
        commit_request=commit_request,
        reviewed_files=(Path("app/workflow/engine.py"),),
        expected_branch="feature/atlas-agent",
        expected_head="abc123",
        reviewed_content_fingerprint="a" * 64,
    )
    bad_approval = approval_request(
        waiting.identifier,
        ApprovalPurpose.COMMIT,
        root=tmp_path,
        fingerprint="b" * 64,
    )

    with pytest.raises(StatePersistenceError):
        persistence.mutate_aggregate(
            lambda workflow, repo: (
                workflow.create_session(waiting),
                repo.save_request(bad_approval),
            )
        )

    assert workflow_state.get_session(waiting.identifier) is None


def test_workflow_reports_round_trip(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()
    workflow_state.publish_verification(
        VerificationReport(
            repository_root=tmp_path,
            results=(),
            status=VerificationStatus.PASSED,
            duration_seconds=1.0,
        )
    )
    workflow_state.publish_review(
        ReviewReport(
            request_id="review-a15",
            checkpoint_id="A15.1",
            status=ReviewStatus.APPROVED,
            findings=(),
            recommendations=(),
        )
    )
    workflow_state.create_session(session(tmp_path, WorkflowSessionState.COMPLETED))
    persistence.persist_current_state()

    recovered = WorkflowStateStore()
    coordinator(tmp_path, recovered, ApprovalRepository()).initialize()

    assert recovered.get_verification().status is VerificationStatus.PASSED
    assert recovered.get_review().status is ReviewStatus.APPROVED
    assert recovered.get_session("workflow-a15").state is WorkflowSessionState.COMPLETED


def test_failed_validation_leaves_live_state_unchanged(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    approvals = ApprovalRepository()
    persistence = coordinator(tmp_path, workflow_state, approvals)
    persistence.initialize()

    with pytest.raises(StatePersistenceError):
        persistence.mutate_workflow(
            lambda workflow: workflow.create_session(
                session(tmp_path, WorkflowSessionState.AWAITING_APPROVAL)
            )
        )

    assert workflow_state.get_session("workflow-a15") is None


def test_interrupted_candidate_execution_recovers_blocked_and_not_replayable(tmp_path: Path) -> None:
    workflow_state = WorkflowStateStore()
    candidate_session = replace(
        session(tmp_path, WorkflowSessionState.EXECUTING, identifier="candidate-workflow-1"),
        source=WorkflowSource.CANDIDATE,
        candidate_metadata=CandidateWorkflowMetadata(
            candidate_planning_session_id="candidate-plan-1",
            candidate_id="candidate-1",
            candidate_fingerprint="candidate-fingerprint-v1:aaa",
            candidate_plan_id="candidate-plan-output-candidate-plan-1",
            candidate_plan_fingerprint="plan-fingerprint-v1:aaa",
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
            conversion_timestamp=datetime(2026, 8, 2, tzinfo=timezone.utc),
            core_revalidation_status="accepted_for_planning",
            core_revalidation_fingerprint="candidate-fingerprint-v1:aaa",
        ),
    )
    persistence = coordinator(tmp_path / "state", workflow_state=workflow_state)
    persistence.initialize()
    persistence.mutate_workflow(lambda workflow: workflow.create_session(candidate_session))

    restored_workflow = WorkflowStateStore()
    restored = coordinator(tmp_path / "state", workflow_state=restored_workflow)
    restored.initialize()

    restored_session = restored_workflow.get_session("candidate-workflow-1")
    assert restored_session is not None
    assert restored_session.state is WorkflowSessionState.BLOCKED
    assert restored_session.blocked_reason == "implementation interrupted by process restart"
