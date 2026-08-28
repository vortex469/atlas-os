"""P3 transport locks for inert installation dispatch handoffs."""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI

from app.installation_dispatch_handoff.service import InstallationDispatchHandoffService
from app.installation_dispatch_handoff.store import InstallationDispatchHandoffStore
from app.installation_dispatch_handoff.test_contract import upstream
from app.installation_dispatch_handoff.test_service import NOW, Reader
from app.operator_auth.models import INSTALLATION_DESTINATION_SELECT, OperatorCredential
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.installation_dispatch_handoff import router
from app.testing import ASGITestClient

URL = "/api/v1/installation/dispatch-handoffs"
ORIGIN = "https://atlas.example"


def _application(
    tmp_path: Path, *, enabled: bool = True, rate_limit: int = 100, now=NOW
):
    candidate, intent, execution_request, create = upstream(tmp_path / "chain")
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
            permissions=(INSTALLATION_DESTINATION_SELECT,),
        )
    )
    store = InstallationDispatchHandoffStore(
        tmp_path / "handoffs.db",
        execution_requests=Reader(
            {execution_request.execution_request_id: execution_request},
            owner_attribute="missing",
        ),
        candidates=Reader(
            {candidate.candidate_record_id: candidate}, owner_attribute="owner_id"
        ),
        approvals=Reader(
            {intent.approval_intent_id: intent}, owner_attribute="operator_id"
        ),
        clock=lambda: now,
        id_factory=lambda: uuid.UUID("00000000-0000-4000-8000-000000000401"),
    )
    application.state.installation_dispatch_handoff_service = (
        InstallationDispatchHandoffService(store=store, enabled=enabled)
    )
    return ASGITestClient(application), session, application, create


def _headers(session, *, key: str = "dispatch-handoff-1") -> dict[str, str]:
    return {
        "Origin": ORIGIN,
        "X-Atlas-CSRF-Token": session.csrf_token,
        "Idempotency-Key": key,
    }


def _cookies(session) -> dict[str, str]:
    return {"atlas_operator_session": session.session_token}


def test_guards_success_owned_reads_exact_surface_and_fixed_false(
    tmp_path: Path,
) -> None:
    client, session, application, create = _application(tmp_path)
    payload = create.model_dump(mode="json")
    assert client.get(URL).status_code == 401
    assert client.post(URL, json=payload, cookies=_cookies(session)).status_code == 403
    assert (
        client.post(
            URL,
            json=payload,
            cookies=_cookies(session),
            headers={**_headers(session), "Origin": "https://foreign.example"},
        ).status_code
        == 403
    )
    made = client.post(
        URL, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    assert made.status_code == 200
    body = made.json()
    assert body["lifecycle_state"] == "prepared"
    assert body["evidence_provenance"] == "core_prepared_not_delivered"
    assert body["mode"] == "handoff-only"
    assert not any(
        body[name]
        for name in (
            "delivery_authorized",
            "agent_admission_authorized",
            "execution_authorized",
            "mutation_authorized",
            "replay_allowed",
        )
    )
    replay = client.post(
        URL, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    assert replay.status_code == 200
    assert replay.json() == body
    assert client.get(URL, cookies=_cookies(session)).json()["dispatch_handoffs"] == [
        body
    ]
    assert (
        client.get(
            f"{URL}/{body['dispatch_envelope_id']}", cookies=_cookies(session)
        ).json()
        == body
    )
    paths = {
        path: set(methods) for path, methods in application.openapi()["paths"].items()
    }
    assert paths == {
        URL: {"get", "post"},
        URL + "/{dispatch_envelope_id}": {"get"},
    }
    prohibited = {
        "install",
        "execute",
        "dispatch",
        "deliver",
        "deploy",
        "send-to-agent",
    }
    assert not any(
        segment in prohibited
        for path in paths
        for segment in path.removeprefix(URL).split("/")
    )


def test_permission_rate_limit_and_closed_input_gates(tmp_path: Path) -> None:
    client, session, application, create = _application(tmp_path / "permissions")
    denied = application.state.operator_session_store.create(
        OperatorCredential(
            operator_id="operator-denied", password_hash="unused", permissions=()
        )
    )
    assert client.get(URL, cookies=_cookies(denied)).status_code == 403

    client, session, _, create = _application(tmp_path / "rate", rate_limit=1)
    assert (
        client.post(
            URL,
            json=create.model_dump(mode="json"),
            headers=_headers(session),
            cookies=_cookies(session),
        ).status_code
        == 200
    )
    assert (
        client.post(
            URL,
            json=create.model_dump(mode="json"),
            headers=_headers(session, key="second"),
            cookies=_cookies(session),
        ).status_code
        == 429
    )

    client, session, _, create = _application(tmp_path / "body")
    cookies = _cookies(session)
    headers = {**_headers(session), "Content-Type": "application/json"}
    raw = json.dumps(create.model_dump(mode="json"))
    duplicate = raw[:-1] + ',"schema":"installation-dispatch-handoff-create-v1"}'
    assert (
        client.request(
            "POST", URL, content=duplicate, headers=headers, cookies=cookies
        ).status_code
        == 422
    )
    unknown = {**create.model_dump(mode="json"), "token": "secret"}
    assert (
        client.post(
            URL, json=unknown, headers=_headers(session, key="unknown"), cookies=cookies
        ).status_code
        == 422
    )
    nested: object = "leaf"
    for _ in range(18):
        nested = {"x": nested}
    assert (
        client.post(
            URL, json=nested, headers=_headers(session, key="nested"), cookies=cookies
        ).status_code
        == 422
    )
    assert (
        client.request(
            "POST", URL, content=b"{" + b"x" * 1024, headers=headers, cookies=cookies
        ).status_code
        == 413
    )
    assert (
        client.post(
            URL,
            json=create.model_dump(mode="json"),
            headers=_headers(session, key="not visible\t"),
            cookies=cookies,
        ).status_code
        == 422
    )


def test_ownership_stale_disabled_and_redacted_failures(tmp_path: Path) -> None:
    client, session, application, create = _application(tmp_path / "ownership")
    made = client.post(
        URL,
        json=create.model_dump(mode="json"),
        headers=_headers(session),
        cookies=_cookies(session),
    ).json()
    other = application.state.operator_session_store.create(
        OperatorCredential(
            operator_id="operator-b",
            password_hash="unused",
            permissions=(INSTALLATION_DESTINATION_SELECT,),
        )
    )
    missing = "00000000-0000-4000-8000-000000000499"
    absent = client.get(f"{URL}/{missing}", cookies=_cookies(session))
    foreign = client.get(
        f"{URL}/{made['dispatch_envelope_id']}", cookies=_cookies(other)
    )
    assert absent.status_code == foreign.status_code == 404
    assert absent.json() == foreign.json()

    stale_client, stale_session, _, stale_create = _application(
        tmp_path / "stale", now=NOW + timedelta(days=1)
    )
    stale = stale_client.post(
        URL,
        json=stale_create.model_dump(mode="json"),
        headers=_headers(stale_session),
        cookies=_cookies(stale_session),
    )
    assert stale.status_code == 409
    assert "traceback" not in stale.text.lower()
    assert "12:00" not in stale.text

    disabled_client, disabled_session, _, disabled_create = _application(
        tmp_path / "disabled", enabled=False
    )
    disabled = disabled_client.post(
        URL,
        json=disabled_create.model_dump(mode="json"),
        headers=_headers(disabled_session),
        cookies=_cookies(disabled_session),
    )
    assert disabled.status_code == 503
    assert "unavailable" in disabled.text.lower()
