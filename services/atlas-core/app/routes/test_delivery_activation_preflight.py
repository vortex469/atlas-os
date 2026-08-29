"""P3 API locks for non-authorizing delivery activation preflight evidence."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI

from app.delivery_activation_preflight.test_contract import (
    OPERATOR,
    PREFLIGHT_ID,
    _create,
)
from app.delivery_activation_preflight.test_service import _service
from app.operator_auth.models import (
    INSTALLATION_DELIVERY_PREFLIGHT_CREATE,
    INSTALLATION_DELIVERY_PREFLIGHT_READ,
    OperatorCredential,
)
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.delivery_activation_preflight import router
from app.testing import ASGITestClient

URL = "/api/v1/installation-delivery-preflights"
ORIGIN = "https://atlas.example"


def _application(tmp_path: Path, *, permissions=None, rate_limit: int = 100):
    service, reader, clock, evidence = _service(tmp_path / "service")
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    application.state.operator_auth_enabled = True
    application.state.operator_auth_trusted_origins = frozenset({ORIGIN})
    application.state.operator_mutation_rate_limiter = OperatorRateLimiter(rate_limit, 60)
    sessions = OperatorSessionStore(tmp_path / "sessions.db", 3600)
    application.state.operator_session_store = sessions
    session = sessions.create(
        OperatorCredential(
            operator_id=OPERATOR,
            password_hash="unused",
            permissions=permissions
            or (
                INSTALLATION_DELIVERY_PREFLIGHT_CREATE,
                INSTALLATION_DELIVERY_PREFLIGHT_READ,
            ),
        )
    )
    application.state.delivery_activation_preflight_service = service
    return ASGITestClient(application), session, application, evidence, reader, clock


def _cookies(session):
    return {"atlas_operator_session": session.session_token}


def _headers(session, key="preflight-one"):
    return {
        "Origin": ORIGIN,
        "X-Atlas-CSRF-Token": session.csrf_token,
        "Idempotency-Key": key,
    }


def test_auth_permission_mutation_gates_and_success(tmp_path: Path) -> None:
    client, session, _, evidence, _, _ = _application(tmp_path)
    payload = _create(evidence).model_dump(mode="json")
    assert client.get(URL).status_code == 401
    assert client.post(URL, json=payload, cookies=_cookies(session)).status_code == 403
    assert client.post(
        URL,
        json=payload,
        cookies=_cookies(session),
        headers={**_headers(session), "Origin": "https://foreign.example"},
    ).status_code == 403
    made = client.post(URL, json=payload, cookies=_cookies(session), headers=_headers(session))
    assert made.status_code == 201
    body = made.json()
    assert body["result"]["decision"] == "eligible_for_later_activation"
    assert body["status"]["lifecycle"] == "eligible"
    assert not body["delivery_activated"]
    listed = client.get(URL, cookies=_cookies(session)).json()["preflights"][0]
    fetched = client.get(f"{URL}/{PREFLIGHT_ID}", cookies=_cookies(session)).json()
    assert listed["result"] == fetched["result"] == body["result"]
    replay = client.post(URL, json=payload, cookies=_cookies(session), headers=_headers(session))
    assert replay.status_code == 200
    assert replay.json()["result"] == body["result"]


def test_closed_body_idempotency_rate_limit_and_methods(tmp_path: Path) -> None:
    client, session, _, evidence, _, _ = _application(tmp_path, rate_limit=4)
    payload = _create(evidence).model_dump(mode="json")
    cookies = _cookies(session)
    headers = _headers(session)
    assert client.post(URL, content=b"{}", cookies=cookies, headers={**headers, "Content-Type": "text/plain"}).status_code == 415
    duplicate = json.dumps(payload)[:-1] + ',"schema":"delivery-activation-preflight-create-v1"}'
    assert client.post(URL, content=duplicate, cookies=cookies, headers={**headers, "Content-Type": "application/json"}).status_code == 422
    assert client.post(URL, json={**payload, "operator_id": OPERATOR}, cookies=cookies, headers=headers).status_code == 422
    assert client.post(URL, json=payload, cookies=cookies, headers=_headers(session, "contains space")).status_code == 422
    assert client.post(URL, json=payload, cookies=cookies, headers=_headers(session, "rate-limited")).status_code == 429
    assert client.request("PUT", URL).status_code == 405
    assert client.post(f"{URL}/{PREFLIGHT_ID}").status_code == 405


def test_owner_isolation_and_redacted_unavailable(tmp_path: Path) -> None:
    client, session, application, evidence, _, _ = _application(tmp_path)
    made = client.post(URL, json=_create(evidence).model_dump(mode="json"), cookies=_cookies(session), headers=_headers(session))
    assert made.status_code == 201
    sessions = application.state.operator_session_store
    foreign = sessions.create(
        OperatorCredential(
            operator_id="operator-b",
            password_hash="unused",
            permissions=(INSTALLATION_DELIVERY_PREFLIGHT_READ,),
        )
    )
    absent = client.get(f"{URL}/00000000-0000-4000-8000-000000000999", cookies=_cookies(session))
    hidden = client.get(f"{URL}/{PREFLIGHT_ID}", cookies=_cookies(foreign))
    assert absent.status_code == hidden.status_code == 404
    assert absent.json() == hidden.json()
    assert OPERATOR not in absent.text and "operator-b" not in hidden.text


def test_openapi_is_exact_and_production_service_is_default_absent(tmp_path: Path) -> None:
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    paths = application.openapi()["paths"]
    assert set(paths) == {URL, f"{URL}/{{preflight_id}}"}
    assert set(paths[URL]) == {"get", "post"}
    assert set(paths[f"{URL}/{{preflight_id}}"] ) == {"get"}
    lowered = " ".join(paths).lower()
    for verb in ("activate", "send", "deliver", "execute", "deploy"):
        assert verb not in lowered.replace("delivery-preflights", "preflights")
    # Service construction is never performed by the route module itself.
    assert "delivery_activation_preflight_service" not in application.state._state
