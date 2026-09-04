"""P3 API locks for v0.39 worker queue reservation evidence."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Literal

from fastapi import FastAPI

from app.operator_auth.models import (
    INSTALLATION_WORKER_QUEUE_RESERVATION_READ,
    INSTALLATION_WORKER_QUEUE_RESERVATION_RECORD,
    OperatorCredential,
)
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.worker_queue_reservation import router
from app.testing import ASGITestClient
from app.worker_queue_reservation.test_contract import RESERVATION_ID
from app.worker_queue_reservation.test_service_store import _service

ORIGIN = "https://atlas.example"


def _application(
    tmp_path: Path,
    *,
    permissions=None,
    rate_limit: int = 100,
    second: int = 34,
    evidence=None,
    queue_reference=None,
    service_present: bool = True,
    boundary_enabled: bool = True,
):
    (
        queue_service,
        _,
        evidence_reader,
        queue_reader,
        id_factory,
        stub,
        status,
        intake,
        create,
    ) = _service(
        tmp_path / "service",
        evidence=evidence,
        queue_reference=queue_reference,
        second=second,
        enabled=boundary_enabled,
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
                INSTALLATION_WORKER_QUEUE_RESERVATION_RECORD,
                INSTALLATION_WORKER_QUEUE_RESERVATION_READ,
            ),
        )
    )
    if service_present:
        application.state.worker_queue_reservation_service = queue_service
    collection = (
        f"/api/v1/installation/candidate-records/{stub.candidate_record_id}"
        "/worker-queue-reservations"
    )
    return (
        ASGITestClient(application), session, application, stub, status, intake,
        create, evidence_reader, queue_reader, id_factory, collection, sessions,
    )


def _cookies(session):
    return {"atlas_operator_session": session.session_token}


def _headers(session, key: str = "worker-queue-reservation-key-1"):
    return {
        "Origin": ORIGIN,
        "X-Atlas-CSRF-Token": session.csrf_token,
        "Idempotency-Key": key,
    }


def test_auth_csrf_origin_rate_limit_and_create_list_get_success(
    tmp_path: Path,
) -> None:
    (
        client, session, _, stub, _, _, create, evidence_reader, queue_reader,
        id_factory, url, _,
    ) = _application(tmp_path)
    payload = create.model_dump(mode="json")
    assert client.get(url).status_code == 401
    assert client.post(url, json=payload, cookies=_cookies(session)).status_code == 403
    assert client.post(
        url, json=payload, cookies=_cookies(session),
        headers={**_headers(session), "X-Atlas-CSRF-Token": "wrong"},
    ).status_code == 403
    assert client.post(
        url, json=payload, cookies=_cookies(session),
        headers={**_headers(session), "Origin": "https://foreign.example"},
    ).status_code == 403
    made = client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    assert made.status_code == 201
    body = made.json()
    assert body["disposition"] == "recorded"
    assert body["reservation"]["eligibility"] == "worker_queue_reservation_recorded"
    assert body["status"]["lifecycle"] == "active"
    assert body["reservation"]["evidence_only"]
    for field in (
        "live_enqueue_allowed", "dequeue_allowed", "worker_start_allowed",
        "execution_start_allowed", "dispatch_allowed", "agent_invocation_allowed",
        "workflow_start_allowed", "provider_mutation_allowed",
        "repository_mutation_allowed", "in_guest_mutation_allowed",
    ):
        assert body["reservation"][field] is False
    listed = client.get(url, cookies=_cookies(session)).json()
    assert listed["count"] == 1 and listed["items"][0]["reservation"] == body["reservation"]
    assert client.get(
        f"{url}/{RESERVATION_ID}", cookies=_cookies(session)
    ).json()["reservation"] == body["reservation"]
    duplicate = client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    assert duplicate.status_code == 200
    assert evidence_reader.calls == queue_reader.calls == id_factory.calls == 1
    assert body["reservation"]["operator_id"] == stub.operator_id

    values = _application(tmp_path / "limited", rate_limit=1)
    limited, limited_session, _, _, _, _, limited_create, *tail = values
    limited_url = tail[-2]
    assert limited.post(
        limited_url, json=limited_create.model_dump(mode="json"),
        cookies=_cookies(limited_session),
        headers=_headers(limited_session, "worker-queue-key-one"),
    ).status_code == 201
    limited_result = limited.post(
        limited_url, json=limited_create.model_dump(mode="json"),
        cookies=_cookies(limited_session),
        headers=_headers(limited_session, "worker-queue-key-two"),
    )
    assert limited_result.status_code == 429
    assert limited_result.json()["error"]["redacted"]


def test_create_and_read_permissions_are_independent(tmp_path: Path) -> None:
    values = _application(
        tmp_path / "read",
        permissions=(INSTALLATION_WORKER_QUEUE_RESERVATION_READ,),
    )
    client, session, _, _, _, _, create, *_, url, _ = values
    assert client.get(url, cookies=_cookies(session)).status_code == 200
    assert client.post(
        url, json=create.model_dump(mode="json"), cookies=_cookies(session),
        headers=_headers(session),
    ).status_code == 403
    values = _application(
        tmp_path / "record",
        permissions=(INSTALLATION_WORKER_QUEUE_RESERVATION_RECORD,),
    )
    client, session, _, _, _, _, create, *_, url, _ = values
    assert client.get(url, cookies=_cookies(session)).status_code == 403
    assert client.post(
        url, json=create.model_dump(mode="json"), cookies=_cookies(session),
        headers=_headers(session),
    ).status_code == 201


def test_body_query_method_duplicate_nesting_and_idempotency_validation(
    tmp_path: Path,
) -> None:
    client, session, _, _, _, _, create, *_, url, _ = _application(tmp_path)
    payload = create.model_dump(mode="json")
    cookies, headers = _cookies(session), _headers(session)
    assert client.post(
        url, content=b"{}", cookies=cookies,
        headers={**headers, "Content-Type": "text/plain"},
    ).status_code == 415
    duplicate = json.dumps(payload)[:-1] + ',"schema":"duplicate"}'
    assert client.post(
        url, content=duplicate, cookies=cookies,
        headers={**headers, "Content-Type": "application/json"},
    ).status_code == 422
    assert client.post(
        url, json={**payload, "operator_id": "operator-a"},
        cookies=cookies, headers=headers,
    ).status_code == 422
    nested: object = "bottom"
    for _ in range(17):
        nested = {"nested": nested}
    assert client.post(
        url, json=nested, cookies=cookies, headers=headers
    ).status_code == 422
    assert client.post(
        url, content=b" " * (16 * 1024 + 1), cookies=cookies,
        headers={**headers, "Content-Type": "application/json"},
    ).status_code == 413
    for invalid in (None, "short", "contains space key", "x" * 129, "bad\x7f-key-value"):
        exact = {
            name: value for name, value in headers.items()
            if name != "Idempotency-Key"
        }
        if invalid is not None:
            exact["Idempotency-Key"] = invalid
        assert client.post(
            url, json=payload, cookies=cookies, headers=exact
        ).status_code == 422
    assert client.post(
        url + "?enqueue=true", json=payload, cookies=cookies, headers=headers
    ).status_code == 422
    assert client.get(url + "?limit=1", cookies=cookies).status_code == 422
    assert client.request("PUT", url).status_code == 405
    assert client.request("POST", f"{url}/{RESERVATION_ID}").status_code == 405


def test_missing_service_default_disabled_stale_mismatch_and_limits_redacted(
    tmp_path: Path,
) -> None:
    values = _application(tmp_path / "missing", service_present=False)
    client, session, _, _, _, _, create, *_, url, _ = values
    result = client.post(
        url, json=create.model_dump(mode="json"), cookies=_cookies(session),
        headers=_headers(session),
    )
    assert result.status_code == 503 and result.json()["error"]["redacted"]

    values = _application(tmp_path / "disabled", boundary_enabled=False)
    client, session, _, _, _, _, create, *_, url, _ = values
    assert client.post(
        url, json=create.model_dump(mode="json"), cookies=_cookies(session),
        headers=_headers(session),
    ).status_code == 409

    values = _application(tmp_path / "stale", second=50)
    client, session, _, _, _, _, create, *_, url, _ = values
    assert client.post(
        url, json=create.model_dump(mode="json"), cookies=_cookies(session),
        headers=_headers(session),
    ).status_code == 409

    values = _application(tmp_path / "mismatch")
    client, session, _, _, _, _, create, *_, url, _ = values
    payload = create.model_dump(mode="json")
    payload["queue_intake_reference_fingerprint"]["value"] = "f" * 64
    mismatch = client.post(
        url, json=payload, cookies=_cookies(session),
        headers=_headers(session, "queue-linkage-mismatch-key"),
    )
    assert mismatch.status_code == 409 and "/opt/" not in mismatch.text.lower()
    payload = create.model_dump(mode="json")
    payload["inherited_limits_fingerprint"]["value"] = "e" * 64
    assert client.post(
        url, json=payload, cookies=_cookies(session),
        headers=_headers(session, "queue-limits-mismatch-key"),
    ).status_code == 409


def test_owner_isolation_and_indistinguishable_foreign_get(tmp_path: Path) -> None:
    values = _application(tmp_path)
    client, session, _, stub, _, _, create, *_, url, sessions = values
    assert client.post(
        url, json=create.model_dump(mode="json"), cookies=_cookies(session),
        headers=_headers(session),
    ).status_code == 201
    foreign = sessions.create(
        OperatorCredential(
            operator_id="operator-b", password_hash="unused",
            permissions=(INSTALLATION_WORKER_QUEUE_RESERVATION_READ,),
        )
    )
    assert client.get(
        f"{url}/{RESERVATION_ID}", cookies=_cookies(foreign)
    ).status_code == 404
    assert client.get(url, cookies=_cookies(foreign)).json()["items"] == []
    hidden = url.replace(
        stub.candidate_record_id, "bf819229-618a-44f5-a14e-4c0f5878ea14"
    )
    assert client.get(
        f"{hidden}/{RESERVATION_ID}", cookies=_cookies(session)
    ).status_code == 404
    assert client.get(hidden, cookies=_cookies(session)).json()["items"] == []


def test_openapi_exactness_and_no_effect_sibling_routes(tmp_path: Path) -> None:
    _, _, application, *_ = _application(tmp_path)
    paths = application.openapi()["paths"]
    collection = next(
        path for path in paths if path.endswith("/worker-queue-reservations")
    )
    item = next(
        path
        for path in paths
        if path.endswith("/worker-queue-reservations/{reservation_id}")
    )
    assert set(paths) == {collection, item}
    assert set(paths[collection]) == {"get", "post"}
    assert set(paths[item]) == {"get"}
    post = paths[collection]["post"]
    assert post["requestBody"]["required"] is True
    idempotency = next(
        value for value in post["parameters"]
        if value["name"] == "Idempotency-Key"
    )
    assert idempotency["required"] is True
    assert idempotency["schema"]["minLength"] == 16
    for forbidden in (
        "enqueue", "dequeue", "dispatch", "execute", "worker-start", "start",
        "run", "retry", "resend", "deploy", "rollback", "agent", "workflow",
        "mutation",
    ):
        assert f"{collection}/{forbidden}" not in paths
        assert f"{item}/{forbidden}" not in paths


def test_route_has_no_queue_worker_execution_or_mutation_consumers() -> None:
    path = Path(__file__).with_name("worker_queue_reservation.py")
    tree = ast.parse(path.read_text())
    imports = {
        alias.name if isinstance(node, ast.Import) else node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden = (
        "operational_dispatch", "execution_candidates", "atlas_agent",
        "execution_worker", "provider", "repository", "workflow",
        "execution_intake", "docker", "subprocess", "socket", "httpx",
        "requests",
    )
    assert not [
        name for name in imports if any(marker in name for marker in forbidden)
    ]


def test_v039_authority_limits_and_exact_duplicate_remain_evidence_only(
    tmp_path: Path,
) -> None:
    from app.worker_queue_reservation.contract import (
        NoAuthorityV1,
        WorkerQueueReservationAuditEvidenceV1,
    )

    values = _application(tmp_path)
    client, session, _, stub, _, _, create, *_, url, _ = values
    payload = create.model_dump(mode="json")
    first = client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    duplicate = client.post(
        url, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    assert first.status_code == 201
    assert duplicate.status_code == 200
    assert duplicate.json()["disposition"] == "exact_duplicate"
    record = first.json()["reservation"]
    assert record["inherited_limits"] == record["queue_intake_reference"][
        "inherited_limits"
    ]
    assert record["linkage"]["inherited_limits_fingerprint"] == record[
        "inherited_limits"
    ]["limits_fingerprint"]
    assert record["linkage"]["worker_admission_stub_fingerprint"] == stub.model_dump(
        mode="json"
    )["stub_fingerprint"]
    for model in (NoAuthorityV1, WorkerQueueReservationAuditEvidenceV1):
        for name, field in model.model_fields.items():
            if name.endswith(("_allowed", "_attempted")):
                assert field.annotation == Literal[False]


def test_v039_has_no_runtime_agent_worker_or_mutation_consumer() -> None:
    repository_root = Path(__file__).parents[4]
    package = Path(__file__).parents[1] / "worker_queue_reservation"
    allowed = {package / name for name in ("contract.py", "service.py", "store.py")}
    route = Path(__file__).with_name("worker_queue_reservation.py")
    allowed.add(route)
    allowed.add(Path(__file__).parents[1] / "config" / "settings.py")
    allowed.add(Path(__file__).parents[1] / "worker_intake_admission" / "contract.py")
    allowed.add(Path(__file__).parents[1] / "worker_intake_admission" / "service.py")
    allowed.add(
        Path(__file__).parents[1]
        / "installation_live_enqueue_admission"
        / "contract.py"
    )
    allowed.add(
        Path(__file__).parents[1]
        / "installation_live_enqueue_admission"
        / "service.py"
    )
    allowed.add(
        Path(__file__).parents[1]
        / "installation_one_shot_live_enqueue"
        / "contract.py"
    )
    allowed.add(
        Path(__file__).parents[1]
        / "installation_one_shot_live_enqueue"
        / "service.py"
    )
    markers = (
        "app.worker_queue_reservation",
        "WorkerQueueReservationV1",
        "worker-queue-reservation-v1",
        "worker_queue_reservations",
    )
    roots = (
        Path(__file__).parents[1],
        repository_root / "services" / "atlas-agent" / "app",
        repository_root / "services" / "atlas-execution-worker",
    )
    violations = []
    for root in roots:
        for path in root.rglob("*.py"):
            if path.name.startswith("test_") or path in allowed or package in path.parents:
                continue
            source = path.read_text(encoding="utf-8")
            violations.extend(
                f"{path.relative_to(repository_root)} -> {marker}"
                for marker in markers
                if marker in source
            )
    assert violations == []
    service_source = (package / "service.py").read_text(encoding="utf-8").lower()
    for forbidden in (
        "subprocess", "docker", "podman", "shell", "socket", "httpx",
        "requests", "enqueue(", "dequeue(", "dispatch(", "execute(",
        "start_worker", "start_workflow", "agent invocation", "rollback(",
    ):
        assert forbidden not in service_source


def test_v039_home_assistant_stays_blocked_without_deployment_artifact() -> None:
    repository_root = Path(__file__).parents[4]
    agent_models = repository_root / "services/atlas-agent/app/candidate_planning/models.py"
    assert "install-container" not in agent_models.read_text(encoding="utf-8")
    artifacts = [
        path.relative_to(repository_root)
        for root in (repository_root / "compose", repository_root / "deploy")
        if root.exists()
        for path in root.rglob("*")
        if path.is_file()
        and "home-assistant" in path.name.lower()
        and path.suffix.lower() in {".yaml", ".yml", ".json", ".toml"}
    ]
    assert artifacts == []
