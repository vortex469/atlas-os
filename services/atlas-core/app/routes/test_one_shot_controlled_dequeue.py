"""P3 API locks for v0.45 one-shot controlled dequeue evidence."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.one_shot_controlled_dequeue.contract import (
    OneShotControlledDequeueAdapterResultV1,
    opaque_fingerprint,
)
from app.one_shot_controlled_dequeue.test_service_store import _service
from app.operator_auth.models import (
    INSTALLATION_ONE_SHOT_CONTROLLED_DEQUEUE_READ,
    INSTALLATION_ONE_SHOT_CONTROLLED_DEQUEUE_RECORD,
    SUPPORTED_OPERATOR_PERMISSIONS,
    OperatorCredential,
)
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.one_shot_controlled_dequeue import router
from app.testing import ASGITestClient

ORIGIN = "https://atlas.example"


class Adapter:
    def __init__(self) -> None:
        self.calls = []

    def attempt_exact_item(self, request):
        self.calls.append(request)
        return OneShotControlledDequeueAdapterResultV1(
            outcome="success",
            adapter_receipt_fingerprint=opaque_fingerprint(
                "atlas:one-shot-controlled-dequeue-adapter-receipt:v1",
                "route-success",
            ),
            queue_identity_fingerprint=request.queue_identity_fingerprint,
            item_identity_fingerprint=request.item_identity_fingerprint,
        )


def _application(
    tmp_path: Path,
    *,
    permissions=None,
    rate_limit: int = 100,
    service_installed: bool = True,
    service_enabled: bool = True,
    queue_adapter=None,
):
    adapter = queue_adapter if queue_adapter is not None else Adapter()
    (
        dequeue_service,
        _store,
        reader,
        admission,
        _status,
        create,
    ) = _service(
        tmp_path / "service",
        enabled=service_enabled,
        queue_adapter=adapter,
    )
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    application.state.operator_auth_enabled = True
    application.state.operator_auth_trusted_origins = frozenset({ORIGIN})
    application.state.operator_mutation_rate_limiter = OperatorRateLimiter(
        rate_limit, 60
    )
    sessions = OperatorSessionStore(tmp_path / "sessions.db", 3600)
    application.state.operator_session_store = sessions
    session = sessions.create(
        OperatorCredential(
            operator_id=admission.operator_id,
            password_hash="unused",
            permissions=permissions
            or (
                INSTALLATION_ONE_SHOT_CONTROLLED_DEQUEUE_RECORD,
                INSTALLATION_ONE_SHOT_CONTROLLED_DEQUEUE_READ,
            ),
        )
    )
    if service_installed:
        application.state.one_shot_controlled_dequeue_service = dequeue_service
    collection = (
        f"/api/v1/installation/candidate-records/{admission.candidate_record_id}"
        "/one-shot-controlled-dequeues"
    )
    return (
        ASGITestClient(application),
        session,
        admission,
        create,
        reader,
        adapter,
        collection,
        sessions,
    )


def _cookies(session):
    return {"atlas_operator_session": session.session_token}


def _headers(session, key: str = "one-shot-controlled-route-key-1"):
    return {
        "Origin": ORIGIN,
        "X-Atlas-CSRF-Token": session.csrf_token,
        "Idempotency-Key": key,
    }


def test_auth_csrf_success_readback_and_exact_no_replay(tmp_path: Path) -> None:
    client, session, admission, create, reader, adapter, url, sessions = _application(
        tmp_path
    )
    payload = create.model_dump(mode="json")
    assert client.get(url).status_code == 401
    assert client.post(url, json=payload, cookies=_cookies(session)).status_code == 403
    assert client.post(
        url,
        json=payload,
        cookies=_cookies(session),
        headers={**_headers(session), "Origin": "https://foreign.example"},
    ).status_code == 403

    made = client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    assert made.status_code == 201
    body = made.json()
    assert body["ok"] is True
    assert body["outcome"] == "success"
    assert body["one_shot_controlled_dequeue_recorded"] is True
    assert body["record"]["candidate_record_id"] == admission.candidate_record_id
    assert body["record"]["outcome"] == "success"
    assert body["record"]["disposition"] == "exact_inert_item_dequeued"
    assert body["record"]["bounded_receipt"]["adapter_receipt_redacted"] is True
    assert body["record"]["bounded_receipt"]["exact_admitted_item_only"] is True
    for field in (
        "queue_polling_allowed",
        "queue_claim_allowed",
        "queue_lease_allowed",
        "queue_ack_allowed",
        "worker_contact_allowed",
        "worker_start_allowed",
        "agent_invocation_allowed",
        "execution_start_allowed",
        "process_execution_allowed",
        "dispatch_allowed",
        "retry_allowed",
        "resend_allowed",
        "installation_allowed",
        "deployment_allowed",
        "rollback_allowed",
    ):
        assert body["record"][field] is False

    listed = client.get(url, cookies=_cookies(session))
    assert listed.status_code == 200
    assert listed.json()["items"] == [body["record"]]
    fetched = client.get(
        f"{url}/{body['record']['dequeue_id']}", cookies=_cookies(session)
    )
    assert fetched.status_code == 200
    assert fetched.json()["record"] == body["record"]
    foreign = sessions.create(
        OperatorCredential(
            operator_id="operator-b",
            password_hash="unused",
            permissions=(INSTALLATION_ONE_SHOT_CONTROLLED_DEQUEUE_READ,),
        )
    )
    foreign_get = client.get(
        f"{url}/{body['record']['dequeue_id']}", cookies=_cookies(foreign)
    )
    assert foreign_get.status_code == 404
    assert foreign_get.json()["error"]["error_code"] == "not_found"
    duplicate = client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["record"] == body["record"]
    assert reader.calls == 1
    assert len(adapter.calls) == 1


def test_dedicated_permissions_default_off_and_redaction(tmp_path: Path) -> None:
    read_client, read_session, _, create, _, _, url, _ = _application(
        tmp_path / "read",
        permissions=(INSTALLATION_ONE_SHOT_CONTROLLED_DEQUEUE_READ,),
    )
    assert read_client.get(url, cookies=_cookies(read_session)).status_code == 200
    assert read_client.post(
        url,
        json=create.model_dump(mode="json"),
        cookies=_cookies(read_session),
        headers=_headers(read_session),
    ).status_code == 403

    create_client, create_session, _, create, _, _, url, _ = _application(
        tmp_path / "create",
        permissions=(INSTALLATION_ONE_SHOT_CONTROLLED_DEQUEUE_RECORD,),
    )
    assert create_client.get(url, cookies=_cookies(create_session)).status_code == 403

    disabled, disabled_session, _, create, reader, adapter, url, _ = _application(
        tmp_path / "disabled", service_enabled=False
    )
    blocked = disabled.post(
        url,
        json=create.model_dump(mode="json"),
        cookies=_cookies(disabled_session),
        headers=_headers(disabled_session),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["error_code"] == "installation_capability_unsupported"
    assert reader.calls == 0
    assert adapter.calls == []

    missing_client, missing_session, _, create, _, _, missing_url, _ = _application(
        tmp_path / "missing", service_installed=False
    )
    unavailable = missing_client.post(
        missing_url,
        json=create.model_dump(mode="json"),
        cookies=_cookies(missing_session),
        headers=_headers(missing_session),
    )
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["error_code"] == "internal_error"
    assert "one-shot-controlled-route-key-1" not in json.dumps(unavailable.json())


def test_strict_body_query_method_rate_and_idempotency_bounds(tmp_path: Path) -> None:
    client, session, _, create, _, _, url, _ = _application(tmp_path)
    payload = create.model_dump(mode="json")
    cookies, headers = _cookies(session), _headers(session)
    assert client.post(
        url,
        content=b"{}",
        cookies=cookies,
        headers={**headers, "Content-Type": "text/plain"},
    ).status_code == 415
    duplicate = json.dumps(payload)[:-1] + ',"schema":"duplicate"}'
    assert client.post(
        url,
        content=duplicate,
        cookies=cookies,
        headers={**headers, "Content-Type": "application/json"},
    ).status_code == 422
    assert client.post(
        url,
        json={**payload, "endpoint": "amqp://secret"},
        cookies=cookies,
        headers=headers,
    ).status_code == 422
    assert client.post(url + "?poll=true", json=payload, cookies=cookies, headers=headers).status_code == 422
    assert client.get(url + "?limit=1", cookies=cookies).status_code == 422
    for invalid_key in (None, "too-short", "contains space here", "x" * 129, "bad\x7f"):
        exact_headers = {
            name: value for name, value in headers.items() if name != "Idempotency-Key"
        }
        if invalid_key is not None:
            exact_headers["Idempotency-Key"] = invalid_key
        assert client.post(
            url, json=payload, cookies=cookies, headers=exact_headers
        ).status_code == 422
    assert client.request("PUT", url).status_code == 405
    assert client.request(
        "POST", f"{url}/4b3beb58-c4b9-5b2b-9995-4f629abefaf4"
    ).status_code == 405

    limited_client, limited_session, _, limited_create, _, _, limited_url, _ = (
        _application(tmp_path / "limited", rate_limit=1)
    )
    assert limited_client.post(
        limited_url,
        json=limited_create.model_dump(mode="json"),
        cookies=_cookies(limited_session),
        headers=_headers(limited_session, "one-shot-controlled-first-key"),
    ).status_code == 201
    limited = limited_client.post(
        limited_url,
        json=limited_create.model_dump(mode="json"),
        cookies=_cookies(limited_session),
        headers=_headers(limited_session, "one-shot-controlled-second-key"),
    )
    assert limited.status_code == 429
    assert limited.json()["error"]["error_code"] == "rate_limited"


def test_permissions_openapi_method_and_authority_isolation() -> None:
    assert INSTALLATION_ONE_SHOT_CONTROLLED_DEQUEUE_RECORD == (
        "installation.execution.one_shot_controlled_dequeue.record"
    )
    assert INSTALLATION_ONE_SHOT_CONTROLLED_DEQUEUE_READ == (
        "installation.execution.one_shot_controlled_dequeue.read"
    )
    assert {
        INSTALLATION_ONE_SHOT_CONTROLLED_DEQUEUE_RECORD,
        INSTALLATION_ONE_SHOT_CONTROLLED_DEQUEUE_READ,
    } <= SUPPORTED_OPERATOR_PERMISSIONS

    application = FastAPI()
    application.include_router(api_v1_router)
    paths = application.openapi()["paths"]
    collection = (
        "/api/v1/installation/candidate-records/{candidate_record_id}"
        "/one-shot-controlled-dequeues"
    )
    item = f"{collection}/{{dequeue_id}}"
    assert set(paths[collection]) == {"get", "post"}
    assert set(paths[item]) == {"get"}
    post = paths[collection]["post"]
    assert set(post["requestBody"]["content"]) == {"application/json"}
    idempotency = next(
        value for value in post["parameters"] if value["name"] == "Idempotency-Key"
    )
    assert idempotency["in"] == "header" and idempotency["required"] is True
    prohibited_segments = {
        "poll",
        "claim",
        "lease",
        "ack",
        "consume",
        "worker",
        "start",
        "run",
        "execute",
        "dispatch",
        "retry",
        "resend",
        "install",
        "deploy",
        "rollback",
        "agent",
        "workflow",
        "scheduler",
    }
    assert not any(
        segment in prohibited_segments
        for path in paths
        if "one-shot-controlled-dequeues" in path
        for segment in path.split("one-shot-controlled-dequeues", 1)[1]
        .strip("/")
        .split("/")
        if segment
    )


def test_route_has_no_runtime_effect_imports_or_broad_calls() -> None:
    path = Path(__file__).with_name("one_shot_controlled_dequeue.py")
    source = path.read_text()
    tree = ast.parse(source)
    imports = {
        alias.name if isinstance(node, ast.Import) else node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden_imports = (
        "operational_dispatch",
        "atlas_agent",
        "provider",
        "repository",
        "workflow",
        "worker_queue",
        "worker_runtime",
        "transport",
        "deployment",
        "rollback",
        "subprocess",
        "docker",
        "podman",
        "socket",
    )
    assert not [
        name for name in imports if any(term in name for term in forbidden_imports)
    ]
    for forbidden in (
        "send(",
        "publish(",
        "poll(",
        "claim(",
        "lease(",
        "ack(",
        "consume(",
        "start(",
        "run(",
        "execute(",
        "dispatch(",
        "retry(",
        "resend(",
        "install(",
        "deploy(",
        "rollback(",
    ):
        assert forbidden not in source


def test_production_startup_does_not_construct_one_shot_controlled_dequeue() -> None:
    source = Path(__file__).parents[1].joinpath("main.py").read_text()
    assert "one_shot_controlled_dequeue_service" not in source
    assert "create_one_shot_controlled_dequeue_reservation_service" not in source
