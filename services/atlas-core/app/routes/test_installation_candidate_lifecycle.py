"""P3 transport locks for inert installation candidate records."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI

from app.installation_candidate_admission.test_admission import admit
from app.installation_candidate_lifecycle.service import (
    InstallationCandidateLifecycleService,
)
from app.installation_candidate_lifecycle.store import InstallationCandidateRecordStore
from app.installation_candidate_lifecycle.test_lifecycle import NOW
from app.operator_auth.models import INSTALLATION_DESTINATION_SELECT, OperatorCredential
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.installation_candidate_lifecycle import router
from app.testing import ASGITestClient

SELECTION_ID = "00000000-0000-4000-8000-000000000001"
URL = "/api/v1/installation/candidate-records"
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
    created = sessions.create(OperatorCredential(operator_id="operator-a", password_hash="unused", permissions=(INSTALLATION_DESTINATION_SELECT,)))
    service = InstallationCandidateLifecycleService(
        store=InstallationCandidateRecordStore(
            tmp_path / "records.db", clock=lambda: NOW
        ),
        admissions=_Admissions(admit()),
    )
    application.state.installation_candidate_lifecycle_service = service
    return ASGITestClient(application), created, application


def _mutation(created) -> dict[str, str]:
    return {"Origin": ORIGIN, "X-Atlas-CSRF-Token": created.csrf_token, "Idempotency-Key": "preserve-00000001"}


def test_auth_guards_exact_surface_and_redacted_projection(tmp_path: Path) -> None:
    client, created, application = _application(tmp_path)
    payload = {"item_id": "example", "selection_id": SELECTION_ID}
    assert client.get(URL).status_code == 401
    response = client.post(URL, json=payload, headers=_mutation(created), cookies={"atlas_operator_session": created.session_token})
    assert response.status_code == 200
    body = response.json()
    assert "owner_id" not in body
    assert body["lifecycle_state"] == "active"
    assert all(body["candidate_record"][field] is False for field in ("approved", "executable", "deployable", "dispatchable", "agent_execution_supported"))
    paths = {path: set(methods) for path, methods in application.openapi()["paths"].items()}
    assert paths == {URL: {"get", "post"}, URL + "/{candidate_record_id}": {"get", "delete"}}


def test_list_get_delete_tombstone_and_cross_operator_absence(tmp_path: Path) -> None:
    client, created, _ = _application(tmp_path)
    cookies = {"atlas_operator_session": created.session_token}
    payload = {"item_id": "example", "selection_id": SELECTION_ID}
    made = client.post(URL, json=payload, headers=_mutation(created), cookies=cookies).json()
    item_url = f"{URL}/{made['candidate_record_id']}"
    assert client.get(URL, cookies=cookies).json()["records"] == [made]
    assert client.get(item_url, cookies=cookies).json() == made
    assert client.request(
        "DELETE", item_url, headers=_mutation(created), cookies=cookies
    ).status_code == 204
    assert client.get(item_url, cookies=cookies).status_code == 404
    assert client.post(URL, json=payload, headers=_mutation(created), cookies=cookies).status_code == 409


def test_mutation_controls_and_body_bounds(tmp_path: Path) -> None:
    client, created, _ = _application(tmp_path)
    cookies = {"atlas_operator_session": created.session_token}
    payload = {"item_id": "example", "selection_id": SELECTION_ID}
    assert client.post(URL, json=payload, cookies=cookies).status_code == 403
    headers = _mutation(created)
    assert client.request("POST", URL, content=b'{"item_id":"example","item_id":"other"}', headers={**headers, "Content-Type": "application/json"}, cookies=cookies).status_code == 422
    assert client.request("POST", URL, content=b"{" + b"x" * 8192, headers={**headers, "Content-Type": "application/json"}, cookies=cookies).status_code == 413
