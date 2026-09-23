"""API/authz/OpenAPI locks for the guarded v0.65 Core evidence API."""

from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI

from app.control_plane import (
    ControlPlaneEvidenceService,
    ControlPlaneEvidenceStore,
    ControlPlaneInputV1,
    ControlPlaneLineageV1,
    ControlPlanePolicyV1,
    input_fingerprint,
    lineage_fingerprint,
    policy_fingerprint,
)
from app.operator_auth.models import (
    CONTROL_PLANE_EVIDENCE_READ,
    CONTROL_PLANE_EVIDENCE_RECORD,
    OperatorCredential,
)
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.control_plane_evidence import router
from app.testing import ASGITestClient

URL = "/api/v1/control-plane-evidence"
ORIGIN = "https://atlas.example"
OWNER = "owner-a"
NOW = "2026-09-23T12:00:00Z"
PREDECESSOR = "a" * 64


def _input() -> ControlPlaneInputV1:
    lineage_raw = {"lineage_id": "lineage-1", "predecessor_fingerprint": PREDECESSOR}
    lineage_raw["lineage_fingerprint"] = lineage_fingerprint(lineage_raw)
    lineage = ControlPlaneLineageV1.model_validate(lineage_raw)
    raw = {
        "subject_id": "subject-1",
        "lineage": lineage,
        "policy": ControlPlanePolicyV1(),
        "observed_fingerprint": "0" * 64,
        "observed_at": NOW,
        "valid_until": "2026-09-23T12:05:00Z",
    }
    raw["observed_fingerprint"] = input_fingerprint(raw)
    return ControlPlaneInputV1.model_validate(raw)


def _application(tmp_path: Path, *, enabled: bool = True, permissions=None, owner: str = OWNER):
    tmp_path.mkdir(parents=True, exist_ok=True)
    item = _input()
    service = ControlPlaneEvidenceService(
        store=ControlPlaneEvidenceStore(tmp_path / "evidence.db"),
        clock=lambda: datetime(2026, 9, 23, 12, tzinfo=UTC),
        expected_lineage_fingerprint=item.lineage.lineage_fingerprint,
        expected_policy_fingerprint=policy_fingerprint(item.policy),
        expected_predecessor_fingerprint=PREDECESSOR,
        enabled=enabled,
    )
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    application.state.operator_auth_enabled = True
    application.state.operator_auth_trusted_origins = frozenset({ORIGIN})
    application.state.operator_mutation_rate_limiter = OperatorRateLimiter(100, 60)
    sessions = OperatorSessionStore(tmp_path / "sessions.db", 3600)
    session = sessions.create(
        OperatorCredential(
            operator_id=owner,
            password_hash="unused",
            permissions=permissions or (CONTROL_PLANE_EVIDENCE_RECORD, CONTROL_PLANE_EVIDENCE_READ),
        )
    )
    application.state.operator_session_store = sessions
    application.state.control_plane_evidence_service = service
    return ASGITestClient(application), session, item


def _cookies(session):
    return {"atlas_operator_session": session.session_token}


def _headers(session, key="evidence-key"):
    return {"Origin": ORIGIN, "X-Atlas-CSRF-Token": session.csrf_token, "Idempotency-Key": key}


def _payload(item, owner=OWNER):
    return {"owner_id": owner, "input": item.model_dump(mode="json"), "idempotency_key": "body-key"}


def test_guarded_owner_bound_create_list_get_and_default_off(tmp_path: Path) -> None:
    client, session, item = _application(tmp_path)
    cookies = _cookies(session)
    made = client.post(URL, json=_payload(item), cookies=cookies, headers=_headers(session))
    assert made.status_code == 201
    assert made.json()["subject_id"] == item.subject_id
    assert client.get(URL, cookies=cookies).json()["records"][0]["owner_id"] == OWNER
    assert client.get(f"{URL}/{item.subject_id}", cookies=cookies).status_code == 200

    disabled, disabled_session, disabled_item = _application(tmp_path / "disabled", enabled=False)
    assert disabled.post(URL, json=_payload(disabled_item), cookies=_cookies(disabled_session), headers=_headers(disabled_session)).status_code == 503
    assert disabled.get(URL, cookies=_cookies(disabled_session)).status_code == 503


def test_authz_forgery_bounds_and_methods(tmp_path: Path) -> None:
    client, session, item = _application(tmp_path)
    assert client.get(URL).status_code == 401
    assert client.post(URL, json=_payload(item), cookies=_cookies(session)).status_code == 403
    forged = _payload(item)
    forged["input"]["authority_granted"] = True
    assert client.post(URL, json=forged, cookies=_cookies(session), headers=_headers(session)).status_code == 422
    assert client.post(URL, content=b"{}", cookies=_cookies(session), headers={**_headers(session), "Content-Type": "text/plain"}).status_code == 415
    assert client.request("PUT", URL).status_code == 405
    assert client.post(f"{URL}/subject-1").status_code == 405


def test_foreign_owner_is_hidden_and_openapi_is_closed(tmp_path: Path) -> None:
    client, session, item = _application(tmp_path)
    made = client.post(URL, json=_payload(item), cookies=_cookies(session), headers=_headers(session))
    assert made.status_code == 201
    foreign, foreign_session, _ = _application(tmp_path, owner="owner-b")
    hidden = foreign.get(f"{URL}/{item.subject_id}", cookies=_cookies(foreign_session))
    assert hidden.status_code == 404
    paths = client._app.openapi()["paths"]
    assert set(paths) == {URL, f"{URL}/{{subject_id}}"}
    assert set(paths[URL]) == {"get", "post"}
    assert set(paths[f"{URL}/{{subject_id}}"] ) == {"get"}
