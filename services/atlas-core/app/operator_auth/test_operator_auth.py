from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.operator_auth import credentials as credentials_module
from app.operator_auth.audit import OperatorSecurityAuditStore
from app.operator_auth.credentials import (
    OperatorCredentialError,
    OperatorCredentialVerifier,
)
from app.operator_auth.models import (
    OPERATIONAL_INTENT_CREATE,
    OperatorCredential,
    OperatorCredentialFile,
)
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.operator_auth import router

ORIGIN = "https://atlas.test"
PASSWORD = "test-only-operator-password"


def credential_file(
    path: Path,
    *,
    operators: list[dict[str, object]] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "operators": operators
        if operators is not None
        else [
            {
                "operator_id": "kenny",
                "password_hash": PasswordHasher().hash(PASSWORD),
                "enabled": True,
                "permissions": [OPERATIONAL_INTENT_CREATE],
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o400)
    return path


def test_credential_models_are_strict_and_closed() -> None:
    with pytest.raises(ValidationError):
        OperatorCredentialFile.model_validate(
            {
                "schema_version": 1,
                "operators": [
                    {
                        "operator_id": "operator",
                        "password_hash": "$argon2id$invalid",
                        "enabled": True,
                        "permissions": ["unknown:permission"],
                        "password": "forbidden",
                    }
                ],
            }
        )
    with pytest.raises(ValidationError, match="unique"):
        OperatorCredentialFile(
            schema_version=1,
            operators=(
                OperatorCredential(
                    operator_id="same",
                    password_hash="hash",
                    permissions=(),
                ),
                OperatorCredential(
                    operator_id="same",
                    password_hash="hash",
                    permissions=(),
                ),
            ),
        )


@pytest.mark.parametrize("unsafe", ["mode", "symlink", "directory"])
def test_verifier_rejects_unsafe_file(tmp_path: Path, unsafe: str) -> None:
    source = credential_file(tmp_path / "source.json")
    target = source
    if unsafe == "mode":
        source.chmod(0o600)
    elif unsafe == "symlink":
        target = tmp_path / "link.json"
        target.symlink_to(source)
    else:
        target = tmp_path / "directory"
        target.mkdir()
        target.chmod(0o400)
    with pytest.raises(OperatorCredentialError):
        OperatorCredentialVerifier(target)


def test_verifier_authenticates_argon2id_and_fails_generically(tmp_path: Path) -> None:
    verifier = OperatorCredentialVerifier(credential_file(tmp_path / "operators.json"))
    assert verifier.authenticate("kenny", PASSWORD) is not None
    assert verifier.authenticate("kenny", "wrong") is None
    assert verifier.authenticate("missing", PASSWORD) is None

    disabled = credential_file(
        tmp_path / "disabled.json",
        operators=[
            {
                "operator_id": "disabled",
                "password_hash": PasswordHasher().hash(PASSWORD),
                "enabled": False,
                "permissions": [],
            }
        ],
    )
    assert OperatorCredentialVerifier(disabled).authenticate("disabled", PASSWORD) is None


@pytest.mark.parametrize(
    "operators",
    [
        [{"operator_id": "bad", "password_hash": "not-an-argon-hash", "enabled": True, "permissions": []}],
        [
            {"operator_id": "same", "password_hash": PasswordHasher().hash(PASSWORD), "enabled": True, "permissions": []},
            {"operator_id": "same", "password_hash": PasswordHasher().hash(PASSWORD), "enabled": True, "permissions": []},
        ],
        [{"operator_id": "bad", "password_hash": PasswordHasher().hash(PASSWORD), "enabled": True, "permissions": [], "password": "forbidden"}],
    ],
)
def test_verifier_rejects_malformed_duplicate_and_plaintext_fields(
    tmp_path: Path,
    operators: list[dict[str, object]],
) -> None:
    with pytest.raises(OperatorCredentialError):
        OperatorCredentialVerifier(
            credential_file(tmp_path / "invalid.json", operators=operators)
        )


def test_verifier_rejects_wrong_runtime_owner(tmp_path: Path, monkeypatch) -> None:
    path = credential_file(tmp_path / "operators.json")
    monkeypatch.setattr(credentials_module.os, "geteuid", lambda: path.stat().st_uid + 1)
    with pytest.raises(OperatorCredentialError, match="owned"):
        OperatorCredentialVerifier(path)


def test_session_store_is_restart_safe_expires_revokes_and_stores_only_digests(
    tmp_path: Path,
) -> None:
    database = tmp_path / "sessions.db"
    store = OperatorSessionStore(database, lifetime_seconds=300)
    credential = OperatorCredential(
        operator_id="kenny",
        password_hash="not-copied",
        permissions=(OPERATIONAL_INTENT_CREATE,),
    )
    now = datetime.now(UTC)
    created = store.create(credential, now=now)
    restarted = OperatorSessionStore(database, lifetime_seconds=300)
    resolved = restarted.resolve(created.session_token, now=now + timedelta(seconds=1))
    assert resolved is not None
    assert resolved.principal.operator_id == "kenny"
    assert restarted.verify_csrf(resolved, created.csrf_token)
    persisted = database.read_bytes()
    assert database.stat().st_mode & 0o777 == 0o600
    assert created.session_token.encode() not in persisted
    assert created.csrf_token.encode() not in persisted
    assert b"not-copied" not in persisted
    assert restarted.resolve("tampered", now=now) is None
    restarted.revoke(resolved, now=now)
    assert restarted.resolve(created.session_token, now=now) is None

    expiring = store.create(credential, now=now)
    assert store.resolve(expiring.session_token, now=now + timedelta(seconds=301)) is None


def test_rate_limiter_is_bounded_and_keys_are_isolated() -> None:
    limiter = OperatorRateLimiter(limit=2, window_seconds=60, max_keys=2)
    now = datetime.now(UTC)
    assert limiter.allow("operator:a", now)
    assert limiter.allow("operator:a", now)
    assert not limiter.allow("operator:a", now)
    assert limiter.allow("operator:b", now)
    assert limiter.allow("operator:a", now + timedelta(seconds=61))
    assert limiter.allow("operator:c", now + timedelta(seconds=61))
    assert len(limiter._events) <= 2


def app_client(
    tmp_path: Path,
    *,
    permissions=(OPERATIONAL_INTENT_CREATE,),
    mutation_limit=10,
    login_limit=3,
):
    verifier_path = credential_file(
        tmp_path / "operators.json",
        operators=[
            {
                "operator_id": "kenny",
                "password_hash": PasswordHasher().hash(PASSWORD),
                "enabled": True,
                "permissions": list(permissions),
            }
        ],
    )
    app = FastAPI()
    app.state.operator_auth_enabled = True
    app.state.operator_auth_trusted_origins = frozenset({ORIGIN})
    app.state.operator_credential_verifier = OperatorCredentialVerifier(verifier_path)
    app.state.operator_session_store = OperatorSessionStore(tmp_path / "sessions.db", 300)
    app.state.operator_security_audit = OperatorSecurityAuditStore(tmp_path / "audit.db")
    app.state.operator_login_rate_limiter = OperatorRateLimiter(login_limit, 60)
    app.state.operator_mutation_rate_limiter = OperatorRateLimiter(mutation_limit, 60)
    app.include_router(router, prefix="/api/v1")
    return TestClient(app, base_url=ORIGIN), app


def login(client: TestClient):
    response = client.post(
        "/api/v1/operator-auth/login",
        headers={"Origin": ORIGIN},
        json={"operator_id": "kenny", "password": PASSWORD},
    )
    return response, response.headers.get("X-Atlas-CSRF-Token")


def test_end_to_end_login_session_probe_and_logout(tmp_path: Path) -> None:
    client, app = app_client(tmp_path)
    response, csrf = login(client)
    assert response.status_code == 200
    assert csrf
    cookie = response.headers["set-cookie"]
    for flag in ("HttpOnly", "Secure", "SameSite=strict", "Path=/api/v1/"):
        assert flag in cookie
    assert PASSWORD not in response.text
    assert "atlas_operator_session" not in response.json()

    session = client.get("/api/v1/operator-auth/session")
    assert session.status_code == 200
    rotated_csrf = session.headers["X-Atlas-CSRF-Token"]
    assert rotated_csrf != csrf
    probe = client.post(
        "/api/v1/operator-auth/probe",
        headers={"Origin": ORIGIN, "X-Atlas-CSRF-Token": rotated_csrf},
        json={},
    )
    assert probe.status_code == 200
    assert probe.json() == {
        "operator_id": "kenny",
        "permission": OPERATIONAL_INTENT_CREATE,
        "action": "operator-auth-boundary-probe",
        "authorized": True,
    }
    logout = client.post(
        "/api/v1/operator-auth/logout",
        headers={"Origin": ORIGIN, "X-Atlas-CSRF-Token": rotated_csrf},
        json={},
    )
    assert logout.status_code == 200
    assert client.get("/api/v1/operator-auth/session").status_code == 401
    events = app.state.operator_security_audit.list()
    accepted = [(event.action, event.outcome) for event in events if event.outcome == "accepted"]
    assert accepted == [
        ("operator.login", "accepted"),
        ("operator-auth-boundary-probe", "accepted"),
        ("operator.logout", "accepted"),
    ]
    assert all(event.request_id for event in events)
    audit_bytes = (tmp_path / "audit.db").read_bytes()
    assert PASSWORD.encode() not in audit_bytes
    assert rotated_csrf.encode() not in audit_bytes


@pytest.mark.parametrize("origin", [None, "null", "http://atlas.test", "https://evil.test"])
def test_login_rejects_missing_null_http_and_cross_origin(tmp_path: Path, origin: str | None) -> None:
    client, _app = app_client(tmp_path, login_limit=6)
    headers = {} if origin is None else {"Origin": origin}
    response = client.post(
        "/api/v1/operator-auth/login",
        headers=headers,
        json={"operator_id": "kenny", "password": PASSWORD},
    )
    assert response.status_code == 403


def test_login_is_strict_bounded_generic_and_rate_limited(tmp_path: Path) -> None:
    client, _app = app_client(tmp_path, login_limit=5)
    headers = {"Origin": ORIGIN}
    assert client.post("/api/v1/operator-auth/login", headers=headers, content="text").status_code == 415
    assert client.post(
        "/api/v1/operator-auth/login",
        headers={**headers, "Content-Type": "application/json"},
        content=b"x" * 9_000,
    ).status_code == 413
    extra = client.post(
        "/api/v1/operator-auth/login",
        headers=headers,
        json={"operator_id": "kenny", "password": PASSWORD, "role": "admin"},
    )
    assert extra.status_code == 422
    for operator_id in ("missing", "kenny"):
        response = client.post(
            "/api/v1/operator-auth/login",
            headers=headers,
            json={"operator_id": operator_id, "password": "wrong"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Operator authentication failed."
    assert client.post(
        "/api/v1/operator-auth/login",
        headers=headers,
        json={"operator_id": "kenny", "password": "wrong"},
    ).status_code == 429


def test_probe_rejects_missing_session_permission_origin_csrf_and_forged_headers(
    tmp_path: Path,
) -> None:
    client, _app = app_client(tmp_path)
    forged = client.post(
        "/api/v1/operator-auth/probe",
        headers={
            "Origin": ORIGIN,
            "X-Atlas-CSRF-Token": "forged",
            "X-Atlas-Operator": "kenny",
            "X-Auth-User": "kenny",
        },
        json={},
    )
    assert forged.status_code == 401
    response, csrf = login(client)
    assert response.status_code == 200 and csrf
    assert client.post("/api/v1/operator-auth/probe", json={}).status_code == 403
    assert client.post(
        "/api/v1/operator-auth/probe", headers={"Origin": "https://evil.test", "X-Atlas-CSRF-Token": csrf}, json={}
    ).status_code == 403
    assert client.post(
        "/api/v1/operator-auth/probe", headers={"Origin": ORIGIN}, json={}
    ).status_code == 403
    assert client.post(
        "/api/v1/operator-auth/probe", headers={"Origin": ORIGIN, "X-Atlas-CSRF-Token": "wrong"}, json={}
    ).status_code == 403

    unauthorized, _app = app_client(tmp_path / "unauthorized", permissions=())
    login_response, unauthorized_csrf = login(unauthorized)
    assert login_response.status_code == 200
    assert unauthorized.post(
        "/api/v1/operator-auth/probe",
        headers={"Origin": ORIGIN, "X-Atlas-CSRF-Token": unauthorized_csrf},
        json={},
    ).status_code == 403


def test_probe_rate_limit_is_per_operator_and_disabled_boundary_is_fail_closed(
    tmp_path: Path,
) -> None:
    client, _app = app_client(tmp_path, mutation_limit=1)
    response, csrf = login(client)
    assert response.status_code == 200 and csrf
    headers = {"Origin": ORIGIN, "X-Atlas-CSRF-Token": csrf}
    assert client.post("/api/v1/operator-auth/probe", headers=headers, json={}).status_code == 200
    assert client.post("/api/v1/operator-auth/probe", headers=headers, json={}).status_code == 429

    disabled = FastAPI()
    disabled.state.operator_auth_enabled = False
    disabled.include_router(router, prefix="/api/v1")
    disabled_client = TestClient(disabled, base_url=ORIGIN)
    assert disabled_client.post(
        "/api/v1/operator-auth/probe", headers=headers, json={}
    ).status_code == 503


def test_database_schema_contains_no_raw_secret_columns(tmp_path: Path) -> None:
    store = OperatorSessionStore(tmp_path / "sessions.db", 300)
    with sqlite3.connect(store.database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(operator_sessions)")}
    assert not columns & {"token", "cookie", "csrf_token", "password", "password_hash", "authorization"}
    assert {"token_digest", "csrf_digest"} <= columns


def test_operator_auth_source_is_separate_from_dispatch_and_mutation_domains() -> None:
    package = Path(__file__).parent
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in package.glob("*.py")
        if path.name != Path(__file__).name
    )
    forbidden = (
        "OperationalDispatchAuthenticator",
        "/run/atlas-core-agent-auth/token",
        "operational_dispatch.service",
        "ExecutionCandidate",
        "OperationalActionRequest",
        "ProxmoxProvider",
        "docker",
        "subprocess",
    )
    assert not any(value in source for value in forbidden)
