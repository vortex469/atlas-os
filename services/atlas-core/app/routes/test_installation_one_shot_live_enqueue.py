"""P3 API locks for v0.42 one-shot live enqueue evidence."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.installation_one_shot_live_enqueue.test_service_store import _service
from app.operator_auth.models import (
    INSTALLATION_LIVE_ENQUEUE_ADMISSION_READ,
    INSTALLATION_LIVE_ENQUEUE_ADMISSION_RECORD,
    INSTALLATION_ONE_SHOT_LIVE_ENQUEUE_READ,
    INSTALLATION_ONE_SHOT_LIVE_ENQUEUE_RECORD,
    INSTALLATION_WORKER_INTAKE_ADMISSION_READ,
    INSTALLATION_WORKER_INTAKE_ADMISSION_RECORD,
    INSTALLATION_WORKER_QUEUE_RESERVATION_READ,
    INSTALLATION_WORKER_QUEUE_RESERVATION_RECORD,
    SUPPORTED_OPERATOR_PERMISSIONS,
    OperatorCredential,
)
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.installation_one_shot_live_enqueue import router
from app.testing import ASGITestClient

ORIGIN = "https://atlas.example"


def _application(
    tmp_path: Path,
    *,
    permissions=None,
    rate_limit: int = 100,
    second: int = 34,
    evidence=None,
    service_installed: bool = True,
    service_enabled: bool = True,
):
    (
        enqueue_service,
        _enqueue_store,
        evidence_reader,
        live,
        _live_status,
        _intake,
        _intake_status,
        _queue,
        _queue_status,
        create,
    ) = _service(
        tmp_path / "service",
        evidence=evidence,
        second=second,
        enabled=service_enabled,
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
            operator_id=live.operator_id,
            password_hash="unused",
            permissions=permissions
            or (
                INSTALLATION_ONE_SHOT_LIVE_ENQUEUE_RECORD,
                INSTALLATION_ONE_SHOT_LIVE_ENQUEUE_READ,
            ),
        )
    )
    if service_installed:
        application.state.one_shot_live_enqueue_service = enqueue_service
    collection = (
        f"/api/v1/installation/candidate-records/{live.candidate_record_id}"
        "/one-shot-live-enqueues"
    )
    return (
        ASGITestClient(application),
        session,
        application,
        live,
        create,
        evidence_reader,
        collection,
        sessions,
    )


def _cookies(session):
    return {"atlas_operator_session": session.session_token}


def _headers(session, key: str = "one-shot-live-enqueue-key-1"):
    return {
        "Origin": ORIGIN,
        "X-Atlas-CSRF-Token": session.csrf_token,
        "Idempotency-Key": key,
    }


def test_auth_permission_csrf_origin_success_and_one_shot_idempotency(
    tmp_path: Path,
) -> None:
    client, session, _, live, create, reader, url, _ = _application(tmp_path)
    payload = create.model_dump(mode="json")
    assert client.get(url).status_code == 401
    assert client.post(url, json=payload, cookies=_cookies(session)).status_code == 403
    assert client.post(
        url,
        json=payload,
        cookies=_cookies(session),
        headers={**_headers(session), "X-Atlas-CSRF-Token": "wrong"},
    ).status_code == 403
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
    assert body["record"]["candidate_record_id"] == live.candidate_record_id
    assert body["record"]["outcome"] == "one_shot_live_enqueue_recorded"
    assert body["record"]["queue_item"]["item_kind"] == "inert_reference_only_queue_item"
    assert body["status"]["lifecycle"] == "active"
    assert body["error"] is None
    for field in (
        "reference_only",
        "one_shot_live_enqueue_recorded",
    ):
        assert body["record"][field] is True
    for field in (
        "payload_constructed",
        "payload_serialized",
        "dequeue_allowed",
        "queue_polling_allowed",
        "worker_contact_allowed",
        "worker_start_allowed",
        "execution_start_allowed",
        "agent_invocation_allowed",
        "workflow_start_allowed",
        "retry_allowed",
        "resend_allowed",
        "installation_allowed",
        "deployment_allowed",
        "rollback_allowed",
    ):
        assert body["record"][field] is False

    listed = client.get(url, cookies=_cookies(session))
    assert listed.status_code == 200
    assert listed.json()["items"][0] == body["record"]
    fetched = client.get(
        f"{url}/{body['record']['enqueue_id']}", cookies=_cookies(session)
    )
    assert fetched.status_code == 200
    assert fetched.json()["record"] == body["record"]
    duplicate = client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["record"] == body["record"]
    assert reader.calls == 1


def test_dedicated_create_and_read_permissions_are_independent(tmp_path: Path) -> None:
    read_client, read_session, _, _, create, _, url, _ = _application(
        tmp_path / "read", permissions=(INSTALLATION_ONE_SHOT_LIVE_ENQUEUE_READ,)
    )
    assert read_client.get(url, cookies=_cookies(read_session)).status_code == 200
    assert read_client.post(
        url,
        json=create.model_dump(mode="json"),
        cookies=_cookies(read_session),
        headers=_headers(read_session),
    ).status_code == 403

    create_client, create_session, _, _, create, _, url, _ = _application(
        tmp_path / "create", permissions=(INSTALLATION_ONE_SHOT_LIVE_ENQUEUE_RECORD,)
    )
    assert create_client.get(url, cookies=_cookies(create_session)).status_code == 403
    assert create_client.post(
        url,
        json=create.model_dump(mode="json"),
        cookies=_cookies(create_session),
        headers=_headers(create_session),
    ).status_code == 201


def test_strict_body_query_method_and_idempotency_validation(tmp_path: Path) -> None:
    client, session, _, _, create, _, url, _ = _application(tmp_path)
    payload = create.model_dump(mode="json")
    cookies, headers = _cookies(session), _headers(session)
    assert client.post(
        url,
        content=b"{}",
        cookies=cookies,
        headers={**headers, "Content-Type": "text/plain"},
    ).status_code == 415
    assert client.post(
        url,
        content=json.dumps(payload).encode(),
        cookies=cookies,
        headers={**headers, "Content-Type": "application/json; charset=utf-8"},
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
        json={**payload, "operator_id": "operator-a"},
        cookies=cookies,
        headers=headers,
    ).status_code == 422
    nested: object = "bottom"
    for _ in range(17):
        nested = {"nested": nested}
    assert client.post(url, json=nested, cookies=cookies, headers=headers).status_code == 422
    assert client.post(
        url,
        content=b" " * (16 * 1024 + 1),
        cookies=cookies,
        headers={**headers, "Content-Type": "application/json"},
    ).status_code == 413
    for invalid_key in (None, "too-short", "contains space here", "x" * 129, "bad\x7f"):
        exact_headers = {
            name: value for name, value in headers.items() if name != "Idempotency-Key"
        }
        if invalid_key is not None:
            exact_headers["Idempotency-Key"] = invalid_key
        assert client.post(
            url, json=payload, cookies=cookies, headers=exact_headers
        ).status_code == 422
    assert client.post(
        url + "?retry=true", json=payload, cookies=cookies, headers=headers
    ).status_code == 422
    assert client.get(url + "?limit=1", cookies=cookies).status_code == 422
    assert client.request("PUT", url).status_code == 405
    assert client.request("POST", f"{url}/4b3beb58-c4b9-5b2b-9995-4f629abefaf4").status_code == 405


def test_default_off_rate_limit_service_unavailable_and_indeterminate_redaction(
    tmp_path: Path,
) -> None:
    client, session, _, _, create, reader, url, _ = _application(
        tmp_path / "limited", rate_limit=1
    )
    payload = create.model_dump(mode="json")
    assert client.post(
        url,
        json=payload,
        cookies=_cookies(session),
        headers=_headers(session, "one-valid-key-123"),
    ).status_code == 201
    limited = client.post(
        url,
        json=payload,
        cookies=_cookies(session),
        headers=_headers(session, "two-valid-key-123"),
    )
    assert limited.status_code == 429
    assert limited.json()["error"]["error_code"] == "rate_limited"
    assert limited.json()["error"]["retryable"] is False
    assert reader.calls == 1

    disabled, disabled_session, _, _, disabled_create, _, disabled_url, _ = (
        _application(tmp_path / "disabled", service_installed=False)
    )
    unavailable = disabled.post(
        disabled_url,
        json=disabled_create.model_dump(mode="json"),
        cookies=_cookies(disabled_session),
        headers=_headers(disabled_session),
    )
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["error_code"] == "internal_error"

    gated, gated_session, _, _, gated_create, gated_reader, gated_url, _ = _application(
        tmp_path / "gated", service_enabled=False
    )
    blocked = gated.post(
        gated_url,
        json=gated_create.model_dump(mode="json"),
        cookies=_cookies(gated_session),
        headers=_headers(gated_session),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["error_code"] == (
        "installation_capability_unsupported"
    )
    assert gated_reader.calls == 0

    indeterminate_client, indeterminate_session, app, _, create, _, url, _ = (
        _application(tmp_path / "indeterminate")
    )

    class IndeterminateService:
        def create(self, *_args, **kwargs):
            from app.installation_one_shot_live_enqueue.service import _failure

            return _failure(
                "append_indeterminate",
                kwargs["correlation_id"],
                outcome="indeterminate",
            )

    app.state.one_shot_live_enqueue_service = IndeterminateService()
    ambiguous = indeterminate_client.post(
        url,
        json=create.model_dump(mode="json"),
        cookies=_cookies(indeterminate_session),
        headers=_headers(indeterminate_session, "indeterminate-key-1"),
    )
    assert ambiguous.status_code == 503
    body = ambiguous.json()
    assert body["outcome"] == "indeterminate"
    assert body["error"]["error_code"] == "append_indeterminate"
    assert body["error"]["retryable"] is False
    rendered = json.dumps(body)
    assert "indeterminate-key-1" not in rendered
    assert "secret" not in rendered
    assert "traceback" not in rendered.lower()


def test_foreign_get_matches_not_found_and_foreign_list_is_empty(tmp_path: Path) -> None:
    client, session, _, live, create, _, url, sessions = _application(tmp_path)
    made = client.post(
        url,
        json=create.model_dump(mode="json"),
        cookies=_cookies(session),
        headers=_headers(session),
    )
    assert made.status_code == 201
    enqueue_id = made.json()["record"]["enqueue_id"]
    foreign = sessions.create(
        OperatorCredential(
            operator_id="operator-b",
            password_hash="unused",
            permissions=(INSTALLATION_ONE_SHOT_LIVE_ENQUEUE_READ,),
        )
    )
    assert client.get(f"{url}/{enqueue_id}", cookies=_cookies(session)).status_code == 200
    foreign_get = client.get(f"{url}/{enqueue_id}", cookies=_cookies(foreign))
    assert foreign_get.status_code == 404
    assert foreign_get.json()["error"]["error_code"] == "not_found"
    listed = client.get(url, cookies=_cookies(foreign))
    assert listed.status_code == 200 and listed.json()["items"] == []
    other_candidate = "bf819229-618a-44f5-a14e-4c0f5878ea14"
    hidden = url.replace(live.candidate_record_id, other_candidate)
    wrong_candidate = client.get(f"{hidden}/{enqueue_id}", cookies=_cookies(session))
    nonexistent = client.get(
        f"{hidden}/4b3beb58-c4b9-5b2b-9995-4f629abefaf4",
        cookies=_cookies(session),
    )
    assert wrong_candidate.status_code == nonexistent.status_code == 404
    assert wrong_candidate.json()["error"] == nonexistent.json()["error"]
    assert client.get(hidden, cookies=_cookies(session)).json()["items"] == []


def test_openapi_is_exact_and_integrated_without_sibling_routes(tmp_path: Path) -> None:
    _, _, application, _, _, _, _, _ = _application(tmp_path)
    paths = application.openapi()["paths"]
    collection = next(path for path in paths if path.endswith("/one-shot-live-enqueues"))
    item = next(
        path for path in paths if path.endswith("/one-shot-live-enqueues/{enqueue_id}")
    )
    assert set(paths[collection]) == {"get", "post"}
    assert set(paths[item]) == {"get"}
    assert set(paths) == {collection, item}
    post = paths[collection]["post"]
    assert post["requestBody"]["required"] is True
    assert set(post["requestBody"]["content"]) == {"application/json"}
    idempotency = next(
        value for value in post["parameters"] if value["name"] == "Idempotency-Key"
    )
    assert idempotency["in"] == "header" and idempotency["required"] is True

    integrated = FastAPI()
    integrated.include_router(api_v1_router)
    integrated_paths = integrated.openapi()["paths"]
    integrated_collection = (
        "/api/v1/installation/candidate-records/{candidate_record_id}"
        "/one-shot-live-enqueues"
    )
    integrated_item = f"{integrated_collection}/{{enqueue_id}}"
    assert set(integrated_paths[integrated_collection]) == {"get", "post"}
    assert set(integrated_paths[integrated_item]) == {"get"}
    one_shot_paths = {
        path: methods
        for path, methods in integrated_paths.items()
        if "one-shot-live-enqueues" in path
    }
    rendered = json.dumps(one_shot_paths).lower()
    for forbidden in (
        "/dequeue",
        "/poll",
        "/claim",
        "/lease",
        "/start",
        "/run",
        "/execute",
        "/dispatch",
        "/retry",
        "/resend",
        "/deploy",
        "/rollback",
    ):
        assert forbidden not in rendered
    prohibited_segments = {
        "dequeue",
        "poll",
        "claim",
        "lease",
        "start",
        "run",
        "execute",
        "dispatch",
        "retry",
        "resend",
        "install",
        "deploy",
        "rollback",
    }
    assert not any(
        segment in prohibited_segments
        for path in one_shot_paths
        for segment in path.strip("/").split("/")
    )


def test_v039_to_v041_permissions_and_routes_remain_unchanged() -> None:
    assert INSTALLATION_WORKER_QUEUE_RESERVATION_RECORD == (
        "installation.execution.worker_queue_reservation.record"
    )
    assert INSTALLATION_WORKER_QUEUE_RESERVATION_READ == (
        "installation.execution.worker_queue_reservation.read"
    )
    assert INSTALLATION_WORKER_INTAKE_ADMISSION_RECORD == (
        "installation.execution.worker_intake_admission.record"
    )
    assert INSTALLATION_WORKER_INTAKE_ADMISSION_READ == (
        "installation.execution.worker_intake_admission.read"
    )
    assert INSTALLATION_LIVE_ENQUEUE_ADMISSION_RECORD == (
        "installation.execution.live_enqueue_admission.record"
    )
    assert INSTALLATION_LIVE_ENQUEUE_ADMISSION_READ == (
        "installation.execution.live_enqueue_admission.read"
    )
    assert INSTALLATION_ONE_SHOT_LIVE_ENQUEUE_RECORD == (
        "installation.execution.one_shot_live_enqueue.record"
    )
    assert INSTALLATION_ONE_SHOT_LIVE_ENQUEUE_READ == (
        "installation.execution.one_shot_live_enqueue.read"
    )
    assert {
        INSTALLATION_WORKER_QUEUE_RESERVATION_RECORD,
        INSTALLATION_WORKER_QUEUE_RESERVATION_READ,
        INSTALLATION_WORKER_INTAKE_ADMISSION_RECORD,
        INSTALLATION_WORKER_INTAKE_ADMISSION_READ,
        INSTALLATION_LIVE_ENQUEUE_ADMISSION_RECORD,
        INSTALLATION_LIVE_ENQUEUE_ADMISSION_READ,
        INSTALLATION_ONE_SHOT_LIVE_ENQUEUE_RECORD,
        INSTALLATION_ONE_SHOT_LIVE_ENQUEUE_READ,
    } <= SUPPORTED_OPERATOR_PERMISSIONS
    app = FastAPI()
    app.include_router(api_v1_router)
    paths = app.openapi()["paths"]
    assert (
        "/api/v1/installation/candidate-records/{candidate_record_id}"
        "/worker-queue-reservations"
    ) in paths
    assert (
        "/api/v1/installation/candidate-records/{candidate_record_id}"
        "/worker-intake-admissions"
    ) in paths
    assert (
        "/api/v1/installation/candidate-records/{candidate_record_id}"
        "/live-enqueue-admissions"
    ) in paths


def test_route_has_no_runtime_effect_dependencies_or_sibling_effect_routes() -> None:
    path = Path(__file__).with_name("installation_one_shot_live_enqueue.py")
    source = path.read_text()
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert not any(
        marker in imported
        for imported in imports
        for marker in (
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
        )
    )
    for forbidden in (
        "send(",
        "publish(",
        "dequeue(",
        "poll(",
        "claim(",
        "lease(",
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
