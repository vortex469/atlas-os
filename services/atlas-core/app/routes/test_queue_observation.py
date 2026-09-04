"""P3 API locks for v0.43 queue observation evidence."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.operator_auth.models import (
    INSTALLATION_ONE_SHOT_LIVE_ENQUEUE_READ,
    INSTALLATION_ONE_SHOT_LIVE_ENQUEUE_RECORD,
    INSTALLATION_QUEUE_OBSERVATION_READ,
    INSTALLATION_QUEUE_OBSERVATION_RECORD,
    SUPPORTED_OPERATOR_PERMISSIONS,
    OperatorCredential,
)
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.queue_observation_receipt.test_service_store import _service
from app.routes.queue_observation import router
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
    observation_service, _store, reader, enqueue, _status, create = _service(
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
            operator_id=enqueue.operator_id,
            password_hash="unused",
            permissions=permissions
            or (
                INSTALLATION_QUEUE_OBSERVATION_RECORD,
                INSTALLATION_QUEUE_OBSERVATION_READ,
            ),
        )
    )
    if service_installed:
        application.state.queue_observation_receipt_service = observation_service
    collection = (
        f"/api/v1/installation/candidate-records/{enqueue.candidate_record_id}"
        "/queue-observations"
    )
    return (
        ASGITestClient(application),
        session,
        application,
        enqueue,
        create,
        reader,
        collection,
        sessions,
    )


def _cookies(session):
    return {"atlas_operator_session": session.session_token}


def _headers(session, key: str = "queue-observation-route-key-1"):
    return {
        "Origin": ORIGIN,
        "X-Atlas-CSRF-Token": session.csrf_token,
        "Idempotency-Key": key,
    }


def test_auth_permission_csrf_origin_success_readback_and_idempotency(
    tmp_path: Path,
) -> None:
    client, session, _, enqueue, create, reader, url, _ = _application(tmp_path)
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
    assert body["queue_observation_recorded"] is True
    assert body["record"]["candidate_record_id"] == enqueue.candidate_record_id
    assert body["record"]["queue_observation"]["observation_state"] == (
        "observed_recorded_not_consumable"
    )
    assert body["record"]["v042_enqueue"]["enqueue_id"] == enqueue.enqueue_id
    assert body["status"]["lifecycle"] == "active"
    assert body["error"] is None
    for field in (
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
        f"{url}/{body['record']['receipt_id']}", cookies=_cookies(session)
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
        tmp_path / "read", permissions=(INSTALLATION_QUEUE_OBSERVATION_READ,)
    )
    assert read_client.get(url, cookies=_cookies(read_session)).status_code == 200
    assert read_client.post(
        url,
        json=create.model_dump(mode="json"),
        cookies=_cookies(read_session),
        headers=_headers(read_session),
    ).status_code == 403

    create_client, create_session, _, _, create, _, url, _ = _application(
        tmp_path / "create", permissions=(INSTALLATION_QUEUE_OBSERVATION_RECORD,)
    )
    assert create_client.get(url, cookies=_cookies(create_session)).status_code == 403
    assert create_client.post(
        url,
        json=create.model_dump(mode="json"),
        cookies=_cookies(create_session),
        headers=_headers(create_session),
    ).status_code == 201


def test_strict_body_query_method_rate_and_idempotency_bounds(tmp_path: Path) -> None:
    client, session, _, _, create, _, url, _ = _application(tmp_path)
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
        json={**payload, "command": "sh -c whoami"},
        cookies=cookies,
        headers=headers,
    ).status_code == 422
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
        url + "?poll=true", json=payload, cookies=cookies, headers=headers
    ).status_code == 422
    assert client.get(url + "?limit=1", cookies=cookies).status_code == 422
    assert client.post(
        url,
        json=payload,
        cookies=cookies,
        headers=_headers(session, "queue-observation-rate-key"),
    ).status_code == 201
    limited_client, limited_session, _, _, limited_create, _, limited_url, _ = (
        _application(tmp_path / "limited", rate_limit=1)
    )
    limited = limited_client.post(
        limited_url,
        json=limited_create.model_dump(mode="json"),
        cookies=_cookies(limited_session),
        headers=_headers(limited_session, "queue-observation-rate-key"),
    )
    assert limited.status_code == 201
    limited = limited_client.post(
        limited_url,
        json=limited_create.model_dump(mode="json"),
        cookies=_cookies(limited_session),
        headers=_headers(limited_session, "queue-observation-next-key"),
    )
    assert limited.status_code == 429
    assert limited.json()["error"]["error_code"] == "rate_limited"
    assert client.request("PUT", url).status_code == 405
    assert client.request(
        "POST", f"{url}/4b3beb58-c4b9-5b2b-9995-4f629abefaf4"
    ).status_code == 405


def test_default_off_malformed_stale_mismatch_redaction_and_foreign_read(
    tmp_path: Path,
) -> None:
    disabled, disabled_session, _, _, disabled_create, disabled_reader, disabled_url, _ = (
        _application(tmp_path / "disabled", service_enabled=False)
    )
    blocked = disabled.post(
        disabled_url,
        json=disabled_create.model_dump(mode="json"),
        cookies=_cookies(disabled_session),
        headers=_headers(disabled_session),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["error_code"] == "installation_capability_unsupported"
    assert disabled_reader.calls == 0

    missing_client, missing_session, _, _, missing_create, _, missing_url, _ = (
        _application(tmp_path / "missing", service_installed=False)
    )
    unavailable = missing_client.post(
        missing_url,
        json=missing_create.model_dump(mode="json"),
        cookies=_cookies(missing_session),
        headers=_headers(missing_session),
    )
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["error_code"] == "internal_error"

    stale, stale_session, _, _, stale_create, _, stale_url, _ = _application(
        tmp_path / "stale", second=80
    )
    stale_response = stale.post(
        stale_url,
        json=stale_create.model_dump(mode="json"),
        cookies=_cookies(stale_session),
        headers=_headers(stale_session),
    )
    assert stale_response.status_code == 409
    assert stale_response.json()["error"]["error_code"] == "evidence_stale"

    client, session, _, enqueue, create, _, url, sessions = _application(
        tmp_path / "mismatch"
    )
    bad = create.model_dump(mode="json")
    bad["queue_item_reference_fingerprint"]["value"] = "f" * 64
    mismatch = client.post(
        url, json=bad, cookies=_cookies(session), headers=_headers(session)
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["error_code"] == "queue_identity_mismatch"
    rendered = json.dumps(mismatch.json()).lower()
    assert "queue-observation-route-key-1" not in rendered
    assert "traceback" not in rendered
    assert "sh -c" not in rendered

    made = client.post(
        url,
        json=create.model_dump(mode="json"),
        cookies=_cookies(session),
        headers=_headers(session, "queue-observation-read-key"),
    )
    assert made.status_code == 201
    observation_id = made.json()["record"]["receipt_id"]
    foreign = sessions.create(
        OperatorCredential(
            operator_id="operator-b",
            password_hash="unused",
            permissions=(INSTALLATION_QUEUE_OBSERVATION_READ,),
        )
    )
    assert client.get(f"{url}/{observation_id}", cookies=_cookies(session)).status_code == 200
    foreign_get = client.get(f"{url}/{observation_id}", cookies=_cookies(foreign))
    assert foreign_get.status_code == 404
    assert foreign_get.json()["error"]["error_code"] == "not_found"
    assert client.get(url, cookies=_cookies(foreign)).json()["items"] == []
    hidden = url.replace(enqueue.candidate_record_id, "bf819229-618a-44f5-a14e-4c0f5878ea14")
    assert client.get(f"{hidden}/{observation_id}", cookies=_cookies(session)).status_code == 404


def test_permissions_openapi_and_no_sibling_effect_routes() -> None:
    assert INSTALLATION_QUEUE_OBSERVATION_RECORD == (
        "installation.execution.queue_observation.record"
    )
    assert INSTALLATION_QUEUE_OBSERVATION_READ == (
        "installation.execution.queue_observation.read"
    )
    assert {
        INSTALLATION_ONE_SHOT_LIVE_ENQUEUE_RECORD,
        INSTALLATION_ONE_SHOT_LIVE_ENQUEUE_READ,
        INSTALLATION_QUEUE_OBSERVATION_RECORD,
        INSTALLATION_QUEUE_OBSERVATION_READ,
    } <= SUPPORTED_OPERATOR_PERMISSIONS

    application = FastAPI()
    application.include_router(api_v1_router)
    paths = application.openapi()["paths"]
    collection = (
        "/api/v1/installation/candidate-records/{candidate_record_id}"
        "/queue-observations"
    )
    item = f"{collection}/{{observation_id}}"
    assert set(paths[collection]) == {"get", "post"}
    assert set(paths[item]) == {"get"}
    post = paths[collection]["post"]
    assert post["requestBody"]["required"] is True
    assert set(post["requestBody"]["content"]) == {"application/json"}
    idempotency = next(
        value for value in post["parameters"] if value["name"] == "Idempotency-Key"
    )
    assert idempotency["in"] == "header" and idempotency["required"] is True
    observation_paths = {
        path: methods for path, methods in paths.items() if "queue-observations" in path
    }
    prohibited_segments = {
        "dequeue",
        "poll",
        "claim",
        "lease",
        "ack",
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
        for path in observation_paths
        for segment in path.split("queue-observations", 1)[1].strip("/").split("/")
        if segment
    )


def test_route_has_no_runtime_effect_dependencies_or_authority_calls() -> None:
    path = Path(__file__).with_name("queue_observation.py")
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
            "docker",
            "podman",
            "socket",
        )
    )
    for forbidden in (
        "send(",
        "publish(",
        "dequeue(",
        "poll(",
        "claim(",
        "lease(",
        "ack(",
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


def test_production_startup_does_not_construct_queue_observation_service() -> None:
    source = Path(__file__).parents[1].joinpath("main.py").read_text()
    assert "queue_observation_service" not in source
    assert "queue_observation_receipt_service" not in source
    assert "create_queue_observation_receipt_service" not in source
