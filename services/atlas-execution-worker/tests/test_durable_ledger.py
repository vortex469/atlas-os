"""Durable worker ledger and crash-recovery tests."""

from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from app.execution.worker_contracts import CODEX_WORKSPACE_EXEC_ARGV_PREFIX
from asgi_test_client import ASGITestClient as TestClient
from atlas_execution_worker.api import _disabled_result, create_app
from atlas_execution_worker.durable_ledger import (
    DurableLedgerConflictError,
    DurableLedgerCorruptionError,
    DurableRequestLedger,
)
from atlas_execution_worker.workspace import WorkerWorkspaceManager
from test_worker import make_request


def test_terminal_result_survives_reopen_and_duplicate_is_exact(tmp_path: Path) -> None:
    database = tmp_path / "state" / "ledger.sqlite3"
    request = make_request()
    first = DurableRequestLedger(database)
    first.claim(request)
    stored = first.persist_result(request, _disabled_result(request))

    reopened = DurableRequestLedger(database)
    duplicate = reopened.claim(request)
    assert duplicate.state == "failed_terminal"
    assert duplicate.result == stored.result
    assert reopened.get(request.execution_request_id) == stored


def test_conflicting_digest_after_restart_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "ledger.sqlite3"
    request = make_request()
    ledger = DurableRequestLedger(database)
    ledger.claim(request)
    with pytest.raises(DurableLedgerConflictError):
        DurableRequestLedger(database).claim(
            make_request(argv=(*CODEX_WORKSPACE_EXEC_ARGV_PREFIX, "different prompt"))
        )


def test_execution_start_marker_becomes_unknown_and_never_relaunches(tmp_path: Path) -> None:
    database = tmp_path / "ledger.sqlite3"
    request = make_request()
    ledger = DurableRequestLedger(database)
    ledger.claim(request)
    executing = ledger.mark_executing(request)
    assert executing.state == "executing"

    recovered = DurableRequestLedger(database)
    counts = recovered.reconcile_startup()
    assert counts == {"claimed": 0, "unknown_outcome": 1}
    unknown = recovered.get(request.execution_request_id)
    assert unknown is not None
    assert unknown.state == "unknown_outcome"
    assert unknown.result is not None
    assert unknown.result.failure_code == "worker_crash"
    assert recovered.claim(request).state == "unknown_outcome"


def test_claim_before_start_remains_recoverable(tmp_path: Path) -> None:
    database = tmp_path / "ledger.sqlite3"
    request = make_request()
    ledger = DurableRequestLedger(database)
    ledger.claim(request)
    recovered = DurableRequestLedger(database)
    assert recovered.reconcile_startup() == {"claimed": 1, "unknown_outcome": 0}
    assert recovered.claim(request).state == "claimed"


def test_terminal_result_is_immutable(tmp_path: Path) -> None:
    database = tmp_path / "ledger.sqlite3"
    request = make_request()
    ledger = DurableRequestLedger(database)
    ledger.claim(request)
    result = _disabled_result(request)
    ledger.persist_result(request, result)
    with pytest.raises(Exception, match="terminal result is immutable"):
        ledger.persist_result(
            request,
            replace(result, stderr=replace(result.stderr, text="different")),
        )


def test_concurrent_instances_have_one_claim(tmp_path: Path) -> None:
    database = tmp_path / "ledger.sqlite3"
    request = make_request()

    def claim() -> str:
        return DurableRequestLedger(database).claim(request).state

    with ThreadPoolExecutor(max_workers=8) as executor:
        states = list(executor.map(lambda _: claim(), range(8)))
    assert states == ["claimed"] * 8
    assert len(DurableRequestLedger(database)) == 1


def test_corrupt_result_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "ledger.sqlite3"
    request = make_request()
    ledger = DurableRequestLedger(database)
    ledger.claim(request)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE executions SET state='failed_terminal', result_json=? WHERE execution_request_id=?",
            (json.dumps({"not": "a result"}), request.execution_request_id),
        )
    with pytest.raises(DurableLedgerCorruptionError):
        DurableRequestLedger(database).get(request.execution_request_id)


