"""P3 API locks for operator-controlled delivery enablement evidence."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import FastAPI

from app.operator_auth.models import (
    INSTALLATION_DELIVERY_ENABLEMENT_CREATE,
    INSTALLATION_DELIVERY_ENABLEMENT_READ,
    OperatorCredential,
)
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.operator_controlled_delivery_enablement.test_contract import (
    ENABLEMENT_ID,
    OPERATOR,
    _create,
)
from app.operator_controlled_delivery_enablement.test_service import _service
from app.routes.delivery_enablement import router
from app.testing import ASGITestClient

URL = "/api/v1/installation-delivery-enablements"
ORIGIN = "https://atlas.example"


def _application(
    tmp_path: Path,
    *,
    permissions=None,
    rate_limit: int = 100,
    enabled: bool = True,
    at: str = "2026-08-27T12:00:13Z",
):
    service, reader, clock, evidence = _service(
        tmp_path / "service", enabled=enabled, at=at
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
            operator_id=OPERATOR,
            password_hash="unused",
            permissions=permissions
            or (
                INSTALLATION_DELIVERY_ENABLEMENT_CREATE,
                INSTALLATION_DELIVERY_ENABLEMENT_READ,
            ),
        )
    )
    application.state.operator_controlled_delivery_enablement_service = service
    return ASGITestClient(application), session, application, evidence, reader, clock


def _cookies(session):
    return {"atlas_operator_session": session.session_token}


def _headers(session, key="enablement-one"):
    return {
        "Origin": ORIGIN,
        "X-Atlas-CSRF-Token": session.csrf_token,
        "Idempotency-Key": key,
    }


def test_auth_permission_csrf_origin_and_success(tmp_path: Path) -> None:
    client, session, _, evidence, _, _ = _application(tmp_path)
    payload = _create(evidence).model_dump(mode="json")
    assert client.get(URL).status_code == 401
    assert client.post(URL, json=payload, cookies=_cookies(session)).status_code == 403
    assert client.post(
        URL, json=payload, cookies=_cookies(session),
        headers={**_headers(session), "X-Atlas-CSRF-Token": "wrong"},
    ).status_code == 403
    assert client.post(
        URL, json=payload, cookies=_cookies(session),
        headers={**_headers(session), "Origin": "https://foreign.example"},
    ).status_code == 403
    made = client.post(
        URL, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    assert made.status_code == 201
    body = made.json()
    assert body["record"]["operator_enabled"]
    assert body["status"]["lifecycle"] == "enabled"
    assert not any((body["delivery_activated"], body["delivery_sent"],
                    body["delivery_authorized"], body["execution_attempted"],
                    body["mutation_attempted"], body["replay_allowed"]))
    listed = client.get(URL, cookies=_cookies(session)).json()["enablements"][0]
    fetched = client.get(
        f"{URL}/{ENABLEMENT_ID}", cookies=_cookies(session)
    ).json()
    assert listed["record"] == fetched["record"] == body["record"]
    replay = client.post(
        URL, json=payload, cookies=_cookies(session), headers=_headers(session)
    )
    assert replay.status_code == 200
    assert replay.json()["record"] == body["record"]


def test_dedicated_permissions_are_independent(tmp_path: Path) -> None:
    read_client, read_session, _, evidence, _, _ = _application(
        tmp_path / "read", permissions=(INSTALLATION_DELIVERY_ENABLEMENT_READ,)
    )
    payload = _create(evidence).model_dump(mode="json")
    assert read_client.get(URL, cookies=_cookies(read_session)).status_code == 200
    assert read_client.post(
        URL, json=payload, cookies=_cookies(read_session),
        headers=_headers(read_session),
    ).status_code == 403
    create_client, create_session, _, evidence, _, _ = _application(
        tmp_path / "create", permissions=(INSTALLATION_DELIVERY_ENABLEMENT_CREATE,)
    )
    assert create_client.get(URL, cookies=_cookies(create_session)).status_code == 403
    assert create_client.post(
        URL, json=_create(evidence).model_dump(mode="json"),
        cookies=_cookies(create_session), headers=_headers(create_session),
    ).status_code == 201


def test_closed_body_nesting_idempotency_rate_and_methods(tmp_path: Path) -> None:
    client, session, _, evidence, _, _ = _application(tmp_path, rate_limit=6)
    payload = _create(evidence).model_dump(mode="json")
    cookies, headers = _cookies(session), _headers(session)
    assert client.post(
        URL, content=b"{}", cookies=cookies,
        headers={**headers, "Content-Type": "text/plain"},
    ).status_code == 415
    duplicate = json.dumps(payload)[:-1] + (
        ',"schema":"operator-controlled-delivery-enablement-create-v1"}'
    )
    assert client.post(
        URL, content=duplicate, cookies=cookies,
        headers={**headers, "Content-Type": "application/json"},
    ).status_code == 422
    assert client.post(
        URL, json={**payload, "operator_id": OPERATOR},
        cookies=cookies, headers=headers,
    ).status_code == 422
    nested: object = "bottom"
    for _ in range(18):
        nested = {"nested": nested}
    assert client.post(
        URL, json=nested, cookies=cookies, headers=headers
    ).status_code == 422
    assert client.post(
        URL, content=b" " * 1025, cookies=cookies,
        headers={**headers, "Content-Type": "application/json"},
    ).status_code == 413
    assert client.post(
        URL, json=payload, cookies=cookies,
        headers=_headers(session, "contains space"),
    ).status_code == 422
    assert client.post(
        URL, json=payload, cookies=cookies,
        headers=_headers(session, "rate-limited"),
    ).status_code == 429
    assert client.request("PUT", URL).status_code == 405
    assert client.post(f"{URL}/{ENABLEMENT_ID}").status_code == 405


def test_exact_confirmation_default_off_stale_and_mismatch(tmp_path: Path) -> None:
    client, session, _, evidence, _, _ = _application(tmp_path / "confirmation")
    payload = _create(evidence).model_dump(mode="json")
    assert client.post(
        URL, json={**payload, "confirmation": "Enable delivery"},
        cookies=_cookies(session), headers=_headers(session),
    ).status_code == 422
    disabled, session, _, evidence, _, _ = _application(
        tmp_path / "disabled", enabled=False
    )
    result = disabled.post(
        URL, json=_create(evidence).model_dump(mode="json"),
        cookies=_cookies(session), headers=_headers(session),
    )
    assert result.status_code == 409
    assert result.json()["error"]["redacted"]
    stale, session, _, evidence, _, _ = _application(
        tmp_path / "stale", at="2026-08-27T12:00:42Z"
    )
    result = stale.post(
        URL, json=_create(evidence).model_dump(mode="json"),
        cookies=_cookies(session), headers=_headers(session),
    )
    assert result.status_code == 409
    changed = _create(evidence).model_dump(mode="json")
    changed["preflight_fingerprint"]["value"] = "0" * 64
    mismatch = stale.post(
        URL, json=changed, cookies=_cookies(session),
        headers=_headers(session, "mismatch"),
    )
    assert mismatch.status_code in (409, 422)
    assert mismatch.json()["error"]["redacted"]


def test_owner_isolation_and_corruption_are_redacted(tmp_path: Path) -> None:
    client, session, application, evidence, _, _ = _application(tmp_path)
    made = client.post(
        URL, json=_create(evidence).model_dump(mode="json"),
        cookies=_cookies(session), headers=_headers(session),
    )
    assert made.status_code == 201
    foreign = application.state.operator_session_store.create(
        OperatorCredential(
            operator_id="operator-b", password_hash="unused",
            permissions=(INSTALLATION_DELIVERY_ENABLEMENT_READ,),
        )
    )
    absent = client.get(
        f"{URL}/00000000-0000-4000-8000-000000000999",
        cookies=_cookies(session),
    )
    hidden = client.get(f"{URL}/{ENABLEMENT_ID}", cookies=_cookies(foreign))
    assert absent.status_code == hidden.status_code == 404
    assert absent.json() == hidden.json()
    assert OPERATOR not in absent.text and "operator-b" not in hidden.text
    with sqlite3.connect(tmp_path / "service" / "enablement.sqlite3") as connection:
        connection.execute(
            "UPDATE operator_delivery_enablements SET record_json = ?", ("{}",)
        )
    corrupt = client.get(f"{URL}/{ENABLEMENT_ID}", cookies=_cookies(session))
    assert corrupt.status_code == 503
    assert corrupt.json()["error"] == {
        "schema": "operator-controlled-delivery-enablement-error-v1",
        "error_code": "unavailable",
        "correlation_id": corrupt.json()["error"]["correlation_id"],
        "preflight_id": None,
        "preflight_fingerprint": None,
        "redacted": True,
    }
    assert "sqlite" not in corrupt.text.lower()


def test_openapi_exact_methods_and_default_absent() -> None:
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    paths = application.openapi()["paths"]
    assert set(paths) == {URL, f"{URL}/{{enablement_id}}"}
    assert set(paths[URL]) == {"get", "post"}
    assert set(paths[f"{URL}/{{enablement_id}}"] ) == {"get"}
    for path in paths:
        normalized = path.lower().replace("installation-delivery-enablements", "")
        assert all(word not in normalized for word in (
            "send", "deliver", "activate", "install", "execute", "deploy",
        ))
    assert (
        "operator_controlled_delivery_enablement_service"
        not in application.state._state
    )
