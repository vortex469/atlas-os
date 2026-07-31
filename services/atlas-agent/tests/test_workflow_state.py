"""Tests for passive in-memory workflow session state."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from pathlib import Path
from threading import Barrier
from unittest.mock import Mock

import pytest

from app.model_providers.models import ModelResponse
from app.planning.models import ImplementationPlan, RoadmapCheckpoint
from app.workflow.models import (
    SprintPhase,
    SprintStatus,
    WorkflowRequest,
    WorkflowSession,
    WorkflowSessionState,
)
from app.workflow.state import WorkflowStateStore


def make_request(root: Path) -> WorkflowRequest:
    """Create one immutable workflow request."""

    return WorkflowRequest(
        checkpoint=RoadmapCheckpoint(
            identifier="A15.1",
            title="Workflow Session Model",
            goal="Store passive workflow sessions.",
        ),
        repository_root=root,
        execution_identifier="execution-a15-1",
        execution_argv=("codex", "implement"),
        execution_workdir=root,
        verification_checks=(),
        review_identifier="review-a15-1",
    )


def make_plan(root: Path) -> ImplementationPlan:
    """Create one immutable deterministic implementation plan."""

    return ImplementationPlan(
        checkpoint_id="A15.1",
        title="Workflow Session Model",
        goal="Store passive workflow sessions.",
        repository_root=root,
        branch="feature/atlas-agent",
        head_commit="e647aa5",
        scope_items=("Add workflow session storage",),
        affected_files=(Path("app/workflow/state.py"),),
        required_tests=("Run workflow state tests",),
        risks=(),
    )


def make_session(
    root: Path,
    *,
    identifier: str = "workflow-a15-1",
    request: WorkflowRequest | None = None,
    plan: ImplementationPlan | None = None,
    planning_analysis: ModelResponse | None = None,
) -> WorkflowSession:
    """Create one passive planned workflow session."""

    return WorkflowSession(
        identifier=identifier,
        request=request or make_request(root),
        plan=plan or make_plan(root),
        state=WorkflowSessionState.PLANNED,
        planning_analysis=planning_analysis,
    )


def test_session_can_be_stored_and_retrieved(tmp_path: Path) -> None:
    store = WorkflowStateStore()
    session = make_session(tmp_path)

    store.create_session(session)

    assert store.get_session(session.identifier) is session


def test_unknown_session_identifier_returns_none() -> None:
    store = WorkflowStateStore()

    assert store.get_session("unknown") is None


def test_session_can_be_deleted_without_leaving_state(tmp_path: Path) -> None:
    store = WorkflowStateStore()
    session = make_session(tmp_path)
    store.create_session(session)

    assert store.delete_session(session.identifier) is True
    assert store.get_session(session.identifier) is None
    assert store.delete_session(session.identifier) is False


def test_duplicate_session_identifier_is_rejected(tmp_path: Path) -> None:
    store = WorkflowStateStore()
    original = make_session(tmp_path)
    duplicate = make_session(tmp_path, identifier=original.identifier)
    store.create_session(original)

    with pytest.raises(ValueError, match="already exists"):
        store.create_session(duplicate)

    assert store.get_session(original.identifier) is original


def test_session_preserves_exact_artifact_objects(tmp_path: Path) -> None:
    store = WorkflowStateStore()
    request = make_request(tmp_path)
    plan = make_plan(tmp_path)
    analysis = ModelResponse(
        text="Keep the scope unchanged.",
        model="test-model",
        provider_id="test-provider",
    )
    session = make_session(
        tmp_path,
        request=request,
        plan=plan,
        planning_analysis=analysis,
    )

    store.create_session(session)
    stored = store.get_session(session.identifier)

    assert stored is session
    assert stored.request is request
    assert stored.plan is plan
    assert stored.planning_analysis is analysis


def test_existing_latest_artifact_state_remains_unchanged() -> None:
    store = WorkflowStateStore()
    sprint = SprintStatus(
        checkpoint_id="A15.1",
        title="Workflow Session Model",
        goal="Store passive workflow sessions.",
        phase=SprintPhase.PLANNED,
    )
    verification = Mock()
    review = Mock()

    assert store.get_sprint() is None
    assert store.get_verification() is None
    assert store.get_review() is None

    store.publish_sprint(sprint)
    store.publish_verification(verification)
    store.publish_review(review)

    assert store.get_sprint() is sprint
    assert store.get_verification() is verification
    assert store.get_review() is review


def test_concurrent_session_creation_cannot_overwrite(
    tmp_path: Path,
) -> None:
    store = WorkflowStateStore()
    sessions = (
        make_session(tmp_path, identifier="shared-workflow"),
        make_session(tmp_path, identifier="shared-workflow"),
    )
    barrier = Barrier(len(sessions))

    def create(session: WorkflowSession) -> bool:
        barrier.wait()
        try:
            store.create_session(session)
        except ValueError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=len(sessions)) as executor:
        results = tuple(executor.map(create, sessions))

    assert sorted(results) == [False, True]
    assert store.get_session("shared-workflow") in sessions


def test_workflow_session_is_immutable(tmp_path: Path) -> None:
    session = make_session(tmp_path)

    with pytest.raises(FrozenInstanceError):
        session.identifier = "replacement"


def test_awaiting_approval_state_is_supported(tmp_path: Path) -> None:
    session = WorkflowSession(
        identifier="workflow-a15-2",
        request=make_request(tmp_path),
        plan=make_plan(tmp_path),
        state=WorkflowSessionState.AWAITING_APPROVAL,
    )
    store = WorkflowStateStore()

    store.create_session(session)

    assert store.get_session(session.identifier) is session
    assert session.state.value == "awaiting_approval"
    assert SprintPhase.AWAITING_APPROVAL.value == "awaiting_approval"


def test_session_transition_replaces_state_and_preserves_artifacts(
    tmp_path: Path,
) -> None:
    store = WorkflowStateStore()
    session = make_session(tmp_path)
    store.create_session(session)

    assert store.transition_session(
        session.identifier,
        WorkflowSessionState.PLANNED,
        WorkflowSessionState.EXECUTING,
    )

    transitioned = store.get_session(session.identifier)
    assert transitioned is not session
    assert transitioned.state is WorkflowSessionState.EXECUTING
    assert transitioned.request is session.request
    assert transitioned.plan is session.plan
    assert transitioned.planning_analysis is session.planning_analysis


def test_session_transition_requires_expected_state(tmp_path: Path) -> None:
    store = WorkflowStateStore()
    session = make_session(tmp_path)
    store.create_session(session)

    assert not store.transition_session(
        session.identifier,
        WorkflowSessionState.AWAITING_APPROVAL,
        WorkflowSessionState.EXECUTING,
    )
    assert store.get_session(session.identifier) is session
    assert not store.transition_session(
        "missing",
        WorkflowSessionState.PLANNED,
        WorkflowSessionState.EXECUTING,
    )


def test_session_transition_stores_artifacts_with_waiting_state_atomically(
    tmp_path: Path,
) -> None:
    store = WorkflowStateStore()
    session = make_session(tmp_path)
    execution_result = Mock()
    changed_files = (Path("app/workflow/engine.py"),)
    store.create_session(session)

    assert store.transition_session(
        session.identifier,
        WorkflowSessionState.PLANNED,
        WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
        execution_result=execution_result,
        changed_files=changed_files,
    )

    stored = store.get_session(session.identifier)
    assert stored is not None
    assert stored.state is WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL
    assert stored.execution_result is execution_result
    assert stored.changed_files == changed_files


def test_concurrent_session_transition_allows_one_claim(
    tmp_path: Path,
) -> None:
    store = WorkflowStateStore()
    session = WorkflowSession(
        identifier="workflow-a15-3",
        request=make_request(tmp_path),
        plan=make_plan(tmp_path),
        state=WorkflowSessionState.AWAITING_APPROVAL,
    )
    store.create_session(session)
    barrier = Barrier(2)

    def claim(_: int) -> bool:
        barrier.wait()
        return store.transition_session(
            session.identifier,
            WorkflowSessionState.AWAITING_APPROVAL,
            WorkflowSessionState.EXECUTING,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(claim, range(2)))

    assert sorted(results) == [False, True]
    assert (
        store.get_session(session.identifier).state
        is WorkflowSessionState.EXECUTING
    )