def test_durable_api_reuses_disabled_result_after_restart(tmp_path: Path) -> None:
    database = tmp_path / "ledger.sqlite3"
    request = make_request()
    first = TestClient(create_app(durable_ledger=DurableRequestLedger(database)))
    first_response = first.post("/v1/executions", json=request.to_dict())
    second = TestClient(create_app(durable_ledger=DurableRequestLedger(database)))
    second_response = second.post("/v1/executions", json=request.to_dict())
    assert first_response.status_code == second_response.status_code == 200
    assert first_response.json() == second_response.json()
    assert second.get(f"/v1/executions/{request.execution_request_id}").json() == second_response.json()


def test_lost_response_reconciles_authenticated_durable_result_without_reexecution(tmp_path):
    from app.execution.backends import WorkerExecutionBackend, WorkerExecutionContext
    from app.execution.models import ExecutionRequest, ExecutionStatus
    from app.execution.worker_client import WorkerTransportError
    from app.execution.worker_contracts import WorkerExecutionStatus
    from app.planning.models import ImplementationPlan

    request = make_request()
    database = tmp_path / "ledger.sqlite3"

    class InertRunner:
        calls = 0

        def execute(self, worker_request):
            self.calls += 1
            return replace(
                _disabled_result(worker_request),
                status=WorkerExecutionStatus.SUCCEEDED,
                failure_code=None, return_code=0,
                workspace_head=worker_request.expected_repository_head,
                base_repository_head=worker_request.expected_repository_head,
            )

    runner = InertRunner()
    api = TestClient(create_app(
        durable_ledger=DurableRequestLedger(database), execution_enabled=True,
        runners={request.repository_token: runner}, authentication_token="test-only-token",
    ))

    class LosingClient:
        submissions = 0
        lookups = 0

        def submit(self, worker_request):
            self.submissions += 1
            response = api.post(
                "/v1/executions", json=worker_request.to_dict(),
                headers={"Authorization": "Bearer test-only-token"},
            )
            assert response.status_code == 200
            raise WorkerTransportError("response dropped after durable completion")

        def get_result(self, request_id):
            self.lookups += 1
            reopened = TestClient(create_app(
                durable_ledger=DurableRequestLedger(database),
                authentication_token="test-only-token",
            ))
            assert reopened.get(f"/v1/executions/{request_id}").status_code == 401
            response = reopened.get(
                f"/v1/executions/{request_id}",
                headers={"Authorization": "Bearer test-only-token"},
            )
            assert response.status_code == 200
            return response.json()

    client = LosingClient()
    backend = WorkerExecutionBackend(client, repository_token=request.repository_token)
    plan = ImplementationPlan(
        checkpoint_id="checkpoint", title="Inert rehearsal", goal="No execution",
        repository_root=tmp_path, branch=request.repository_branch,
        head_commit=request.expected_repository_head,
        scope_items=(request.execution_intent,),
        affected_files=(Path("compose.production.yaml"),), required_tests=(), risks=(),
    )
    execution = ExecutionRequest(request.execution_request_id, plan, request.argv, tmp_path)
    context = WorkerExecutionContext(
        workflow_id=request.workflow_id, candidate_id=request.candidate_id,
        candidate_fingerprint=request.candidate_fingerprint,
        plan_id=request.plan_id, plan_fingerprint=request.plan_fingerprint,
        expected_repository_head=request.expected_repository_head,
        repository_token=request.repository_token,
        allowed_affected_files=request.allowed_affected_files,
        repository_branch=request.repository_branch,
    )

    assert backend.execute(execution, context=context).status is ExecutionStatus.UNKNOWN
    assert backend.reconcile(execution, context=context).status is ExecutionStatus.SUCCEEDED
    assert client.submissions == client.lookups == runner.calls == 1
    assert len(DurableRequestLedger(database)) == 1


