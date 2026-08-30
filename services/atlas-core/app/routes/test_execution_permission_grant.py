"""P3 API locks for v0.35 execution-permission evidence."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from fastapi import FastAPI

from app.execution_permission_grant.contract import CONFIRMATION_TEXT
from app.execution_permission_grant.test_service_store import (
    GRANT_ID,
    _create,
    _response,
    _service,
)
from app.operator_auth.models import (
    INSTALLATION_EXECUTION_PERMISSION_GRANT,
    INSTALLATION_EXECUTION_PERMISSION_GRANT_READ,
    OperatorCredential,
)
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.execution_permission_grant import router
from app.testing import ASGITestClient

ORIGIN = "https://atlas.example"


def _application(
    tmp_path: Path,
    *,
    permissions=None,
    rate_limit: int = 100,
    second: int = 20,
    readiness_response=None,
):
    grant_service, _, reader, factory, response = _service(
        tmp_path / "service", response=readiness_response, second=second
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
            operator_id="operator-a",
            password_hash="unused",
            permissions=permissions
            or (
                INSTALLATION_EXECUTION_PERMISSION_GRANT,
                INSTALLATION_EXECUTION_PERMISSION_GRANT_READ,
            ),
        )
    )
    application.state.execution_permission_grant_service = grant_service
    candidate = response.review.candidate_record_id
    collection = (
        f"/api/v1/installation/candidate-records/{candidate}"
        "/execution-permission-grants"
    )
    return (
        ASGITestClient(application), session, application, response,
        reader, factory, collection, sessions,
    )


def _cookies(session):
    return {"atlas_operator_session": session.session_token}


def _headers(session, key: str = "permission-key-1"):
    return {
        "Origin": ORIGIN,
        "X-Atlas-CSRF-Token": session.csrf_token,
        "Idempotency-Key": key,
    }


def test_auth_permission_csrf_origin_rate_limit_and_success(tmp_path: Path) -> None:
    client, session, _, readiness, reader, factory, url, _ = _application(tmp_path)
    payload = _create(readiness).model_dump(mode="json")
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
    assert body["disposition"] == "recorded"
    assert body["grant"]["confirmation_text"] == CONFIRMATION_TEXT
    assert body["status"]["lifecycle"] == "active"
    assert not any(
        body[field]
        for field in (
            "execution_authorized", "installation_allowed", "dispatch_allowed",
            "agent_invocation_allowed", "worker_allowed", "workflow_allowed",
            "provider_mutation_allowed", "repository_mutation_allowed",
            "in_guest_mutation_allowed", "deployment_allowed", "rollback_allowed",
            "retry_allowed", "resend_allowed", "replay_allowed",
        )
    )
    listed = client.get(url, cookies=_cookies(session))
    assert listed.status_code == 200
    assert listed.json()["grants"][0]["grant"] == body["grant"]
    fetched = client.get(f"{url}/{GRANT_ID}", cookies=_cookies(session))
    assert fetched.status_code == 200
    assert fetched.json()["grant"] == body["grant"]
    duplicate = client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["grant"] == body["grant"]
    assert reader.calls == 1 and factory.calls == 1


def test_dedicated_create_and_owned_read_permissions_are_independent(tmp_path: Path) -> None:
    read_client, read_session, _, readiness, _, _, url, _ = _application(
        tmp_path / "read", permissions=(INSTALLATION_EXECUTION_PERMISSION_GRANT_READ,)
    )
    assert read_client.get(url, cookies=_cookies(read_session)).status_code == 200
    assert read_client.post(
        url,
        json=_create(readiness).model_dump(mode="json"),
        cookies=_cookies(read_session),
        headers=_headers(read_session),
    ).status_code == 403
    create_client, create_session, _, readiness, _, _, url, _ = _application(
        tmp_path / "create", permissions=(INSTALLATION_EXECUTION_PERMISSION_GRANT,)
    )
    assert create_client.get(url, cookies=_cookies(create_session)).status_code == 403
    assert create_client.post(
        url,
        json=_create(readiness).model_dump(mode="json"),
        cookies=_cookies(create_session),
        headers=_headers(create_session),
    ).status_code == 201


def test_strict_body_query_method_and_idempotency_validation(tmp_path: Path) -> None:
    client, session, _, readiness, _, _, url, _ = _application(tmp_path)
    payload = _create(readiness).model_dump(mode="json")
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
        url, json={**payload, "operator_id": "operator-a"},
        cookies=cookies, headers=headers,
    ).status_code == 422
    nested: object = "bottom"
    for _ in range(6):
        nested = {"nested": nested}
    assert client.post(url, json=nested, cookies=cookies, headers=headers).status_code == 422
    assert client.post(
        url,
        content=b" " * 8193,
        cookies=cookies,
        headers={**headers, "Content-Type": "application/json"},
    ).status_code == 413
    for invalid_key in (None, "contains space", "x" * 129):
        exact_headers = {
            name: value
            for name, value in headers.items()
            if name != "Idempotency-Key"
        }
        if invalid_key is not None:
            exact_headers["Idempotency-Key"] = invalid_key
        assert client.post(
            url, json=payload, cookies=cookies, headers=exact_headers
        ).status_code == 422
    assert client.post(url + "?retry=true", json=payload, cookies=cookies, headers=headers).status_code == 422
    assert client.get(url + "?limit=1", cookies=cookies).status_code == 422
    assert client.request("PUT", url).status_code == 405
    assert client.request("POST", f"{url}/{GRANT_ID}").status_code == 405


def test_rate_limit_is_applied_before_service(tmp_path: Path) -> None:
    client, session, _, readiness, reader, _, url, _ = _application(
        tmp_path, rate_limit=1
    )
    payload = _create(readiness).model_dump(mode="json")
    assert client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session, "one")
    ).status_code == 201
    limited = client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session, "two")
    )
    assert limited.status_code == 429
    assert limited.json()["error"]["redacted"]
    assert reader.calls == 1


def test_confirmation_stale_mismatch_and_blocked_are_redacted(tmp_path: Path) -> None:
    client, session, _, readiness, _, _, url, _ = _application(tmp_path / "exact")
    payload = _create(readiness).model_dump(mode="json")
    assert client.post(
        url,
        json={**payload, "confirmation_text": "I approve execution."},
        cookies=_cookies(session), headers=_headers(session),
    ).status_code == 422

    stale_client, stale_session, _, stale_readiness, _, _, stale_url, _ = _application(
        tmp_path / "stale", second=47
    )
    stale = stale_client.post(
        stale_url,
        json=_create(stale_readiness).model_dump(mode="json"),
        cookies=_cookies(stale_session), headers=_headers(stale_session),
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["error_code"] == "expired"

    mismatch = payload.copy()
    mismatch["readiness_review_fingerprint"] = {
        **mismatch["readiness_review_fingerprint"], "value": "f" * 64,
    }
    mismatched = client.post(
        url, json=mismatch, cookies=_cookies(session), headers=_headers(session, "mismatch")
    )
    assert mismatched.status_code == 404
    assert "fingerprint" not in mismatched.json()["error"]["safe_message"].lower()

    blocked_response = _response(
        tmp_path / "blocked-evidence",
        home_assistant=True,
        installation_capability_supported=False,
    )
    blocked_client, blocked_session, _, _, _, _, blocked_url, _ = _application(
        tmp_path / "blocked", readiness_response=blocked_response
    )
    blocked = blocked_client.post(
        blocked_url,
        json=_create(blocked_response).model_dump(mode="json"),
        cookies=_cookies(blocked_session), headers=_headers(blocked_session),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["error_code"] == "not_readiness_gated"


def test_foreign_get_is_not_found_and_foreign_list_is_empty(tmp_path: Path) -> None:
    client, session, _, readiness, _, _, url, sessions = _application(tmp_path)
    made = client.post(
        url,
        json=_create(readiness).model_dump(mode="json"),
        cookies=_cookies(session), headers=_headers(session),
    )
    assert made.status_code == 201
    foreign = sessions.create(
        OperatorCredential(
            operator_id="operator-b",
            password_hash="unused",
            permissions=(INSTALLATION_EXECUTION_PERMISSION_GRANT_READ,),
        )
    )
    assert client.get(f"{url}/{GRANT_ID}", cookies=_cookies(foreign)).status_code == 404
    listed = client.get(url, cookies=_cookies(foreign))
    assert listed.status_code == 200 and listed.json()["grants"] == []
    other_candidate = "bf819229-618a-44f5-a14e-4c0f5878ea14"
    hidden = url.replace(readiness.review.candidate_record_id, other_candidate)
    assert client.get(f"{hidden}/{GRANT_ID}", cookies=_cookies(session)).status_code == 404
    assert client.get(hidden, cookies=_cookies(session)).json()["grants"] == []


def test_openapi_is_closed_and_has_no_effect_siblings(tmp_path: Path) -> None:
    _, _, application, _, _, _, _, _ = _application(tmp_path)
    paths = application.openapi()["paths"]
    collection = next(path for path in paths if path.endswith("/execution-permission-grants"))
    item = next(path for path in paths if path.endswith("/execution-permission-grants/{grant_id}"))
    assert set(paths[collection]) == {"get", "post"}
    assert set(paths[item]) == {"get"}
    assert set(paths) == {collection, item}
    post = paths[collection]["post"]
    assert post["requestBody"]["required"] is True
    idempotency = next(
        value for value in post["parameters"] if value["name"] == "Idempotency-Key"
    )
    assert idempotency["in"] == "header" and idempotency["required"] is True
    rendered = json.dumps(paths).lower()
    for forbidden in (
        "/execute", "/dispatch", "/retry", "/resend", "/deploy",
        "/rollback", "/agent", "/workflow", "/worker", "/mutation",
    ):
        assert forbidden not in rendered


def test_route_has_no_execution_or_runtime_consumers() -> None:
    path = Path(__file__).with_name("execution_permission_grant.py")
    tree = ast.parse(path.read_text())
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
            "operational_dispatch", "execution_candidates", "atlas_agent", "provider",
            "repository", "workflow", "worker", "docker", "subprocess",
        )
    )
