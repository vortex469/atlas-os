from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.config.settings import ProviderIntentActivation, ProviderIntentSettings
from app.models.provider_intents import (
    ProviderIntentCoordinateMutationResult,
    VerifiedProviderIntentMutationTarget,
)
from app.operator_auth.audit import OperatorSecurityAuditStore
from app.operator_auth.models import (
    OPERATIONAL_INTENT_CREATE,
    PROVIDER_INTENT_UPDATE,
    OperatorCredential,
)
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.provider_intents.mutation import (
    ProviderIntentMutationFailureReason,
    ProviderIntentMutationServiceError,
)
from app.provider_intents.store import ProviderIntentStore
from app.provider_intents.target_resolver import (
    ProviderIntentTargetFailureReason,
    ProviderIntentTargetResolutionError,
)
from app.routes.provider_intent_mutation import router
from app.testing import ASGITestClient

ORIGIN = "https://atlas.test"
FINGERPRINT = "provider-management-fingerprint-v1:" + "a" * 64
URL = "/providers/proxmox/management/resources/qemu/110/monitoring-intent"


def body(
    suffix: str = "a",
    *,
    fingerprint: str = FINGERPRINT,
    expectation: str = "running",
    version: int = 0,
) -> dict[str, object]:
    return {
        "request_id": "provider-intent-mutation-" + suffix * 32,
        "expected_management_fingerprint": fingerprint,
        "expectation": expectation,
        "expected_record_version": version,
        "acknowledge_monitoring_suppression": expectation == "ignored",
    }


def app_client(
    tmp_path: Path,
    *,
    permissions: tuple[str, ...] = (PROVIDER_INTENT_UPDATE,),
    mutation_limit: int = 20,
) -> tuple[ASGITestClient, FastAPI, str, str]:
    app = FastAPI()
    app.include_router(router)
    app.state.operator_auth_enabled = True
    app.state.operator_auth_trusted_origins = frozenset({ORIGIN})
    sessions = OperatorSessionStore(tmp_path / "sessions.db", 3600)
    app.state.operator_session_store = sessions
    app.state.operator_security_audit = OperatorSecurityAuditStore(
        tmp_path / "audit.db"
    )
    app.state.operator_mutation_rate_limiter = OperatorRateLimiter(
        mutation_limit, 60
    )
    created = sessions.create(
        OperatorCredential(
            operator_id="authenticated-operator",
            password_hash="unused-test-hash",
            permissions=permissions,
        )
    )
    return (
        ASGITestClient(app),
        app,
        created.session_token,
        created.csrf_token,
    )


def headers(csrf: str | None, *, origin: str | None = ORIGIN) -> dict[str, str]:
    values = {"Content-Type": "application/json"}
    if origin is not None:
        values["Origin"] = origin
    if csrf is not None:
        values["X-Atlas-CSRF-Token"] = csrf
    return values