def test_unknown_workspace_is_quarantined(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    workspace_root = tmp_path / "workspaces"
    manager = WorkerWorkspaceManager(source, workspace_root, "token", trusted_repository_paths=(source,), git_config_path=workspace_root / "gitconfig")
    leftover = workspace_root / "execution-1"
    leftover.mkdir(parents=True)
    (leftover / "evidence.txt").write_text("preserve", encoding="utf-8")
    quarantined = manager.quarantine("execution-1")
    assert quarantined is not None
    assert quarantined.name == "execution-1.unknown"
    assert (quarantined / "evidence.txt").read_text(encoding="utf-8") == "preserve"


@pytest.mark.parametrize('column,value', [('state','invalid'),('attempt',2),('schema_version',2),('request_digest','invalid'),('created_at','not-a-time')])
def test_corrupt_row_is_refused_without_repair_or_replay(tmp_path, column, value):
    database = tmp_path/'ledger.sqlite3'
    ledger = DurableRequestLedger(database)
    request = make_request()
    ledger.claim(request)
    with sqlite3.connect(database) as connection:
        connection.execute(f'UPDATE executions SET {column}=?', (value,))
        before = connection.execute('SELECT * FROM executions').fetchall()
    for operation in (lambda: ledger.get(request.execution_request_id), lambda: ledger.claim(request), ledger.reconcile_startup):
        with pytest.raises(DurableLedgerCorruptionError):
            operation()
    with sqlite3.connect(database) as connection:
        assert connection.execute('SELECT * FROM executions').fetchall() == before


def test_startup_validates_all_rows_before_classifying_execution(tmp_path):
    database = tmp_path/'ledger.sqlite3'
    ledger = DurableRequestLedger(database)
    first = make_request()
    ledger.claim(first)
    ledger.mark_executing(first)
    other = make_request(execution_request_id='other-id')
    ledger.claim(other)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE executions SET attempt=2 WHERE execution_request_id='other-id'")
    with pytest.raises(DurableLedgerCorruptionError):
        ledger.reconcile_startup()
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT state FROM executions WHERE execution_request_id='execution-1'").fetchone()[0] == 'executing'


@pytest.mark.parametrize('field', ['created_at','result_json'])
def test_corrupt_record_error_chain_does_not_echo_stored_values(tmp_path, field):
    import traceback
    database = tmp_path/'ledger.sqlite3'
    ledger = DurableRequestLedger(database)
    request = make_request()
    ledger.claim(request)
    private = 'PRIVATE_STORED_VALUE'
    with sqlite3.connect(database) as connection:
        if field == 'created_at':
            connection.execute('UPDATE executions SET created_at=?', (private,))
        else:
            payload = _disabled_result(request).to_dict()
            payload['status'] = private
            connection.execute("UPDATE executions SET state='failed_terminal',result_json=?", (json.dumps(payload),))
    with pytest.raises(DurableLedgerCorruptionError) as raised:
        ledger.get(request.execution_request_id)
    assert private not in ''.join(traceback.format_exception(raised.value))


def test_concurrent_start_barrier_has_exactly_one_winner(tmp_path):
    from atlas_execution_worker.durable_ledger import DurableLedgerStartConflict

    database = tmp_path / 'start.sqlite3'
    request = make_request()
    DurableRequestLedger(database).claim(request)

    def start(_):
        try:
            DurableRequestLedger(database).mark_executing(request)
            return 'winner'
        except DurableLedgerStartConflict as conflict:
            assert conflict.entry.state == 'executing'
            return 'loser'

    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(start, range(8)))
    assert outcomes.count('winner') == 1
    assert outcomes.count('loser') == 7


def test_submitter_losing_start_barrier_never_calls_runner(tmp_path, monkeypatch):
    from test_worker import FakeRunner

    request = make_request()
    ledger = DurableRequestLedger(tmp_path / 'race.sqlite3')
    original_claim = ledger.claim

    def racing_claim(request):
        entry = original_claim(request)
        ledger.mark_executing(request)
        return entry

    monkeypatch.setattr(ledger, 'claim', racing_claim)
    runner = FakeRunner()
    client = TestClient(create_app(durable_ledger=ledger, execution_enabled=True,
                                  runners={request.repository_token: runner}))
    response = client.post('/v1/executions', json=request.to_dict())
    assert response.status_code == 200
    assert response.json()['state'] == 'executing'
    assert runner.calls == 0


