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
