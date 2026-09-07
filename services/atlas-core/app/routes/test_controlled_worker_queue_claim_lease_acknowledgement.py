"""P3 API locks for v0.52 queue claim/lease/ack receipt evidence."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.controlled_worker_queue_claim_lease_acknowledgement.test_service_store import (
    _service,
)
from app.operator_auth.models import (
    INSTALLATION_CONTROLLED_WORKER_QUEUE_CLAIM_LEASE_ACK_EVALUATE,
    INSTALLATION_CONTROLLED_WORKER_QUEUE_CLAIM_LEASE_ACK_READ,
    SUPPORTED_OPERATOR_PERMISSIONS,
    OperatorCredential,
)
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.controlled_worker_queue_claim_lease_acknowledgement import (
    router,
)
from app.testing import ASGITestClient

ORIGIN = "https://atlas.example"


def _application(
    tmp_path: Path,
    *,
    permissions=None,
    rate_limit: int = 100,
    service_installed: bool = True,
    service_enabled: bool = True,
):
    (
        admission_service,
        _store,
        reader,
        _adapter_reader,
        prerequisite,
        _status,
        _adapter,
        create,
    ) = _service(tmp_path / "service", enabled=service_enabled)
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
            operator_id=prerequisite.operator_id,
            password_hash="unused",
            permissions=permissions
            or (
                INSTALLATION_CONTROLLED_WORKER_QUEUE_CLAIM_LEASE_ACK_EVALUATE,
                INSTALLATION_CONTROLLED_WORKER_QUEUE_CLAIM_LEASE_ACK_READ,
            ),
        )
    )
    if service_installed:
        application.state.controlled_worker_queue_claim_lease_acknowledgement_service = admission_service
    collection = (
        f"/api/v1/installation/candidate-records/{prerequisite.candidate_record_id}"
        "/controlled-worker-queue-claim-lease-acknowledgements"
    )
    return (
        ASGITestClient(application),
        session,
        prerequisite,
        create,
        reader,
        collection,
        sessions,
    )


def _cookies(session):
    return {"atlas_operator_session": session.session_token}


def _headers(session, key: str = "controlled-worker-claim-lease-ack-admission-key-1"):
    return {
        "Origin": ORIGIN,
        "X-Atlas-CSRF-Token": session.csrf_token,
        "Idempotency-Key": key,
    }


def test_auth_csrf_success_readback_and_exact_no_replay(tmp_path: Path) -> None:
    client, session, prerequisite, create, reader, url, sessions = _application(
        tmp_path
    )
    payload = create.model_dump(mode="json")
    assert client.get(url).status_code == 401
    assert client.post(url, json=payload, cookies=_cookies(session)).status_code == 403
    assert (
        client.post(
            url,
            json=payload,
            cookies=_cookies(session),
            headers={**_headers(session), "Origin": "https://foreign.example"},
        ).status_code
        == 403
    )

    made = client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    assert made.status_code == 201
    body = made.json()
    assert body["ok"] is True
    assert body["outcome"] == "success"
    assert body["controlled_worker_queue_claim_lease_acknowledgement_recorded"] is True
    assert body["record"]["candidate_record_id"] == prerequisite.candidate_record_id
    assert body["record"]["receipt_state"] == "recorded"
    from app.controlled_worker_queue_claim_lease_acknowledgement.contract import (
        SUCCESS_BLOCKERS,
        ClosedAuthorityV1,
    )

    assert body["record"]["blockers"] == list(SUCCESS_BLOCKERS)
    for field, definition in ClosedAuthorityV1.model_fields.items():
        if definition.default is False:
            assert body["record"][field] is False

    listed = client.get(url, cookies=_cookies(session))
    assert listed.status_code == 200
    assert listed.json()["items"] == [body["record"]]
    fetched = client.get(
        f"{url}/{body['record']['admission_id']}",
        cookies=_cookies(session),
    )
    assert fetched.status_code == 200
    assert fetched.json()["record"] == body["record"]
    foreign = sessions.create(
        OperatorCredential(
            operator_id="operator-b",
            password_hash="unused",
            permissions=(INSTALLATION_CONTROLLED_WORKER_QUEUE_CLAIM_LEASE_ACK_READ,),
        )
    )
    foreign_get = client.get(
        f"{url}/{body['record']['admission_id']}", cookies=_cookies(foreign)
    )
    assert foreign_get.status_code == 404
    assert foreign_get.json()["error"]["error_code"] == "not_found"
    duplicate = client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["record"] == body["record"]
    assert reader.calls == 3


def test_dedicated_permissions_default_off_and_redaction(tmp_path: Path) -> None:
    read_client, read_session, _, create, _, url, _ = _application(
        tmp_path / "read",
        permissions=(INSTALLATION_CONTROLLED_WORKER_QUEUE_CLAIM_LEASE_ACK_READ,),
    )
    assert read_client.get(url, cookies=_cookies(read_session)).status_code == 200
    assert (
        read_client.post(
            url,
            json=create.model_dump(mode="json"),
            cookies=_cookies(read_session),
            headers=_headers(read_session),
        ).status_code
        == 403
    )

    create_client, create_session, _, _create, _, url, _ = _application(
        tmp_path / "create",
        permissions=(INSTALLATION_CONTROLLED_WORKER_QUEUE_CLAIM_LEASE_ACK_EVALUATE,),
    )
    assert create_client.get(url, cookies=_cookies(create_session)).status_code == 403

    disabled, disabled_session, _, create, reader, url, _ = _application(
        tmp_path / "disabled", service_enabled=False
    )
    blocked = disabled.post(
        url,
        json=create.model_dump(mode="json"),
        cookies=_cookies(disabled_session),
        headers=_headers(disabled_session),
    )
    assert blocked.status_code == 409
    assert (
        blocked.json()["error"]["error_code"] == "installation_capability_unsupported"
    )
    assert reader.calls == 0

    missing_client, missing_session, _, create, _, missing_url, _ = _application(
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
    assert "controlled-worker-claim-lease-ack-admission-key-1" not in json.dumps(
        unavailable.json()
    )


def test_strict_body_query_method_rate_and_idempotency_bounds(tmp_path: Path) -> None:
    client, session, _, create, _, url, _ = _application(tmp_path)
    payload = create.model_dump(mode="json")
    cookies, headers = _cookies(session), _headers(session)
    assert (
        client.post(
            url,
            content=b"{}",
            cookies=cookies,
            headers={**headers, "Content-Type": "text/plain"},
        ).status_code
        == 415
    )
    duplicate = json.dumps(payload)[:-1] + ',"schema":"duplicate"}'
    assert (
        client.post(
            url,
            content=duplicate,
            cookies=cookies,
            headers={**headers, "Content-Type": "application/json"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            url,
            json={**payload, "claim_token": "secret-token"},
            cookies=cookies,
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.post(
            url + "?claim=true", json=payload, cookies=cookies, headers=headers
        ).status_code
        == 422
    )
    assert client.get(url + "?limit=1", cookies=cookies).status_code == 422
    assert (
        client.request("GET", url, content=b"unexpected", cookies=cookies).status_code
        == 422
    )
    assert (
        client.get(
            url.replace("candidate-records/", "candidate-records/invalid"),
            cookies=cookies,
        ).status_code
        == 422
    )
    for invalid_key in (
        None,
        "too-short",
        "contains space here",
        "x" * 129,
        "bad\x7f",
    ):
        exact_headers = {
            name: value for name, value in headers.items() if name != "Idempotency-Key"
        }
        if invalid_key is not None:
            exact_headers["Idempotency-Key"] = invalid_key
        assert (
            client.post(
                url, json=payload, cookies=cookies, headers=exact_headers
            ).status_code
            == 422
        )
    assert client.request("PUT", url).status_code == 405
    assert (
        client.request(
            "POST", f"{url}/a70ea6f4-18ba-57f3-867e-f5eae39bfb2d"
        ).status_code
        == 405
    )

    limited_client, limited_session, _, limited_create, _, limited_url, _ = (
        _application(tmp_path / "limited", rate_limit=1)
    )
    assert (
        limited_client.post(
            limited_url,
            json=limited_create.model_dump(mode="json"),
            cookies=_cookies(limited_session),
            headers=_headers(limited_session, "controlled-worker-admission-first"),
        ).status_code
        == 201
    )
    limited = limited_client.post(
        limited_url,
        json=limited_create.model_dump(mode="json"),
        cookies=_cookies(limited_session),
        headers=_headers(limited_session, "controlled-worker-admission-second"),
    )
    assert limited.status_code == 429
    assert limited.json()["error"]["error_code"] == "rate_limited"


def test_permissions_openapi_method_and_authority_isolation() -> None:
    from app.controlled_worker_queue_claim_lease_acknowledgement.contract import (
        PERMISSION,
    )

    assert INSTALLATION_CONTROLLED_WORKER_QUEUE_CLAIM_LEASE_ACK_EVALUATE == PERMISSION
    assert INSTALLATION_CONTROLLED_WORKER_QUEUE_CLAIM_LEASE_ACK_EVALUATE == (
        "installation.execution."
        "controlled_worker_queue_claim_lease_acknowledgement.evaluate"
    )
    assert INSTALLATION_CONTROLLED_WORKER_QUEUE_CLAIM_LEASE_ACK_READ == (
        "installation.execution."
        "controlled_worker_queue_claim_lease_acknowledgement.read"
    )
    assert {
        INSTALLATION_CONTROLLED_WORKER_QUEUE_CLAIM_LEASE_ACK_EVALUATE,
        INSTALLATION_CONTROLLED_WORKER_QUEUE_CLAIM_LEASE_ACK_READ,
    } <= SUPPORTED_OPERATOR_PERMISSIONS

    application = FastAPI()
    application.include_router(api_v1_router)
    paths = application.openapi()["paths"]
    collection = (
        "/api/v1/installation/candidate-records/{candidate_record_id}"
        "/controlled-worker-queue-claim-lease-acknowledgements"
    )
    item = f"{collection}/{{admission_id}}"
    assert set(paths[collection]) == {"get", "post"}
    assert set(paths[item]) == {"get"}
    for parameter in paths[item]["get"]["parameters"]:
        examples = {
            "candidate_record_id": "00000000-0000-4000-8000-000000000001",
            "admission_id": "a70ea6f4-18ba-57f3-867e-f5eae39bfb2d",
        }
        assert re.fullmatch(parameter["schema"]["pattern"], examples[parameter["name"]])
        assert not re.fullmatch(parameter["schema"]["pattern"], "invalid")
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
        "activate",
    }
    assert not any(
        segment in prohibited_segments
        for path in paths
        if "controlled-worker-queue-claim-lease-acknowledgements" in path
        for segment in path.split(
            "controlled-worker-queue-claim-lease-acknowledgements", 1
        )[1]
        .strip("/")
        .split("/")
        if segment
    )


def test_route_has_no_runtime_effect_imports_or_broad_calls() -> None:
    path = Path(__file__).with_name(
        "controlled_worker_queue_claim_lease_acknowledgement.py"
    )
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name if isinstance(node, ast.Import) else node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
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
    allowed_contract_import = (
        "app.controlled_worker_queue_claim_lease_acknowledgement.contract"
    )
    assert not [
        name
        for name in imports
        if name != allowed_contract_import
        and any(term in name for term in forbidden_imports)
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
        "activate(",
    ):
        assert forbidden not in source


def test_production_startup_does_not_construct_v052_admission_service() -> None:
    source = Path(__file__).parents[1].joinpath("main.py").read_text(encoding="utf-8")
    assert "controlled_worker_queue_claim_lease_acknowledgement_service" not in source
    assert (
        "create_controlled_worker_queue_claim_lease_acknowledgement_service"
        not in source
    )


def test_lineage_isolation_staleness_and_permanent_reservation(tmp_path: Path) -> None:
    from app.controlled_worker_queue_claim_lease_acknowledgement.test_service_store import (
        _clock,
    )

    client, session, admission, create, reader, url, sessions = _application(tmp_path)
    cookies, headers = _cookies(session), _headers(session)
    payload = create.model_dump(mode="json")
    foreign = sessions.create(
        OperatorCredential(
            operator_id="operator-b",
            password_hash="unused",
            permissions=(
                INSTALLATION_CONTROLLED_WORKER_QUEUE_CLAIM_LEASE_ACK_EVALUATE,
                INSTALLATION_CONTROLLED_WORKER_QUEUE_CLAIM_LEASE_ACK_READ,
            ),
        )
    )
    assert (
        client.post(
            url, json=payload, cookies=_cookies(foreign), headers=_headers(foreign)
        ).status_code
        == 404
    )
    assert client.get(url, cookies=_cookies(foreign)).json()["items"] == []
    wrong_url = url.replace(
        admission.candidate_record_id, "00000000-0000-4000-8000-000000000099"
    )
    assert (
        client.post(
            wrong_url, json=payload, cookies=cookies, headers=headers
        ).status_code
        == 409
    )
    changed = json.loads(json.dumps(payload))
    changed["admission_status_fingerprint"]["value"] = "0" * 64
    assert (
        client.post(url, json=changed, cookies=cookies, headers=headers).status_code
        == 409
    )
    service = (
        client._app.state.controlled_worker_queue_claim_lease_acknowledgement_service
    )
    service._clock = _clock(80)
    assert (
        client.post(url, json=payload, cookies=cookies, headers=headers).status_code
        == 409
    )
    service._clock = _clock()
    made = client.post(url, json=payload, cookies=cookies, headers=headers)
    assert made.status_code == 201
    item_id = made.json()["record"]["admission_id"]
    assert client.get(f"{wrong_url}/{item_id}", cookies=cookies).status_code == 404
    assert (
        client.post(
            url,
            json=payload,
            cookies=cookies,
            headers=_headers(session, "another-permanent-subject-key"),
        ).status_code
        == 409
    )
    assert (
        client.post(url, json=changed, cookies=cookies, headers=headers).status_code
        == 409
    )
    calls = reader.calls
    service._clock = _clock(80)
    duplicate = client.post(url, json=payload, cookies=cookies, headers=headers)
    assert duplicate.status_code == 201
    assert duplicate.json()["record"] == made.json()["record"]
    assert duplicate.json()["status"]["lifecycle"] == "expired"
    assert reader.calls == calls


def test_bounded_input_and_redacted_untrusted_service_outputs(
    tmp_path: Path, monkeypatch
) -> None:
    from app.controlled_worker_queue_claim_lease_acknowledgement.contract import (
        MAX_CREATE_BYTES,
    )

    client, session, _, create, _, url, _ = _application(tmp_path)
    cookies, headers = _cookies(session), _headers(session)
    assert (
        client.post(
            url,
            content=b"x" * (MAX_CREATE_BYTES + 1),
            cookies=cookies,
            headers={**headers, "Content-Type": "application/json"},
        ).status_code
        == 413
    )
    assert (
        client.post(
            url,
            json=create.model_dump(mode="json"),
            cookies=cookies,
            headers=[*headers.items(), ("Idempotency-Key", "duplicate-header-key")],
        ).status_code
        == 422
    )
    for method in ("get", "post"):
        response = client.request(
            method.upper(),
            url.replace("candidate-records/", "candidate-records/not-a-uuid/"),
            cookies=cookies,
            headers=headers,
        )
        assert response.status_code in (404, 422)
    service = (
        client._app.state.controlled_worker_queue_claim_lease_acknowledgement_service
    )
    made = client.post(
        url, json=create.model_dump(mode="json"), cookies=cookies, headers=headers
    )
    assert made.status_code == 201
    item = f"{url}/{made.json()['record']['admission_id']}"
    real = service.get(
        authenticated_operator_id=made.json()["record"]["operator_id"],
        permission_verified=True,
        admission_id=made.json()["record"]["admission_id"],
        correlation_id="test",
    )
    bad = real.model_copy(update={"worker_start_allowed": True})
    monkeypatch.setattr(service, "get", lambda **kwargs: bad)
    assert client.get(item, cookies=cookies).status_code == 503
    monkeypatch.setattr(service, "list", lambda **kwargs: real)
    assert client.get(url, cookies=cookies).status_code == 503

    def fail(*args, **kwargs):
        raise RuntimeError("secret-token https://private.example")

    monkeypatch.setattr(service, "create", fail)
    response = client.post(
        url, json=create.model_dump(mode="json"), cookies=cookies, headers=headers
    )
    assert response.status_code == 503
    assert "secret-token" not in response.text
    assert "private.example" not in response.text


def test_chunked_body_stops_at_bound_without_content_length() -> None:
    import asyncio

    import pytest
    from fastapi import HTTPException, Request

    from app.controlled_worker_queue_claim_lease_acknowledgement.contract import (
        MAX_CREATE_BYTES,
    )
    from app.routes.controlled_worker_queue_claim_lease_acknowledgement import _body

    calls = 0

    async def receive():
        nonlocal calls
        calls += 1
        assert calls == 1
        return {
            "type": "http.request",
            "body": b"x" * (MAX_CREATE_BYTES + 1),
            "more_body": True,
        }

    request = Request(
        {"type": "http", "headers": [(b"content-type", b"application/json")]}, receive
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(_body(request))
    assert error.value.status_code == 413
    assert calls == 1