def test_success_requires_start_and_invalid_result_never_persists(tmp_path):
    from app.execution.worker_contracts import WorkerExecutionStatus, WorkerFailureCode
    from atlas_execution_worker.durable_ledger import DurableLedgerError

    request = make_request()
    ledger = DurableRequestLedger(tmp_path / 'barrier.sqlite3')
    before = ledger.claim(request)
    success = replace(_disabled_result(request), status=WorkerExecutionStatus.SUCCEEDED,
                      failure_code=None, return_code=0,
                      workspace_head=request.expected_repository_head,
                      base_repository_head=request.expected_repository_head)
    with pytest.raises(DurableLedgerError, match='start barrier'):
        ledger.persist_result(request, success)
    assert ledger.get(request.execution_request_id) == before
    unknown = replace(_disabled_result(request), status=WorkerExecutionStatus.UNKNOWN,
                      failure_code=WorkerFailureCode.WORKER_CRASH)
    with pytest.raises(DurableLedgerCorruptionError):
        ledger.persist_result(request, unknown)
    assert ledger.get(request.execution_request_id) == before
    ledger.mark_executing(request)
    assert ledger.persist_result(request, success).state == 'completed'


def test_reconcile_rolls_back_every_classification_on_write_failure(tmp_path):
    database = tmp_path / 'reconcile.sqlite3'
    ledger = DurableRequestLedger(database)
    for identity in ['first', 'second']:
        request = make_request(execution_request_id=identity)
        ledger.claim(request)
        ledger.mark_executing(request)
    with sqlite3.connect(database) as connection:
        connection.execute("""CREATE TRIGGER reject_second BEFORE UPDATE ON executions
            WHEN NEW.execution_request_id = 'second'
            BEGIN SELECT RAISE(ABORT, 'synthetic write failure'); END""")
    with pytest.raises(sqlite3.DatabaseError):
        ledger.reconcile_startup()
    assert ledger.get('first').state == ledger.get('second').state == 'executing'
    with sqlite3.connect(database) as connection:
        connection.execute('DROP TRIGGER reject_second')
    assert ledger.reconcile_startup() == {'claimed': 0, 'unknown_outcome': 2}
    assert ledger.reconcile_startup() == {'claimed': 0, 'unknown_outcome': 0}


@pytest.mark.parametrize('operation', ['claim', 'get', 'mark_executing', 'persist_result'])
def test_database_failure_is_controlled_without_reexecution(tmp_path, monkeypatch, caplog, operation):
    from test_worker import FakeRunner

    request = make_request()
    ledger = DurableRequestLedger(tmp_path / 'unavailable.sqlite3')
    runner = FakeRunner()
    original = getattr(ledger, operation)

    def broken(*args, **kwargs):
        raise sqlite3.OperationalError('PRIVATE_DATABASE_PATH')

    monkeypatch.setattr(ledger, operation, broken)
    client = TestClient(create_app(durable_ledger=ledger, execution_enabled=True,
                                  runners={request.repository_token: runner}))
    response = (client.get('/v1/executions/execution-1') if operation == 'get'
                else client.post('/v1/executions', json=request.to_dict()))
    assert response.status_code == 503
    assert response.json()['error']['code'] == 'ledger_unavailable'
    assert 'PRIVATE_DATABASE_PATH' not in response.text + caplog.text
    assert runner.calls == (1 if operation == 'persist_result' else 0)
    monkeypatch.setattr(ledger, operation, original)
    if operation == 'persist_result':
        # Failure after execution must remain in-flight; duplicate cannot rerun.
        duplicate = client.post('/v1/executions', json=request.to_dict())
        assert duplicate.json()['state'] == 'executing'
        assert runner.calls == 1
