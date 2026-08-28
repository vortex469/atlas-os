"""P3 transport locks for immutable installation approval evidence."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI

from app.installation_approval_intent.service import InstallationApprovalIntentService
from app.installation_approval_intent.store import InstallationApprovalIntentStore
from app.installation_candidate_admission.test_admission import admit
from app.installation_candidate_lifecycle.service import (
    InstallationCandidateLifecycleService,
)
from app.installation_candidate_lifecycle.store import InstallationCandidateRecordStore
from app.installation_candidate_lifecycle.test_lifecycle import NOW
from app.operator_auth.models import INSTALLATION_DESTINATION_SELECT, OperatorCredential
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.installation_approval_intent import router
from app.testing import ASGITestClient

SELECTION_ID = "00000000-0000-4000-8000-000000000001"
URL = "/api/v1/installation/candidate-approval-intents"
ORIGIN = "https://atlas.example"


@dataclass
class _Admissions:
    value: object

    async def assemble(self, *, item_id: str, selection_id: str, principal_id: str):
        del item_id, selection_id, principal_id
        return self.value


def _application(tmp_path: Path):
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    application.state.operator_auth_enabled = True
    application.state.operator_auth_trusted_origins = frozenset({ORIGIN})
    application.state.operator_mutation_rate_limiter = OperatorRateLimiter(100, 60)
    sessions = OperatorSessionStore(tmp_path / "sessions.db", 3600)
    application.state.operator_session_store = sessions
    created = sessions.create(
        OperatorCredential(
            operator_id="operator-a",
            password_hash="unused",
            permissions=(INSTALLATION_DESTINATION_SELECT,),
        )
    )
    candidates = InstallationCandidateRecordStore(
        tmp_path / "records.db", clock=lambda: NOW
    )
    lifecycle = InstallationCandidateLifecycleService(
        store=candidates, admissions=_Admissions(admit())
    )
    envelope = asyncio.run(
        lifecycle.preserve(
            owner_id="operator-a",
            item_id="example",
            selection_id=SELECTION_ID,
            idempotency_key="preserve-00000001",
        )
    )
    application.state.installation_approval_intent_service = (
        InstallationApprovalIntentService(
            store=InstallationApprovalIntentStore(
                tmp_path / "approval-intents.db",
                candidates=candidates,
                clock=lambda: NOW,
            )
        )
    )
    return ASGITestClient(application), created, application, envelope


def _headers(created, *, key: str = "approve-00000001") -> dict[str, str]:
    return {
        "Origin": ORIGIN,
        "X-Atlas-CSRF-Token": created.csrf_token,
        "Idempotency-Key": key,
    }


def test_auth_exact_surface_redaction_and_own_reads(tmp_path: Path) -> None:
    client, created, application, envelope = _application(tmp_path)
    assert client.get(URL).status_code == 401
    cookies = {"atlas_operator_session": created.session_token}
    response = client.post(
        URL,
        json={"candidate_record_id": envelope.candidate_record_id},
        headers=_headers(created),
        cookies=cookies,
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "schema",
        "approval_intent_id",
        "operator_id",
        "recorded_at",
        "approved_subject",
        "statement",
        "intent_fingerprint",
    }
    assert set(body["approved_subject"]) == {
        "candidate_record_id",
        "candidate_envelope_fingerprint",
        "admission_fingerprint",
        "candidate_record_fingerprint",
    }
    assert body["statement"] == "operator_approved_exact_non_executable_candidate"
    serialized = str(body).lower()
    assert not any(
        token in serialized
        for token in ("credential", "payload", "command", "target", "workflow", "dispatch")
    )
    assert client.get(URL, cookies=cookies).json()["approval_intents"] == [body]
    assert client.get(
        f"{URL}/{body['approval_intent_id']}", cookies=cookies
    ).json() == body
    paths = {path: set(methods) for path, methods in application.openapi()["paths"].items()}
    assert paths == {
        URL: {"get", "post"},
        URL + "/{approval_intent_id}": {"get"},
    }


def test_append_guards_replay_and_body_bounds(tmp_path: Path) -> None:
    client, created, _, envelope = _application(tmp_path)
    cookies = {"atlas_operator_session": created.session_token}
    payload = {"candidate_record_id": envelope.candidate_record_id}
    assert client.post(URL, json=payload, cookies=cookies).status_code == 403
    headers = _headers(created)
    assert client.request(
        "POST",
        URL,
        content=b'{"candidate_record_id":"a","candidate_record_id":"b"}',
        headers={**headers, "Content-Type": "application/json"},
        cookies=cookies,
    ).status_code == 422
    assert client.request(
        "POST",
        URL,
        content=b"{" + b"x" * 8192,
        headers={**headers, "Content-Type": "application/json"},
        cookies=cookies,
    ).status_code == 413
    assert client.post(
        URL,
        json=payload,
        headers=_headers(created, key="not visible\t"),
        cookies=cookies,
    ).status_code == 422
    first = client.post(URL, json=payload, headers=headers, cookies=cookies)
    replay = client.post(URL, json=payload, headers=headers, cookies=cookies)
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    for method in ("DELETE", "PATCH", "PUT"):
        assert client.request(method, URL, cookies=cookies).status_code == 405


def test_missing_and_cross_operator_are_indistinguishable(tmp_path: Path) -> None:
    client, created, application, envelope = _application(tmp_path)
    cookies = {"atlas_operator_session": created.session_token}
    made = client.post(
        URL,
        json={"candidate_record_id": envelope.candidate_record_id},
        headers=_headers(created),
        cookies=cookies,
    ).json()
    sessions = application.state.operator_session_store
    other = sessions.create(
        OperatorCredential(
            operator_id="operator-b",
            password_hash="unused",
            permissions=(INSTALLATION_DESTINATION_SELECT,),
        )
    )
    other_cookies = {"atlas_operator_session": other.session_token}
    missing = "00000000-0000-4000-8000-000000000099"
    own_lookup = client.get(f"{URL}/{missing}", cookies=cookies)
    cross_lookup = client.get(
        f"{URL}/{made['approval_intent_id']}", cookies=other_cookies
    )
    assert own_lookup.status_code == cross_lookup.status_code == 404
    assert own_lookup.json() == cross_lookup.json()
    create_cross = client.post(
        URL,
        json={"candidate_record_id": envelope.candidate_record_id},
        headers=_headers(other),
        cookies=other_cookies,
    )
    assert create_cross.status_code == 404
