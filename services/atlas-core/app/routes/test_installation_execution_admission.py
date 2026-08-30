"""P3 API locks for v0.36 installation execution admission evidence."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from fastapi import FastAPI

from app.installation_execution_admission.test_contract import ADMISSION_ID, _grant
from app.installation_execution_admission.test_service_store import (
    _create,
    _service,
)
from app.operator_auth.models import (
    INSTALLATION_EXECUTION_ADMISSION_READ,
    INSTALLATION_EXECUTION_ADMISSION_RECORD,
    OperatorCredential,
)
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.installation_execution_admission import router
from app.testing import ASGITestClient

ORIGIN = "https://atlas.example"


def _application(
    tmp_path: Path,
    *,
    permissions=None,
    rate_limit: int = 100,
    second: int = 30,
    evidence=None,
    service_enabled: bool = True,
):
    admission_service, _, reader, factory, grant, status = _service(
        tmp_path / "service", evidence=evidence, second=second
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
                INSTALLATION_EXECUTION_ADMISSION_RECORD,
                INSTALLATION_EXECUTION_ADMISSION_READ,
            ),
        )
    )
    if service_enabled:
        application.state.installation_execution_admission_service = (
            admission_service
        )
    collection = (
        f"/api/v1/installation/candidate-records/{grant.candidate_record_id}"
        "/execution-admissions"
    )
    return (
        ASGITestClient(application), session, application, grant, status,
        reader, factory, collection, sessions,
    )


def _cookies(session):
    return {"atlas_operator_session": session.session_token}


def _headers(session, key: str = "admission-key-1"):
    return {
        "Origin": ORIGIN,
        "X-Atlas-CSRF-Token": session.csrf_token,
        "Idempotency-Key": key,
    }


def test_auth_permission_csrf_origin_rate_limit_and_success(tmp_path: Path) -> None:
    client, session, _, grant, _, reader, factory, url, _ = _application(tmp_path)
    payload = _create(grant).model_dump(mode="json")
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
    assert body["admission"]["readiness"] == "admission_gated"
    assert body["status"]["lifecycle"] == "active"
    assert not body["admission"]["runner_binding_allowed"]
    assert not body["admission"]["execution_start_allowed"]
    listed = client.get(url, cookies=_cookies(session))
    assert listed.status_code == 200
    assert listed.json()["admissions"][0]["admission"] == body["admission"]
    fetched = client.get(f"{url}/{ADMISSION_ID}", cookies=_cookies(session))
    assert fetched.status_code == 200
    assert fetched.json()["admission"] == body["admission"]
    duplicate = client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["admission"] == body["admission"]
    assert reader.calls == 1 and factory.calls == 1


def test_dedicated_create_and_read_permissions_are_independent(tmp_path: Path) -> None:
    read_client, read_session, _, grant, _, _, _, url, _ = _application(
        tmp_path / "read", permissions=(INSTALLATION_EXECUTION_ADMISSION_READ,)
    )
    assert read_client.get(url, cookies=_cookies(read_session)).status_code == 200
    assert read_client.post(
        url,
        json=_create(grant).model_dump(mode="json"),
        cookies=_cookies(read_session),
        headers=_headers(read_session),
    ).status_code == 403
    create_client, create_session, _, grant, _, _, _, url, _ = _application(
        tmp_path / "create", permissions=(INSTALLATION_EXECUTION_ADMISSION_RECORD,)
    )
    assert create_client.get(url, cookies=_cookies(create_session)).status_code == 403
    assert create_client.post(
        url,
        json=_create(grant).model_dump(mode="json"),
        cookies=_cookies(create_session),
        headers=_headers(create_session),
    ).status_code == 201


def test_strict_body_query_method_and_idempotency_validation(tmp_path: Path) -> None:
    client, session, _, grant, _, _, _, url, _ = _application(tmp_path)
    payload = _create(grant).model_dump(mode="json")
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
        json={**payload, "operator_id": "operator-a"},
        cookies=cookies,
        headers=headers,
    ).status_code == 422
    nested: object = "bottom"
    for _ in range(6):
        nested = {"nested": nested}
    assert client.post(
        url, json=nested, cookies=cookies, headers=headers
    ).status_code == 422
    assert client.post(
        url,
        content=b" " * 8193,
        cookies=cookies,
        headers={**headers, "Content-Type": "application/json"},
    ).status_code == 413
    for invalid_key in (None, "contains space", "x" * 129, "bad\x7f"):
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
    assert client.request("POST", f"{url}/{ADMISSION_ID}").status_code == 405


def test_rate_limit_and_default_disabled_fail_closed(tmp_path: Path) -> None:
    client, session, _, grant, _, reader, _, url, _ = _application(
        tmp_path / "limited", rate_limit=1
    )
    payload = _create(grant).model_dump(mode="json")
    assert client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session, "one")
    ).status_code == 201
    limited = client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session, "two")
    )
    assert limited.status_code == 429 and limited.json()["error"]["redacted"]
    assert reader.calls == 1

    disabled, disabled_session, _, disabled_grant, _, _, _, disabled_url, _ = (
        _application(tmp_path / "disabled", service_enabled=False)
    )
    unavailable = disabled.post(
        disabled_url,
        json=_create(disabled_grant).model_dump(mode="json"),
        cookies=_cookies(disabled_session),
        headers=_headers(disabled_session),
    )
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["error_code"] == "unavailable"


def test_stale_mismatch_and_home_assistant_are_redacted(tmp_path: Path) -> None:
    stale_client, stale_session, _, grant, _, _, _, stale_url, _ = _application(
        tmp_path / "stale", second=61
    )
    stale = stale_client.post(
        stale_url,
        json=_create(grant).model_dump(mode="json"),
        cookies=_cookies(stale_session),
        headers=_headers(stale_session),
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["error_code"] == "expired"

    client, session, _, grant, _, _, _, url, _ = _application(tmp_path / "mismatch")
    payload = _create(grant).model_dump(mode="json")
    payload["permission_grant_fingerprint"] = {
        **payload["permission_grant_fingerprint"], "value": "f" * 64
    }
    mismatch = client.post(
        url,
        json=payload,
        cookies=_cookies(session),
        headers=_headers(session, "mismatch"),
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["redacted"]
    assert "fingerprint" not in mismatch.json()["error"]["safe_message"].lower()

    home_grant, home_status = _grant(tmp_path / "home-evidence")
    home_client, home_session, _, _, _, _, _, home_url, _ = _application(
        tmp_path / "home", evidence=(home_grant, home_status, True)
    )
    blocked = home_client.post(
        home_url,
        json=_create(home_grant).model_dump(mode="json"),
        cookies=_cookies(home_session),
        headers=_headers(home_session),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["blocker_codes"] == [
        "installation_capability_unsupported"
    ]


def test_foreign_get_is_not_found_and_foreign_list_is_empty(tmp_path: Path) -> None:
    client, session, _, grant, _, _, _, url, sessions = _application(tmp_path)
    assert client.post(
        url,
        json=_create(grant).model_dump(mode="json"),
        cookies=_cookies(session),
        headers=_headers(session),
    ).status_code == 201
    foreign = sessions.create(
        OperatorCredential(
            operator_id="operator-b",
            password_hash="unused",
            permissions=(INSTALLATION_EXECUTION_ADMISSION_READ,),
        )
    )
    assert client.get(
        f"{url}/{ADMISSION_ID}", cookies=_cookies(foreign)
    ).status_code == 404
    listed = client.get(url, cookies=_cookies(foreign))
    assert listed.status_code == 200 and listed.json()["admissions"] == []
    other_candidate = "bf819229-618a-44f5-a14e-4c0f5878ea14"
    hidden = url.replace(grant.candidate_record_id, other_candidate)
    assert client.get(
        f"{hidden}/{ADMISSION_ID}", cookies=_cookies(session)
    ).status_code == 404
    assert client.get(hidden, cookies=_cookies(session)).json()["admissions"] == []


def test_openapi_is_exact_and_has_no_effect_siblings(tmp_path: Path) -> None:
    _, _, application, _, _, _, _, _, _ = _application(tmp_path)
    paths = application.openapi()["paths"]
    collection = next(path for path in paths if path.endswith("/execution-admissions"))
    item = next(
        path for path in paths if path.endswith("/execution-admissions/{admission_id}")
    )
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
        "/runner", "/execute", "/start", "/dispatch", "/retry", "/resend",
        "/deploy", "/rollback", "/agent", "/workflow", "/worker", "/mutation",
    ):
        assert forbidden not in rendered


def test_route_has_no_execution_or_runtime_consumers() -> None:
    path = Path(__file__).with_name("installation_execution_admission.py")
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
            "operational_dispatch", "execution_candidates", "atlas_agent",
            "provider", "repository", "workflow", "worker", "docker", "subprocess",
        )
    )