@pytest.fixture(autouse=True)
def accepted_service(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    from app.routes import provider_intent_mutation as route

    captured: dict[str, object] = {}

    async def mutate(**values):
        captured.update(values)
        request = values["request"]
        return ProviderIntentCoordinateMutationResult(
            outcome="created",
            request_id=request.request_id,
            provider_id="proxmox",
            resource_type="qemu",
            resource_id="110",
            management_fingerprint=request.expected_management_fingerprint,
            expectation=request.expectation,
            record_version=1,
            superseded_previous_incarnation=False,
        )

    monkeypatch.setattr(route, "mutate_provider_monitoring_intent", mutate)
    return captured


def put(client, token, csrf, *, payload=None, request_headers=None):
    return client.request(
        "PUT",
        URL,
        cookies={"atlas_operator_session": token} if token else None,
        headers=request_headers or headers(csrf),
        json=body() if payload is None else payload,
    )


def test_exact_permission_uses_session_actor_and_returns_bounded_result(
    tmp_path: Path,
    accepted_service: dict[str, object],
) -> None:
    client, app, token, csrf = app_client(tmp_path)
    response = put(client, token, csrf)
    assert response.status_code == 201
    assert accepted_service["operator_id"] == "authenticated-operator"
    assert set(response.json()) == {
        "outcome", "request_id", "provider_id", "resource_type", "resource_id",
        "management_fingerprint", "expectation", "record_version",
        "superseded_previous_incarnation",
    }
    serialized = response.text.casefold()
    for forbidden in (
        "operator_id", "audit", "digest", "intent_id", "vmgenid", "cookie",
        "csrf", "database", "old_fingerprint",
    ):
        assert forbidden not in serialized
    event = app.state.operator_security_audit.list()[-1]
    assert (event.action, event.outcome, event.reason) == (
        PROVIDER_INTENT_UPDATE, "accepted", "created"
    )


def test_auth_permission_origin_and_csrf_fail_closed(tmp_path: Path) -> None:
    client, _app, token, csrf = app_client(tmp_path / "allowed")
    assert put(client, "", csrf).status_code == 401
    assert put(client, token, csrf, request_headers=headers(csrf, origin=None)).status_code == 403
    assert put(client, token, csrf, request_headers=headers(csrf, origin="https://evil.test")).status_code == 403
    assert put(client, token, None).status_code == 403
    assert put(client, token, "wrong").status_code == 403

    no_permission, _app, no_token, no_csrf = app_client(
        tmp_path / "none", permissions=()
    )
    assert put(no_permission, no_token, no_csrf).status_code == 403
    operational, _app, op_token, op_csrf = app_client(
        tmp_path / "operational", permissions=(OPERATIONAL_INTENT_CREATE,)
    )
    assert put(operational, op_token, op_csrf).status_code == 403
    with pytest.raises(ValidationError, match="unsupported permission"):
        OperatorCredential(
            operator_id="provider-action-only",
            password_hash="unused-test-hash",
            permissions=("provider_action:update",),
        )


def test_json_body_limits_strictness_rate_limit_and_method_surface(
    tmp_path: Path,
) -> None:
    client, _app, token, csrf = app_client(tmp_path, mutation_limit=3)
    assert put(
        client,
        token,
        csrf,
        request_headers={**headers(csrf), "Content-Type": "text/plain"},
    ).status_code == 415
    assert client.request(
        "PUT",
        URL,
        cookies={"atlas_operator_session": token},
        headers=headers(csrf),
        content=b"x" * 9_000,
    ).status_code == 413
    assert put(client, token, csrf, payload={**body(), "operator_id": "forged"}).status_code == 422
    assert put(client, token, csrf).status_code == 429
    for method in ("POST", "PATCH", "DELETE"):
        assert client.request(method, URL).status_code == 405


def test_disposable_http_create_update_stale_fingerprint_and_rebind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.provider_intents import mutation
    from app.routes import provider_intent_mutation as route

    database = tmp_path / "provider_intents.db"
    ProviderIntentStore(database)
    live = {"fingerprint": FINGERPRINT}

    async def verify(**values):
        if values["expected_management_fingerprint"] != live["fingerprint"]:
            raise ProviderIntentTargetResolutionError(
                ProviderIntentTargetFailureReason.FINGERPRINT_MISMATCH
            )
        return VerifiedProviderIntentMutationTarget(
            provider_id="proxmox",
            resource_type="qemu",
            resource_id="110",
            management_fingerprint=live["fingerprint"],
        )

    monkeypatch.setattr(mutation, "resolve_provider_intent_mutation_target", verify)
    monkeypatch.setattr(
        route, "mutate_provider_monitoring_intent", mutation.mutate_provider_monitoring_intent
    )
    monkeypatch.setattr(
        route,
        "settings",
        SimpleNamespace(
            provider_intents=ProviderIntentSettings(
                activation=ProviderIntentActivation.ACTIVATED,
                database=str(database),
                expected_legacy_import_id=(
                    "provider-intent-legacy-policy-import-v1:" + "f" * 64
                ),
            )
        ),
    )
    client, _app, token, csrf = app_client(tmp_path / "auth", mutation_limit=20)
    assert put(client, token, csrf, payload=body("a")).status_code == 201
    updated = put(
        client,
        token,
        csrf,
        payload=body("b", expectation="stopped", version=1),
    )
    assert updated.status_code == 200
    assert updated.json()["record_version"] == 2
    assert put(
        client,
        token,
        csrf,
        payload=body("b", expectation="stopped", version=1),
    ).json() == updated.json()
    stale_version = put(
        client,
        token,
        csrf,
        payload=body("e", expectation="running", version=1),
    )
    assert stale_version.status_code == 409
    assert stale_version.json()["detail"] == "cas_conflict"
    request_conflict = put(
        client,
        token,
        csrf,
        payload=body("b", expectation="ignored", version=0),
    )
    assert request_conflict.status_code == 409
    assert request_conflict.json()["detail"] == "request_conflict"

    live["fingerprint"] = "provider-management-fingerprint-v1:" + "b" * 64
    stale = put(client, token, csrf, payload=body("c", version=2))
    assert stale.status_code == 409
    assert stale.json()["detail"] == "fingerprint_mismatch"
    rebound = put(
        client,
        token,
        csrf,
        payload=body(
            "d",
            fingerprint=live["fingerprint"],
            expectation="ignored",
        ),
    )
    assert rebound.status_code == 200
    assert rebound.json()["outcome"] == "rebound"
    assert rebound.json()["superseded_previous_incarnation"] is True
    store = ProviderIntentStore.open_existing(database)
    assert len(store.read_snapshot().active_identity_bound_records) == 1
    assert {event.operator_id for event in store.operation_audit()} == {
        "authenticated-operator"
    }


def test_http_p2c_store_reports_migration_required_without_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.provider_intents import mutation
    from app.routes import provider_intent_mutation as route

    database = tmp_path / "provider_intents.db"
    ProviderIntentStore(database)
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE provider_intent_operation_audit")
        connection.execute("DROP TABLE provider_intent_operations")
        connection.execute("DROP TABLE provider_intent_active_coordinates")
        connection.execute("UPDATE provider_intent_store_meta SET schema_version=1")

    async def verify(**values):
        return VerifiedProviderIntentMutationTarget(
            provider_id="proxmox",
            resource_type="qemu",
            resource_id="110",
            management_fingerprint=values["expected_management_fingerprint"],
        )

    monkeypatch.setattr(mutation, "resolve_provider_intent_mutation_target", verify)
    monkeypatch.setattr(
        route, "mutate_provider_monitoring_intent", mutation.mutate_provider_monitoring_intent
    )
    monkeypatch.setattr(
        route,
        "settings",
        SimpleNamespace(
            provider_intents=ProviderIntentSettings(
                activation=ProviderIntentActivation.ACTIVATED,
                database=str(database),
                expected_legacy_import_id=(
                    "provider-intent-legacy-policy-import-v1:" + "f" * 64
                ),
            )
        ),
    )
    client, _app, token, csrf = app_client(tmp_path / "auth")
    response = put(client, token, csrf)
    assert response.status_code == 503
    assert response.json()["detail"] == "store_migration_required"
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT schema_version FROM provider_intent_store_meta"
        ).fetchone()[0] == 1


