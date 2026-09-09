"""P3 API locks for v0.56 worker activation runtime plan review evidence."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest
from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.operator_auth.models import (
    INSTALLATION_WORKER_ACTIVATION_RUNTIME_PLAN_REVIEW_EVALUATE,
    INSTALLATION_WORKER_ACTIVATION_RUNTIME_PLAN_REVIEW_READ,
    SUPPORTED_OPERATOR_PERMISSIONS,
    OperatorCredential,
)
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.worker_activation_runtime_plan_review import (
    router,
)
from app.testing import ASGITestClient
from app.worker_activation_runtime_plan_review import test_contract as p1
from app.worker_activation_runtime_plan_review.test_contract import (
    admission_facts,  # noqa: F401
    plan_facts,  # noqa: F401
    prior_facts,  # noqa: F401
)
from app.worker_activation_runtime_plan_review.test_service_store import (
    setup,
)

ORIGIN = "https://atlas.example"


@pytest.fixture(scope="module")
def facts(request):
    return p1.facts.__wrapped__(request)


def _application(
    tmp_path: Path,
    facts,
    *,
    permissions=None,
    rate_limit: int = 100,
    service_installed: bool = True,
    service_enabled: bool = True,
):
    tmp_path.mkdir(parents=True, exist_ok=True)
    review_service, _store, reader, _clock = setup(
        tmp_path, facts, enabled=service_enabled
    )
    original_read = reader.read_owned

    def read_owned(**kwargs):
        if (
            kwargs["operator_id"] != facts.operator_id
            or kwargs["candidate_record_id"] != facts.candidate_record_id
            or kwargs["runtime_plan_id"] != facts.create.runtime_plan_id
        ):
            reader.calls += 1
            return None
        return original_read(**kwargs)

    reader.read_owned = read_owned
    prerequisite = facts
    create = facts.create
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
                INSTALLATION_WORKER_ACTIVATION_RUNTIME_PLAN_REVIEW_EVALUATE,
                INSTALLATION_WORKER_ACTIVATION_RUNTIME_PLAN_REVIEW_READ,
            ),
        )
    )
    if service_installed:
        application.state.worker_activation_runtime_plan_review_service = review_service
    collection = (
        f"/api/v1/installation/candidate-records/{prerequisite.candidate_record_id}"
        "/worker-activation-runtime-plan-reviews"
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


def _headers(session, key: str = "v056-api-plan-review-key-1"):
    return {
        "Origin": ORIGIN,
        "X-Atlas-CSRF-Token": session.csrf_token,
        "Idempotency-Key": key,
    }


def test_auth_csrf_success_readback_and_exact_no_replay(tmp_path: Path, facts) -> None:
    client, session, prerequisite, create, reader, url, sessions = _application(
        tmp_path, facts
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
    assert body["worker_activation_runtime_plan_review_recorded"] is True
    assert body["record"]["candidate_record_id"] == prerequisite.candidate_record_id
    from app.worker_activation_runtime_plan_review.contract import (
        SUCCESS_BLOCKERS,
        ClosedAuthorityV1,
    )

    assert body["record"]["blockers"] == list(SUCCESS_BLOCKERS)
    assert body["record"]["findings"] == [
        "exact_plan_lineage",
        "fixed_design_consistent",
        "unresolved_interfaces_preserved",
    ]
    assert body["record"]["worker_activation_runtime_plan"] == (
        facts.worker_activation_runtime_plan.model_dump(mode="json")
    )
    assert body["record"]["worker_activation_runtime_plan_status"] == (
        facts.worker_activation_runtime_plan_status.model_dump(mode="json")
    )
    for field, definition in ClosedAuthorityV1.model_fields.items():
        if definition.default is False:
            assert body["record"][field] is False

    listed = client.get(url, cookies=_cookies(session))
    assert listed.status_code == 200
    assert listed.json()["items"] == [body["record"]]
    fetched = client.get(
        f"{url}/{body['record']['runtime_plan_review_id']}",
        cookies=_cookies(session),
    )
    assert fetched.status_code == 200
    assert fetched.json()["record"] == body["record"]
    foreign = sessions.create(
        OperatorCredential(
            operator_id="operator-b",
            password_hash="unused",
            permissions=(INSTALLATION_WORKER_ACTIVATION_RUNTIME_PLAN_REVIEW_READ,),
        )
    )
    foreign_get = client.get(
        f"{url}/{body['record']['runtime_plan_review_id']}", cookies=_cookies(foreign)
    )
    assert foreign_get.status_code == 404
    assert foreign_get.json()["error_code"] == "evidence_not_found"
    duplicate = client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["record"] == body["record"]
    assert reader.calls == 2


def test_dedicated_permissions_default_off_and_redaction(tmp_path: Path, facts) -> None:
    read_client, read_session, _, create, _, url, _ = _application(
        tmp_path / "read",
        facts,
        permissions=(INSTALLATION_WORKER_ACTIVATION_RUNTIME_PLAN_REVIEW_READ,),
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
        facts,
        permissions=(INSTALLATION_WORKER_ACTIVATION_RUNTIME_PLAN_REVIEW_EVALUATE,),
    )
    assert create_client.get(url, cookies=_cookies(create_session)).status_code == 403

    disabled, disabled_session, _, create, reader, url, _ = _application(
        tmp_path / "disabled", facts, service_enabled=False
    )
    blocked = disabled.post(
        url,
        json=create.model_dump(mode="json"),
        cookies=_cookies(disabled_session),
        headers=_headers(disabled_session),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error_code"] == "installation_capability_unsupported"
    assert reader.calls == 0

    missing_client, missing_session, _, create, _, missing_url, _ = _application(
        tmp_path / "missing", facts, service_installed=False
    )
    unavailable = missing_client.post(
        missing_url,
        json=create.model_dump(mode="json"),
        cookies=_cookies(missing_session),
        headers=_headers(missing_session),
    )
    assert unavailable.status_code == 503
    assert unavailable.json()["error_code"] == "unavailable"
    assert "v056-api-plan-review-key-1" not in json.dumps(unavailable.json())


def test_strict_body_query_method_rate_and_idempotency_bounds(
    tmp_path: Path, facts
) -> None:
    client, session, _, create, _, url, _ = _application(tmp_path, facts)
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
        _application(tmp_path / "limited", facts, rate_limit=1)
    )
    assert (
        limited_client.post(
            limited_url,
            json=limited_create.model_dump(mode="json"),
            cookies=_cookies(limited_session),
            headers=_headers(limited_session, "v056-api-review-first-key"),
        ).status_code
        == 201
    )
    limited = limited_client.post(
        limited_url,
        json=limited_create.model_dump(mode="json"),
        cookies=_cookies(limited_session),
        headers=_headers(limited_session, "v056-api-review-second-key"),
    )
    assert limited.status_code == 429
    assert limited.json()["error_code"] == "forbidden"


def test_permissions_openapi_method_and_authority_isolation() -> None:
    from app.worker_activation_runtime_plan_review.contract import (
        PERMISSION,
    )

    assert INSTALLATION_WORKER_ACTIVATION_RUNTIME_PLAN_REVIEW_EVALUATE == PERMISSION
    assert INSTALLATION_WORKER_ACTIVATION_RUNTIME_PLAN_REVIEW_EVALUATE == (
        "installation.execution.worker_activation_runtime_plan_review.evaluate"
    )
    assert INSTALLATION_WORKER_ACTIVATION_RUNTIME_PLAN_REVIEW_READ == (
        "installation.execution.worker_activation_runtime_plan_review.read"
    )
    assert {
        INSTALLATION_WORKER_ACTIVATION_RUNTIME_PLAN_REVIEW_EVALUATE,
        INSTALLATION_WORKER_ACTIVATION_RUNTIME_PLAN_REVIEW_READ,
    } <= SUPPORTED_OPERATOR_PERMISSIONS

    application = FastAPI()
    application.include_router(api_v1_router)
    paths = application.openapi()["paths"]
    collection = (
        "/api/v1/installation/candidate-records/{candidate_record_id}"
        "/worker-activation-runtime-plan-reviews"
    )
    item = f"{collection}/{{runtime_plan_review_id}}"
    assert set(paths[collection]) == {"get", "post"}
    assert set(paths[item]) == {"get"}
    for parameter in paths[item]["get"]["parameters"]:
        examples = {
            "candidate_record_id": "00000000-0000-4000-8000-000000000001",
            "runtime_plan_review_id": "a70ea6f4-18ba-57f3-867e-f5eae39bfb2d",
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
        if "worker-activation-runtime-plan-reviews" in path
        for segment in path.split("worker-activation-runtime-plan-reviews", 1)[1]
        .strip("/")
        .split("/")
        if segment
    )


def test_route_has_no_runtime_effect_imports_or_broad_calls() -> None:
    path = Path(__file__).with_name("worker_activation_runtime_plan_review.py")
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
    allowed_contract_import = "app.worker_activation_runtime_plan_review.contract"
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


def test_production_startup_does_not_construct_v056_review_service() -> None:
    source = Path(__file__).parents[1].joinpath("main.py").read_text(encoding="utf-8")
    assert "worker_activation_runtime_plan_review_service" not in source
    assert "create_worker_activation_runtime_plan_review_service" not in source


def test_lineage_isolation_staleness_and_permanent_reservation(
    tmp_path: Path, facts
) -> None:
    from datetime import datetime, timedelta

    client, session, prerequisite, create, reader, url, sessions = _application(
        tmp_path, facts
    )
    cookies, headers = _cookies(session), _headers(session)
    payload = create.model_dump(mode="json")
    foreign = sessions.create(
        OperatorCredential(
            operator_id="operator-b",
            password_hash="unused",
            permissions=(
                INSTALLATION_WORKER_ACTIVATION_RUNTIME_PLAN_REVIEW_EVALUATE,
                INSTALLATION_WORKER_ACTIVATION_RUNTIME_PLAN_REVIEW_READ,
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
        prerequisite.candidate_record_id, "00000000-0000-4000-8000-000000000099"
    )
    assert (
        client.post(
            wrong_url, json=payload, cookies=cookies, headers=headers
        ).status_code
        == 404
    )
    changed = json.loads(json.dumps(payload))
    changed["status_fingerprint"]["value"] = "0" * 64
    assert (
        client.post(url, json=changed, cookies=cookies, headers=headers).status_code
        == 409
    )
    service = client._app.state.worker_activation_runtime_plan_review_service
    service._clock.now += timedelta(seconds=80)
    assert (
        client.post(url, json=payload, cookies=cookies, headers=headers).status_code
        == 409
    )
    service._clock.now = datetime.fromisoformat(facts.authority.request_received_at)
    made = client.post(url, json=payload, cookies=cookies, headers=headers)
    assert made.status_code == 201
    item_id = made.json()["record"]["runtime_plan_review_id"]
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
    service._clock.now += timedelta(seconds=80)
    duplicate = client.post(url, json=payload, cookies=cookies, headers=headers)
    assert duplicate.status_code == 201
    assert duplicate.json()["record"] == made.json()["record"]
    assert duplicate.json()["status"]["lifecycle"] == "expired"
    assert reader.calls == calls


def test_bounded_input_and_redacted_untrusted_service_outputs(
    tmp_path: Path, facts, monkeypatch
) -> None:
    from app.worker_activation_runtime_plan_review.contract import (
        MAX_CREATE_BYTES,
    )

    client, session, _, create, _, url, _ = _application(tmp_path, facts)
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
    service = client._app.state.worker_activation_runtime_plan_review_service
    made = client.post(
        url, json=create.model_dump(mode="json"), cookies=cookies, headers=headers
    )
    assert made.status_code == 201
    item = f"{url}/{made.json()['record']['runtime_plan_review_id']}"
    real = service.get(
        authenticated_operator_id=made.json()["record"]["operator_id"],
        permission_verified=True,
        runtime_plan_review_id=made.json()["record"]["runtime_plan_review_id"],
        candidate_record_id=facts.candidate_record_id,
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

    from app.routes.worker_activation_runtime_plan_review import _body
    from app.worker_activation_runtime_plan_review.contract import (
        MAX_CREATE_BYTES,
    )

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


@pytest.mark.parametrize(
    "mutation",
    [
        {"worker_start_allowed": 0},
        {"runtime_effect_allowed": True},
        {"operator_id": "foreign"},
        {"endpoint": "https://private.example"},
        {"status_fingerprint": {"algorithm": "sha256", "value": "0" * 64}},
    ],
)
def test_malformed_requests_never_read_or_reserve(tmp_path, facts, mutation):
    from app.worker_activation_runtime_plan_review.test_service_store import counts

    client, session, _, create, reader, url, _ = _application(tmp_path, facts)
    service = client._app.state.worker_activation_runtime_plan_review_service
    response = client.post(
        url,
        json={**create.model_dump(mode="json"), **mutation},
        cookies=_cookies(session),
        headers=_headers(session),
    )
    assert response.status_code == 422
    assert reader.calls == 0
    assert counts(service._store) == (0, 0, 0)
    assert "private.example" not in response.text
    assert response.json()["retryable"] is False


@pytest.mark.parametrize(
    "raw",
    [
        b"[" * 17 + b"0" + b"]" * 17,
        b'{"unknown": NaN}',
        b"\xff",
        b'{"status_fingerprint":{"value":"a","value":"b"}}',
    ],
)
def test_strict_json_rejection(tmp_path, facts, raw):
    client, session, _, _, reader, url, _ = _application(tmp_path, facts)
    response = client.post(
        url,
        content=raw,
        cookies=_cookies(session),
        headers={**_headers(session), "Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert reader.calls == 0


@pytest.mark.parametrize("target", ["result", "nested", "extra", "collection", "error"])
def test_reparse_every_service_output_including_constructed_models(
    tmp_path, facts, monkeypatch, target
):
    from app.worker_activation_runtime_plan_review import contract as c

    client, session, _, create, _, url, _ = _application(tmp_path, facts)
    service = client._app.state.worker_activation_runtime_plan_review_service
    result = service.create(
        create,
        authenticated_operator_id=facts.operator_id,
        permission_verified=True,
        candidate_record_id=facts.candidate_record_id,
        idempotency_key="v056-output-validation",
        correlation_id="test",
    )
    assert isinstance(result, c.WorkerActivationRuntimePlanReviewResultV1)
    item = f"{url}/{result.record.runtime_plan_review_id}"
    if target == "result":
        bad = result.model_copy(update={"worker_start_allowed": 0})
    elif target == "nested":
        bad = result.model_copy(
            update={
                "record": result.record.model_copy(
                    update={"runtime_effect_allowed": True}
                )
            }
        )
    elif target == "extra":
        bad = result.model_copy(update={"secret": "private-token"})
    elif target == "error":
        bad = service._failure("unavailable", "test").model_copy(
            update={"message": "private-token"}
        )
    else:
        bad = service.list(
            authenticated_operator_id=facts.operator_id,
            permission_verified=True,
            candidate_record_id=facts.candidate_record_id,
            correlation_id="test",
        ).model_copy(update={"count": 17})
        item = url
    monkeypatch.setattr(service, "get" if item != url else "list", lambda **kwargs: bad)
    response = client.get(item, cookies=_cookies(session))
    assert response.status_code == 503
    assert "private-token" not in response.text


def test_corrupted_nested_prerequisite_cannot_create_evidence(tmp_path, facts):
    from app.worker_activation_runtime_plan_review.test_service_store import counts

    client, session, _, create, reader, url, _ = _application(tmp_path, facts)
    receipt, status = reader.pair
    reader.pair = receipt.model_copy(update={"worker_start_allowed": True}), status
    response = client.post(
        url,
        json=create.model_dump(mode="json"),
        cookies=_cookies(session),
        headers=_headers(session),
    )
    assert response.status_code == 422
    assert counts(
        client._app.state.worker_activation_runtime_plan_review_service._store
    ) == (0, 0, 0)


def test_exact_registered_surface_and_zero_agent_worker_consumers():
    collection = "/installation/candidate-records/{candidate_record_id}/worker-activation-runtime-plan-reviews"
    assert {
        (route.path, method) for route in router.routes for method in route.methods
    } == {
        (collection, "GET"),
        (collection, "POST"),
        (collection + "/{runtime_plan_review_id}", "GET"),
    }
    root = Path(__file__).resolve().parents[4]
    for directory in ("atlas-agent", "atlas-execution-worker"):
        for path in (root / "services" / directory).rglob("*.py"):
            if path.name.startswith("test_"):
                continue
            source = path.read_text()
            assert "worker_activation_runtime_plan_review" not in source, path
            assert "worker-activation-runtime-plan-reviews" not in source, path


def test_security_headers_and_authentication_fail_before_evidence_access(
    tmp_path, facts
):
    client, session, _, create, reader, url, _ = _application(tmp_path, facts)
    payload = create.model_dump(mode="json")
    headers = _headers(session)
    for name in ("Origin", "X-Atlas-CSRF-Token"):
        for invalid in (
            [(key, value) for key, value in headers.items() if key != name],
            [*headers.items(), (name, headers[name])],
            {**headers, name: "invalid"},
        ):
            assert (
                client.post(
                    url, json=payload, cookies=_cookies(session), headers=invalid
                ).status_code
                == 403
            )
    assert client.post(url, json=payload, headers=headers).status_code == 401
    item = url + "/a70ea6f4-18ba-57f3-867e-f5eae39bfb2d"
    assert client.get(item).status_code == 401
    client._app.state.operator_auth_enabled = False
    assert client.get(url, cookies=_cookies(session)).status_code == 503
    assert reader.calls == 0


@pytest.mark.parametrize(
    "field",
    [
        "runtime_plan_id",
        "valid_until",
        "runtime_plan_record_fingerprint",
        "status_fingerprint",
    ],
)
def test_valid_service_response_must_match_exact_request(
    tmp_path, facts, monkeypatch, field
):
    client, session, _, create, _, url, _ = _application(tmp_path, facts)
    service = client._app.state.worker_activation_runtime_plan_review_service
    result = service.create(
        create,
        authenticated_operator_id=facts.operator_id,
        permission_verified=True,
        candidate_record_id=facts.candidate_record_id,
        idempotency_key="v056-response-linkage",
        correlation_id="test",
    )
    monkeypatch.setattr(service, "get", lambda **kwargs: result)
    wrong_item = url + "/a70ea6f4-18ba-57f3-867e-f5eae39bfb2d"
    assert client.get(wrong_item, cookies=_cookies(session)).status_code == 404
    monkeypatch.setattr(service, "create", lambda *args, **kwargs: result)
    payload = create.model_dump(mode="json")
    if field.endswith("fingerprint"):
        payload[field]["value"] = "0" * 64
    else:
        payload[field] = (
            "a70ea6f4-18ba-57f3-867e-f5eae39bfb2d"
            if field == "runtime_plan_id"
            else "2099-01-01T00:00:00Z"
        )
    assert (
        client.post(
            url,
            json=payload,
            cookies=_cookies(session),
            headers=_headers(session, "v056-response-linkage"),
        ).status_code
        == 503
    )


def test_unexpected_dependency_http_errors_are_redacted(tmp_path, facts, monkeypatch):
    from fastapi import HTTPException

    client, session, _, create, _, url, _ = _application(tmp_path, facts)

    def fail(*args, **kwargs):
        raise HTTPException(200, "private-token")

    monkeypatch.setattr(
        client._app.state.worker_activation_runtime_plan_review_service, "create", fail
    )
    response = client.post(
        url,
        json=create.model_dump(mode="json"),
        cookies=_cookies(session),
        headers=_headers(session),
    )
    assert response.status_code == 503
    assert "private-token" not in response.text


def test_response_must_bind_exact_idempotency_key(tmp_path, facts, monkeypatch):
    client, session, _, create, _, url, _ = _application(tmp_path, facts)
    service = client._app.state.worker_activation_runtime_plan_review_service
    result = service.create(
        create,
        authenticated_operator_id=facts.operator_id,
        permission_verified=True,
        candidate_record_id=facts.candidate_record_id,
        idempotency_key="different-historical-key",
        correlation_id="test",
    )
    monkeypatch.setattr(service, "create", lambda *args, **kwargs: result)
    response = client.post(
        url,
        json=create.model_dump(mode="json"),
        cookies=_cookies(session),
        headers=_headers(session),
    )
    assert response.status_code == 503
    assert "different-historical-key" not in response.text


@pytest.mark.parametrize(
    "extra_headers,expected",
    [
        (
            [
                ("Content-Type", "application/json"),
                ("Content-Type", "application/json"),
            ],
            415,
        ),
        ([("Content-Type", "application/json"), ("Content-Length", "-1")], 413),
        (
            [("Content-Type", "application/json"), ("Content-Length", "99999999999")],
            413,
        ),
        (
            [
                ("Content-Type", "application/json"),
                ("Content-Length", "1"),
                ("Content-Length", "1"),
            ],
            413,
        ),
    ],
)
def test_ambiguous_headers_fail_before_read_or_reservation(
    tmp_path, facts, extra_headers, expected
):
    from app.worker_activation_runtime_plan_review.test_service_store import counts

    client, session, _, create, reader, url, _ = _application(tmp_path, facts)
    response = client.post(
        url,
        content=create.model_dump_json(),
        cookies=_cookies(session),
        headers=[*_headers(session).items(), *extra_headers],
    )
    assert response.status_code == expected
    assert reader.calls == 0
    assert counts(
        client._app.state.worker_activation_runtime_plan_review_service._store
    ) == (0, 0, 0)


def test_api_durable_lineage_restart_expiry_and_corrupt_readback(
    tmp_path, facts, request
):
    import sqlite3
    from datetime import timedelta

    from app.worker_activation_runtime_plan.test_service_store import (
        create as prior_create,
    )
    from app.worker_activation_runtime_plan.test_service_store import (
        setup as prior_setup,
    )
    from app.worker_activation_runtime_plan_review import contract as c
    from app.worker_activation_runtime_plan_review.readers import (
        WorkerActivationRuntimePlanReviewPrerequisiteStoreReader,
    )
    from app.worker_activation_runtime_plan_review.store import (
        WorkerActivationRuntimePlanReviewStore,
    )
    from app.worker_activation_runtime_plan_review.test_service_store import counts

    client, session, _, _, _, url, sessions = _application(tmp_path, facts)
    service = client._app.state.worker_activation_runtime_plan_review_service
    predecessor = request.getfixturevalue("plan_facts")
    prior, journal, _, clock = prior_setup(tmp_path, predecessor)
    record = prior_create(prior, predecessor).record
    prior_bytes = journal.database_path.read_bytes()
    service._prerequisite_reader = (
        WorkerActivationRuntimePlanReviewPrerequisiteStoreReader(
            store=type(journal)(journal.database_path),
            clock=clock,
        )
    )
    payload = c.build_create(
        receipt=record,
        receipt_status=c.v055.derive_status(record, evaluated_at=record.recorded_at),
    ).model_dump(mode="json")
    foreign = sessions.create(
        OperatorCredential(
            operator_id="foreign",
            password_hash="unused",
            permissions=(INSTALLATION_WORKER_ACTIVATION_RUNTIME_PLAN_REVIEW_EVALUATE,),
        )
    )
    denied = client.post(
        url, json=payload, cookies=_cookies(foreign), headers=_headers(foreign)
    )
    assert denied.status_code == 404
    assert counts(service._store) == (0, 0, 0)
    made = client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    assert made.status_code == 201
    admitted = c.WorkerActivationRuntimePlanReviewResultV1.model_validate_json(
        made.text
    )
    assert (
        admitted.record.worker_activation_runtime_plan.model_dump_json()
        == record.model_dump_json()
    )
    assert journal.database_path.read_bytes() == prior_bytes
    service._store = WorkerActivationRuntimePlanReviewStore(
        service._store.database_path
    )
    service._clock.now += timedelta(seconds=31)
    clock.now += timedelta(seconds=31)

    def no_read(**kwargs):
        pytest.fail(
            "historical API reads/duplicates must not read predecessor evidence"
        )

    service._prerequisite_reader.read_owned = no_read
    duplicate = client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["exact_duplicate"] is True
    assert duplicate.json()["status"]["lifecycle"] == "expired"
    assert duplicate.json()["record"] == made.json()["record"]
    assert counts(service._store) == (1, 1, 0)
    item = f"{url}/{admitted.record.runtime_plan_review_id}"
    assert (
        client.get(item, cookies=_cookies(session)).json()["status"]["lifecycle"]
        == "expired"
    )
    with sqlite3.connect(service._store.database_path) as connection:
        connection.execute("DROP TABLE evidence")
    for response in (
        client.get(item, cookies=_cookies(session)),
        client.get(url, cookies=_cookies(session)),
        client.post(
            url, json=payload, cookies=_cookies(session), headers=_headers(session)
        ),
    ):
        assert response.status_code == 503
        assert response.json()["error_code"] == "store_corrupt"
        assert response.json()["retryable"] is False
        assert "sqlite" not in response.text


def test_route_rejects_valid_foreign_service_results(tmp_path, facts, monkeypatch):
    client, session, _, create, _, url, sessions = _application(tmp_path, facts)
    service = client._app.state.worker_activation_runtime_plan_review_service
    result = service.create(
        create,
        authenticated_operator_id=facts.operator_id,
        permission_verified=True,
        candidate_record_id=facts.candidate_record_id,
        idempotency_key=_headers(session)["Idempotency-Key"],
        correlation_id="test",
    )
    collection = service.list(
        authenticated_operator_id=facts.operator_id,
        permission_verified=True,
        candidate_record_id=facts.candidate_record_id,
        correlation_id="test",
    )
    foreign = sessions.create(
        OperatorCredential(
            operator_id="foreign",
            password_hash="unused",
            permissions=(
                INSTALLATION_WORKER_ACTIVATION_RUNTIME_PLAN_REVIEW_EVALUATE,
                INSTALLATION_WORKER_ACTIVATION_RUNTIME_PLAN_REVIEW_READ,
            ),
        )
    )
    monkeypatch.setattr(service, "get", lambda **kwargs: result)
    monkeypatch.setattr(service, "create", lambda *args, **kwargs: result)
    monkeypatch.setattr(service, "list", lambda **kwargs: collection)
    for response in (
        client.get(url, cookies=_cookies(foreign)),
        client.get(
            f"{url}/{result.record.runtime_plan_review_id}", cookies=_cookies(foreign)
        ),
        client.post(
            url,
            json=create.model_dump(mode="json"),
            cookies=_cookies(foreign),
            headers=_headers(foreign),
        ),
    ):
        assert response.status_code == 404
        assert response.json()["error_code"] == "evidence_not_found"
        assert facts.operator_id not in response.text


@pytest.mark.parametrize("target", ["collection", "result"])
def test_oversized_service_envelopes_fail_closed(tmp_path, facts, monkeypatch, target):
    from app.worker_activation_runtime_plan_review import contract as c

    client, session, _, create, _, url, _ = _application(tmp_path, facts)
    service = client._app.state.worker_activation_runtime_plan_review_service
    result = service.create(
        create,
        authenticated_operator_id=facts.operator_id,
        permission_verified=True,
        candidate_record_id=facts.candidate_record_id,
        idempotency_key="v056-envelope-bound",
        correlation_id="test",
    )
    assert isinstance(result, c.WorkerActivationRuntimePlanReviewResultV1)
    if target == "collection":
        bad = service.list(
            authenticated_operator_id=facts.operator_id,
            permission_verified=True,
            candidate_record_id=facts.candidate_record_id,
            correlation_id="test",
        ).model_copy(update={"items": (result.record,) * 16, "count": 16})
        method, path = "list", url
    else:
        bad = result.model_copy(
            update={
                "record": result.record.model_copy(
                    update={
                        "operator_id": "private-token" * c.MAX_MODEL_BYTES,
                    }
                ),
            }
        )
        method, path = "get", f"{url}/{result.record.runtime_plan_review_id}"
    assert len(c.canonical_json(bad)) > c.MAX_MODEL_BYTES
    monkeypatch.setattr(service, method, lambda **kwargs: bad)
    response = client.get(path, cookies=_cookies(session))
    assert response.status_code == 503
    assert len(response.content) < 16 * 1024
    assert "private-token" not in response.text
    assert response.json()["retryable"] is False
