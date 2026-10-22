"""Lost-response rehearsal using disposable repositories and persisted Agent state."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest
from app.candidate_planning.execution import (
    CandidateExecutionFailureCode,
    CandidateExecutionValidationResult,
    candidate_worker_execution_context,
)
from app.execution.backends import WorkerExecutionBackend
from app.execution.engine import ExecutionEngine
from app.execution.models import ExecutionStatus
from app.execution.worker_client import WorkerTransportError
from app.workflow.models import WorkflowSessionState
from tests.test_worker_journal_workflow_integration import TARGET, _fixture


class LostResponseClient:
    def __init__(self, worker, snapshot: Path) -> None:
        self.worker = worker
        self.snapshot = snapshot
        self.submissions = 0
        self.lookups: list[str] = []
        self.response = None
        self.lookup_error = False
        self.on_lookup = lambda: None

    def submit(self, request):
        # The exact identity must be on disk before a worker can receive it.
        payload = json.loads(self.snapshot.read_text())
        assert request.to_dict() == payload["workflow_state"]["sessions"][request.workflow_id]["worker_execution_request"]
        self.submissions += 1
        self.response = self.worker.submit(request)
        self.response["request_digest"] = request.request_digest
        raise WorkerTransportError("response lost after the worker persisted its result")

    def get_result(self, request_id):
        self.lookups.append(request_id)
        self.on_lookup()
        if self.lookup_error:
            raise WorkerTransportError("lookup unavailable")
        return self.response


def lost_attempt(tmp_path):
    engine, state, approvals, persistence, worker, root, _ = _fixture(tmp_path)
    client = LostResponseClient(worker, tmp_path / "state" / "atlas-agent-state.json")
    engine._execution_engine = ExecutionEngine(backend=WorkerExecutionBackend(client))
    result = engine.resume("candidate-workflow-1")
    assert result.execution_result.status is ExecutionStatus.UNKNOWN
    assert result.error_message == "worker_outcome_unknown"
    assert client.submissions == 1
    assert (root / TARGET).read_text() == "old\n"
    assert approvals.get_request("approval-verification-candidate-workflow-1") is None
    return engine, state, approvals, persistence, client, root


def test_review_preparation_matches_durable_native_dispatch(tmp_path):
    engine, state, _, persistence, worker, _, _ = _fixture(tmp_path)
    session = state.get_session("candidate-workflow-1")
    request = engine._candidate_execution_validator.result.execution_request
    backend = engine._execution_engine
    context = candidate_worker_execution_context(
        session, request.plan, repository_token=backend.repository_token,
    )
    reviewed = backend.prepare_worker_request(request, context=context)
    assert type(reviewed.timeout_seconds) is float
    # Preparation must be inert.
    assert worker.calls == 0
    assert not persistence.snapshot_path.exists()
    assert backend.prepare_worker_request(request, context=context).to_json() == reviewed.to_json()
    assert not persistence.snapshot_path.exists()

    engine.resume(session.identifier)

    actual = state.get_session(session.identifier).worker_execution_request
    assert actual.to_json() == reviewed.to_json()
    assert actual.request_digest == reviewed.request_digest
    payload = json.loads(persistence.snapshot_path.read_text())
    assert payload["workflow_state"]["sessions"][session.identifier]["worker_execution_request"] == reviewed.to_dict()
    assert worker.calls == 1


def test_lost_response_recovers_after_agent_restart_without_resubmission(tmp_path):
    _, state, _, _, client, root = lost_attempt(tmp_path)
    original = state.get_session("candidate-workflow-1").worker_execution_request
    recovered, recovered_state, approvals, _, _, _, _ = _fixture(
        tmp_path / "fresh", root=root, state_dir=tmp_path / "state",
    )
    recovered._execution_engine = ExecutionEngine(backend=WorkerExecutionBackend(client))

    result = recovered.resume("candidate-workflow-1")

    assert result.sprint.phase.value == "awaiting_verification_approval"
    assert (root / TARGET).read_text() == "new\n"
    assert client.submissions == 1
    assert client.lookups == [original.execution_request_id]
    assert recovered_state.get_session("candidate-workflow-1").worker_execution_request == original
    assert approvals.get_request("approval-verification-candidate-workflow-1").decision.status.value == "pending"
    recovered.resume("candidate-workflow-1")
    assert client.submissions == 1
    assert client.lookups == [original.execution_request_id]


@pytest.mark.parametrize("outcome", ["unavailable", "missing", "unknown", "wrong-digest"])
def test_uncertain_reconciliation_stays_blocked_without_resubmission(tmp_path, outcome):
    engine, state, approvals, _, client, root = lost_attempt(tmp_path)
    if outcome == "unavailable":
        client.lookup_error = True
    elif outcome == "missing":
        client.response = {"state": "claimed", "result": None, "request_digest": client.response["request_digest"]}
    elif outcome == "unknown":
        client.response["state"] = "unknown_outcome"
    else:
        client.response["request_digest"] = "execution-request-digest-v1:" + "0" * 64

    for _ in range(2):
        result = engine.resume("candidate-workflow-1")
        assert result.execution_result.status is ExecutionStatus.UNKNOWN
        assert state.get_session("candidate-workflow-1").state is WorkflowSessionState.BLOCKED
    assert client.submissions == 1
    assert len(client.lookups) == 2
    assert (root / TARGET).read_text() == "old\n"
    assert approvals.get_request("approval-verification-candidate-workflow-1") is None


def test_reconciliation_revalidates_the_original_candidate_before_consuming_result(tmp_path):
    engine, _, _, _, client, root = lost_attempt(tmp_path)
    engine._candidate_execution_validator.result = CandidateExecutionValidationResult(
        approved=False, failure_code=CandidateExecutionFailureCode.CANDIDATE_STALE,
        should_block=True,
    )

    engine.resume("candidate-workflow-1")

    assert client.submissions == 1
    assert client.lookups == []
    assert (root / TARGET).read_text() == "old\n"


def test_changed_repository_configuration_cannot_redirect_reconciliation(tmp_path):
    engine, _, _, _, client, root = lost_attempt(tmp_path)
    engine._execution_engine = ExecutionEngine(
        backend=WorkerExecutionBackend(client, repository_token="foreign-repository"),
    )

    engine.resume("candidate-workflow-1")

    assert client.submissions == 1
    assert client.lookups == []
    assert (root / TARGET).read_text() == "old\n"


def test_concurrent_reconciliation_claims_one_lookup_and_never_resubmits(tmp_path):
    engine, _, _, _, client, root = lost_attempt(tmp_path)
    entered, release = Event(), Event()

    def pause_lookup():
        entered.set()
        assert release.wait(5)

    client.on_lookup = pause_lookup
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(engine.resume, "candidate-workflow-1")
        try:
            assert entered.wait(5)
            second = engine.resume("candidate-workflow-1")
            assert second.error_message == "Workflow already in progress"
        finally:
            release.set()
        assert first.result().sprint.phase.value == "awaiting_verification_approval"
    assert client.submissions == 1
    assert len(client.lookups) == 1
    assert (root / TARGET).read_text() == "new\n"


def test_process_restart_between_submission_and_agent_response_keeps_original_identity(tmp_path):
    _engine, state, _, persistence, client, root = lost_attempt(tmp_path)
    interrupted = replace(
        state.get_session("candidate-workflow-1"),
        state=WorkflowSessionState.EXECUTING, execution_result=None,
    )
    persistence.mutate_workflow(lambda workflows: workflows.transition_session(
        interrupted.identifier, WorkflowSessionState.BLOCKED,
        WorkflowSessionState.EXECUTING, execution_result=None,
    ))
    recovered, recovered_state, _, _, _, _, _ = _fixture(
        tmp_path / "fresh", root=root, state_dir=tmp_path / "state",
    )
    recovered._execution_engine = ExecutionEngine(backend=WorkerExecutionBackend(client))
    assert recovered_state.get_session(interrupted.identifier).can_reconcile_worker
    assert recovered.resume(interrupted.identifier).sprint.phase.value == "awaiting_verification_approval"
    assert client.submissions == 1
    assert len(client.lookups) == 1


def test_worker_is_not_contacted_when_request_cannot_be_persisted(tmp_path):
    engine, state, _, persistence, worker, _, _ = _fixture(tmp_path)
    original = persistence._write_payload

    def fail_record(payload):
        session = payload["workflow_state"]["sessions"]["candidate-workflow-1"]
        if session["worker_execution_request"] is not None:
            raise OSError("read-only state volume")
        return original(payload)

    persistence._write_payload = fail_record
    result = engine.resume("candidate-workflow-1")
    assert result.sprint.phase.value == "blocked"
    assert worker.calls == 0
    assert state.get_session("candidate-workflow-1").worker_execution_request is None


def test_workflow_api_exposes_unknown_outcome_and_checks_only_on_explicit_resume(tmp_path, monkeypatch):
    from app.config.settings import Settings
    from app.main import create_app
    from asgi_test_client import ASGITestClient

    engine, state, approvals, persistence, client, root = lost_attempt(tmp_path)
    monkeypatch.setattr("app.main.load_settings", lambda: Settings(
        repository_root=root, state_dir=tmp_path / "api-state",
    ))
    application = create_app()
    application.state.container = replace(
        application.state.container,
        workflow_state=state, workflow_engine=engine,
        approval_repository=approvals, state_persistence=persistence,
    )
    api = ASGITestClient(application)
    path = "/api/v1/agent/workflows/candidate-workflow-1"

    detail = api.get(path + "/implementation-request")
    assert detail.status_code == 200
    assert detail.json()["execution"]["execution_status"] == "unknown"
    assert detail.json()["worker_reconciliation"]["can_check_result"] is True
    assert detail.json()["worker_reconciliation"]["request_digest"] == state.get_session("candidate-workflow-1").worker_execution_request.request_digest
    assert client.lookups == []
    client.lookup_error = True
    uncertain = api.post(path + "/resume")
    assert uncertain.status_code == 409
    assert uncertain.json()["detail"]["code"] == "worker_outcome_unknown"
    client.lookup_error = False
    assert api.post(path + "/resume").status_code == 200
    assert api.get(path + "/implementation-request").json()["worker_reconciliation"]["can_check_result"] is False
    assert client.submissions == 1
    assert len(client.lookups) == 2