def test_post_commit_security_audit_failure_is_surfaced_without_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.provider_intents import mutation
    from app.routes import provider_intent_mutation as route

    database = tmp_path / "provider_intents.db"
    ProviderIntentStore(database)

    async def verify(**values):
        return VerifiedProviderIntentMutationTarget(
            provider_id="proxmox",
            resource_type="qemu",
            resource_id="110",
            management_fingerprint=values["expected_management_fingerprint"],
        )

    monkeypatch.setattr(mutation, "resolve_provider_intent_mutation_target", verify)
    monkeypatch.setattr(
        route, "mutate_provider_monitoring_intent", mutation.mutate_provider_monitoring_intent
    )
    monkeypatch.setattr(
        route,
        "settings",
        SimpleNamespace(
            provider_intents=ProviderIntentSettings(
                activation=ProviderIntentActivation.ACTIVATED,
                database=str(database),
                expected_legacy_import_id=(
                    "provider-intent-legacy-policy-import-v1:" + "f" * 64
                ),
            )
        ),
    )
    client, app, token, csrf = app_client(tmp_path / "auth")

    class FailingAudit:
        def record(self, **values):
            raise OSError("audit unavailable")

    app.state.operator_security_audit = FailingAudit()
    response = put(client, token, csrf)
    assert response.status_code == 503
    assert response.json()["detail"] == "security_audit_unavailable"
    assert len(
        ProviderIntentStore.open_existing(
            database
        ).read_snapshot().active_identity_bound_records
    ) == 1


@pytest.mark.parametrize(
    ("reason", "status_code"),
    (
        (ProviderIntentMutationFailureReason.STORE_UNAVAILABLE, 503),
        (ProviderIntentMutationFailureReason.STORE_MIGRATION_REQUIRED, 503),
        (ProviderIntentMutationFailureReason.CAS_CONFLICT, 409),
        (ProviderIntentMutationFailureReason.REQUEST_CONFLICT, 409),
    ),
)
def test_service_failures_map_to_bounded_http_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reason: ProviderIntentMutationFailureReason,
    status_code: int,
) -> None:
    from app.routes import provider_intent_mutation as route

    async def fail(**values):
        raise ProviderIntentMutationServiceError(reason)

    monkeypatch.setattr(route, "mutate_provider_monitoring_intent", fail)
    client, _app, token, csrf = app_client(tmp_path)
    response = put(client, token, csrf)
    assert response.status_code == status_code
    assert response.json()["detail"] == reason.value
    assert set(response.json()) == {"detail"}


def test_new_put_and_activated_legacy_put_remain_distinct_routes() -> None:
    from app.api.v1.router import router as api_router

    app = FastAPI()
    app.include_router(api_router)
    paths = app.openapi()["paths"]
    new_path = (
        "/api/v1/providers/{provider_id}/management/resources/"
        "{resource_type}/{resource_id}/monitoring-intent"
    )
    legacy_path = (
        "/api/v1/providers/{provider_id}/resources/{resource_id}/expectation"
    )
    assert set(paths[new_path]) == {"put"}
    assert set(paths[legacy_path]) == {"put"}
    assert new_path != legacy_path
