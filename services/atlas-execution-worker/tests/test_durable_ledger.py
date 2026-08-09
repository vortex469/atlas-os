"""Durable worker ledger and crash-recovery tests."""

from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from atlas_execution_worker.api import _disabled_result, create_app
from atlas_execution_worker.durable_ledger import (
    DurableLedgerConflictError,
    DurableLedgerCorruptionError,
    DurableRequestLedger,
)
from atlas_execution_worker.workspace import WorkerWorkspaceManager
from fastapi.testclient import TestClient
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
            make_request(argv=("codex", "exec", "different prompt"))
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


def test_unknown_workspace_is_quarantined(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    workspace_root = tmp_path / "workspaces"
    manager = WorkerWorkspaceManager(source, workspace_root, "token")
    leftover = workspace_root / "execution-1"
    leftover.mkdir(parents=True)
    (leftover / "evidence.txt").write_text("preserve", encoding="utf-8")
    quarantined = manager.quarantine("execution-1")
    assert quarantined is not None
    assert quarantined.name == "execution-1.unknown"
    assert (quarantined / "evidence.txt").read_text(encoding="utf-8") == "preserve"
