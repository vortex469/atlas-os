import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.operational_dispatch.auth import OperationalDispatchAuthenticator
from app.operational_dispatch.ledger import OperationalDispatchLedger
from app.operational_dispatch.lifecycle import (
    OperationalLifecycleService,
    OperationalVerifierRegistry,
)
from app.operational_dispatch.models import OperationalDispatchAuditStatus
from app.operational_dispatch.service import OperationalDispatchService
from app.operational_dispatch.test_support import make_request
from app.routes.internal_operational_actions import router


def _client(tmp_path) -> tuple[TestClient, OperationalDispatchLedger, str]:
    token = "dedicated-test-service-token"
    token_file = tmp_path / "token"
    token_file.write_text(f"{token}\n", encoding="ascii")
    token_file.chmod(0o400)
    ledger = OperationalDispatchLedger(tmp_path / "operational.db")
    app = FastAPI()
    app.state.operational_dispatch_ledger = ledger
    app.state.operational_dispatch_authenticator = OperationalDispatchAuthenticator(
        token_file
    )
    dispatcher = OperationalDispatchService(
        ledger=ledger,
        execution_intents=frozenset(),
    )
    app.state.operational_dispatch_service = dispatcher
    app.state.operational_lifecycle_service = OperationalLifecycleService(
        ledger=ledger,
        dispatcher=dispatcher,
        verifiers=OperationalVerifierRegistry(),
    )
    app.include_router(router, prefix="/api/v1")
    return TestClient(app), ledger, token


def _post(client: TestClient, token: str, payload: dict[str, object]):
    return client.post(
        "/api/v1/internal/operational-actions/dispatch",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )


def test_missing_malformed_and_wrong_auth_are_rejected_before_body_parse(tmp_path) -> None:
    client, ledger, token = _client(tmp_path)
    url = "/api/v1/internal/operational-actions/dispatch"
    for headers in ({}, {"Authorization": token}, {"Authorization": "Bearer wrong"}):
        response = client.post(url, headers=headers, content=b"not-json")
        assert response.status_code == 401
        assert token not in response.text
    statuses = tuple(event.status for event in ledger.list_events())
    assert statuses.count(OperationalDispatchAuditStatus.AUTH_ATTEMPTED) == 3
    assert statuses.count(OperationalDispatchAuditStatus.AUTH_REJECTED) == 3


def test_authenticated_strict_request_reaches_explicit_empty_execution_gate(tmp_path) -> None:
    client, ledger, token = _client(tmp_path)
    request = make_request()
    response = _post(client, token, request.model_dump(mode="json"))
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["sanitized_message"] == (
        "Operational execution capability is disabled."
    )
    statuses = {event.status for event in ledger.list_events()}
    assert OperationalDispatchAuditStatus.REQUEST_ACCEPTED in statuses
    assert OperationalDispatchAuditStatus.EXECUTION_DISABLED in statuses
    persisted = (tmp_path / "operational.db").read_bytes()
    assert token.encode() not in persisted
    assert b"Authorization" not in persisted


def test_sanitized_lifecycle_read_requires_auth_and_does_not_write(tmp_path) -> None:
    client, ledger, token = _client(tmp_path)
    request = make_request()
    _post(client, token, request.model_dump(mode="json"))
    url = f"/api/v1/internal/operational-actions/lifecycle/{request.request_id}"
    before = ledger.list_events(limit=1000)

    assert client.get(url).status_code == 401
    response = client.get(url, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == request.request_id
    assert payload["ledger_state"] == "failed"
    assert payload["barrier_crossing_count"] == 0
    assert payload["provider_operation_capture_count"] == 0
    assert payload["controlled_reason"] == "dispatch_failed"
    assert ledger.list_events(limit=1000) == before
    serialized = json.dumps(payload)
    assert "approval" not in serialized
    assert "Authorization" not in serialized
    assert "vmgenid" not in serialized


def test_authenticated_request_rejects_extra_fields_and_large_body(tmp_path) -> None:
    client, _ledger, token = _client(tmp_path)
    payload = make_request().model_dump(mode="json")
    payload["command"] = "restart now"
    assert _post(client, token, payload).status_code == 422
    oversized = json.dumps({"padding": "x" * 66_000})
    response = client.post(
        "/api/v1/internal/operational-actions/dispatch",
        headers={"Authorization": f"Bearer {token}"},
        content=oversized,
    )
    assert response.status_code == 413


def test_authenticated_replay_is_idempotent_and_digest_conflict_is_rejected(
    tmp_path,
) -> None:
    client, ledger, token = _client(tmp_path)
    request = make_request()
    first = _post(client, token, request.model_dump(mode="json"))
    second = _post(client, token, request.model_dump(mode="json"))
    assert first.json() == second.json()
    conflicting = make_request(candidate_id="candidate-2")
    response = _post(client, token, conflicting.model_dump(mode="json"))
    assert response.status_code == 409
    assert OperationalDispatchAuditStatus.REQUEST_CONFLICT in {
        event.status for event in ledger.list_events()
    }


def test_internal_dispatch_route_is_not_published_in_openapi(tmp_path) -> None:
    client, _ledger, _token = _client(tmp_path)
    assert "/api/v1/internal/operational-actions/dispatch" not in client.get(
        "/openapi.json"
    ).json()["paths"]


def test_authenticated_status_is_typed_read_only_and_missing_auth_is_rejected(
    tmp_path,
) -> None:
    client, _ledger, token = _client(tmp_path)
    request = make_request()
    _post(client, token, request.model_dump(mode="json"))
    url = f"/api/v1/internal/operational-actions/{request.request_id}"
    assert client.get(url).status_code == 401
    response = client.get(url, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["request_digest"] == request.request_digest
    assert response.json()["ledger_state"] == "failed"
    assert response.json()["verification_resumable"] is False
