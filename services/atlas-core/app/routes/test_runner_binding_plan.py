"""P3 API locks for v0.37 runner binding plan evidence."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from fastapi import FastAPI

from app.operator_auth.models import (
    INSTALLATION_RUNNER_BINDING_PLAN_READ,
    INSTALLATION_RUNNER_BINDING_PLAN_RECORD,
    OperatorCredential,
)
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.runner_binding_plan import router
from app.runner_binding_plan.test_contract import PLAN_ID
from app.runner_binding_plan.test_service_store import _create, _service
from app.testing import ASGITestClient

ORIGIN = "https://atlas.example"


def _application(
    tmp_path: Path,
    *,
    permissions=None,
    rate_limit: int = 100,
    second: int = 32,
    evidence=None,
    runner=None,
    service_enabled: bool = True,
):
    (
        plan_service,
        _,
        evidence_reader,
        runner_reader,
        factory,
        admission,
        status,
        reference,
    ) = _service(
        tmp_path / "service",
        evidence=evidence,
        runner=runner,
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
                INSTALLATION_RUNNER_BINDING_PLAN_RECORD,
                INSTALLATION_RUNNER_BINDING_PLAN_READ,
            ),
        )
    )
    if service_enabled:
        application.state.runner_binding_plan_service = plan_service
    collection = (
        f"/api/v1/installation/candidate-records/{admission.candidate_record_id}"
        "/runner-binding-plans"
    )
    return (
        ASGITestClient(application),
        session,
        application,
        admission,
        status,
        reference,
        evidence_reader,
        runner_reader,
        factory,
        collection,
        sessions,
    )


def _cookies(session):
    return {"atlas_operator_session": session.session_token}


def _headers(session, key: str = "runner-binding-plan-key-1"):
    return {
        "Origin": ORIGIN,
        "X-Atlas-CSRF-Token": session.csrf_token,
        "Idempotency-Key": key,
    }


def test_auth_permission_csrf_origin_rate_limit_and_success(tmp_path: Path) -> None:
    (
        client, session, _, admission, _, reference, evidence_reader,
        runner_reader, factory, url, _,
    ) = _application(tmp_path)
    payload = _create(admission, reference).model_dump(mode="json")
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
    assert body["plan"]["eligibility"] == "binding_planned"
    assert body["status"]["lifecycle"] == "active"
    assert body["plan"]["evidence_only"]
    assert not body["plan"]["runner_bound"]
    assert not body["plan"]["execution_authorized"]
    listed = client.get(url, cookies=_cookies(session))
    assert listed.status_code == 200
    assert listed.json()["plans"][0]["plan"] == body["plan"]
    fetched = client.get(f"{url}/{PLAN_ID}", cookies=_cookies(session))
    assert fetched.status_code == 200
    assert fetched.json()["plan"] == body["plan"]
    duplicate = client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["plan"] == body["plan"]
    assert evidence_reader.calls == runner_reader.calls == factory.calls == 1

    limited, limited_session, _, limited_admission, _, limited_runner, *_rest = (
        _application(tmp_path / "limited", rate_limit=1)
    )
    limited_payload = _create(limited_admission, limited_runner).model_dump(mode="json")
    assert limited.post(
        _rest[-2],
        json=limited_payload,
        cookies=_cookies(limited_session),
        headers=_headers(limited_session, "one"),
    ).status_code == 201
    rate_limited = limited.post(
        _rest[-2],
        json=limited_payload,
        cookies=_cookies(limited_session),
        headers=_headers(limited_session, "two"),
    )
    assert rate_limited.status_code == 429
    assert rate_limited.json()["error"]["redacted"]


def test_dedicated_create_and_read_permissions_are_independent(tmp_path: Path) -> None:
    values = _application(
        tmp_path / "read", permissions=(INSTALLATION_RUNNER_BINDING_PLAN_READ,)
    )
    client, session, _, admission, _, reference, *_, url, _ = values
    assert client.get(url, cookies=_cookies(session)).status_code == 200
    assert client.post(
        url,
        json=_create(admission, reference).model_dump(mode="json"),
        cookies=_cookies(session),
        headers=_headers(session),
    ).status_code == 403

    values = _application(
        tmp_path / "record", permissions=(INSTALLATION_RUNNER_BINDING_PLAN_RECORD,)
    )
    client, session, _, admission, _, reference, *_, url, _ = values
    assert client.get(url, cookies=_cookies(session)).status_code == 403
    assert client.post(
        url,
        json=_create(admission, reference).model_dump(mode="json"),
        cookies=_cookies(session),
        headers=_headers(session),
    ).status_code == 201


def test_closed_body_query_method_and_idempotency_validation(tmp_path: Path) -> None:
    client, session, _, admission, _, reference, *_, url, _ = _application(tmp_path)
    payload = _create(admission, reference).model_dump(mode="json")
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
    for _ in range(9):
        nested = {"nested": nested}
    assert client.post(url, json=nested, cookies=cookies, headers=headers).status_code == 422
    assert client.post(
        url,
        content=b" " * 4097,
        cookies=cookies,
        headers={**headers, "Content-Type": "application/json"},
    ).status_code == 413
    for invalid_key in (None, "contains space", "x" * 129, "bad\x7f"):
        exact = {name: value for name, value in headers.items() if name != "Idempotency-Key"}
        if invalid_key is not None:
            exact["Idempotency-Key"] = invalid_key
        assert client.post(url, json=payload, cookies=cookies, headers=exact).status_code == 422
    assert client.post(
        url + "?bind=true", json=payload, cookies=cookies, headers=headers
    ).status_code == 422
    assert client.get(url + "?limit=1", cookies=cookies).status_code == 422
    assert client.request("PUT", url).status_code == 405
    assert client.request("POST", f"{url}/{PLAN_ID}").status_code == 405


def test_default_disabled_stale_mismatch_and_home_assistant_are_redacted(tmp_path: Path) -> None:
    values = _application(tmp_path / "disabled", service_enabled=False)
    client, session, _, admission, _, reference, *_, url, _ = values
    unavailable = client.post(
        url,
        json=_create(admission, reference).model_dump(mode="json"),
        cookies=_cookies(session),
        headers=_headers(session),
    )
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["error_code"] == "unavailable"

    values = _application(tmp_path / "stale", second=50)
    client, session, _, admission, _, reference, *_, url, _ = values
    stale = client.post(
        url,
        json=_create(admission, reference).model_dump(mode="json"),
        cookies=_cookies(session),
        headers=_headers(session),
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["error_code"] == "expired"

    values = _application(tmp_path / "mismatch")
    client, session, _, admission, _, reference, *_, url, _ = values
    payload = _create(admission, reference).model_dump(mode="json")
    payload["runner_reference_fingerprint"]["value"] = "f" * 64
    mismatch = client.post(
        url,
        json=payload,
        cookies=_cookies(session),
        headers=_headers(session, "mismatch"),
    )
    assert mismatch.status_code == 409
    rendered = mismatch.text.lower()
    assert "fingerprint mismatch" not in rendered
    assert "/opt/" not in rendered

    admission, status, reference = _service(tmp_path / "home-source")[-3:]
    values = _application(
        tmp_path / "home",
        evidence=(admission, status, True),
        runner=reference,
    )
    client, session, _, _, _, _, *_, url, _ = values
    blocked = client.post(
        url,
        json=_create(admission, reference).model_dump(mode="json"),
        cookies=_cookies(session),
        headers=_headers(session),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["error_code"] == "not_eligible"


def test_runner_reference_and_all_limit_ceiling_failures_are_closed(tmp_path: Path) -> None:
    admission, _, reference = _service(tmp_path / "source")[-3:]
    payload = _create(admission, reference).model_dump(mode="json")
    mutations = (
        ("runner_kind", "general_runner"),
        ("limits.sandbox.privileged", True),
        ("limits.resources.cpu_millis_max", 1001),
        ("limits.network.egress_allowed", True),
        ("limits.filesystem.host_mounts_allowed", True),
    )
    for index, (path, value) in enumerate(mutations):
        raw = reference.model_dump(mode="json")
        target = raw
        parts = path.split(".")
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value
        values = _application(tmp_path / f"invalid-{index}", runner=raw)
        client, session, _, _, _, _, *_, url, _ = values
        result = client.post(
            url,
            json=payload,
            cookies=_cookies(session),
            headers=_headers(session, f"invalid-{index}"),
        )
        assert result.status_code in {409, 503}
        assert result.json()["error"]["redacted"]


def test_foreign_get_is_not_found_and_foreign_list_is_empty(tmp_path: Path) -> None:
    values = _application(tmp_path)
    client, session, _, admission, _, reference, *_, url, sessions = values
    assert client.post(
        url,
        json=_create(admission, reference).model_dump(mode="json"),
        cookies=_cookies(session),
        headers=_headers(session),
    ).status_code == 201
    foreign = sessions.create(
        OperatorCredential(
            operator_id="operator-b",
            password_hash="unused",
            permissions=(INSTALLATION_RUNNER_BINDING_PLAN_READ,),
        )
    )
    assert client.get(f"{url}/{PLAN_ID}", cookies=_cookies(foreign)).status_code == 404
    listed = client.get(url, cookies=_cookies(foreign))
    assert listed.status_code == 200 and listed.json()["plans"] == []
    other = "bf819229-618a-44f5-a14e-4c0f5878ea14"
    hidden = url.replace(admission.candidate_record_id, other)
    assert client.get(f"{hidden}/{PLAN_ID}", cookies=_cookies(session)).status_code == 404
    assert client.get(hidden, cookies=_cookies(session)).json()["plans"] == []


def test_openapi_is_exact_and_has_no_effect_siblings(tmp_path: Path) -> None:
    _, _, application, *_ = _application(tmp_path)
    paths = application.openapi()["paths"]
    collection = next(path for path in paths if path.endswith("/runner-binding-plans"))
    item = next(path for path in paths if path.endswith("/runner-binding-plans/{plan_id}"))
    assert set(paths) == {collection, item}
    assert set(paths[collection]) == {"get", "post"}
    assert set(paths[item]) == {"get"}
    post = paths[collection]["post"]
    assert post["requestBody"]["required"] is True
    idempotency = next(value for value in post["parameters"] if value["name"] == "Idempotency-Key")
    assert idempotency["in"] == "header" and idempotency["required"] is True
    for forbidden in (
        "bind", "run", "execute", "start", "install", "dispatch", "retry",
        "resend", "deploy", "rollback", "replay", "agent", "worker",
        "workflow", "mutation",
    ):
        assert f"{collection}/{forbidden}" not in paths
        assert f"{item}/{forbidden}" not in paths


def test_route_has_no_execution_or_runtime_consumers() -> None:
    path = Path(__file__).with_name("runner_binding_plan.py")
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
            "provider", "repository", "workflow", "worker", "docker",
            "subprocess", "socket", "httpx", "requests",
        )
    )
