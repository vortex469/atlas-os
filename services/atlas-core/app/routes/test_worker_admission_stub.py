"""P3 API locks for v0.38 worker-admission stub evidence."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from fastapi import FastAPI

from app.operator_auth.models import (
    INSTALLATION_WORKER_ADMISSION_STUB_READ,
    INSTALLATION_WORKER_ADMISSION_STUB_RECORD,
    OperatorCredential,
)
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.worker_admission_stub import router
from app.testing import ASGITestClient
from app.worker_admission_stub.test_contract import STUB_ID
from app.worker_admission_stub.test_service_store import _create, _service

ORIGIN = "https://atlas.example"


def _application(
    tmp_path: Path,
    *,
    permissions=None,
    rate_limit: int = 100,
    second: int = 33,
    evidence=None,
    worker=None,
    service_enabled: bool = True,
):
    (
        stub_service,
        _,
        evidence_reader,
        worker_reader,
        stub_factory,
        intent_factory,
        plan,
        status,
        reference,
    ) = _service(
        tmp_path / "service",
        evidence=evidence,
        worker=worker,
        second=second,
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
                INSTALLATION_WORKER_ADMISSION_STUB_RECORD,
                INSTALLATION_WORKER_ADMISSION_STUB_READ,
            ),
        )
    )
    if service_enabled:
        application.state.worker_admission_stub_service = stub_service
    collection = (
        f"/api/v1/installation/candidate-records/{plan.candidate_record_id}"
        "/worker-admission-stubs"
    )
    return (
        ASGITestClient(application),
        session,
        application,
        plan,
        status,
        reference,
        evidence_reader,
        worker_reader,
        stub_factory,
        intent_factory,
        collection,
        sessions,
    )


def _cookies(session):
    return {"atlas_operator_session": session.session_token}


def _headers(session, key: str = "worker-admission-stub-key-1"):
    return {
        "Origin": ORIGIN,
        "X-Atlas-CSRF-Token": session.csrf_token,
        "Idempotency-Key": key,
    }


def test_auth_permission_csrf_origin_rate_limit_and_success(tmp_path: Path) -> None:
    (
        client, session, _, plan, _, reference, evidence_reader, worker_reader,
        stub_factory, intent_factory, url, _,
    ) = _application(tmp_path)
    payload = _create(plan, reference).model_dump(mode="json")
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
    assert body["stub"]["eligibility"] == "worker_admission_stubbed"
    assert body["status"]["lifecycle"] == "active"
    assert body["stub"]["evidence_only"]
    assert not body["stub"]["worker_started"]
    assert not body["stub"]["work_enqueued"]
    assert client.get(url, cookies=_cookies(session)).json()["stubs"][0]["stub"] == body["stub"]
    assert client.get(f"{url}/{STUB_ID}", cookies=_cookies(session)).json()["stub"] == body["stub"]
    duplicate = client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    assert duplicate.status_code == 200
    assert evidence_reader.calls == worker_reader.calls == 1
    assert stub_factory.calls == intent_factory.calls == 1

    values = _application(tmp_path / "limited", rate_limit=1)
    limited, limited_session, _, limited_plan, _, limited_worker, *tail = values
    limited_url = tail[-2]
    limited_payload = _create(limited_plan, limited_worker).model_dump(mode="json")
    assert limited.post(
        limited_url,
        json=limited_payload,
        cookies=_cookies(limited_session),
        headers=_headers(limited_session, "worker-admission-key-one"),
    ).status_code == 201
    rate_limited = limited.post(
        limited_url,
        json=limited_payload,
        cookies=_cookies(limited_session),
        headers=_headers(limited_session, "worker-admission-key-two"),
    )
    assert rate_limited.status_code == 429
    assert rate_limited.json()["error"]["redacted"]


def test_create_and_read_permissions_are_independent(tmp_path: Path) -> None:
    values = _application(
        tmp_path / "read", permissions=(INSTALLATION_WORKER_ADMISSION_STUB_READ,)
    )
    client, session, _, plan, _, worker, *_, url, _ = values
    assert client.get(url, cookies=_cookies(session)).status_code == 200
    assert client.post(
        url,
        json=_create(plan, worker).model_dump(mode="json"),
        cookies=_cookies(session),
        headers=_headers(session),
    ).status_code == 403
    values = _application(
        tmp_path / "record",
        permissions=(INSTALLATION_WORKER_ADMISSION_STUB_RECORD,),
    )
    client, session, _, plan, _, worker, *_, url, _ = values
    assert client.get(url, cookies=_cookies(session)).status_code == 403
    assert client.post(
        url,
        json=_create(plan, worker).model_dump(mode="json"),
        cookies=_cookies(session),
        headers=_headers(session),
    ).status_code == 201


def test_closed_body_query_method_nesting_and_idempotency(tmp_path: Path) -> None:
    client, session, _, plan, _, worker, *_, url, _ = _application(tmp_path)
    payload = _create(plan, worker).model_dump(mode="json")
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
    for _ in range(17):
        nested = {"nested": nested}
    assert client.post(url, json=nested, cookies=cookies, headers=headers).status_code == 422
    assert client.post(
        url,
        content=b" " * (16 * 1024 + 1),
        cookies=cookies,
        headers={**headers, "Content-Type": "application/json"},
    ).status_code == 413
    for invalid_key in (None, "short", "contains space key", "x" * 129, "bad\x7f-key-value"):
        exact = {name: value for name, value in headers.items() if name != "Idempotency-Key"}
        if invalid_key is not None:
            exact["Idempotency-Key"] = invalid_key
        assert client.post(url, json=payload, cookies=cookies, headers=exact).status_code == 422
    assert client.post(url + "?queue=true", json=payload, cookies=cookies, headers=headers).status_code == 422
    assert client.get(url + "?limit=1", cookies=cookies).status_code == 422
    assert client.request("PUT", url).status_code == 405
    assert client.request("POST", f"{url}/{STUB_ID}").status_code == 405


def test_disabled_stale_mismatch_limits_and_home_assistant_are_redacted(tmp_path: Path) -> None:
    values = _application(tmp_path / "disabled", service_enabled=False)
    client, session, _, plan, _, worker, *_, url, _ = values
    result = client.post(
        url,
        json=_create(plan, worker).model_dump(mode="json"),
        cookies=_cookies(session),
        headers=_headers(session),
    )
    assert result.status_code == 503 and result.json()["error"]["redacted"]

    values = _application(tmp_path / "stale", second=50)
    client, session, _, plan, _, worker, *_, url, _ = values
    assert client.post(
        url,
        json=_create(plan, worker).model_dump(mode="json"),
        cookies=_cookies(session),
        headers=_headers(session),
    ).status_code == 409

    values = _application(tmp_path / "mismatch")
    client, session, _, plan, _, worker, *_, url, _ = values
    payload = _create(plan, worker).model_dump(mode="json")
    payload["worker_reference_fingerprint"]["value"] = "f" * 64
    mismatch = client.post(
        url,
        json=payload,
        cookies=_cookies(session),
        headers=_headers(session, "worker-mismatch-key"),
    )
    assert mismatch.status_code == 409
    assert "/opt/" not in mismatch.text.lower()
    payload = _create(plan, worker).model_dump(mode="json")
    payload["inherited_limits_fingerprint"]["value"] = "e" * 64
    assert client.post(
        url,
        json=payload,
        cookies=_cookies(session),
        headers=_headers(session, "inherited-limits-mismatch"),
    ).status_code == 409

    plan2, status2, worker2 = _service(tmp_path / "home-source")[-3:]
    values = _application(
        tmp_path / "home", evidence=(plan2, status2, True), worker=worker2
    )
    client, session, _, _, _, _, *_, url, _ = values
    blocked = client.post(
        url,
        json=_create(plan2, worker2).model_dump(mode="json"),
        cookies=_cookies(session),
        headers=_headers(session),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["error_code"] == "not_eligible"


def test_foreign_get_is_not_found_and_foreign_list_is_empty(tmp_path: Path) -> None:
    values = _application(tmp_path)
    client, session, _, plan, _, worker, *_, url, sessions = values
    assert client.post(
        url,
        json=_create(plan, worker).model_dump(mode="json"),
        cookies=_cookies(session),
        headers=_headers(session),
    ).status_code == 201
    foreign = sessions.create(
        OperatorCredential(
            operator_id="operator-b",
            password_hash="unused",
            permissions=(INSTALLATION_WORKER_ADMISSION_STUB_READ,),
        )
    )
    assert client.get(f"{url}/{STUB_ID}", cookies=_cookies(foreign)).status_code == 404
    assert client.get(url, cookies=_cookies(foreign)).json()["stubs"] == []
    hidden = url.replace(plan.candidate_record_id, "bf819229-618a-44f5-a14e-4c0f5878ea14")
    assert client.get(f"{hidden}/{STUB_ID}", cookies=_cookies(session)).status_code == 404
    assert client.get(hidden, cookies=_cookies(session)).json()["stubs"] == []


def test_openapi_is_exact_and_has_no_effect_siblings(tmp_path: Path) -> None:
    _, _, application, *_ = _application(tmp_path)
    paths = application.openapi()["paths"]
    collection = next(path for path in paths if path.endswith("/worker-admission-stubs"))
    item = next(path for path in paths if path.endswith("/worker-admission-stubs/{stub_id}"))
    assert set(paths) == {collection, item}
    assert set(paths[collection]) == {"get", "post"}
    assert set(paths[item]) == {"get"}
    post = paths[collection]["post"]
    assert post["requestBody"]["required"] is True
    idempotency = next(value for value in post["parameters"] if value["name"] == "Idempotency-Key")
    assert idempotency["required"] is True and idempotency["schema"]["minLength"] == 16
    for forbidden in (
        "worker", "start", "enqueue", "queue", "run", "execute", "dispatch",
        "retry", "resend", "deploy", "rollback", "agent", "workflow", "mutation",
    ):
        assert f"{collection}/{forbidden}" not in paths
        assert f"{item}/{forbidden}" not in paths


def test_route_has_no_execution_or_runtime_consumers() -> None:
    path = Path(__file__).with_name("worker_admission_stub.py")
    tree = ast.parse(path.read_text())
    imports = {
        alias.name if isinstance(node, ast.Import) else node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden = (
        "operational_dispatch", "execution_candidates", "atlas_agent", "provider",
        "repository", "workflow", "execution_worker", "docker", "subprocess",
        "socket", "httpx", "requests",
    )
    assert not [name for name in imports if any(marker in name for marker in forbidden)]
