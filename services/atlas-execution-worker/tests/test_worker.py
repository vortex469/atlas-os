"""S2 worker socket, ledger, and execution-disabled API tests."""

from __future__ import annotations

import logging
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from app.execution.worker_contracts import WorkerExecutionRequest
from atlas_execution_worker.api import _disabled_result, create_app
from atlas_execution_worker.ledger import RequestConflictError, RequestLedger
from atlas_execution_worker.server import (
    bind_socket,
    cleanup_socket,
    prepare_socket_path,
)
from fastapi.testclient import TestClient

HEAD = "a" * 40


def make_request(**overrides: object) -> WorkerExecutionRequest:
    values: dict[str, object] = {
        "execution_request_id": "execution-1",
        "workflow_id": "workflow-1",
        "candidate_id": "candidate-1",
        "candidate_fingerprint": "candidate-fingerprint-1",
        "plan_id": "plan-1",
        "plan_fingerprint": "plan-fingerprint-1",
        "execution_intent": "update-compose-stack",
        "repository_token": "repository-token-1",
        "expected_repository_head": HEAD,
        "repository_branch": "feature/worker",
        "argv": ("codex", "exec", "do not execute this prompt"),
        "working_directory": ".",
        "allowed_affected_files": ("compose.production.yaml",),
        "timeout_seconds": 120,
    }
    values.update(overrides)
    return WorkerExecutionRequest.build(**values)


def test_health_and_disabled_submission_have_bounded_contract() -> None:
    client = TestClient(create_app())

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {
        "service": "atlas-execution-worker",
        "status": "healthy",
        "contract_schema_version": 1,
        "execution_enabled": False,
    }

    response = client.post("/v1/executions", json=make_request().to_dict())
    body = response.json()
    assert response.status_code == 200
    assert body["state"] == "completed"
    assert body["result"]["status"] == "blocked"
    assert body["result"]["failure_code"] == "worker_unavailable"
    assert body["result"]["changed_files"] == []


def test_validation_conflict_and_lookup_errors_are_deterministic() -> None:
    client = TestClient(create_app())
    request = make_request()

    malformed = client.post("/v1/executions", json={"schema_version": 1})
    assert malformed.status_code == 400
    assert malformed.json()["error"]["code"] == "invalid_request"

    tampered = request.to_dict()
    tampered["request_digest"] = "execution-request-digest-v1:" + "0" * 64
    digest_error = client.post("/v1/executions", json=tampered)
    assert digest_error.status_code == 400
    assert digest_error.json()["error"]["code"] == "invalid_request"

    assert client.post("/v1/executions", json=request.to_dict()).status_code == 200
    conflicting = make_request(argv=("codex", "exec", "different prompt"))
    conflict = client.post("/v1/executions", json=conflicting.to_dict())
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "request_id_conflict"

    unknown = client.get("/v1/executions/unknown-request")
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "execution_not_found"


def test_ledger_claims_identical_request_once_and_reuses_completion() -> None:
    ledger = RequestLedger()
    request = make_request()

    first = ledger.claim(request)
    second = ledger.claim(request)
    assert first == second
    assert first.state == "claimed"
    assert len(ledger) == 1

    result = _disabled_result(request)
    completed = ledger.complete(request, result)
    assert completed.state == "completed"
    assert ledger.claim(request) == completed


def test_ledger_rejects_same_id_with_different_digest() -> None:
    ledger = RequestLedger()
    ledger.claim(make_request())
    different = make_request(argv=("codex", "exec", "different prompt"))

    with pytest.raises(RequestConflictError):
        ledger.claim(different)


def test_concurrent_identical_claims_have_one_entry() -> None:
    ledger = RequestLedger()
    request = make_request()
    barrier = threading.Barrier(8)
    entries = []
    errors = []

    def claim() -> None:
        try:
            barrier.wait()
            entries.append(ledger.claim(request))
        except (RuntimeError, ValueError) as exc:  # pragma: no cover - assertion below reports it.
            errors.append(exc)

    threads = [threading.Thread(target=claim) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(entries) == 8
    assert len(ledger) == 1
    assert {entry.request_digest for entry in entries} == {request.request_digest}


def test_socket_lifecycle_is_private_and_cleans_stale_socket(tmp_path: Path) -> None:
    socket_path = tmp_path / "worker.sock"
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(str(socket_path))
    stale.close()

    prepare_socket_path(socket_path)
    server = bind_socket(socket_path)
    try:
        assert socket_path.exists()
        assert socket_path.stat().st_mode & 0o777 == 0o660
        assert server.family == socket.AF_UNIX
    finally:
        server.close()
        cleanup_socket(socket_path)
    assert not socket_path.exists()


def test_socket_health_and_submit_through_unix_socket(tmp_path: Path) -> None:
    socket_path = tmp_path / "worker.sock"
    app = create_app()
    config = uvicorn.Config(app, uds=str(socket_path), log_level="critical")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not socket_path.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    try:
        from app.execution.worker_client import UnixSocketWorkerClient

        client = UnixSocketWorkerClient(socket_path)
        assert client.health()["execution_enabled"] is False
        result = client.submit(make_request())
        assert result["result"]["failure_code"] == "worker_unavailable"
        assert client.get_result("execution-1")["state"] == "completed"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        cleanup_socket(socket_path)
    assert not thread.is_alive()


def test_prompt_and_auth_like_values_are_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    client = TestClient(create_app())
    prompt = "SECRET_PROMPT_SHOULD_NOT_BE_LOGGED"
    auth_like = "sk-secret-value"
    request = make_request(argv=("codex", "exec", prompt + " " + auth_like))

    with caplog.at_level(logging.INFO):
        assert client.post("/v1/executions", json=request.to_dict()).status_code == 200
    rendered = "\n".join(record.getMessage() for record in caplog.records)
    assert prompt not in rendered
    assert auth_like not in rendered
