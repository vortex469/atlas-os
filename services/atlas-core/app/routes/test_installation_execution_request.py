"""P3 transport locks for inert installation execution requests."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI

from app.installation_candidate_lifecycle.test_lifecycle import NOW
from app.installation_execution_request.contract import (
    InstallationExecutionRequestCreateV1,
)
from app.installation_execution_request.service import (
    InstallationExecutionRequestService,
)
from app.installation_execution_request.store import (
    InstallationExecutionRequestStore,
)
from app.installation_execution_request.test_contract import chain
from app.operator_auth.models import INSTALLATION_DESTINATION_SELECT, OperatorCredential
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.installation_execution_request import router
from app.testing import ASGITestClient

URL = "/api/v1/installation/execution-requests"
ORIGIN = "https://atlas.example"


class _Candidates:
    def __init__(self, value) -> None:
        self.value = value

    def get(self, *, owner_id: str, candidate_record_id: str):
        if (
            owner_id != self.value.owner_id
            or candidate_record_id != self.value.candidate_record_id
        ):
            raise KeyError
        return self.value


class _Approvals:
    def __init__(self, value) -> None:
        self.value = value

    def get(self, *, operator_id: str, approval_intent_id: str):
        if (
            operator_id != self.value.operator_id
            or approval_intent_id != self.value.approval_intent_id
        ):
            raise KeyError
        return self.value


def _application(
    tmp_path: Path, *, enabled: bool = True, rate_limit: int = 100, now=NOW
):
    envelope, intent, create = chain(tmp_path / "chain")
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
    store = InstallationExecutionRequestStore(
        tmp_path / "execution-requests.db",
        candidates=_Candidates(envelope),
        approvals=_Approvals(intent),
        clock=lambda: now,
        id_factory=lambda: uuid.UUID("00000000-0000-4000-8000-000000000301"),
    )
    application.state.installation_execution_request_service = (
        InstallationExecutionRequestService(store=store, enabled=enabled)
    )
    return ASGITestClient(application), session, application, create


def _headers(session, *, key: str = "execution-request-1") -> dict[str, str]:
    return {
        "Origin": ORIGIN,
        "X-Atlas-CSRF-Token": session.csrf_token,
        "Idempotency-Key": key,
    }


def _cookies(session) -> dict[str, str]:
    return {"atlas_operator_session": session.session_token}


def test_auth_guards_success_exact_surface_and_fixed_false_authority(
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
        URL,
        json=payload,
        cookies=_cookies(session),
        headers=_headers(session),
    )
    assert made.status_code == 200
    body = made.json()
    assert body["lifecycle_state"] == "recorded"
    assert body["evidence_provenance"] == (
        "operator_submitted_agent_validation_evidence"
    )
    assert body["mode"] == "record-only"
    assert not any(
        body[name]
        for name in (
            "execution_authorized",
            "dispatch_allowed",
            "agent_invocation_allowed",
            "mutation_allowed",
            "replay_allowed",
        )
    )
    replay = client.post(
        URL,
        json=payload,
        cookies=_cookies(session),
        headers=_headers(session),
    )
    assert replay.status_code == 200
    assert replay.json() == body
    assert client.get(URL, cookies=_cookies(session)).json()["execution_requests"] == [
        body
    ]
    assert client.get(
        f"{URL}/{body['execution_request_id']}", cookies=_cookies(session)
    ).json() == body
    paths = {path: set(methods) for path, methods in application.openapi()["paths"].items()}
    assert paths == {
        URL: {"get", "post"},
        URL + "/{execution_request_id}": {"get"},
    }
    for path in paths:
        assert not any(
            token in path.removeprefix(URL).split("/")
            for token in ("install", "execute", "dispatch", "deploy")
        )


def test_permission_rate_limit_body_and_idempotency_gates(tmp_path: Path) -> None:
    client, session, application, create = _application(tmp_path / "permissions")
    denied = application.state.operator_session_store.create(
        OperatorCredential(
            operator_id="operator-denied", password_hash="unused", permissions=()
        )
    )
    assert client.get(URL, cookies=_cookies(denied)).status_code == 403

    client, session, _, create = _application(tmp_path / "rate", rate_limit=1)
    cookies = _cookies(session)
    headers = _headers(session)
    payload = create.model_dump(mode="json")
    assert client.post(URL, json=payload, headers=headers, cookies=cookies).status_code == 200
    assert (
        client.post(
            URL,
            json=payload,
            headers=_headers(session, key="execution-request-2"),
            cookies=cookies,
        ).status_code
        == 429
    )

    client, session, _, create = _application(tmp_path / "body")
    cookies = _cookies(session)
    headers = {**_headers(session), "Content-Type": "application/json"}
    raw = json.dumps(create.model_dump(mode="json"))
    duplicate = raw[:-1] + ',"schema":"installation-execution-request-create-v1"}'
    assert client.request("POST", URL, content=duplicate, headers=headers, cookies=cookies).status_code == 422
    unknown = create.model_dump(mode="json")
    unknown["token"] = "secret"
    assert client.post(URL, json=unknown, headers=_headers(session, key="unknown"), cookies=cookies).status_code == 422
    nested: object = "leaf"
    for _ in range(18):
        nested = {"x": nested}
    assert client.post(URL, json=nested, headers=_headers(session, key="nested"), cookies=cookies).status_code == 422
    assert client.request("POST", URL, content=b"{" + b"x" * (96 * 1024), headers=headers, cookies=cookies).status_code == 413
    assert client.post(URL, json=create.model_dump(mode="json"), headers=_headers(session, key="not visible\t"), cookies=cookies).status_code == 422


def test_ownership_staleness_disabled_and_redacted_failures(tmp_path: Path) -> None:
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
    missing = "00000000-0000-4000-8000-000000000399"
    absent = client.get(f"{URL}/{missing}", cookies=_cookies(session))
    foreign = client.get(
        f"{URL}/{made['execution_request_id']}", cookies=_cookies(other)
    )
    assert absent.status_code == foreign.status_code == 404
    assert absent.json() == foreign.json()

    stale_client, stale_session, _, stale_create = _application(
        tmp_path / "stale", now=NOW + timedelta(seconds=31)
    )
    stale = stale_client.post(
        URL,
        json=stale_create.model_dump(mode="json"),
        headers=_headers(stale_session),
        cookies=_cookies(stale_session),
    )
    assert stale.status_code == 409
    assert "11:59" not in stale.text
    assert "traceback" not in stale.text.lower()

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

    mismatch_client, mismatch_session, _, mismatch_create = _application(
        tmp_path / "mismatch"
    )
    changed = deepcopy(mismatch_create.model_dump(mode="json"))
    changed["candidate_record_id"] = missing
    mismatch = mismatch_client.post(
        URL,
        json=InstallationExecutionRequestCreateV1.model_validate(changed).model_dump(
            mode="json"
        ),
        headers=_headers(mismatch_session),
        cookies=_cookies(mismatch_session),
    )
    assert mismatch.status_code == 404
    assert "operator-a" not in mismatch.text
